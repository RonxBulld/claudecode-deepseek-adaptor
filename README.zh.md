# claudecode-deepseek-adaptor — Claude Code ↔ DeepSeek API 适配器

一个透明的 HTTP 代理，用于修复 Claude Code 的 Anthropic 格式请求与 DeepSeek
`/anthropic` 端点之间的不兼容问题。

DeepSeek 的 `/anthropic` 端点**原生接受 Anthropic Messages API 格式**——无需
完整的翻译层。代理仅剥离或重写 DeepSeek 不支持的少数几个参数。

```
Claude Code ── Anthropic API ──► claudecode-deepseek-adaptor ──► api.deepseek.com/anthropic
             ◄── Anthropic API ──            ◄──
```

## 快速开始

### 1. 配置 Claude Code

在 `~/.claude/settings.json` 中：

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:8089",
    "ANTHROPIC_AUTH_TOKEN": "sk-your-deepseek-api-key",
    "ANTHROPIC_MODEL": "deepseek-v4-pro[1m]"
  }
}
```

### 2. 启动代理

```bash
python3 server.py
```

就这么简单。无需 pip install——仅依赖标准库。

### 3. 验证

确认 `~/.claude/settings.json` 中包含上述环境变量，然后正常使用 Claude Code。
所有 API 调用将自动通过代理路由。

## 配置

| 变量 | 默认值 | 说明 |
|---|---|---|
| `UPSTREAM_URL` | `https://api.deepseek.com/anthropic` | DeepSeek 端点地址 |
| `PROXY_PORT` | `8089` | 代理监听端口 |
| `PROXY_HOST` | `127.0.0.1` | 代理监听地址 |
| `CLAUDE_DS_ADAPTOR_DEBUG` | `0` | 设为 `1` 开启请求日志 |

调试模式：
```bash
CLAUDE_DS_ADAPTOR_DEBUG=1 python3 server.py
```
日志输出到 stderr。每条请求会显示模型、thinking、reasoning_effort 以及是否应用了修复。

## 适配策略

所有修复仅作用于**请求体**——响应、请求头、API 密钥和 SSE 流均原样透传。
修复按顺序执行，每个修复的输出是下一个修复的输入。

### 1. `adaptive` → `enabled`

| | |
|---|---|
| **问题** | Claude Code（Opus 4.6+）发送 `thinking.type: "adaptive"`。DeepSeek 文档仅列出 `"enabled"` 和 `"disabled"`。 |
| **修复** | 将 `"adaptive"` 重写为 `"enabled"`。思考深度仍由 `output_config.effort` 控制。 |

### 2. 剥离 `thinking.display`

| | |
|---|---|
| **问题** | Anthropic Opus 4.7+ 支持 `thinking.display`（`"summarized"`、`"omitted"`）。DeepSeek 文档中未包含此字段。 |
| **修复** | 从 `thinking` 对象中移除 `display`。如果剥离后 `thinking` 变为空对象，则整体移除。 |

### 3. 处理 `thinking: {type: "disabled"}` 冲突

| | |
|---|---|
| **问题** | DeepSeek 在两种场景下拒绝 `thinking.type=disabled`：(a) 同时设置了 `reasoning_effort`；(b) 模型本身不支持 `thinking` 参数——即使未设置 `reasoning_effort` 也会返回误导性的 400 错误。 |
| **修复** | **模型无关**：当 thinking 类型为 `"disabled"` 时，彻底剥离 `thinking` 和 `reasoning_effort`。同时处理边界情况：空字典 `{}`、非标准值如 `false` 或 `"disabled"`（字符串）。 |

### 4. 精简 `output_config`

| | |
|---|---|
| **问题** | Claude Code 发送 Anthropic 专有的 `output_config` 字段（`task_budget`、`format`）。DeepSeek 仅支持 `effort`。 |
| **修复** | 仅保留 `output_config` 中的 `effort`。如果 `output_config` 变为空，则整体移除。 |

## 有意保留的参数

根据 [DeepSeek Anthropic API 文档](https://api-docs.deepseek.com/zh-cn/guides/anthropic_api)，
以下参数要么完全支持，要么会被静默忽略——我们原样透传而非剥离，以免阻止未来 DeepSeek
新增支持：

| 参数 | 文档说明 | 行为 |
|---|---|---|
| `thinking.budget_tokens` | "会被忽略" | 原样透传，无报错 |
| `temperature` | "完全支持"（0.0–2.0） | 原样透传 |
| `top_p` | "完全支持" | 原样透传 |
| `top_k` | "忽略" | 原样透传，无报错 |

## 原样透传的内容

- API 密钥（`ANTHROPIC_AUTH_TOKEN` → `Authorization` 请求头）
- 所有其他 HTTP 请求头
- SSE 流式响应
- 错误响应（状态码、响应体）
- 非 JSON 请求体
- 所有模型名称（修复逻辑中不做模型名匹配）

## 项目结构

```
claudecode-deepseek-adaptor/
├── server.py       # HTTP 代理（ThreadingMixIn，纯标准库）
├── fixups.py       # 四步修复链 + 工具函数
├── test_fixups.py  # 单元测试
└── README.md
```

零外部依赖——`json`、`http.server`、`urllib`、`socketserver`、`typing`。

## 测试

```bash
python3 -m unittest test_fixups.py -v
```

## 许可证

MIT
