# ccadaptor — Claude Code ↔ DeepSeek API Adapter

A lightweight HTTP proxy that translates between the Anthropic Messages API (which Claude Code CLI speaks) and the DeepSeek/OpenAI Chat Completions API (which DeepSeek expects).

## Problem

Claude Code spawns sub-agents (Agent, WebSearch, WebFetch, Explore tools) by sending API requests with both `thinking: {type: "disabled"}` and `reasoning_effort`. DeepSeek rejects this combination:

```
400: thinking options type cannot be disabled when reasoning_effort is set
```

This breaks all sub-agent functionality in Claude Code when using DeepSeek as the backend.

## Solution

ccadaptor sits between Claude Code and DeepSeek, translating requests and responses in real-time:

```
Claude Code  ──Anthropic API──►  ccadaptor  ──OpenAI API──►  DeepSeek
              ◄──Anthropic API──  (proxy)    ◄──OpenAI API──
```

### Key Fixes

- **thinking/reasoning_effort conflict**: Strips `reasoning_effort` when `thinking.type` is `"disabled"`
- **budget_tokens**: Strips Anthropic-specific `budget_tokens` from the `thinking` object
- **Full API translation**: Messages, tools, tool calls, system prompts, stop reasons, streaming SSE

## Quick Start

### 1. Install dependencies

```bash
pip install aiohttp
```

### 2. Start the proxy

```bash
export DEEPSEEK_API_KEY="sk-your-deepseek-api-key"
python server.py
```

### 3. Configure Claude Code

In `~/.claude/settings.json`:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:8089",
    "ANTHROPIC_AUTH_TOKEN": "sk-your-deepseek-api-key",
    "ANTHROPIC_MODEL": "deepseek-v4-pro"
  }
}
```

Or pass at command line:

```bash
claude --base-url http://127.0.0.1:8089 --api-key sk-your-deepseek-api-key
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DEEPSEEK_API_KEY` | (required) | DeepSeek API key |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API base URL |
| `DEEPSEEK_MODEL` | (passthrough) | Force a specific model |
| `PROXY_PORT` | `8089` | Proxy listen port |
| `PROXY_HOST` | `127.0.0.1` | Proxy listen host |

## Architecture

```
ccadaptor/
├── server.py       # HTTP proxy server (stdlib only)
├── fixups.py       # Provider-specific request fixups
├── test_fixups.py  # Unit tests for fixups
└── README.md       # This file
```

DeepSeek's `/anthropic` endpoint natively understands Anthropic format, so only minimal
parameter fixups are needed — no full format translation layer is required.

## Testing

```bash
python -m unittest test_fixups.py -v
```

## License

MIT
