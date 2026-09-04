# Business Intelligence — Increment 4a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real-time stock/forex/crypto price quotes via a single `get_market_quote` tool, the first sub-increment of Business Intelligence (§15).

**Architecture:** `_tool_get_market_quote` calls Finnhub's `/quote` endpoint (generic across asset classes by symbol format), with the response-shaping logic in a pure function `_parse_finnhub_quote(data, symbol)` that also detects Finnhub's all-zero-fields response for invalid symbols and converts it to a clear error.

**Tech Stack:** FastAPI, stdlib `urllib`, pytest. No new dependencies.

**Note on git:** the user handles all git init/commit/push themselves. No task in this plan runs a git command — each ends with a test/manual-verification step instead.

---

### Task 1: Finnhub signup and configuration

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/.env`
- Modify: `backend/.env.example`
- Modify: `backend/tests/test_google_auth.py:6-23` (`_fake_settings`)

- [ ] **Step 1: Manual signup (done by the user)**

Go to `https://finnhub.io`, create a free account (no card required). Copy the API key from the dashboard.

- [ ] **Step 2: Add `finnhub_api_key` to `Settings`**

Modify `backend/app/config.py`, replacing the `Settings` dataclass:
```python
@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    allowed_origins: list[str]
    provider: str
    openai_api_key: str
    openai_model: str
    groq_api_key: str
    groq_model: str
    groq_whisper_model: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    tavily_api_key: str
    youtube_api_key: str
    finnhub_api_key: str
    database_path: Path
```

- [ ] **Step 3: Populate it in `get_settings`**

Modify `backend/app/config.py`, replacing the `get_settings` function's `return Settings(...)` call:
```python
    return Settings(
        host=os.getenv("JARVIS_HOST", "127.0.0.1"),
        port=int(os.getenv("JARVIS_PORT", "8000")),
        allowed_origins=parse_csv(origins),
        provider=os.getenv("JARVIS_PROVIDER", "auto").lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        groq_whisper_model=os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        google_redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/api/gmail/callback"),
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
        finnhub_api_key=os.getenv("FINNHUB_API_KEY", ""),
        database_path=DATA_DIR / "jarvis.db",
    )
```

- [ ] **Step 4: Add the env variable**

Modify `backend/.env`, appending after the existing `YOUTUBE_API_KEY=...` line:
```

# Finnhub market data — see Task 1 for setup steps
FINNHUB_API_KEY=
```
Fill in `FINNHUB_API_KEY` with the key from Step 1.

Modify `backend/.env.example`, appending the same block with `FINNHUB_API_KEY` left blank.

- [ ] **Step 5: Fix `test_google_auth.py`'s fake settings**

`Settings` is a dataclass with all-required fields, so adding `finnhub_api_key` breaks any test that constructs one directly unless it's updated too. Modify `backend/tests/test_google_auth.py`, replacing `_fake_settings` (current lines 6-23):
```python
def _fake_settings() -> Settings:
    return Settings(
        host="127.0.0.1",
        port=8000,
        allowed_origins=[],
        provider="auto",
        openai_api_key="",
        openai_model="",
        groq_api_key="",
        groq_model="",
        groq_whisper_model="",
        google_client_id="test-client-id",
        google_client_secret="test-secret",
        google_redirect_uri="http://127.0.0.1:8000/api/gmail/callback",
        tavily_api_key="",
        youtube_api_key="",
        finnhub_api_key="",
        database_path=Path("unused.db"),
    )
```

- [ ] **Step 6: Verify settings load and tests pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
python -c "from app.config import get_settings; s = get_settings(); print(bool(s.finnhub_api_key))"
python -m pytest tests/ -v
```
Expected: first command prints `True` (assuming Step 4's key was filled in); second command shows 43 passed, no regressions.

---

### Task 2: `_parse_finnhub_quote` and `get_market_quote` tool (TDD)

**Files:**
- Modify: `backend/tests/test_tools.py` (append tests)
- Modify: `backend/app/ai/tools.py` (add `_parse_finnhub_quote`, `_tool_get_market_quote`, `TOOL_DEFINITIONS` entry, `TOOL_REGISTRY` entry)

- [ ] **Step 1: Write the failing tests**

Modify `backend/tests/test_tools.py`, appending to the end of the file:
```python


