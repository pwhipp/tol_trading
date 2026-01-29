from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LlmPricing:
    input_cost_per_1k: float
    output_cost_per_1k: float

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        input_cost = (prompt_tokens / 1000.0) * self.input_cost_per_1k
        output_cost = (completion_tokens / 1000.0) * self.output_cost_per_1k
        return input_cost + output_cost


@dataclass(frozen=True)
class LlmSettings:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float
    temperature: float
    max_tokens: int
    usage_log_path: Path | None
    pricing: LlmPricing | None
    spend_limit_usd: float | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LlmSettings":
        pricing = None
        input_cost = data.get("input_cost_per_1k")
        output_cost = data.get("output_cost_per_1k")
        if input_cost is not None and output_cost is not None:
            pricing = LlmPricing(
                input_cost_per_1k=float(input_cost),
                output_cost_per_1k=float(output_cost),
            )

        usage_log_path = data.get("usage_log_path")
        return cls(
            api_key=str(data.get("api_key", "")),
            base_url=str(
                data.get(
                    "base_url",
                    "https://api.openai.com/v1/chat/completions",
                )
            ),
            model=str(data.get("model", "gpt-4o-mini")),
            timeout_seconds=float(data.get("timeout_seconds", 30.0)),
            temperature=float(data.get("temperature", 0.2)),
            max_tokens=int(data.get("max_tokens", 512)),
            usage_log_path=Path(usage_log_path) if usage_log_path else None,
            pricing=pricing,
            spend_limit_usd=_optional_float(data.get("spend_limit_usd")),
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
            "input_cost_per_1k": None,
            "output_cost_per_1k": None,
            "spend_limit_usd": self.spend_limit_usd,
        }
        if self.pricing:
            data["input_cost_per_1k"] = self.pricing.input_cost_per_1k
            data["output_cost_per_1k"] = self.pricing.output_cost_per_1k
        return data


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


__all__ = ["LlmPricing", "LlmSettings"]
