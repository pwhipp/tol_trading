from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class LlmSettings:
    api_key: str
    base_url: str
    model: str
    mode: str
    broker: str
    timeout_seconds: float
    temperature: float
    max_tokens: int
    usage_log_path: Path | None
    usage_log_level: str
    api_log_path: Path | None
    api_log_level: str
    default_exchange: Optional[str]
    default_currency: Optional[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LlmSettings":
        usage_log_path = data.get("usage_log_path")
        api_log_path = data.get("api_log_path")
        mode = str(data.get("mode", "paper")).lower()
        if mode not in {"paper", "live"}:
            raise ValueError("mode must be 'paper' or 'live'")
        broker = _normalize_broker_name(data.get("broker"))
        return cls(
            api_key=str(data.get("api_key", "")),
            base_url=str(
                data.get(
                    "base_url",
                    "https://api.openai.com/v1",
                )
            ),
            model=str(data.get("model", "gpt-4.1")),
            mode=mode,
            broker=broker,
            timeout_seconds=float(data.get("timeout_seconds", 30.0)),
            temperature=float(data.get("temperature", 0.0)),
            max_tokens=int(data.get("max_tokens", 50000)),
            usage_log_path=Path(usage_log_path) if usage_log_path else None,
            usage_log_level=str(data.get("usage_log_level", "INFO")),
            api_log_path=Path(api_log_path) if api_log_path else None,
            api_log_level=str(data.get("api_log_level", "INFO")),
            default_exchange=_normalize_optional_code(
                data.get("default_exchange")
            ),
            default_currency=_normalize_optional_code(
                data.get("default_currency")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model,
            "mode": self.mode,
            "broker": self.broker,
            "timeout_seconds": self.timeout_seconds,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "usage_log_path": str(self.usage_log_path)
            if self.usage_log_path
            else None,
            "usage_log_level": self.usage_log_level,
            "api_log_path": str(self.api_log_path) if self.api_log_path else None,
            "api_log_level": self.api_log_level,
            "default_exchange": self.default_exchange,
            "default_currency": self.default_currency,
        }
        return data


def _normalize_optional_code(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def _normalize_broker_name(value: Any) -> str:
    name = str(value or "IBKRBrokerAPI").strip()
    if name not in {"IBKRBrokerAPI", "FakeBrokerAPI"}:
        raise ValueError("broker must be 'IBKRBrokerAPI' or 'FakeBrokerAPI'")
    return name


__all__ = ["LlmSettings"]
