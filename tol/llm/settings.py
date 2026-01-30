from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LlmSettings:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float
    temperature: float
    max_tokens: int
    usage_log_path: Path | None
    usage_log_level: str
    api_log_path: Path | None
    api_log_level: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LlmSettings":
        usage_log_path = data.get("usage_log_path")
        api_log_path = data.get("api_log_path")
        return cls(
            api_key=str(data.get("api_key", "")),
            base_url=str(
                data.get(
                    "base_url",
                    "https://api.openai.com/v1",
                )
            ),
            model=str(data.get("model", "gpt-4o-mini")),
            timeout_seconds=float(data.get("timeout_seconds", 30.0)),
            temperature=float(data.get("temperature", 0.2)),
            max_tokens=int(data.get("max_tokens", 50000)),
            usage_log_path=Path(usage_log_path) if usage_log_path else None,
            usage_log_level=str(data.get("usage_log_level", "INFO")),
            api_log_path=Path(api_log_path) if api_log_path else None,
            api_log_level=str(data.get("api_log_level", "INFO")),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "usage_log_path": str(self.usage_log_path)
            if self.usage_log_path
            else None,
            "usage_log_level": self.usage_log_level,
            "api_log_path": str(self.api_log_path) if self.api_log_path else None,
            "api_log_level": self.api_log_level,
        }
        return data


__all__ = ["LlmSettings"]
