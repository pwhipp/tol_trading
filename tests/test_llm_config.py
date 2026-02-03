from pathlib import Path

import pytest

from tol import config as app_config


def test_load_settings_creates_default_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app_config.get_config.cache_clear()
    config_path = app_config.get_config_path()
    assert not config_path.exists()

    settings = app_config.get_config()
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
    app_config.get_config.cache_clear()
    settings = app_config.get_config()

    updated = app_config.set_setting(settings, "model", "gpt-4o")
    updated = app_config.set_setting(updated, "broker", "FakeBrokerAPI")
    updated.save()

    reloaded = app_config.load_config()
    assert app_config.get_setting(reloaded, "model") == "gpt-4o"
    assert app_config.get_setting(reloaded, "broker") == "FakeBrokerAPI"


def test_set_mode_setting_normalizes_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app_config.get_config.cache_clear()
    settings = app_config.get_config()

    updated = app_config.set_setting(settings, "mode", "LIVE")
    updated.save()

    reloaded = app_config.load_config()
    assert reloaded.mode == "live"


def test_legacy_yaml_config_migrates_to_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app_config.get_config.cache_clear()

    legacy_path = tmp_path / "tol" / "config.yaml"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text("model: gpt-4o\n", encoding="utf-8")

    config = app_config.load_config()
    json_path = app_config.get_config_path()

    assert config.model == "gpt-4o"
    assert json_path.exists()
