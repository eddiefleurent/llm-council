"""Unit tests for council orchestration logic."""

from backend.council import (
    _index_to_alpha_label,
    calculate_aggregate_rankings,
    calculate_tournament_rankings,
    parse_ranking_from_text,
)


def test_parse_ranking_from_text_valid_json_format():
    """Test parsing strict JSON ranking format."""
    text = '{"final_ranking": ["Response B", "Response A", "Response C"]}'
    result = parse_ranking_from_text(text)
    assert result == ["Response B", "Response A", "Response C"]


def test_index_to_alpha_label_scales_beyond_z():
    """Label generation scales like spreadsheet columns."""
    assert _index_to_alpha_label(0) == "A"
    assert _index_to_alpha_label(25) == "Z"
    assert _index_to_alpha_label(26) == "AA"
    assert _index_to_alpha_label(27) == "AB"
    assert _index_to_alpha_label(51) == "AZ"
    assert _index_to_alpha_label(52) == "BA"


def test_parse_ranking_from_text_accepts_multi_letter_labels():
    """Parser accepts multi-letter labels when expected labels are provided."""
    text = '{"final_ranking": ["Response AA", "Response B", "Response Z"]}'
    result = parse_ranking_from_text(
        text, expected_labels={"Response AA", "Response B", "Response Z"}
    )
    assert result == ["Response AA", "Response B", "Response Z"]


def test_parse_ranking_from_text_rejects_non_json():
    """Non-JSON output is rejected."""
    text = "FINAL RANKING:\n1. Response A\n2. Response B\n3. Response C"
    result = parse_ranking_from_text(text)
    assert result == []


def test_parse_ranking_from_text_rejects_wrong_schema():
    """JSON missing final_ranking key is rejected."""
    text = '{"ranking": ["Response B", "Response A"]}'
    result = parse_ranking_from_text(text)
    assert result == []


def test_parse_ranking_from_text_empty():
    """Test parsing empty text."""
    result = parse_ranking_from_text("")
    assert result == []


def test_parse_ranking_from_text_rejects_partial_with_expected_labels():
    """Partial rankings are rejected when expected labels are provided."""
    text = '{"final_ranking": ["Response A", "Response B"]}'
    result = parse_ranking_from_text(
        text, expected_labels={"Response A", "Response B", "Response C"}
    )
    assert result == []


def test_parse_ranking_from_text_rejects_extra_with_expected_labels():
    """Rankings with extra labels are rejected when expected labels are provided."""
    text = '{"final_ranking": ["Response A", "Response B", "Response C"]}'
    result = parse_ranking_from_text(text, expected_labels={"Response A", "Response B"})
    assert result == []


def test_parse_ranking_from_text_accepts_exact_with_expected_labels():
    """Exact rankings are accepted when expected labels are provided."""
    text = '{"final_ranking": ["Response C", "Response A", "Response B"]}'
    result = parse_ranking_from_text(
        text, expected_labels={"Response A", "Response B", "Response C"}
    )
    assert result == ["Response C", "Response A", "Response B"]


def test_calculate_aggregate_rankings():
    """Test aggregate ranking calculation."""
    stage2_results = [
        {
            "model": "model1",
            "ranking": '{"final_ranking": ["Response A", "Response B"]}',
            "parsed_ranking": ["Response A", "Response B"],
        },
        {
            "model": "model2",
            "ranking": '{"final_ranking": ["Response B", "Response A"]}',
            "parsed_ranking": ["Response B", "Response A"],
        },
    ]
    label_to_model = {
        "Response A": "openai/gpt-4o",
        "Response B": "anthropic/claude-3",
    }

    result = calculate_aggregate_rankings(stage2_results, label_to_model)

    assert len(result) == 2
    # Both should have average rank of 1.5 (one first, one second)
    assert result[0]["average_rank"] == 1.5
    assert result[1]["average_rank"] == 1.5


def test_calculate_tournament_rankings():
    """Test tournament-style pairwise ranking calculation."""
    stage2_results = [
        {
            "model": "model1",
            "ranking": '{"final_ranking": ["Response A", "Response B", "Response C"]}',
            "parsed_ranking": ["Response A", "Response B", "Response C"],
        },
        {
            "model": "model2",
            "ranking": '{"final_ranking": ["Response A", "Response C", "Response B"]}',
            "parsed_ranking": ["Response A", "Response C", "Response B"],
        },
        {
            "model": "model3",
            "ranking": '{"final_ranking": ["Response B", "Response A", "Response C"]}',
            "parsed_ranking": ["Response B", "Response A", "Response C"],
        },
    ]
    label_to_model = {
        "Response A": "openai/gpt-4o",
        "Response B": "anthropic/claude-3",
        "Response C": "google/gemini",
    }

    result = calculate_tournament_rankings(stage2_results, label_to_model)

    assert len(result) == 3
    # Model A should win (2-1 against B, 3-0 against C)
    assert result[0]["model"] == "openai/gpt-4o"
    assert result[0]["win_percentage"] == 1.0


def test_calculate_tournament_rankings_tie():
    """Test tournament ranking handles ties correctly."""
    stage2_results = [
        {
            "model": "model1",
            "ranking": '{"final_ranking": ["Response A", "Response B"]}',
            "parsed_ranking": ["Response A", "Response B"],
        },
        {
            "model": "model2",
            "ranking": '{"final_ranking": ["Response B", "Response A"]}',
            "parsed_ranking": ["Response B", "Response A"],
        },
    ]
    label_to_model = {
        "Response A": "openai/gpt-4o",
        "Response B": "anthropic/claude-3",
    }

    result = calculate_tournament_rankings(stage2_results, label_to_model)

    assert len(result) == 2
    # Both should have 0.5 win percentage (tie)
    assert result[0]["win_percentage"] == 0.5
    assert result[1]["win_percentage"] == 0.5