def test_parse_finnhub_quote_extracts_price_fields():
    from app.ai.tools import _parse_finnhub_quote

    data = {"c": 227.5, "d": 1.25, "dp": 0.55, "h": 228.9, "l": 225.1, "o": 226.0, "pc": 226.25}

    result = _parse_finnhub_quote(data, "AAPL")

    assert result == {
        "symbol": "AAPL",
        "price": 227.5,
        "change": 1.25,
        "change_percent": 0.55,
        "high": 228.9,
        "low": 225.1,
        "open": 226.0,
        "previous_close": 226.25,
    }


def test_parse_finnhub_quote_detects_all_zero_invalid_symbol():
    from app.ai.tools import _parse_finnhub_quote

    data = {"c": 0, "d": 0, "dp": 0, "h": 0, "l": 0, "o": 0, "pc": 0}

    result = _parse_finnhub_quote(data, "NOTREAL")

    assert result == {"symbol": "NOTREAL", "error": "I couldn't find a quote for that symbol."}


def test_parse_finnhub_quote_handles_missing_fields():
    from app.ai.tools import _parse_finnhub_quote

    result = _parse_finnhub_quote({}, "AAPL")

    assert result == {"symbol": "AAPL", "error": "I couldn't find a quote for that symbol."}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_tools.py -v
```
Expected: `ImportError: cannot import name '_parse_finnhub_quote' from 'app.ai.tools'` on the 3 new tests.

- [ ] **Step 3: Add `_parse_finnhub_quote` and `_tool_get_market_quote`**

Modify `backend/app/ai/tools.py`, inserting right after `_tool_search_papers` ends (current line 723, `return {"query": query, "answer": "", "results": _parse_semantic_scholar_results(data), "message": ""}`) and before `_tool_play_music` begins:
```python
def _parse_finnhub_quote(data: dict[str, Any], symbol: str) -> dict[str, Any]:
    current, high, low, open_price, previous_close = (
        data.get("c"),
        data.get("h"),
        data.get("l"),
        data.get("o"),
        data.get("pc"),
    )
    if not any([current, high, low, open_price, previous_close]):
        return {"symbol": symbol, "error": "I couldn't find a quote for that symbol."}

    return {
        "symbol": symbol,
        "price": current,
        "change": data.get("d"),
        "change_percent": data.get("dp"),
        "high": high,
        "low": low,
        "open": open_price,
        "previous_close": previous_close,
    }


def _tool_get_market_quote(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    symbol = str(args.get("symbol", "")).strip()
    if not symbol:
        raise ValueError("A symbol is required.")

    settings = get_settings()
    if not settings.finnhub_api_key:
        return {"symbol": symbol, "error": "Market data isn't configured — a Finnhub API key is needed."}

    params = urllib.parse.urlencode({"symbol": symbol, "token": settings.finnhub_api_key})
    request = urllib.request.Request(f"https://finnhub.io/api/v1/quote?{params}")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {"symbol": symbol, "error": f"Market quote failed: {exc}"}

    return _parse_finnhub_quote(data, symbol)
```

Note: `_parse_finnhub_quote` treats it as an invalid symbol only when **all five** price fields (`c`, `h`, `l`, `o`, `pc`) are falsy/zero at once — matching Finnhub's actual behavior of returning all-zero fields for unrecognized symbols. A real quote might occasionally have one field at exactly `0` (e.g. an illiquid symbol), but never all five simultaneously, so `not any([...])` is the correct check — `not all([...])` would be a bug, since it would misfire on a legitimate quote where just one field happens to be zero.

- [ ] **Step 4: Add the `TOOL_DEFINITIONS` entry**

Modify `backend/app/ai/tools.py`, inserting a new entry immediately after the `get_news` entry closes (current lines 173-185, ending `},\n    },`) and before the `search_patents` entry begins:
```python
    {
        "type": "function",
        "function": {
            "name": "get_market_quote",
            "description": "Get a real-time price quote for a stock, forex pair, or cryptocurrency. For stocks, use the plain ticker (e.g. AAPL). For forex, use EXCHANGE:BASE_QUOTE format (e.g. OANDA:EUR_USD). For crypto, use EXCHANGE:PAIR format (e.g. BINANCE:BTCUSDT). If unsure of the exact exchange, default to OANDA for forex and BINANCE for crypto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "The ticker or exchange-formatted symbol to quote."}
                },
                "required": ["symbol"],
            },
        },
    },
