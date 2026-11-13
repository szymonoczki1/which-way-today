import pytest

from app.config import Settings


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_openai_model_uses_default(monkeypatch: pytest.MonkeyPatch, blank: str) -> None:
    # docker compose passes an unset OPENAI_MODEL as "".
    monkeypatch.setenv("OPENAI_MODEL", blank)

    assert Settings().openai_model == "gpt-4o-mini"


def test_openai_model_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "some-other-model")

    assert Settings().openai_model == "some-other-model"
