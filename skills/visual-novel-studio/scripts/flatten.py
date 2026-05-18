"""
VNS 剧本预处理：章节式 JSON → flat SCRIPT 数组
用法: python scripts/flatten.py <input.json> [output.json]
"""
import json, sys, os

def flatten(input_path, output_path="script_flat.json"):
    with open(input_path) as f:
        data = json.load(f)

    flat = []
    chapters = data.get("SCRIPT", [])
    bg_keys = ["bg01", "bg02", "bg03", "bg04", "bg05"]

    scene_idx = 0
    chapter_names = {
        1: "第一章", 2: "第二章", 3: "第三章",
        4: "第四章", 5: "第五章"
    }

    for i, ch in enumerate(chapters):
        nodes = ch.get("nodes", [])
        for node in nodes:
            # 映射 bg key
            if node.get("type") == "scene":
                node["bg"] = bg_keys[scene_idx] if scene_idx < len(bg_keys) else "bg_placeholder"
                scene_idx += 1
            # 映射 panel src
            elif node.get("type") == "panel":
                node["src"] = f"panel_{flat.count('panel') + 1}"
            # 映射 hero image
            elif node.get("type") == "hero":
                node["image"] = f"hero_{flat.count('hero') + 1}"
            flat.append(node)

    if not flat or flat[-1].get("type") != "ending":
        flat.append({"type": "ending"})

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(flat, f, ensure_ascii=False, indent=2)
    return flat

if __name__ == "__main__":
    infile = sys.argv[1] if len(sys.argv) > 1 else "script.json"
    outfile = sys.argv[2] if len(sys.argv) > 2 else "script_flat.json"
    nodes = flatten(infile, outfile)
    types = {}
    for n in nodes:
        t = n.get("type", "?")
        types[t] = types.get(t, 0) + 1
    print(f"[ok] {len(nodes)} nodes -> {outfile} ({types})")
