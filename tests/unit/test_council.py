"""Unit tests for council orchestration logic."""

import pytest
from unittest.mock import AsyncMock, patch
from backend.council import (
    parse_ranking_from_text,
    calculate_aggregate_rankings,
    calculate_tournament_rankings,
)


def test_parse_ranking_from_text_numbered_format():
    """Test parsing numbered ranking format."""
    text = """
    Response A is good but lacks depth.
    Response B is excellent.
    Response C is mediocre.

    FINAL RANKING:
    1. Response B
    2. Response A
    3. Response C
    """
    result = parse_ranking_from_text(text)
    assert result == ["Response B", "Response A", "Response C"]


def test_parse_ranking_from_text_plain_format():
    """Test parsing plain ranking format without numbers."""
    text = """
    FINAL RANKING:
    Response C
    Response A
    Response B
    """
    result = parse_ranking_from_text(text)
    assert result == ["Response C", "Response A", "Response B"]


def test_parse_ranking_from_text_no_header():
    """Test fallback parsing when no FINAL RANKING header."""
    text = "I think Response B is best, followed by Response A."
    result = parse_ranking_from_text(text)
    assert result == ["Response B", "Response A"]


def test_parse_ranking_from_text_empty():
    """Test parsing empty text."""
    result = parse_ranking_from_text("")
    assert result == []


def test_calculate_aggregate_rankings():
    """Test aggregate ranking calculation."""
    stage2_results = [
        {
            "model": "model1",
            "ranking": "FINAL RANKING:\n1. Response A\n2. Response B",
            "parsed_ranking": ["Response A", "Response B"],
        },
        {
            "model": "model2",
            "ranking": "FINAL RANKING:\n1. Response B\n2. Response A",
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
            "ranking": "FINAL RANKING:\n1. Response A\n2. Response B\n3. Response C",
            "parsed_ranking": ["Response A", "Response B", "Response C"],
        },
        {
            "model": "model2",
            "ranking": "FINAL RANKING:\n1. Response A\n2. Response C\n3. Response B",
            "parsed_ranking": ["Response A", "Response C", "Response B"],
        },
        {
            "model": "model3",
            "ranking": "FINAL RANKING:\n1. Response B\n2. Response A\n3. Response C",
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
            "ranking": "FINAL RANKING:\n1. Response A\n2. Response B",
            "parsed_ranking": ["Response A", "Response B"],
        },
        {
            "model": "model2",
            "ranking": "FINAL RANKING:\n1. Response B\n2. Response A",
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
