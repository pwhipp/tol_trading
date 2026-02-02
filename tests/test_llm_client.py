from tol.llm.client import (
    _format_api_error,
    _generate_system_message,
    _render_prompt,
)


def test_format_api_error_with_quota_message() -> None:
    detail = (
        '{"error": {"message": "You exceeded your current quota", '
        '"type": "insufficient_quota", "code": "insufficient_quota"}}'
    )
    message = _format_api_error(429, detail)

    assert "HTTP 429" in message
    assert "You exceeded your current quota" in message
    assert "independent of spend_limit_usd" not in message


def test_generate_context_prompt_includes_schema_and_spec() -> None:
    schema = '{"type": "object"}'
    spec = "# Spec"
    mode = "paper"
    prompt = _render_prompt(
        "generate_tol_context.j2",
        spec_text=spec,
        schema_json=schema,
        mode=mode,
        default_exchange="NYSE",
        default_currency="USD",
        exchange_currencies_text="exchanges: {}",
    )

    assert schema in prompt
    assert spec in prompt
    assert "TOL SPECIFICATION (normative):" in prompt
    assert "JSON SCHEMA (authoritative):" in prompt
    assert mode in prompt


def test_generate_user_prompt_includes_request() -> None:
    request = "Buy 10 shares of TSLA."
    prompt = _render_prompt(
        "generate_tol_user.j2",
        user_request=request,
    )

    assert request in prompt
    assert "Convert the follwing request into a TOL document:" in prompt


def test_generate_system_message_has_rules() -> None:
    message = _generate_system_message()

    assert message["role"] == "system"
    assert "Output JSON only." in message["content"]
    assert '{"error": "<reason>"}' in message["content"]
    assert "do not use TARGET for proceeds allocation" in message["content"]
