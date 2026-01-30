from tol.llm.client import _format_api_error, _render_prompt


def test_format_api_error_with_quota_message() -> None:
    detail = (
        '{"error": {"message": "You exceeded your current quota", '
        '"type": "insufficient_quota", "code": "insufficient_quota"}}'
    )
    message = _format_api_error(429, detail)

    assert "HTTP 429" in message
    assert "You exceeded your current quota" in message
    assert "independent of spend_limit_usd" not in message


def test_generate_prompt_includes_schema_and_spec_hint() -> None:
    schema = '{"type": "object"}'
    prompt = _render_prompt("generate_tol_prompt.j2", schema_json=schema)

    assert schema in prompt
    assert "TOL_SPEC.md" in prompt
    assert "\"error\"" in prompt
