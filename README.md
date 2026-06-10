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
| **Problem** | Claude Code (Opus 4.6+) sends `thinking.type: "adaptive"`. DeepSeek only documents `"enabled"` and `"disabled"`. |
| **Fix** | Rewrite `"adaptive"` to `"enabled"`. Thinking depth is still controlled by `output_config.effort`. |

### 2. Strip `thinking.display`

| | |
|---|---|
| **Problem** | Anthropic Opus 4.7+ supports `thinking.display` (`"summarized"`, `"omitted"`). Not present in DeepSeek docs. |
| **Fix** | Remove `display` from the `thinking` object. If `thinking` becomes empty after stripping, remove it entirely. |

### 3. Resolve `thinking: {type: "disabled"}` conflicts

| | |
|---|---|
| **Problem** | DeepSeek rejects `thinking.type=disabled` in two scenarios: (a) when `reasoning_effort` is also set, (b) on models that don't support the `thinking` parameter at all — with a misleading 400 error mentioning `reasoning_effort` even when absent. |
| **Fix** | **Model-agnostic**: strip `thinking` entirely when its type is `"disabled"`. Also strip `reasoning_effort`. Handles edge cases: empty dict `{}`, non-standard values like `false` or `"disabled"` (string). |

### 4. Simplify `output_config`

| | |
|---|---|
| **Problem** | Claude Code sends Anthropic-specific `output_config` fields (`task_budget`, `format`). DeepSeek only supports `effort`. |
| **Fix** | Keep only `effort` inside `output_config`. If `output_config` becomes empty, remove it entirely. |

## Intentionally Passed Through

Per the [DeepSeek Anthropic API docs](https://api-docs.deepseek.com/zh-cn/guides/anthropic_api), these parameters are either fully supported or
silently ignored — we pass them through unchanged rather than stripping,
so that future DeepSeek support isn't blocked by the proxy:

| Parameter | Docs say | Behavior |
|---|---|---|
| `thinking.budget_tokens` | "is ignored" | Passed through, no error |
| `temperature` | "Fully Supported" (0.0–2.0) | Passed through |
| `top_p` | "Fully Supported" | Passed through |
| `top_k` | "Ignored" | Passed through, no error |

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
├── fixups.py       # 4-step fixup chain + utility functions
├── test_fixups.py  # unit tests
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
