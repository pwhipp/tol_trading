from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import json
import logging
from pathlib import Path
import time
from typing import Any

from jinja2 import Environment, FileSystemLoader
from tol.load import normalize_tol_document
from tol.llm.config import load_settings
from tol.llm.settings import LlmSettings


@dataclass
class LlmUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class LlmResponse:
    content: str
    usage: LlmUsage | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class LlmDocumentResponse:
    document: dict[str, Any]
    usage: LlmUsage | None = None
    warnings: list[str] = field(default_factory=list)


class ChatGptClient:
    def __init__(self, settings: LlmSettings) -> None:
        self._settings = settings
        self._usage_logger, self._usage_log_warning = _build_file_logger(
            "tol.llm.usage",
            self._settings.usage_log_path,
            self._settings.usage_log_level,
        )
        self._api_logger, self._api_log_warning = _build_file_logger(
            "tol.llm.api",
            self._settings.api_log_path,
            self._settings.api_log_level,
        )
        import openai as openai_module

        self._openai = openai_module
        if not self._settings.api_key:
            raise RuntimeError(
                "Missing API key. Set api_key in the TOL config file."
            )
        self._client = self._openai.OpenAI(
            api_key=self._settings.api_key,
            base_url=_normalize_base_url(self._settings.base_url),
        )

    @classmethod
    def from_config(cls, model_override: str | None = None) -> "ChatGptClient":
        settings = load_settings()
        if model_override:
            updated = settings.to_dict()
            updated["model"] = model_override
            settings = LlmSettings.from_dict(updated)
        return cls(settings)

    def describe_tol(self, tol_doc: dict[str, Any]) -> LlmResponse:
        prompt = _render_prompt(
            "describe_tol_prompt.j2",
            tol_doc_json=json.dumps(tol_doc, indent=2),
        )
        response = self._chat(messages=[_system_message(), _user_message(prompt)])
        return response

    def generate_tol(self, prompt_text: str) -> LlmDocumentResponse:
        instructions = _render_prompt(
            "generate_tol_prompt.j2",
            schema_json=_load_tol_schema_text(),
        )
        message = self._chat(
            messages=[
                _system_message(),
                _user_message(instructions),
                _user_message(prompt_text),
            ]
        )
        raw_content = _strip_json_fence(message.content)
        try:
            document = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            self._log_api_error(
                "LLM response was not valid JSON.",
                response_content=message.content,
            )
            raise RuntimeError(
                "LLM response was not valid JSON. Adjust the prompt or model."
            ) from exc

        normalized = normalize_tol_document(document)
        return LlmDocumentResponse(
            document=normalized,
            usage=message.usage,
            warnings=message.warnings,
        )

    def _chat(self, messages: list[dict[str, str]]) -> LlmResponse:
        self._log_api_message(messages)
        start_time = time.monotonic()
        try:
            response = self._client.responses.create(
                model=self._settings.model,
                input=messages,
                temperature=self._settings.temperature,
                max_output_tokens=self._settings.max_tokens,
                timeout=self._settings.timeout_seconds,
            )
        except self._openai.APIStatusError as exc:
            self._log_api_error(
                "ChatGPT API status error.",
                status_code=exc.status_code,
                response_content=exc.response.text,
            )
            raise RuntimeError(
                _format_api_error(exc.status_code, exc.response.text)
            ) from exc
        except self._openai.APIError as exc:
            self._log_api_error("ChatGPT API error.", response_content=str(exc))
            raise RuntimeError(f"ChatGPT API error: {exc}") from exc

        response_data = response.model_dump()
        content = _extract_response_text(response_data)
        usage = self._parse_usage(response_data)
        warnings: list[str] = []
        elapsed = time.monotonic() - start_time
        self._log_api_response(content, elapsed)
        if not content:
            self._log_api_error("Empty response content from LLM.")

        if usage and self._usage_logger:
            warning = self._record_usage(usage)
            if warning:
                warnings.append(warning)
        if self._usage_log_warning:
            warnings.append(self._usage_log_warning)
        if self._api_log_warning:
            warnings.append(self._api_log_warning)

        return LlmResponse(content=content, usage=usage, warnings=warnings)

    def _parse_usage(self, data: dict[str, Any]) -> LlmUsage | None:
        usage_data = data.get("usage")
        if not usage_data:
            return None
        prompt_tokens = int(usage_data.get("input_tokens", 0))
        completion_tokens = int(usage_data.get("output_tokens", 0))
        total_tokens = int(usage_data.get("total_tokens", 0))
        return LlmUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    def _record_usage(self, usage: LlmUsage) -> str | None:
        payload = {
            "timestamp": time.time(),
            "model": self._settings.model,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
        }
        try:
            self._usage_logger.info(json.dumps(payload))
        except OSError as exc:
            return f"Failed to write usage log: {exc}"
        return None

    def _log_api_message(self, messages: list[dict[str, str]]) -> None:
        if not self._api_logger:
            return
        self._api_logger.info(
            json.dumps({"event": "request", "messages": messages})
        )

    def _log_api_response(self, content: str, elapsed: float) -> None:
        if not self._api_logger:
            return
        self._api_logger.info(
            json.dumps(
                {
                    "event": "response",
                    "elapsed_seconds": elapsed,
                    "content": content,
                }
            )
        )

    def _log_api_error(self, message: str, **context: Any) -> None:
        if not self._api_logger:
            return
        payload = {"event": "error", "message": message}
        if context:
            payload.update(context)
        self._api_logger.error(json.dumps(payload))


