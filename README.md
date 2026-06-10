# ccadaptor — Claude Code ↔ DeepSeek API Adapter

A transparent HTTP proxy that fixes incompatibilities between Claude Code's
Anthropic-format requests and DeepSeek's `/anthropic` endpoint.

DeepSeek's `/anthropic` endpoint **natively accepts Anthropic Messages API
format** — no full translation layer is needed. The proxy only strips or
rewrites the handful of parameters that DeepSeek doesn't support.

```
Claude Code ── Anthropic API ──► ccadaptor ──► api.deepseek.com/anthropic
             ◄── Anthropic API ──            ◄──
```

## Quick Start

### 1. Configure Claude Code

In `~/.claude/settings.json`:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:8089",
    "ANTHROPIC_AUTH_TOKEN": "sk-your-deepseek-api-key",
    "ANTHROPIC_MODEL": "deepseek-v4-pro[1m]"
  }
}
```

### 2. Start the proxy

```bash
python3 server.py
```

That's it. No pip install — stdlib only.

### 3. Verify

Check `~/.claude/settings.json` has the env vars above, then use Claude Code
normally. All API calls route through the proxy automatically.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `UPSTREAM_URL` | `https://api.deepseek.com/anthropic` | DeepSeek endpoint |
| `PROXY_PORT` | `8089` | Proxy listen port |
| `PROXY_HOST` | `127.0.0.1` | Proxy listen host |
| `CCADAPTOR_DEBUG` | `0` | Set to `1` for request logging |

Debug mode:
```bash
CCADAPTOR_DEBUG=1 python3 server.py
```
Logs go to stderr. Each request shows model, thinking, reasoning_effort, and
whether fixups were applied.

## Adaptation Strategy

All fixups are **request-body only** — responses, headers, API keys, and SSE
streams are passed through untouched. Fixups run in order; each fixup's output
is the next fixup's input.

### 1. `adaptive` → `enabled`

| | |
|---|---|
| **Problem** | Claude Code (Opus 4.6+) sends `thinking.type: "adaptive"`. DeepSeek only understands `"enabled"` and `"disabled"`. |
| **Fix** | Rewrite `"adaptive"` to `"enabled"`. Thinking depth is still controlled by `output_config.effort`. |

### 2. Strip `thinking.display`

| | |
|---|---|
| **Problem** | Anthropic Opus 4.7+ supports `thinking.display` (`"summarized"`, `"omitted"`). DeepSeek does not. |
| **Fix** | Remove `display` from the `thinking` object. If `thinking` becomes empty after stripping, remove it entirely. |

### 3. Strip `thinking.budget_tokens`

| | |
|---|---|
| **Problem** | `budget_tokens` is an Anthropic-specific field for controlling thinking token allocation. DeepSeek ignores it but may reject the request. |
| **Fix** | Remove `budget_tokens`. DeepSeek uses `output_config.effort` for depth control instead. Empty thinking dict → removed. |

### 4. Strip sampling params when thinking is active

| | |
|---|---|
| **Problem** | `temperature`, `top_p`, `top_k` are incompatible with thinking mode. Anthropic Opus 4.7+ rejects them with 400. |
| **Fix** | Remove these parameters when `thinking.type` is NOT `"disabled"` (i.e., thinking is active). |

### 5. Resolve `thinking: {type: "disabled"}` conflicts

| | |
|---|---|
| **Problem** | DeepSeek rejects `thinking.type=disabled` in two scenarios: (a) when `reasoning_effort` is also set (explicit conflict), (b) on models that don't support the `thinking` parameter at all — with a misleading 400 error mentioning `reasoning_effort` even when it's absent. |
| **Fix** | **Model-agnostic**: strip `thinking` entirely when its type is `"disabled"`. This is semantically equivalent to not sending thinking at all. Also strip `reasoning_effort` so it doesn't implicitly re-enable thinking. Also handles edge cases: empty dict `{}`, non-standard values like `false` or `"disabled"` (string). |

### 6. Simplify `output_config`

| | |
|---|---|
| **Problem** | Claude Code sends Anthropic-specific `output_config` fields (`task_budget`, `format`). DeepSeek only supports `effort`. |
| **Fix** | Keep only `effort` inside `output_config`. If `output_config` becomes empty, remove it entirely. |

## What Passes Through Unchanged

- API Key (`ANTHROPIC_AUTH_TOKEN` → `Authorization` header)
- All other HTTP headers
- SSE streaming responses
- Error responses (status codes, bodies)
- Non-JSON request bodies
- All model names (no model-name matching in fixup logic)

## Architecture

```
ccadaptor/
├── server.py       # HTTP proxy (ThreadingMixIn, stdlib only)
├── fixups.py       # 6 fixup functions + apply_all chain
├── test_fixups.py  # 43 unit tests
└── README.md
```

Zero external dependencies — `json`, `http.server`, `urllib`, `socketserver`,
`typing`.

## Testing

```bash
python3 -m unittest test_fixups.py -v
```

## License

MIT
