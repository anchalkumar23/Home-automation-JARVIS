# Business Intelligence — Increment 4a: Real-Time Market Data

## Context

Section 15 of `AGENT.md` (Business Intelligence) spans several distinct capabilities: financial/market data, company/competitor research, business reports, and sales/customer analytics. Per the confirmed decomposition, this is the first sub-increment, focused narrowly on real-time market data — the piece most directly requested by the client (who explicitly listed stocks, Forex, and trading tools among his tools) and the only piece that needs no additional information from him.

- **4a (this increment)**: Real-time stock/forex/crypto price quotes.
- **Later**: Company/competitor research (mostly reuses `web_search`/`read_url_content`, already built). Business reports (synthesis, once data + research exist).
- **Blocked, deferred**: Sales insights / customer analytics — no CRM or sales data source is connected yet; this needs client input on what system (if any) holds that data before it can be designed.

Prior-art research: Alpha Vantage (which the client also listed by name) was considered first, but its free tier was cut to 25 requests/day — too thin for a personal assistant checked throughout the day. **Finnhub** was chosen instead: 60 free calls/minute, no card required, covering real-time US stocks, forex, and crypto under one API key.

## Scope

**In scope:**
1. A new `get_market_quote(symbol)` tool — one tool covering stocks, forex, and crypto, since Finnhub's `/quote` endpoint is generic across asset classes based on symbol format.
2. A new `finnhub_api_key` setting, following the existing pattern (`tavily_api_key`, `youtube_api_key`).
3. A system prompt rule explaining the per-asset-class symbol format (plain ticker for stocks, `EXCHANGE:BASE_QUOTE` for forex, `EXCHANGE:PAIR` for crypto), since this isn't obvious and the model needs to construct the right symbol from a natural-language request.
4. Detection of Finnhub's all-zero-fields response for invalid/unsupported symbols, converted to a clear "couldn't find a quote" message rather than being reported as a real (zero) price.

**Out of scope:**
- Any saved watchlist — confirmed as on-demand only for this increment, matching the precedent set by news monitoring (3c).
- Company/competitor research, business reports, sales/customer analytics — later sub-increments or blocked pending client input.
- A dedicated frontend UI card — the reply is plain text/spoken, same as `get_time`/`get_system_status`.

## Design

### Tool: `get_market_quote`

`backend/app/ai/tools.py` gains `_tool_get_market_quote(args, user_id, store)`, calling `GET https://finnhub.io/api/v1/quote?symbol=<symbol>&token=<finnhub_api_key>`. The response-shaping logic is pulled into a pure function, `_parse_finnhub_quote(data, symbol) -> dict`, mapping Finnhub's fields (`c` current price, `d` change, `dp` percent change, `h` high, `l` low, `o` open, `pc` previous close) into a clean shape: `{symbol, price, change, change_percent, high, low, open, previous_close}`.

**Known wrinkle, to be confirmed during manual testing**: Finnhub's client libraries route forex (`/forex/candle`, `/forex/rates`) and crypto (`/crypto/candle`) pricing through separate endpoints in some contexts, but the generic `/quote` endpoint is documented as covering stocks, forex, and crypto uniformly by symbol format. If forex/crypto symbols don't return real data through `/quote` on the free tier, that will surface clearly during Task 3's manual verification (an all-zero or error response), and can be addressed as a direct bugfix per this project's standing "fix it directly, no full redesign" convention for issues found during testing — not designed around speculatively here.

**Invalid-symbol handling**: Finnhub returns all-zero fields (`c: 0, d: 0, ...`) for a symbol it doesn't recognize, rather than an HTTP error. `_parse_finnhub_quote` detects this (all of `c`, `h`, `l`, `o`, `pc` being exactly `0`) and the tool returns `{"symbol": symbol, "error": "I couldn't find a quote for that symbol."}` instead of reporting fabricated zero prices as real.

### Tool definition

```
name: get_market_quote
description: "Get a real-time price quote for a stock, forex pair, or cryptocurrency. For stocks, use the plain ticker (e.g. AAPL). For forex, use EXCHANGE:BASE_QUOTE format (e.g. OANDA:EUR_USD). For crypto, use EXCHANGE:PAIR format (e.g. BINANCE:BTCUSDT). If unsure of the exact exchange, default to OANDA for forex and BINANCE for crypto."
parameters: { symbol: string, required }
```

### System prompt

A new numbered rule instructs the model on symbol-format construction per asset class (mirroring the tool description above), since translating "what's Bitcoin at" into `BINANCE:BTCUSDT` isn't something the model would reliably infer without explicit guidance.

### Configuration

`backend/app/config.py` gains `finnhub_api_key: str`, read from `FINNHUB_API_KEY`, following the exact pattern already used for `tavily_api_key`/`youtube_api_key`. `.env`/`.env.example` gain the corresponding entry. Getting the actual key is a manual, free, one-time signup step at finnhub.io (no card required), performed by the user.

### Testing

`_parse_finnhub_quote(data, symbol)` gets unit tests: normal quote extraction, and the all-zero-fields invalid-symbol case returning a clear error instead of fabricated data. The actual network call is not unit-tested, consistent with every other tool in this codebase.

### Manual verification plan

1. Ask "What's Apple stock trading at?" — confirm a real, current price with change/percent spoken naturally.
2. Ask about a forex pair (e.g. "what's the EUR to USD rate") and a crypto price (e.g. "what's Bitcoin trading at") — confirm real data comes back. If either doesn't work through the free-tier `/quote` endpoint, note the actual failure mode so it can be fixed directly.
3. Ask for an invalid/nonsense symbol — confirm a clear "couldn't find that" message, not a fabricated zero price.
4. Temporarily remove/break `FINNHUB_API_KEY` — confirm a clear "not configured" message, not a crash.

## Explicitly deferred to future increments

- Saved watchlist / proactive price alerts.
- Company/competitor research.
- Business reports.
- Sales insights / customer analytics (blocked pending client input on data source).
