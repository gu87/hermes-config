# HTML Anything SSE 响应解析

HTML Anything 的 `/api/convert` 返回 SSE (Server-Sent Events) 流，HTML 文本分布在多个事件中。

## SSE 事件格式

```
event: start
data: {"type":"start","bin":"/Users/gu/.local/bin/claude","argv":[...],"promptBytes":5708}

event: meta
data: {"type":"meta","key":"model","value":"claude-opus-4-7"}

event: delta          ← HTML 正文在这里
data: {"type":"delta","text":"<!DOCTYPE html>..."}

event: meta
data: {"type":"meta","key":"usage","value":{"input_tokens":27478,"output_tokens":9015,...}}

event: meta
data: {"type":"meta","key":"cost_usd","value":0.362765}

event: done
data: {"type":"done","code":0}
```

## Python 解析脚本

```python
import json

html_parts = []
with open('/tmp/raw_output.txt') as f:
    for line in f:
        if line.startswith('data: '):
            data = line[6:].strip()
            try:
                obj = json.loads(data)
                if obj.get('type') == 'delta' and 'text' in obj:
                    html_parts.append(obj['text'])
            except json.JSONDecodeError:
                pass

full_html = ''.join(html_parts).strip()
with open('/tmp/output.html', 'w') as f:
    f.write(full_html)
```

## 关键指标参考（2026-05-16 实测）

| 输入大小 | 输出 HTML | 模型 | 耗时 | 费用 |
|---------|----------|------|------|------|
| 7KB Markdown (含表格) | 27KB | Claude Opus | ~5min | $0.36 |
| 更短内容 | 更小 | Sonnet/Haiku | ~1-2min | ~$0.05-0.10 |

## 注意事项

- 不要用简单的 `grep -o '"text":"[^"]*"'` 提取 — 因为 HTML 内含转义字符和多行内容
- 始终用 Python 的 JSON 解析器
- 如果 `code != 0`，最后一个 `done` 事件的 code 会显示错误
- cost_usd 是 meta 事件中的字段，通常出现在最后
