from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Any
from tol.load import normalize_tol_document
from tol.llm.config import load_settings
from tol.llm.settings import LlmSettings


@dataclass
class LlmUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float | None = None


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
        import openai as openai_module

        self._openai = openai_module
        if not self._settings.api_key:
            raise RuntimeError(
                "Missing API key. Set api_key in the TOL config file."
            )
        self._client = self._openai.OpenAI(
            api_key=self._settings.api_key,
            base_url=self._settings.base_url,
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
        prompt = (
            "You are a trading assistant. Describe the following TOL document in a "
            "single concise sentence. Use natural language that references the actions "
            "and constraints. Avoid jargon. Output plain text only.\n\nTOL:\n"
            f"{json.dumps(tol_doc, indent=2)}"
        )
        response = self._chat(messages=[_system_message(), _user_message(prompt)])
        return response

    def generate_tol(self, prompt_text: str) -> LlmDocumentResponse:
        instructions = (
            "Convert the user's request into a TOL document. Output JSON only. "
            "Use the schema: {'version': 1, 'actions': [ ... ]}. Actions are objects "
            "with a single key such as 'buy', 'sell', or 'target'. "
            "Prefer percent targets when explicitly requested. "
            "Include 'using' sources when the user mentions funding sources."
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
        self._enforce_spend_limit()
        try:
            response = self._client.responses.create(
                model=self._settings.model,
                input=messages,
                temperature=self._settings.temperature,
                max_output_tokens=self._settings.max_tokens,
                timeout=self._settings.timeout_seconds,
            )
        except self._openai.APIStatusError as exc:
            raise RuntimeError(
                _format_api_error(exc.status_code, exc.response.text)
            ) from exc
        except self._openai.APIError as exc:
            raise RuntimeError(f"ChatGPT API error: {exc}") from exc

        response_data = response.model_dump()
        content = _extract_response_text(response_data)
        usage = self._parse_usage(response_data)
        warnings: list[str] = []

        if usage and self._settings.usage_log_path:
            warning = self._record_usage(self._settings.usage_log_path, usage)
            if warning:
                warnings.append(warning)

        return LlmResponse(content=content, usage=usage, warnings=warnings)

    def _enforce_spend_limit(self) -> None:
        if (
            self._settings.spend_limit_usd is None
            or self._settings.usage_log_path is None
            or self._settings.pricing is None
        ):
            return

        total_spend = _sum_usage_cost(self._settings.usage_log_path)
        if total_spend >= self._settings.spend_limit_usd:
            raise RuntimeError(
                "Usage spend limit reached. Increase spend_limit_usd in the config."
            )

    def _parse_usage(self, data: dict[str, Any]) -> LlmUsage | None:
        usage_data = data.get("usage")
        if not usage_data:
            return None
        prompt_tokens = int(usage_data.get("input_tokens", 0))
        completion_tokens = int(usage_data.get("output_tokens", 0))
        total_tokens = int(usage_data.get("total_tokens", 0))
        estimated_cost = None
        if self._settings.pricing:
            estimated_cost = self._settings.pricing.estimate_cost(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        return LlmUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
        )

    def _record_usage(self, path: Path, usage: LlmUsage) -> str | None:
        payload = {
            "timestamp": time.time(),
            "model": self._settings.model,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "estimated_cost": usage.estimated_cost,
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload) + "\n")
        except OSError as exc:
            return f"Failed to write usage log: {exc}"
        return None


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


def _sum_usage_cost(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0.0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cost = payload.get("estimated_cost")
                if cost is None:
                    continue
                try:
                    total += float(cost)
                except (TypeError, ValueError):
                    continue
    except OSError:
        return 0.0
    return total


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
