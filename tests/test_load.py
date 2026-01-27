from pathlib import Path

import pytest

from tol.load import load_tol


def test_load_converts_all_and_percent(tmp_path: Path) -> None:
    tol_file = tmp_path / "example.json"
    tol_file.write_text(
        """
{
  "version": 1,
  "actions": [
    {"buy": {"symbol": "TSLA", "quantity": "ALL"}},
    {"sell": {"symbol": "NVDA", "quantity": "25%"}}
  ]
}
""",
        encoding="utf-8",
    )

    tol_doc = load_tol(tol_file)
    actions = tol_doc["actions"]
    assert actions[0]["buy"]["quantity"] == 1.0
    assert actions[1]["sell"]["quantity"] == 0.25


def test_load_converts_string_integer(tmp_path: Path) -> None:
    tol_file = tmp_path / "example.json"
    tol_file.write_text(
        """
{
  "version": 1,
  "actions": [
    {"buy": {"symbol": "TSLA", "quantity": "100"}}
  ]
}
""",
        encoding="utf-8",
    )

    tol_doc = load_tol(tol_file)
    assert tol_doc["actions"][0]["buy"]["quantity"] == 100


def test_load_rejects_float_greater_than_one(tmp_path: Path) -> None:
    tol_file = tmp_path / "example.json"
    tol_file.write_text(
        """
{
  "version": 1,
  "actions": [
    {"buy": {"symbol": "TSLA", "quantity": 1.5}}
  ]
}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_tol(tol_file)


def test_load_parses_target_percent_string(tmp_path: Path) -> None:
    tol_file = tmp_path / "example.json"
    tol_file.write_text(
        """
{
  "version": 1,
  "actions": [
    {"target": {"symbol": "AAPL", "percent": "25%"}}
  ]
}
""",
        encoding="utf-8",
    )

    tol_doc = load_tol(tol_file)
    assert tol_doc["actions"][0]["target"]["percent"] == 25.0
