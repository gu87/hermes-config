#!/usr/bin/env python3
"""
VNS 剧本标准化脚本
将皮尔洛输出的章节式剧本归一化为引擎可用的 flat SCRIPT。
目前处理以下不兼容问题：
  1. 章节结构 nodes[] → 平铺
  2. panel 节点中 layout/left/right 嵌套结构 → 简化
  3. panel 节点中 "illustration" key 嵌套 → 提取 src
  4. hero 节点中 "dialog" 字段 → "title"
  5. 移除多余元数据字段 (id, character, expression, pose, duration_seconds 等)
  6. 图片 key 占位符 "?" → 自动映射到真实 key（bg01-bg05）
"""
import json, sys, os

def fix_script(input_path, output_path=None):
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    script = data.get("SCRIPT", data)
    if isinstance(script, list) and len(script) > 0 and "nodes" in script[0]:
        # 章节格式 → 平铺
        flat = []
        for ch in script:
            flat.extend(ch.get("nodes", []))
        script = flat

    img_keys = {"bg": [], "hero": [], "panel": []}
    seen = set()
    bg_idx = hero_idx = panel_idx = 0

    for node in script:
        t = node.get("type")

        # 移除多余字段
        for f in ["id", "character", "expression", "pose", "duration_seconds",
                   "background_prompt", "background_keywords", "ambient", "keywords",
                   "usage", "layout"]:
            node.pop(f, None)

        if t == "panel":
            # 处理嵌套 illustration key
            if "illustration" in node and isinstance(node["illustration"], dict):
                node.pop("illustration")
            # 处理 left/right 嵌套
            for side in ("left", "right"):
                if side in node and isinstance(node[side], dict):
                    node.pop(side)
            # 确保 src 和 pos
            if "src" not in node or node["src"] in ("?", ""):
                panel_idx += 1
                node["src"] = f"panel_{panel_idx}"
            if "pos" not in node:
                node["pos"] = "br"

        elif t == "hero":
            if "dialog" in node and "title" not in node:
                node["title"] = node.pop("dialog")
            if "image" not in node or node["image"] in ("?", ""):
                hero_idx += 1
                node["image"] = f"hero_{hero_idx}"

        elif t == "scene":
            if "bg" not in node or node["bg"] in ("?", ""):
                bg_idx += 1
                node["bg"] = f"bg{str(bg_idx).zfill(2)}"

        elif t == "card":
            if "photo" not in node or node["photo"] in ("?", ""):
                node["photo"] = None

        elif t == "choice":
            # 确保 options 存在
            if "options" not in node:
                node["options"] = [{"text": "继续", "score": 0}]

    # 补 ending 节点
    if not script or script[-1].get("type") != "ending":
        script.append({"type": "ending"})

    out_path = output_path or input_path
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    type_counts = {}
    for n in script:
        t = n.get("type", "?")
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"[ok] Fixed: {len(script)} nodes -> {out_path}")
    print(f"  Types: {type_counts}")
    return script

if __name__ == "__main__":
    if len(sys.argv) > 1:
        fix_script(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        print("Usage: python fix_script.py input.json [output.json]")