```

- [ ] **Step 5: Register the tool**

Modify `backend/app/ai/tools.py`, adding a line to `TOOL_REGISTRY` right after `"get_news": _tool_get_news,`:
```python
    "get_market_quote": _tool_get_market_quote,
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 46 passed (43 from before + 3 new).

---

### Task 3: System prompt

**Files:**
- Modify: `backend/app/ai/provider.py:81` (`SYSTEM_PROMPT` tool bullet)
- Modify: `backend/app/ai/provider.py:113` (append rule 19)

- [ ] **Step 1: Add the tool bullet**

Modify `backend/app/ai/provider.py`, inserting a new line right after the `get_news` bullet (current line 81):
```python
• get_market_quote — Get a real-time price quote for a stock, forex pair, or cryptocurrency.
```

- [ ] **Step 2: Add rule 19**

Modify `backend/app/ai/provider.py`, appending a new rule 19 right after rule 18 and before the closing `"""`:
```python
19. For get_market_quote, build the symbol correctly for the asset class: plain ticker for stocks (AAPL), EXCHANGE:BASE_QUOTE for forex (OANDA:EUR_USD), EXCHANGE:PAIR for crypto (BINANCE:BTCUSDT). If the tool result has an error, say so plainly rather than making up a price.
"""
```

- [ ] **Step 3: Run the full test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 46 passed, no regressions.

---

### Task 4: End-to-end manual verification

**Files:** None (verification only).

- [ ] **Step 1: Restart the backend**

Run (PowerShell):
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
  $procId = $_
  Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'C:\Anchal\Fiverr\Ultimate JARVIS\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Start-Sleep -Seconds 4
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing | Select-Object -ExpandProperty Content
```
Expected: `{"status":"online","service":"jarvis-backend"}`. Ensure the frontend (`npm run dev`) is running too.

- [ ] **Step 2: Stock quote**

Ask "What's Apple stock trading at?" Expected: a real, current price with change/percent spoken naturally, no bullets or lists.

- [ ] **Step 3: Forex and crypto**

Ask "What's the EUR to USD rate?" and "What's Bitcoin trading at?" Expected: real data comes back. If either returns an error or clearly wrong data (e.g. the all-zero "couldn't find a quote" message when the symbol should be valid), note the exact request/response so it can be diagnosed and fixed directly — this is the "known wrinkle" flagged in the spec about Finnhub's free-tier `/quote` endpoint coverage for forex/crypto.

- [ ] **Step 4: Invalid symbol**

Ask for a nonsense symbol (e.g. "what's XYZQQQ trading at"). Expected: a clear "couldn't find that" message, not a fabricated zero price.

- [ ] **Step 5: Verify the error path**

Temporarily blank out or break `FINNHUB_API_KEY` in `backend\.env`, restart the backend, and ask for a quote again. Expected: a clear "not configured" message, not a crash. Restore the real key and restart the backend afterward.

- [ ] **Step 6: Regression check**

Quickly re-verify `web_search` or `get_news` still works unaffected.

- [ ] **Step 7: Stop the backend**

Ctrl+C in its terminal (leave the frontend running if continuing to use it).

---

### Task 5: Update the testing guide

**Files:**
- Modify: `docs/testing-guide.md`

- [ ] **Step 1: Append a new section**

Modify `docs/testing-guide.md`, inserting a new "Market Data (Stocks/Forex/Crypto)" section right before the closing `## Adding a new feature?` section, following the same format as the existing sections (feature description sentence, then numbered steps), grounded in Task 4's manual verification steps above.

---

## Post-plan: what's explicitly not in this increment

- Saved watchlist / proactive price alerts.
- Company/competitor research.
- Business reports.
- Sales insights / customer analytics (blocked pending client input on data source).
