from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
import os

from tol.llm.settings import LlmSettings


CONFIG_PARAMS: dict[str, dict[str, Any]] = {
    "api_key": {"default": "", "parser": str},
    "base_url": {
        "default": "https://api.openai.com/v1/responses",
        "parser": str,
    },
    "model": {"default": "gpt-4o-mini", "parser": str},
    "timeout_seconds": {"default": 30.0, "parser": float},
    "temperature": {"default": 0.2, "parser": float},
    "max_tokens": {"default": 50000, "parser": int},
    "usage_log_path": {"default": None, "parser": str},
    "input_cost_per_1k": {"default": None, "parser": float},
    "output_cost_per_1k": {"default": None, "parser": float},
    "spend_limit_usd": {"default": 1000.0, "parser": float},
}


DEFAULT_SETTINGS: dict[str, Any] = {
    key: value["default"] for key, value in CONFIG_PARAMS.items()
}


def config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "tol" / "config.yaml"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "tol" / "config.yaml"


def load_settings() -> LlmSettings:
    path = config_path()
    if not path.exists():
        settings = LlmSettings.from_dict(DEFAULT_SETTINGS)
        write_settings(settings)
        return settings

    data = _read_yaml(path)
    if not isinstance(data, dict):
        data = {}
    merged = {**DEFAULT_SETTINGS, **data}
    return LlmSettings.from_dict(merged)


def write_settings(settings: LlmSettings) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = settings.to_dict()
    _write_yaml(path, payload)


def dump_settings(settings: LlmSettings, stream) -> None:
    data = settings.to_dict()
    try:
        import yaml
    except ModuleNotFoundError:
        _write_json_stream(stream, data)
        return
    yaml.safe_dump(data, stream, sort_keys=False, default_flow_style=False)


def get_setting(settings: LlmSettings, key: str) -> Any:
    if key not in CONFIG_PARAMS:
        raise KeyError(f"Unknown setting: {key}")
    payload = settings.to_dict()
    return payload.get(key)


def set_setting(settings: LlmSettings, key: str, raw_value: str) -> LlmSettings:
    if key not in CONFIG_PARAMS:
        raise KeyError(f"Unknown setting: {key}")
    parser = CONFIG_PARAMS[key]["parser"]
    if raw_value == "" and key in {
        "usage_log_path",
        "input_cost_per_1k",
        "output_cost_per_1k",
        "spend_limit_usd",
    }:
        value: Any = None
    else:
        value = parser(raw_value)
    payload = settings.to_dict()
    payload[key] = value
    return LlmSettings.from_dict(payload)


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        return _read_json(path)
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        _write_json(path, data)
        return
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, default_flow_style=False)


def _read_json(path: Path) -> dict[str, Any]:
    import json

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    import json

    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def _write_json_stream(stream, data: dict[str, Any]) -> None:
    import json

    stream.write(json.dumps(data, indent=2))
