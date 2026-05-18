# OpenClaw 工具集配置

## 问题

OpenClaw 默认只有 `[terminal, file]` 工具集，不足以做真正的 web research（搜图、查资料）。需要加 `web` 和 `browser`。

## 症状

- delegate_task(agent_id='openclaw') 返回空或只返回文件内容，找不到图片/搜索结果
- 报错如 `HTTP Error 403/404`（curl 被目标站点拦截）
- tool_trace 中仅 terminal 调用，没有 browser_navigate / web_search 调用

## 修复

### 1. 检查当前配置

```bash
cat ~/.hermes/config/agent-registry.json | python3 -c "import json,sys;d=json.load(sys.stdin);oc=d['agents']['openclaw'];print(json.dumps(oc['subagent_profile']['toolsets'],indent=2))"
```

### 2. 更新 agent-registry.json

由内斯塔执行 patch：将 `"toolsets": ["terminal", "file"]` 改为 `"toolsets": ["terminal", "file", "web", "browser"]`

同时可更新 capabilities:
```json
"capabilities": [
  "web_research",
  "market_intelligence",
  "competitor_monitoring",
  "news_gathering",
  "web_browsing",
  "image_search",
  "visual_analysis"
]
```

### 3. 重启 Gateway

```bash
hermes gateway run --replace
```

### 4. 验证

```python
delegate_task(
    agent_id='openclaw',
    goal='回复此消息确认工具集已生效',
    toolsets=['web','browser','terminal','file']
)
```

检查返回的 `effective_toolsets` 应包含 web 和 browser。
