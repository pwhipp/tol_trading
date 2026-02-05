from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any
import os

import yaml


CONFIG_PARAMS: dict[str, dict[str, Any]] = {
    "api_key": {"default": "", "parser": str},
    "base_url": {
        "default": "https://api.openai.com/v1",
        "parser": str,
    },
    "model": {"default": "gpt-4.1", "parser": str},
    "mode": {"default": "paper", "parser": str},
    "broker": {"default": "IBKRBrokerAPI", "parser": str},
    "broker_client_id": {"default": 11, "parser": int},
    "timeout_seconds": {"default": 30.0, "parser": float},
    "temperature": {"default": 0.0, "parser": float},
    "max_tokens": {"default": 50000, "parser": int},
    "usage_log_path": {"default": "llm_usage.log", "parser": str},
    "usage_log_level": {"default": "INFO", "parser": str},
    "api_log_path": {"default": "llm_api.log", "parser": str},
    "api_log_level": {"default": "INFO", "parser": str},
    "tif": {"default": "GTC", "parser": str},
    "default_exchange": {"default": None, "parser": str},
    "default_currency": {"default": None, "parser": str},
}

DEFAULT_SETTINGS: dict[str, Any] = {
    key: value["default"] for key, value in CONFIG_PARAMS.items()
}

_OPTIONAL_EMPTY_KEYS = {
    "usage_log_path",
    "api_log_path",
    "default_exchange",
    "default_currency",
}


class Config(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self[name] = value

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        payload = {}
        for key in CONFIG_PARAMS:
            value = data.get(key, DEFAULT_SETTINGS[key])
            payload[key] = _normalize_value(key, value)
        return cls(payload)

    def to_dict(self) -> dict[str, Any]:
        return {key: _serialize_value(key, self.get(key)) for key in CONFIG_PARAMS}

    def load(self, path: Path | None = None) -> None:
        config_data = _load_config_data(path)
        self.clear()
        self.update(Config.from_dict(config_data))

    def save(self, path: Path | None = None) -> None:
        config_path = path or get_config_path()
        _write_json(config_path, self.to_dict())


def get_config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "tol" / "config.json"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "tol" / "config.json"


def load_config() -> Config:
    config = Config()
    config.load()
    return config


@lru_cache(maxsize=1)
def get_config() -> Config:
    config = Config()
    config.load()
    return config


def get_setting(config: Config, key: str) -> Any:
    _ensure_setting_key(key)
    return config.get(key)


def set_setting(config: Config, key: str, raw_value: str) -> Config:
    _ensure_setting_key(key)
    value = _normalize_value(key, raw_value)
    config[key] = value
    return config


def dump_settings(config: Config, stream) -> None:
    yaml.safe_dump(config.to_dict(), stream, sort_keys=False)


def _ensure_setting_key(key: str) -> None:
    if key not in CONFIG_PARAMS:
        raise KeyError(f"Unknown setting: {key}")


def _normalize_value(key: str, value: Any) -> Any:
    if key in _OPTIONAL_EMPTY_KEYS and (value is None or value == ""):
        return None
    if key == "mode":
        normalized = str(value).strip().lower()
        if normalized not in {"paper", "live"}:
            raise ValueError("mode must be 'paper' or 'live'")
        return normalized
    if key == "broker":
        normalized = str(value).strip()
        if normalized not in {"IBKRBrokerAPI", "FakeBrokerAPI"}:
            raise ValueError("broker must be 'IBKRBrokerAPI' or 'FakeBrokerAPI'")
        return normalized
    if key == "tif":
        normalized = str(value).strip().upper()
        if not normalized:
            raise ValueError("tif must be a non-empty string")
        return normalized
    if key in {"default_exchange", "default_currency"}:
        return _normalize_optional_code(value)
    if key in {"usage_log_path", "api_log_path"}:
        return Path(value) if value else None
    parser = CONFIG_PARAMS[key]["parser"]
    return parser(value)


def _normalize_optional_code(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def _serialize_value(key: str, value: Any) -> Any:
    if key in {"usage_log_path", "api_log_path"} and value is not None:
        return str(value)
    return value


def _load_config_data(path: Path | None) -> dict[str, Any]:
    config_path = path or get_config_path()
    if config_path.exists():
        data = _read_json(config_path)
        return data if isinstance(data, dict) else {}
    config = Config.from_dict(DEFAULT_SETTINGS)
    config.save(config_path)
    return config.to_dict()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle) or {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=4)
        handle.write("\n")
