"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # Filter by price and size
    candidates = []
    for item in listings:
        if max_price is not None and item["price"] > max_price:
            continue
        if size is not None and size.lower() not in item["size"].lower():
            continue
        candidates.append(item)

    # Score by keyword overlap against title, description, style_tags, colors, category
    keywords = [w for w in re.split(r"\W+", description.lower()) if w]

    def _score(item: dict) -> int:
        blob = " ".join([
            item["title"],
            item["description"],
            " ".join(item["style_tags"]),
            " ".join(item["colors"]),
            item["category"],
            item.get("brand") or "",
        ]).lower()
        return sum(1 for kw in keywords if kw in blob)

    scored = [(item, _score(item)) for item in candidates]
    scored = [(item, score) for item, score in scored if score > 0]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [item for item, _ in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    client = _get_groq_client()
    item_summary = (
        f"Item: {new_item['title']}\n"
        f"Category: {new_item['category']}\n"
        f"Style: {', '.join(new_item['style_tags'])}\n"
        f"Colors: {', '.join(new_item['colors'])}\n"
        f"Condition: {new_item['condition']} | Price: ${new_item['price']} | Platform: {new_item['platform']}"
    )

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        prompt = (
            f"A user is considering buying this secondhand item:\n{item_summary}\n\n"
            "Their wardrobe is empty. Give them 1–2 general outfit ideas: what types of "
            "pieces pair well with this item, what aesthetic it suits, and how to style it "
            "for that vibe. Be specific about silhouette, color, and style. Keep it concise."
        )
    else:
        wardrobe_text = "\n".join(
            f"- {w['name']} ({w['category']}, colors: {', '.join(w['colors'])}, "
            f"style: {', '.join(w['style_tags'])})"
            for w in wardrobe_items
        )
        prompt = (
            f"A user is considering buying this secondhand item:\n{item_summary}\n\n"
            f"Their current wardrobe contains:\n{wardrobe_text}\n\n"
            "Suggest 1–2 complete outfit combinations that pair the new item with specific "
            "named pieces from their wardrobe. For each outfit, explain the styling rationale "
            "(color harmony, silhouette balance, aesthetic). Only reference pieces listed above."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional personal stylist specializing in Gen Z streetwear, "
                    "Y2K, vintage, cottagecore, and grunge aesthetics. You help users style "
                    "secondhand finds with what they already own."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=400,
    )
    return response.choices[0].message.content.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Fit card unavailable: outfit suggestion is missing. Please try again."

    client = _get_groq_client()
    title = new_item.get("title", "this thrifted piece")
    price = new_item.get("price", "?")
    platform = new_item.get("platform", "a resale app")

    prompt = (
        f"Write a 2–4 sentence Instagram/TikTok caption for this thrift find.\n\n"
        f"Item: {title} — ${price} from {platform}\n"
        f"Outfit: {outfit}\n\n"
        "Rules:\n"
        "- Sound like a real Gen Z OOTD post, not a product description\n"
        "- Mention the item name, price, and platform exactly once each\n"
        "- Capture the specific vibe of the outfit (e.g., grunge, cottagecore, Y2K streetwear)\n"
        "- Keep it 2–4 sentences, casual and authentic\n"
        "- No hashtags"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You write short, authentic outfit captions for Gen Z thrift shoppers. "
                    "Your tone is casual, specific, and fun — like a real person's OOTD post."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.9,
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()
