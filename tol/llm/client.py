from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Any
from urllib import request, error

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
        if not self._settings.api_key:
            raise RuntimeError(
                "Missing API key. Set api_key in the TOL config file."
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
        payload = {
            "model": self._settings.model,
            "messages": messages,
            "temperature": self._settings.temperature,
            "max_tokens": self._settings.max_tokens,
        }
        data = json.dumps(payload).encode("utf-8")
        request_obj = request.Request(
            self._settings.base_url,
            data=data,
            headers={
                "Authorization": f"Bearer {self._settings.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(
                request_obj, timeout=self._settings.timeout_seconds
            ) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8") if exc.fp else ""
            raise RuntimeError(
                f"ChatGPT API error: HTTP {exc.code} {detail}".strip()
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"ChatGPT API connection error: {exc}") from exc

        data = json.loads(body)
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        usage = self._parse_usage(data)
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
        prompt_tokens = int(usage_data.get("prompt_tokens", 0))
        completion_tokens = int(usage_data.get("completion_tokens", 0))
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
