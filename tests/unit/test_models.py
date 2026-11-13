"""Unit tests for model catalog parsing and provider grouping."""

from backend import models


def test_parse_model_strips_alias_provider_prefix():
    """~provider/model-latest aliases group under their real provider."""
    parsed = models._parse_model(
        {"id": "~openai/gpt-astra-latest", "name": "OpenAI: GPT Astra Latest"}
    )

    assert parsed is not None
    assert parsed.id == "~openai/gpt-astra-latest"
    assert parsed.provider == "openai"


def test_parse_model_regular_provider_unchanged():
    parsed = models._parse_model(
        {"id": "anthropic/claude-opus-5.5", "name": "Anthropic: Claude Opus 5.5"}
    )

    assert parsed is not None
    assert parsed.provider == "anthropic"


def test_parse_model_rejects_id_without_slash():
    assert models._parse_model({"id": "no-slash"}) is None


def test_organize_models_groups_aliases_with_real_provider():
    alias = models._parse_model({"id": "~openai/gpt-astra-latest"})
    assert alias is not None
    entries = [
        models.ModelInfo(
            id="~openai/gpt-astra-latest",
            name="GPT Astra Latest",
            provider=alias.provider,
            context_length=1050000,
            pricing_prompt=0,
            pricing_completion=0,
        ),
        models.ModelInfo(
            id="openai/gpt-6-astra",
            name="GPT 6 Astra",
            provider="openai",
            context_length=1050000,
            pricing_prompt=0,
            pricing_completion=0,
        ),
    ]

    grouped = models._organize_models(entries)

    assert set(grouped) == {"openai"}
    assert {m.id for m in grouped["openai"]} == {
        "~openai/gpt-astra-latest",
        "openai/gpt-6-astra",
    }
