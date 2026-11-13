import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.clients import openai_client

POST = "app.clients.openai_client.httpx.post"


def _completion(content: str, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        json={"choices": [{"message": {"role": "assistant", "content": content}}]},
        request=httpx.Request("POST", "https://api.openai.test"),
    )


@pytest.mark.parametrize("key", [None, "", "   "])
@patch(POST)
def test_does_not_call_api_without_a_key(mock_post: MagicMock, key: str | None) -> None:
    # Docker passes an unset OPENAI_API_KEY as "", so emptiness, not None, decides.
    assert openai_client.complete_json("sys", "user", api_key=key, model="m") is None
    mock_post.assert_not_called()


@patch(POST)
def test_returns_parsed_json_object(mock_post: MagicMock) -> None:
    mock_post.return_value = _completion(json.dumps({"recommended_mode": "bike"}))

    result = openai_client.complete_json("sys", "user", api_key="sk-test", model="gpt-x")

    assert result == {"recommended_mode": "bike"}
    kwargs = mock_post.call_args.kwargs
    assert kwargs["headers"]["Authorization"] == "Bearer sk-test"
    assert kwargs["json"]["model"] == "gpt-x"
    assert kwargs["json"]["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in kwargs["json"]["messages"]] == ["system", "user"]


@pytest.mark.parametrize(
    "response",
    [
        _completion("not json at all"),
        _completion('["a", "list"]'),  # valid JSON but not an object
        _completion("{}", status=401),
        _completion("{}", status=429),
        httpx.Response(
            200, json={"choices": []}, request=httpx.Request("POST", "https://api.openai.test")
        ),
        httpx.Response(200, text="<html>", request=httpx.Request("POST", "https://x.test")),
    ],
)
@patch(POST)
def test_returns_none_on_bad_responses(mock_post: MagicMock, response: httpx.Response) -> None:
    mock_post.return_value = response

    assert openai_client.complete_json("sys", "user", api_key="sk-test", model="m") is None


@patch(POST)
def test_returns_none_on_timeout(mock_post: MagicMock) -> None:
    mock_post.side_effect = httpx.ReadTimeout("slow")

    assert openai_client.complete_json("sys", "user", api_key="sk-test", model="m") is None


@patch(POST)
def test_never_logs_the_api_key(mock_post: MagicMock, caplog: pytest.LogCaptureFixture) -> None:
    mock_post.side_effect = httpx.ConnectError("boom sk-secret-123")

    openai_client.complete_json("sys", "user", api_key="sk-secret-123", model="m")

    assert "sk-secret-123" not in caplog.text
