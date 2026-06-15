"""
tests/test_tools.py

Pytest tests for the three FitFindr tools.
LLM-dependent tools (suggest_outfit, create_fit_card) are tested with a
mocked Groq client so no real API calls are made.

Run with:
    pytest tests/test_tools.py -v
"""

from unittest.mock import MagicMock, patch

import pytest

from tools import create_fit_card, search_listings, suggest_outfit

# ── Shared fixtures ───────────────────────────────────────────────────────────

SAMPLE_ITEM = {
    "id": "lst_006",
    "title": "Graphic Tee — 2003 Tour Bootleg Style",
    "description": "Vintage-style bootleg tee. Boxy fit. 100% cotton.",
    "category": "tops",
    "style_tags": ["graphic tee", "vintage", "grunge", "streetwear", "band tee"],
    "size": "L",
    "condition": "good",
    "price": 24.0,
    "colors": ["black"],
    "brand": None,
    "platform": "depop",
}

SAMPLE_WARDROBE = {
    "items": [
        {
            "id": "w_001",
            "name": "Baggy straight-leg jeans, dark wash",
            "category": "bottoms",
            "colors": ["dark blue", "indigo"],
            "style_tags": ["denim", "streetwear", "baggy"],
            "notes": "High-waisted, sits above the hip",
        },
        {
            "id": "w_007",
            "name": "Chunky white sneakers",
            "category": "shoes",
            "colors": ["white"],
            "style_tags": ["sneakers", "chunky", "streetwear"],
            "notes": None,
        },
    ]
}

EMPTY_WARDROBE = {"items": []}


def _mock_groq(text: str):
    """Return a mock Groq client whose first completion returns `text`."""
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = text
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp
    return mock_client


# ── Tool 1: search_listings ───────────────────────────────────────────────────
# (user-supplied tests kept verbatim, plus failure-mode tests)

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # Failure mode: no listing matches → must return [] not raise
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter_case_insensitive():
    # "m" should match listings whose size contains "M", "S/M", "M/L", etc.
    results = search_listings("top", size="M", max_price=None)
    assert all("m" in item["size"].lower() for item in results)


def test_search_results_sorted_by_relevance():
    # The most relevant result should appear first
    results = search_listings("vintage graphic tee grunge streetwear")
    assert len(results) > 1
    # Confirm the top result contains at least one of the keywords
    top = results[0]
    blob = (top["title"] + " " + " ".join(top["style_tags"])).lower()
    assert any(kw in blob for kw in ["vintage", "graphic", "tee", "grunge", "streetwear"])


def test_search_never_raises_on_nonsense_query():
    results = search_listings("zzzznonexistentitem1234", size=None, max_price=None)
    assert isinstance(results, list)


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

@patch("tools._get_groq_client")
def test_suggest_outfit_with_wardrobe_returns_nonempty_string(mock_get_client):
    mock_get_client.return_value = _mock_groq(
        "Pair the graphic tee with your baggy jeans and chunky sneakers for a classic streetwear look."
    )
    result = suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


@patch("tools._get_groq_client")
def test_suggest_outfit_empty_wardrobe_does_not_crash(mock_get_client):
    # Failure mode: wardrobe is empty → must return general styling advice, not crash
    mock_get_client.return_value = _mock_groq(
        "This tee works great with wide-leg trousers and platform sneakers for a 90s vibe."
    )
    result = suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


@patch("tools._get_groq_client")
def test_suggest_outfit_empty_wardrobe_calls_llm_with_general_prompt(mock_get_client):
    mock_client = _mock_groq("General styling advice here.")
    mock_get_client.return_value = mock_client

    suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)

    call_args = mock_client.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_msg = next(m["content"] for m in messages if m["role"] == "user")
    # Prompt should mention the empty-wardrobe path (general advice, not wardrobe items)
    assert "empty" in user_msg.lower() or "general" in user_msg.lower()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def test_create_fit_card_empty_outfit_returns_error_string():
    # Failure mode: outfit is empty → must return error string, not crash or return ""
    result = create_fit_card("", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_create_fit_card_whitespace_outfit_returns_error_string():
    # Failure mode: whitespace-only outfit string
    result = create_fit_card("   \n  ", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


@patch("tools._get_groq_client")
def test_create_fit_card_valid_input_returns_caption(mock_get_client):
    mock_get_client.return_value = _mock_groq(
        "thrifted this $24 graphic tee off depop and styled it with baggy jeans — "
        "full 90s grunge mode and I'm not sorry."
    )
    result = create_fit_card("Baggy jeans + chunky sneakers.", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


@patch("tools._get_groq_client")
def test_create_fit_card_uses_high_temperature(mock_get_client):
    mock_client = _mock_groq("some caption")
    mock_get_client.return_value = mock_client

    create_fit_card("Baggy jeans + chunky sneakers.", SAMPLE_ITEM)

    call_args = mock_client.chat.completions.create.call_args
    temperature = call_args.kwargs.get("temperature", call_args.args[0] if call_args.args else None)
    assert temperature is not None and temperature >= 0.8
