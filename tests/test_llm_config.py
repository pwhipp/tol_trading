from pathlib import Path

import pytest

from tol.config import (
    dump_settings,
    get_config,
    get_config_path,
    get_setting,
    load_config,
    set_setting,
)


def test_load_settings_creates_default_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    get_config.cache_clear()
    config_path = get_config_path()
    assert not config_path.exists()

    settings = get_config()
    assert config_path.exists()
    assert settings.llm.model == "gpt-4.1"
    assert settings.broker.base_url == "https://api.openai.com/v1"
    assert settings.broker.mode == "paper"
    assert settings.broker.api == "IBKRBrokerAPI"
    assert settings.llm.temperature == 0.0
    assert settings.broker.client_id == 11
    assert settings.broker.settle_window == 0.3
    assert settings.execution.usage_log_path == Path("llm_usage.log")
    assert settings.execution.usage_log_level == "INFO"
    assert settings.llm.api_log_path == Path("llm_api.log")
    assert settings.llm.api_log_level == "INFO"
    assert settings.execution.default_exchange is None
    assert settings.execution.default_currency is None
    assert settings.broker.watched_tickers == []


def test_set_and_get_setting_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    get_config.cache_clear()
    settings = get_config()

    updated = set_setting(settings, "llm", "model", "gpt-4o")
    updated = set_setting(updated, "broker", "api", "FakeBrokerAPI")
    updated.save()

    reloaded = load_config()
    assert get_setting(reloaded, "llm", "model") == "gpt-4o"
    assert get_setting(reloaded, "broker", "api") == "FakeBrokerAPI"


def test_set_mode_setting_normalizes_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    get_config.cache_clear()
    settings = get_config()

    updated = set_setting(settings, "broker", "mode", "LIVE")
    updated.save()

    reloaded = load_config()
    assert reloaded.broker.mode == "live"


def test_dump_settings_outputs_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io
    import yaml

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    get_config.cache_clear()
    settings = get_config()

    stream = io.StringIO()
    dump_settings(settings, stream)

    output = stream.getvalue()
    parsed = yaml.safe_load(output)

    assert parsed["broker"]["client_id"] == 11


def test_flat_config_shape_is_not_migrated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    get_config.cache_clear()
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"model": "gpt-4o", "broker_client_id": 99}),
        encoding="utf-8",
    )

    settings = load_config()

    assert settings.llm.model == "gpt-4.1"
    assert settings.broker.client_id == 11
    assert settings.broker.settle_window == 0.3


def test_settle_window_must_be_non_negative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    get_config.cache_clear()
    settings = get_config()

    with pytest.raises(ValueError, match="settle_window must be >= 0"):
        set_setting(settings, "broker", "settle_window", "-0.1")


def test_spread_pct_must_be_non_negative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    get_config.cache_clear()
    settings = get_config()

    with pytest.raises(ValueError, match="spread_pct must be >= 0"):
        set_setting(settings, "broker", "spread_pct", "-0.1")
