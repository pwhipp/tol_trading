from pathlib import Path

import pytest

from tol.llm import config as llm_config


def test_load_settings_creates_default_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    config_path = llm_config.config_path()
    assert not config_path.exists()

    settings = llm_config.load_settings()
    assert config_path.exists()
    assert settings.model == "gpt-4.1"
    assert settings.base_url == "https://api.openai.com/v1"
    assert settings.mode == "paper"
    assert settings.broker == "IBKRBrokerAPI"
    assert settings.temperature == 0.0
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
    settings = llm_config.load_settings()

    updated = llm_config.set_setting(settings, "model", "gpt-4o")
    updated = llm_config.set_setting(updated, "broker", "FakeBrokerAPI")
    llm_config.write_settings(updated)

    reloaded = llm_config.load_settings()
    assert llm_config.get_setting(reloaded, "model") == "gpt-4o"
    assert llm_config.get_setting(reloaded, "broker") == "FakeBrokerAPI"


def test_set_mode_setting_normalizes_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    settings = llm_config.load_settings()

    updated = llm_config.set_setting(settings, "mode", "LIVE")
    llm_config.write_settings(updated)

    reloaded = llm_config.load_settings()
    assert reloaded.mode == "live"
