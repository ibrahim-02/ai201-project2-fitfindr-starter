# FitFindr

FitFindr is an AI-powered secondhand shopping assistant. You describe what you're looking for in plain English — it finds a matching listing, suggests how to style it with your existing wardrobe, and generates a shareable outfit caption, all in one automated flow.

---

## Setup

```bash
pip install -r requirements.txt
pip install gradio groq
```

Create a `.env` file in the project root with your Groq API key (get a free key at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

**Run the app:**
```bash
python app.py
```
Then open `http://localhost:7860` in your browser.

**Run the CLI test (both paths):**
```bash
python agent.py
```

**Run the test suite:**
```bash
pytest tests/test_tools.py -v
```

---

## Project Structure

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading data
├── tools.py                   # The three tool implementations
├── agent.py                   # Planning loop — orchestrates the tools
├── app.py                     # Gradio web interface
├── tests/
│   └── test_tools.py          # Pytest test suite (13 tests)
└── planning.md                # Design spec and architecture diagram
```

---

## The Three Tools

All tools are implemented in `tools.py` as standalone functions that can be called and tested independently.

---

### Tool 1: `search_listings`

```python
search_listings(description: str, size: str | None, max_price: float | None) -> list[dict]
```

**What it does:** Searches `data/listings.json` for items matching the user's request. Filters by price ceiling and size, then scores each remaining listing by keyword overlap with the description. Returns results sorted by relevance score, highest first.

**Input parameters:**
| Parameter | Type | Description |
|---|---|---|
| `description` | `str` | Natural language keywords (e.g. `"vintage graphic tee"`) |
| `size` | `str \| None` | Size string to filter by (e.g. `"M"`, `"W30"`). Case-insensitive substring match — `"M"` matches `"S/M"` and `"M/L"`. Pass `None` to skip. |
| `max_price` | `float \| None` | Maximum price inclusive (e.g. `30.0`). Pass `None` to skip. |

**Return value:** A list of matching listing dicts, each containing:
- `id` (str) — unique listing identifier
- `title` (str) — listing name
- `description` (str) — seller's description
- `category` (str) — one of: `tops`, `bottoms`, `outerwear`, `shoes`, `accessories`
- `style_tags` (list[str]) — e.g. `["vintage", "grunge", "streetwear"]`
- `size` (str) — e.g. `"M"`, `"W30"`, `"US 8"`
- `condition` (str) — `excellent`, `good`, or `fair`
- `price` (float) — listing price in USD
- `colors` (list[str]) — e.g. `["black", "charcoal"]`
- `brand` (str | None) — brand name or `None`
- `platform` (str) — `depop`, `thredUp`, or `poshmark`

Returns an empty list if nothing matches — never raises an exception.

---

### Tool 2: `suggest_outfit`

```python
suggest_outfit(new_item: dict, wardrobe: dict) -> str
```

**What it does:** Given the thrifted item the user is considering and their existing wardrobe, calls the Groq LLM (`llama-3.3-70b-versatile`) to suggest one to two complete outfit combinations. Each suggestion names specific wardrobe pieces and explains the styling rationale — color harmony, silhouette balance, and aesthetic.

**Input parameters:**
| Parameter | Type | Description |
|---|---|---|
| `new_item` | `dict` | A listing dict returned by `search_listings` |
| `wardrobe` | `dict` | A wardrobe dict with an `"items"` key containing a list of wardrobe item dicts. May be empty. |

**Return value:** A non-empty string with one or two outfit suggestions. If the wardrobe is empty, returns general styling advice for the item (what it pairs well with, what aesthetic it suits) instead of crashing or returning an empty string.

---

### Tool 3: `create_fit_card`

```python
create_fit_card(outfit: str, new_item: dict) -> str
```

**What it does:** Generates a 2–4 sentence Instagram/TikTok caption in a casual Gen Z voice. Calls the Groq LLM at temperature 0.9 so captions vary across runs.

**Input parameters:**
| Parameter | Type | Description |
|---|---|---|
| `outfit` | `str` | The outfit suggestion string returned by `suggest_outfit` |
| `new_item` | `dict` | The listing dict for the thrifted item — used for the item name, price, and platform |

**Return value:** A 2–4 sentence string that mentions the item name, price, and resale platform exactly once each, and captures the outfit's specific vibe (e.g. grunge, cottagecore, Y2K streetwear). If `outfit` is empty or whitespace-only, returns a descriptive error string instead of crashing.

---

## Multi-Step Workflow

A complete interaction starts with a natural language query and ends with a fit card, passing through all three tools.

**Example query:** `"vintage graphic tee under $30"`

**Step 1 — Parse the query** (`agent.py`)
The planning loop uses regex to extract `description = "vintage graphic tee"`, `max_price = 30.0`, and `size = None` from the raw query. No LLM call needed here.

**Step 2 — Search for listings** (`search_listings`)
Called with `description="vintage graphic tee"`, `size=None`, `max_price=30.0`. Scores each listing in the dataset by keyword overlap and returns matches sorted by relevance. The agent takes the top result — in this case the *Y2K Baby Tee — Butterfly Print* at $18 on Depop.

**Step 3 — Suggest an outfit** (`suggest_outfit`)
Called with the listing dict from Step 2 and the user's wardrobe. The LLM is told which specific wardrobe pieces exist and asked to build outfit combinations around the new item. Returns a string like: *"Pair the Y2K Baby Tee with your Baggy straight-leg jeans and Chunky white sneakers for a casual Y2K look..."*

**Step 4 — Generate the fit card** (`create_fit_card`)
Called with the outfit string from Step 3 and the same listing dict from Step 2. The LLM writes a shareable caption: *"Just scored this Y2K Baby Tee for $18 on Depop and I'm obsessed..."*

**Final output (Gradio UI — three panels):**
- Panel 1: Listing details (title, price, platform, size, condition, colors, style)
- Panel 2: Outfit suggestion with named wardrobe pieces and styling rationale
- Panel 3: Fit card caption ready to post

---

## State Management

All state is stored in a single `session` dict initialized at the start of each `run_agent()` call. No tool writes directly to the session — the planning loop reads each tool's return value and writes it into the session before passing it to the next tool.

```
run_agent(query, wardrobe)
    │
    ├─ session["parsed"]           ← query parsed into {description, size, max_price}
    │
    ├─ search_listings(...)
    │       └─ session["search_results"]    ← list of matching listing dicts
    │       └─ session["selected_item"]     ← session["search_results"][0]
    │
    ├─ suggest_outfit(session["selected_item"], session["wardrobe"])
    │       └─ session["outfit_suggestion"] ← LLM response string
    │
    ├─ create_fit_card(session["outfit_suggestion"], session["selected_item"])
    │       └─ session["fit_card"]          ← caption string
    │
    └─ return session
```

**The item never re-enters manually.** `selected_item` is stored once after `search_listings` and read directly by both `suggest_outfit` and `create_fit_card` — the user never types it again.

**The outfit never re-enters manually.** `outfit_suggestion` is stored after `suggest_outfit` returns and passed directly into `create_fit_card`.

**Session fields and their lifecycle:**

| Field | Written by | Read by |
|---|---|---|
| `session["query"]` | `run_agent()` init | Planning loop (parse step) |
| `session["parsed"]` | Planning loop | `search_listings` |
| `session["search_results"]` | Planning loop (after `search_listings`) | Planning loop (item selection) |
| `session["selected_item"]` | Planning loop | `suggest_outfit`, `create_fit_card` |
| `session["wardrobe"]` | `run_agent()` init | `suggest_outfit` |
| `session["outfit_suggestion"]` | Planning loop (after `suggest_outfit`) | `create_fit_card` |
| `session["fit_card"]` | Planning loop (after `create_fit_card`) | Final output |
| `session["error"]` | Planning loop on failure | Early exit check |

---

## Planning Loop Adaptiveness

The planning loop in `agent.py` does not call all three tools unconditionally. Every tool call is gated on the result of the previous step.

### Conditional logic — what the agent checks and what it decides

**After parsing the query:**
The loop inspects `session["parsed"]` for `description`, `size`, and `max_price`. It runs two filter attempts:
- Attempt 1: `search_listings(description, size, max_price)` — all filters applied
- Attempt 2 (only if attempt 1 returned empty): `search_listings(description, None, max_price)` — size dropped, price kept

The price cap is a hard constraint and is **never dropped**. If a user says "under $10", the agent will never return a $15 item silently.

**After `search_listings`:**
The loop checks `len(session["search_results"]) == 0`.
- If **empty** → the agent sets `session["error"]` with a specific message and calls `return session` immediately. `suggest_outfit` and `create_fit_card` are never reached — no Groq API calls are made.
- If **non-empty** → the agent selects `session["search_results"][0]` as `session["selected_item"]` and proceeds to `suggest_outfit`.

**After `suggest_outfit`:**
The loop checks that `session["outfit_suggestion"]` is a non-empty string before passing it into `create_fit_card`. If it is empty (which `suggest_outfit` is designed to prevent), `create_fit_card` returns an error string rather than making an LLM call with empty input.

### What happens specifically when `search_listings` returns no results

The agent does not proceed to the LLM tools. Instead it:

1. Builds a message describing exactly what was searched: the description keywords, and which filters (size, price) were active during each attempt.
2. Sets `session["error"]` to that message — e.g.: *"No listings found for 'designer ballgown'. We tried: size xxs under $5, then any size under $5 — still nothing. What to try: drop the size filter; or raise your budget above $5; or use broader keywords."*
3. Returns the session immediately with `session["selected_item"] = None`, `session["outfit_suggestion"] = None`, and `session["fit_card"] = None`.

The Gradio UI surfaces `session["error"]` in the first panel and leaves the other two panels empty.

### Two distinct execution paths — verified in source and demo

**Happy path** — query matches listings:
```
parse query → search_listings → select top result → suggest_outfit → create_fit_card → return session
(all 3 tools called, 2 Groq API calls made)
```

**No-results path** — query matches nothing:
```
parse query → search_listings → empty results → set session["error"] → return early
(only search_listings called, 0 Groq API calls made)
```

To reproduce both paths from the CLI:
```bash
# Happy path
python -c "from agent import run_agent; from utils.data_loader import get_example_wardrobe; s = run_agent('vintage graphic tee under 30', get_example_wardrobe()); print('error:', s['error']); print('item:', s['selected_item']['title'] if s['selected_item'] else None)"

# No-results path — impossible price constraint
python -c "from agent import run_agent; from utils.data_loader import get_example_wardrobe; s = run_agent('designer ballgown size XXS under 5', get_example_wardrobe()); print('error:', s['error']); print('item:', s['selected_item'])"
```

---

## Error Handling

Each tool has a specific failure mode that is handled explicitly — no tool crashes or returns silently empty output.

---

### Tool 1 — `search_listings`: no listings match the query

**Failure mode:** The user's query (after up to two filter attempts) returns an empty list — nothing in the 40-item dataset matches the description at the given price.

**What the agent does:**
- Stops the loop immediately at the `search_listings` step
- Never calls `suggest_outfit` or `create_fit_card` (no Groq API calls are made)
- Sets `session["error"]` to a message that names exactly what was searched, which filters were tried, and what the user can change

**Actual error message produced:**
```
No listings found for "designer ballgown". We tried: size xxs under $5,
then any size under $5 — still nothing.
What to try: drop the size filter — nothing in size xxs matched;
or raise your budget above $5; or use broader keywords
(e.g. 'jacket' instead of 'designer blazer').
```

**To trigger this deliberately:**
```bash
python -c "from agent import run_agent; from utils.data_loader import get_example_wardrobe; s = run_agent('designer ballgown size XXS under 5', get_example_wardrobe()); print(s['error']); print('fit_card:', s['fit_card'])"
```

---

### Tool 2 — `suggest_outfit`: wardrobe is empty

**Failure mode:** The user has no wardrobe items — `wardrobe["items"]` is an empty list. There are no named pieces to build outfit combinations from.

**What the agent does:**
- Does not crash or return an empty string
- Detects the empty list before calling the LLM
- Sends a different prompt: asks the LLM for general styling advice (what aesthetic the item suits, what types of pieces pair well) rather than specific wardrobe combinations
- Returns a non-empty string in all cases

**Actual response produced (empty wardrobe):**
```
This graphic tee suits a grunge aesthetic. Pair it with:
1. High-waisted, distressed denim jeans and black combat boots for a classic grunge look.
2. A flowy, neutral-colored skirt and ankle boots for a grunge-lite take.
```

**To trigger this deliberately:**
```bash
python -c "from tools import suggest_outfit; from utils.data_loader import get_empty_wardrobe; item = {'id':'lst_006','title':'Graphic Tee','description':'Boxy tee','category':'tops','style_tags':['vintage','grunge'],'size':'L','condition':'good','price':24.0,'colors':['black'],'brand':None,'platform':'depop'}; print(suggest_outfit(item, get_empty_wardrobe()))"
```

---

### Tool 3 — `create_fit_card`: outfit string is empty or missing

**Failure mode:** The `outfit` argument passed in is an empty string or whitespace-only — no content to write a caption from.

**What the agent does:**
- Guards at the top of the function before making any LLM call
- Returns a descriptive error string immediately
- Never crashes, never returns an empty string

**Actual response produced:**
```
Fit card unavailable: outfit suggestion is missing. Please try again.
```

**To trigger this deliberately:**
```bash
python -c "from tools import create_fit_card; item = {'title':'Graphic Tee','price':24.0,'platform':'depop'}; print(create_fit_card('', item)); print(create_fit_card('   ', item))"
```

---

## AI Usage Transparency

### Instance 1 — Implementing `search_listings` (Tool 1)

**What I directed the AI to do:** I gave Claude the Tool 1 spec block from `planning.md` — the function signature, the three input parameters with types, the return value description (a list of listing dicts sorted by relevance score), and the failure mode (return `[]`, never raise). I asked it to implement `search_listings()` in `tools.py` using `load_listings()` from `utils/data_loader.py` and a keyword overlap scoring approach.

**What I reviewed:** I checked that the generated code (1) filtered by both `max_price` and `size` before scoring, (2) used a blob of `title + description + style_tags + colors + category` for keyword matching — not just the title, (3) dropped zero-score listings before sorting, and (4) returned `[]` on no match without raising an exception.

**What I verified:** I ran three manual tests: `search_listings("vintage graphic tee", max_price=30)` returned results; `search_listings("jacket", size="M", max_price=10)` returned only items priced ≤ $10; `search_listings("designer ballgown", size="XXS", max_price=5)` returned `[]`. All passed.

---

### Instance 2 — Implementing the planning loop in `agent.py`

**What I directed the AI to do:** I gave Claude the Planning Loop section, State Management section, and architecture diagram from `planning.md`, along with the session dict structure already in the `agent.py` stub. I asked it to implement `run_agent()` following the seven numbered TODO steps in the file — specifically: parse the query, call `search_listings`, branch on empty results, select the top item, call `suggest_outfit`, call `create_fit_card`, return the session.

**What I reviewed:** I checked that the generated loop (1) did not call `suggest_outfit` unconditionally — it had to branch on `len(results) == 0`, (2) stored every return value into the correct session field before passing it to the next tool, (3) set `session["error"]` and returned early on no results.

**What I overrode:** The initial retry logic dropped the price filter on the third attempt — so a query for "vintage tee under $10" silently returned an $18 item with `error: None`. I caught this when testing with `"vintage graphic tee under 10"` and the output showed `item: Y2K Baby Tee` at $18. I overrode the retry logic to treat price as a hard constraint that is never relaxed — only the size filter is dropped on retry. I also revised the error message to name the specific filters tried and give three actionable suggestions rather than a generic "no results" message.

---

### Instance 3 — Writing the pytest test suite (`tests/test_tools.py`)

**What I directed the AI to do:** I gave Claude the three tool specs and asked it to write at least one pytest test per failure mode: `search_listings` returning `[]` on an impossible query, `suggest_outfit` not crashing on an empty wardrobe, and `create_fit_card` returning an error string (not `""` or a crash) on an empty outfit input. I asked it to mock the Groq client so no real API calls were made in the test suite.

**What I reviewed:** I checked that (1) the `suggest_outfit` empty-wardrobe test verified `len(result.strip()) > 0` — not just `isinstance(result, str)` — so an empty string would still fail the test, (2) the `create_fit_card` temperature test asserted `temperature >= 0.8` to enforce variety in captions, (3) all mocks patched `tools._get_groq_client` so the patch would still work if the client initialization logic changed.

**What I verified:** Ran `pytest tests/test_tools.py -v` — 13/13 passed with no real API calls made.

---

## Dataset

`data/listings.json` — 40 mock secondhand listings across 5 categories (tops, bottoms, outerwear, shoes, accessories) and styles including vintage, Y2K, grunge, cottagecore, streetwear, and more. Price range: $12–$75.

`data/wardrobe_schema.json` — defines the wardrobe format. Includes an `example_wardrobe` (10 items) and an `empty_wardrobe` template for testing both paths.