def _system_message() -> dict[str, str]:
    return {"role": "system", "content": "You are a helpful trading assistant."}


def _user_message(content: str) -> dict[str, str]:
    return {"role": "user", "content": content}


def _strip_json_fence(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        if lines and lines[0].strip().lower() in {"json", "javascript"}:
            lines = lines[1:]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _extract_response_text(data: dict[str, Any]) -> str:
    output_items = data.get("output", [])
    for item in output_items:
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text = content.get("text", "")
                if text:
                    return text.strip()
    text = data.get("output_text")
    if isinstance(text, str):
        return text.strip()
    return ""


def _format_api_error(status_code: int, detail: str) -> str:
    message = f"ChatGPT API error: HTTP {status_code}"
    if not detail:
        return message
    parsed = _parse_error_payload(detail)
    if not parsed:
        return f"{message} {detail}".strip()
    error_message = parsed.get("message") or detail
    error_code = parsed.get("code")
    if error_code == "insufficient_quota":
        return f"{message} {error_message}".strip()
    return f"{message} {error_message}".strip()


def _parse_error_payload(detail: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(detail)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    error_data = payload.get("error")
    if isinstance(error_data, dict):
        return error_data
    return None


def _normalize_base_url(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    if cleaned.endswith("/responses"):
        cleaned = cleaned[: -len("/responses")]
    return cleaned


def _render_prompt(template_name: str, **context: Any) -> str:
    template = _prompt_environment().get_template(template_name)
    return template.render(**context).strip()


@lru_cache
def _prompt_environment() -> Environment:
    template_dir = Path(__file__).resolve().parent / "templates"
    return Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=False,
    )


@lru_cache
def _load_tol_schema_text() -> str:
    schema_path = Path(__file__).resolve().parents[2] / "TOL_JSON_SCHEMA.json"
    return schema_path.read_text(encoding="utf-8").strip()


def _build_file_logger(
    name: str, path: Path | None, level_name: str
) -> tuple[logging.Logger | None, str | None]:
    if not path:
        return None, None
    logger_name = f"{name}.{path}"
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger, None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
    except OSError as exc:
        return None, f"Failed to set up log file {path}: {exc}"
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(_parse_log_level(level_name))
    logger.propagate = False
    return logger, None


def _parse_log_level(level_name: str) -> int:
    if not isinstance(level_name, str):
        return logging.INFO
    upper_name = level_name.upper()
    level = logging.getLevelName(upper_name)
    return level if isinstance(level, int) else logging.INFO
