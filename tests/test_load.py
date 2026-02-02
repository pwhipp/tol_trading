from pathlib import Path

import pytest

from tol.load import (
    check_tol_syntax_and_static_semantics,
    dump_tol,
    load_tol,
    load_tol_text,
)


def test_load_converts_all_and_percent(tmp_path: Path) -> None:
    tol_file = tmp_path / "example.json"
    tol_file.write_text(
        """
{
  "version": 1,
  "mode": "paper",
  "actions": [
    {"buy": {"symbol": "TSLA.NASDAQ", "quantity": "ALL"}},
    {"sell": {"symbol": "NVDA.NASDAQ", "quantity": "25%"}}
  ]
}
""",
        encoding="utf-8",
    )

    tol_doc = load_tol(tol_file)
    actions = tol_doc["actions"]
    assert actions[0]["buy"]["quantity"] == "ALL"
    assert actions[1]["sell"]["quantity"] == "25%"


def test_load_converts_string_integer(tmp_path: Path) -> None:
    tol_file = tmp_path / "example.json"
    tol_file.write_text(
        """
{
  "version": 1,
  "mode": "paper",
  "actions": [
    {"buy": {"symbol": "TSLA.NASDAQ", "quantity": "100"}}
  ]
}
""",
        encoding="utf-8",
    )

    tol_doc = load_tol(tol_file)
    assert tol_doc["actions"][0]["buy"]["quantity"] == 100


def test_load_accepts_comma_delimited_integer(tmp_path: Path) -> None:
    tol_file = tmp_path / "example.json"
    tol_file.write_text(
        """
{
  "version": 1,
  "mode": "paper",
  "actions": [
    {"buy": {"symbol": "TSLA.NASDAQ", "quantity": "1,000"}}
  ]
}
""",
        encoding="utf-8",
    )

    tol_doc = load_tol(tol_file)
    assert tol_doc["actions"][0]["buy"]["quantity"] == 1000


def test_load_rejects_float_greater_than_one(tmp_path: Path) -> None:
    tol_file = tmp_path / "example.json"
    tol_file.write_text(
        """
{
  "version": 1,
  "mode": "paper",
  "actions": [
    {"buy": {"symbol": "TSLA.NASDAQ", "quantity": 1.5}}
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
  "mode": "paper",
  "actions": [
    {"target": {"symbol": "AAPL.NASDAQ", "percent": "25%"}}
  ]
}
""",
        encoding="utf-8",
    )

    tol_doc = load_tol(tol_file)
    assert tol_doc["actions"][0]["target"]["percent"] == "25%"


def test_load_from_text_and_dump_round_trip() -> None:
    source = """
{
  "version": 1,
  "mode": "paper",
  "actions": [
    {"sell": {"symbol": "NVDA.NASDAQ", "quantity": "50%"}}
  ]
}
"""
    tol_doc = load_tol_text(source)
    assert tol_doc["actions"][0]["sell"]["quantity"] == "50%"

    dumped = dump_tol(tol_doc)
    reloaded = load_tol_text(dumped)
    assert reloaded["actions"][0]["sell"]["quantity"] == "50%"


def test_load_normalizes_using_sources() -> None:
    source = """
{
  "version": 1,
  "mode": "paper",
  "actions": [
    {
      "buy": {
        "symbol": "TSM",
        "quantity": "50%",
        "using": ["proceeds from VOO.NYSE", "CASH (usd)"]
      }
    }
  ]
}
"""
    tol_doc = load_tol_text(source)
    using = tol_doc["actions"][0]["buy"]["using"]

    assert using == ["sellVOO.NYSE", "CASH (USD)"]


def test_load_normalizes_money_quantity() -> None:
    source = """
{
  "version": 1,
  "mode": "paper",
  "actions": [
    {"buy": {"symbol": "AAPL.NASDAQ", "quantity": "$50.00 (USD)"}}
  ]
}
"""
    tol_doc = load_tol_text(source)
    assert tol_doc["actions"][0]["buy"]["quantity"] == "$50 (USD)"


def test_check_requires_mode() -> None:
    with pytest.raises(ValueError):
        check_tol_syntax_and_static_semantics({"version": 1, "actions": []})


def test_check_rejects_invalid_mode() -> None:
    with pytest.raises(ValueError):
        check_tol_syntax_and_static_semantics(
            {"version": 1, "mode": "sandbox", "actions": []}
        )
