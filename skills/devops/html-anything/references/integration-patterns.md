# HTML Anything SSE 流式响应解析

## 问题

`POST /api/convert` 返回的是 Server-Sent Events (SSE) 流，不是完整的 JSON 响应。HTML 内容分布在多个数据事件中，不能直接用 `curl` 拿到完整 HTML。

## SSE 响应格式

```
event: start
data: {"type":"start","bin":"/path/to/claude","argv":[...],"promptBytes":5708}

event: meta
data: {"type":"meta","key":"model","value":"claude-opus-4-7"}

event: meta
data: {"type":"meta","key":"session","value":"uuid..."}

event: delta
data: {"type":"delta","text":"<!DOCTYPE html>"}

event: delta
data: {"type":"delta","text":"\n<html lang=\\"zh-CN\\">"}

...（多个 delta 事件拼接出完整 HTML）

event: meta
data: {"type":"meta","key":"usage","value":{...}}

event: meta
data: {"type":"meta","key":"result","value":"success"}

event: done
data: {"type":"done","code":0}
```

## 提取 HTML（Python）

```python
import json

html_parts = []
with open('/path/to/raw_output.txt') as f:
    for line in f:
        if line.startswith('data: '):
            data = line[6:].strip()
            try:
                obj = json.loads(data)
                if obj.get('type') == 'delta' and 'text' in obj:
                    html_parts.append(obj['text'])
            except json.JSONDecodeError:
                pass

full_html = ''.join(html_parts)
```

## Bash 提取（简陋版）

```bash
grep '"type":"delta"' output.txt | grep -o '"text":"[^"]*"' | sed 's/"text":"//;s/"$//' | perl -pe 's/\\n/\n/g; s/\\"/"/g; s/\\t/\t/g' > output.html
```

⚠️ 这种方式对包含特殊字符或多行内容的 HTML 可能不准确。推荐用 Python 脚本。

## 性能参考（2026-05-16 实测）

| 规模 | 耗时 | 花费 | 输出大小 |
|------|------|------|----------|
| 7KB Markdown（article-magazine 模板，Claude Opus） | ~5min | ~$0.36 | 27KB HTML |

## 注意事项

- 建议先检查服务是否运行：`curl -s -o /dev/null -w "%{http_code}" http://localhost:14732`
- 首次请求较慢（Claude Code 冷启动 + 模板加载）
- `model` 参数不传时默认使用 Claude Opus，传 `haiku` 或 `sonnet` 可降低花费和耗时
- 服务端使用 SSE 推送，客户端需等待全部 `done` 事件后再处理结果
