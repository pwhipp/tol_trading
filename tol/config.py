from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Any

import yaml


ConfigPath = tuple[str, ...]


CONFIG_SCHEMA: dict[str, Any] = {
    "execution": {
        "usage_log_path": {"default": "llm_usage.log", "parser": str},
        "usage_log_level": {"default": "INFO", "parser": str},
        "tif": {"default": "GTC", "parser": str},
        "default_currency": {"default": None, "parser": str},
        "default_exchange": {"default": None, "parser": str},
    },
    "broker": {
        "api_key": {"default": "", "parser": str},
        "base_url": {
            "default": "https://api.openai.com/v1",
            "parser": str,
        },
        "mode": {"default": "paper", "parser": str},
        "api": {"default": "IBKRBrokerAPI", "parser": str},
        "client_id": {"default": 11, "parser": int},
        "timeout_seconds": {"default": 30.0, "parser": float},
        "settle_window": {"default": 0.3, "parser": float},
        "spread_pct": {"default": 0.0, "parser": float},
        "watched_tickers": {"default": [], "parser": list},
    },
    "llm": {
        "model": {"default": "gpt-4.1", "parser": str},
        "temperature": {"default": 0.0, "parser": float},
        "max_tokens": {"default": 50000, "parser": int},
        "api_log_path": {"default": "llm_api.log", "parser": str},
        "api_log_level": {"default": "INFO", "parser": str},
    },
}

_OPTIONAL_EMPTY_KEYS = {
    ("execution", "usage_log_path"),
    ("execution", "default_exchange"),
    ("execution", "default_currency"),
    ("llm", "api_log_path"),
}

_PATH_KEYS = {
    ("execution", "usage_log_path"),
    ("llm", "api_log_path"),
}


class ConfigSection(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
            return
        self[name] = value

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, self._coerce_value(value))

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ConfigSection":
        section = cls()
        for key, value in data.items():
            section[key] = value
        return section

    @staticmethod
    def _coerce_value(value: Any) -> Any:
        if isinstance(value, ConfigSection):
            return value
        if isinstance(value, dict):
            return ConfigSection.from_mapping(value)
        return value


class Config(dict[str, ConfigSection]):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        payload = _normalize_config_shape(CONFIG_SCHEMA, data or {}, ())
        config = cls()
        for category, value in payload.items():
            config[category] = ConfigSection.from_mapping(value)
        return config

    def to_dict(self) -> dict[str, Any]:
        return _serialize_config_shape(CONFIG_SCHEMA, self, ())

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


def get_setting(config: Config, category: str, key: str | None = None) -> Any:
    _ensure_category(category)
    if key is None:
        return config[category]
    _ensure_setting_key(category, key)
    return config[category].get(key)


def set_setting(config: Config, category: str, key: str, raw_value: str) -> Config:
    leaf_schema = _resolve_setting_schema((category, key))
    value = _normalize_value((category, key), leaf_schema, raw_value)
    config[category][key] = value
    return config


def dump_settings(config: Config, stream) -> None:
    yaml.safe_dump(config.to_dict(), stream, sort_keys=False)


def dump_category(config: Config, category: str, stream) -> None:
    _ensure_category(category)
    yaml.safe_dump(
        _serialize_config_shape(CONFIG_SCHEMA[category], config[category], (category,)),
        stream,
        sort_keys=False,
    )


def _ensure_category(category: str) -> None:
    if category not in CONFIG_SCHEMA:
        raise KeyError(f"Unknown config category: {category}")


def _ensure_setting_key(category: str, key: str) -> None:
    _resolve_setting_schema((category, key))


def _resolve_setting_schema(path: ConfigPath) -> dict[str, Any]:
    schema_node: Any = CONFIG_SCHEMA
    for key in path:
        if not isinstance(schema_node, dict) or key not in schema_node:
            raise KeyError(f"Unknown setting: {'.'.join(path)}")
        schema_node = schema_node[key]

    if not _is_leaf_setting(schema_node):
        if len(path) == 1:
            raise KeyError(f"Unknown config category: {path[0]}")
        raise KeyError(f"Unknown setting: {'.'.join(path)}")
    return schema_node


def _is_leaf_setting(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and "default" in value
        and "parser" in value
        and len(value) == 2
    )


def _normalize_config_shape(
    schema_node: dict[str, Any],
    data_node: Any,
    path: ConfigPath,
) -> dict[str, Any]:
    incoming = data_node if isinstance(data_node, dict) else {}
    output: dict[str, Any] = {}

    for key, next_schema in schema_node.items():
        next_path = (*path, key)
        raw_value = incoming.get(key)
        if _is_leaf_setting(next_schema):
            normalized = _normalize_value(
                next_path,
                next_schema,
                next_schema["default"] if key not in incoming else raw_value,
            )
            output[key] = normalized
            continue

        output[key] = _normalize_config_shape(next_schema, raw_value, next_path)

    return output


def _serialize_config_shape(
    schema_node: dict[str, Any],
    data_node: Any,
    path: ConfigPath,
) -> dict[str, Any]:
    source = data_node if isinstance(data_node, dict) else {}
    output: dict[str, Any] = {}

    for key, next_schema in schema_node.items():
        next_path = (*path, key)
        value = source.get(key)
        if _is_leaf_setting(next_schema):
            output[key] = _serialize_value(next_path, value)
            continue

        output[key] = _serialize_config_shape(next_schema, value, next_path)

    return output


def _normalize_value(
    path: ConfigPath,
    leaf_schema: dict[str, Any],
    value: Any,
) -> Any:
    if path in _OPTIONAL_EMPTY_KEYS and (value is None or value == ""):
        return None

    if path == ("broker", "mode"):
        normalized = str(value).strip().lower()
        if normalized not in {"paper", "live"}:
            raise ValueError("mode must be 'paper' or 'live'")
        return normalized

    if path == ("broker", "api"):
        normalized = str(value).strip()
        if normalized not in {"IBKRBrokerAPI", "FakeBrokerAPI"}:
            raise ValueError("api must be 'IBKRBrokerAPI' or 'FakeBrokerAPI'")
        return normalized

    if path == ("execution", "tif"):
        normalized = str(value).strip().upper()
        if not normalized:
            raise ValueError("tif must be a non-empty string")
        return normalized

    if path in {
        ("execution", "default_exchange"),
        ("execution", "default_currency"),
    }:
        return _normalize_optional_code(value)

    if path == ("broker", "watched_tickers"):
        return _normalize_tickers(value)

    if path == ("broker", "settle_window"):
        settle_window = float(value)
        if settle_window < 0:
            raise ValueError("settle_window must be >= 0")
        return settle_window

    if path == ("broker", "spread_pct"):
        spread_pct = float(value)
        if spread_pct < 0:
            raise ValueError("spread_pct must be >= 0")
        return spread_pct

    if path in _PATH_KEYS:
        return Path(value) if value else None

    parser = leaf_schema["parser"]
    return parser(value)


def _normalize_optional_code(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def _normalize_tickers(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = value
    else:
        raise ValueError("watched_tickers must be a list of strings")

    normalized: list[str] = []
    for ticker in candidates:
        cleaned = str(ticker).strip().upper()
        if cleaned:
            normalized.append(cleaned)
    return normalized


def _serialize_value(path: ConfigPath, value: Any) -> Any:
    if path in _PATH_KEYS and value is not None:
        return str(value)
    return value


def _load_config_data(path: Path | None) -> dict[str, Any]:
    config_path = path or get_config_path()
    if config_path.exists():
        data = _read_json(config_path)
        return data if isinstance(data, dict) else {}
    config = Config.from_dict({})
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
