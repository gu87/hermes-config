---
name: minimax-image-generation
description:  MiniMax Image-01 API 调用指南 — 生图 MCP 不支持图片生成，必须直接调 REST；图生图（subject_reference）参考能力有限，精确还原具体车型较困难，需换设计工具方案
category: media
---

# MiniMax Image-01 生图

## 关键发现
- **MCP 不支持生图**：`minimax-coding-plan-mcp` 只有 `web_search` 和 `understand_image`，没有图片生成
- **必须直接调 REST API**

## API 信息
- **接口**: `https://api.minimaxi.com/v1/image_generation`
- **模型**: `image-01`
- **认证**: Bearer Token（Token Plan 的 API Key）
- **响应格式**: base64 或 url
- **生成时间**: ~16秒

## Python 调用（execute_code 环境）

```python
import base64, requests, os, time

# 注意：当前环境用 MINIMAX_CN_API_KEY，不是 MINIMAX_API_KEY
api_key = os.environ.get("MINIMAX_CN_API_KEY", "")
url = "https://api.minimaxi.com/v1/image_generation"
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

payload = {
    "model": "image-01",
    "prompt": "英文描述（控制在 1200-1400 字符以内）",
    "aspect_ratio": "16:9",  # 可选: 1:1, 16:9, 9:16, 3:2, 2:3
    "response_format": "base64",
}

response = requests.post(url, headers=headers, json=payload, timeout=180)
data = response.json()
if data.get("data") and data["data"].get("image_base64"):
    images = data["data"]["image_base64"]
    for i, img_b64 in enumerate(images):
        path = f"/Users/gu/Desktop/image_{i}.jpeg"
        with open(path, "wb") as f:
            f.write(base64.b64decode(img_b64))
        print(f"Saved: {path}")
else:
    print("Error:", data.get("base_resp", data))
```

## 两种可选模型
| 模型 | 说明 |
|------|------|
| `image-01` | 主力模型，质量好 |
| `image-01-highspeed` | 快速模型（未验证） |

## 提示语技巧
- 英文效果通常更好，可加 `cinematic, film grain, photorealistic` 等风格词
- 图生图（参考图）支持 `subject_reference` 参数
- **prompt 必须控制在 1500 字符以内（严格限制，超出会报 2013 错误）**
- 复杂描述优先保留核心构图和色彩信息，删减修饰词

## 常见错误
| 错误信息 | 原因 |
|----------|------|
| `login fail: Please carry the API secret key` | Key 用了 `MINIMAX_API_KEY`，当前环境应用 `MINIMAX_CN_API_KEY` |
| `status_code:1004` | Key 无效或权限不足 |
| `status_code:2013 invalid params, prompt length must be less than 1500` | prompt 超过 1500 字符，需压缩 |

## 相关工具优先级
1. **MiniMax Image-01** (稳) → 直接调 API
2. **GPT-image-2** (不稳定) → `ai.flashapi.top` 中转，180秒超时
