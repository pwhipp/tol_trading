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
    assert settings.model == "gpt-4.1"
    assert settings.base_url == "https://api.openai.com/v1"
    assert settings.mode == "paper"
    assert settings.broker == "IBKRBrokerAPI"
    assert settings.temperature == 0.0
    assert settings.broker_client_id == 11
    assert settings.usage_log_path == Path("llm_usage.log")
    assert settings.usage_log_level == "INFO"
    assert settings.api_log_path == Path("llm_api.log")
    assert settings.api_log_level == "INFO"
    assert settings.default_exchange is None
    assert settings.default_currency is None


def test_set_and_get_setting_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    get_config.cache_clear()
    settings = get_config()

    updated = set_setting(settings, "model", "gpt-4o")
    updated = set_setting(updated, "broker", "FakeBrokerAPI")
    updated.save()

    reloaded = load_config()
    assert get_setting(reloaded, "model") == "gpt-4o"
    assert get_setting(reloaded, "broker") == "FakeBrokerAPI"


def test_set_mode_setting_normalizes_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    get_config.cache_clear()
    settings = get_config()

    updated = set_setting(settings, "mode", "LIVE")
    updated.save()

    reloaded = load_config()
    assert reloaded.mode == "live"


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

    assert parsed["broker_client_id"] == 11
