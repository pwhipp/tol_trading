from tol.llm.client import _format_api_error


def test_format_api_error_with_quota_message() -> None:
    detail = (
        '{"error": {"message": "You exceeded your current quota", '
        '"type": "insufficient_quota", "code": "insufficient_quota"}}'
    )
    message = _format_api_error(429, detail)

    assert "HTTP 429" in message
    assert "You exceeded your current quota" in message
    assert "independent of spend_limit_usd" not in message
