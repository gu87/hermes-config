#!/usr/bin/env python3
"""
VNS Quality Gate A — 剧本数据格式校验
在 assemble.py 之前运行，检查：
  1. 所有节点类型是否引擎支持
  2. 字段名与引擎 handler 期望是否匹配
  3. 必填字段是否缺失
  4. 图片 key 是否有 "?" 占位符残留
  5. 图片 key 是否有对应的生成图片
  6. 是否存在不支持的数据结构（如 panel.left/right 嵌套）

用法: python validate_script.py script_flat.json --img-dir compressed/
"""
import json, os, sys, argparse

# ===== 引擎支持的节点类型及必填字段 =====
NODE_SCHEMA = {
    "scene": {
        "required": [],
        "allowed": ["type", "bg", "chapter", "bgm", "sfx", "amb", "ambStop"],
        "note": "bg 和 chapter 为可选但强烈建议",
        "field_map": {},  # data_field -> engine_field (空=一致)
    },
    "narrate": {
        "required": ["text"],
        "allowed": ["type", "text", "sfx"],
        "field_map": {},
    },
    "dialog": {
        "required": ["speaker", "dialog"],
        "allowed": ["type", "speaker", "dialog", "sfx"],
        "field_map": {"dialog": "dialog"},  # engine 读 node.dialog
    },
    "panel": {
        "required": ["src"],
        "allowed": ["type", "src", "pos", "prompt_text"],
        "field_map": {},
        "forbidden_patterns": [
            ("nested 'left' or 'right' in panel", lambda n: "left" in n or "right" in n),
            ("nested 'illustration' in panel", lambda n: "illustration" in n),
        ],
    },
    "choice": {
        "required": ["question", "options"],
        "allowed": ["type", "question", "options"],
        "field_map": {},
        "option_schema": {
            "required": ["text"],
            "allowed": ["id", "text", "score", "nextText", "next_node", "affinity_effect"],
            "needs_score": True,  # 最好有 score 或 affinity_effect
        },
    },
    "card": {
        "required": ["title"],
        "allowed": ["type", "card_type", "title", "description", "text", "photo", "icon", "icon_img", "teaser", "stat"],
        "field_map": {"description": "text"},  # engine 优先读 description 再fallback text
    },
    "hero": {
        "required": ["title"],
        "allowed": ["type", "image", "title"],
        "field_map": {},
    },
    "gacha": {
        "required": ["question", "pool"],
        "allowed": ["type", "question", "pool", "rerollCost"],
        "field_map": {},
    },
    "timeline": {
        "required": ["events"],
        "allowed": ["type", "events"],
        "field_map": {},
    },
    "ending": {
        "required": [],
        "allowed": ["type"],
        "field_map": {},
    },
}

ALLOWED_TYPES = set(NODE_SCHEMA.keys())


def check_type(node, issues, node_idx):
    """检查节点类型是否引擎支持"""
    t = node.get("type", "")
    if not t:
        issues.append(f"❗ [{node_idx}] 节点缺少 type 字段")
        return False
    if t not in ALLOWED_TYPES:
        issues.append(f"❌ [{node_idx}] 不支持的节点类型 '{t}'，引擎支持: {sorted(ALLOWED_TYPES)}")
        return False
    return True


def check_fields(node, issues, node_idx, schema):
    """检查字段名与 schema 是否匹配"""
    schema_name = schema.get("note", "")

    # 检查必填字段
    for f in schema.get("required", []):
        if f not in node or node[f] is None or (isinstance(node[f], str) and node[f].strip() == ""):
            issues.append(f"❌ [{node_idx}] {node.get('type','?')} 缺少必填字段 '{f}'")

    # 检查不支持的字段
    allowed = set(schema.get("allowed", []))
    for f in node:
        if f not in allowed:
            issues.append(f"⚠️  [{node_idx}] {node.get('type','?')} 有不支持的字段 '{f}'（引擎可能忽略它）")

    # 检查 forbidden patterns
    for desc, pattern_fn in schema.get("forbidden_patterns", []):
        if pattern_fn(node):
            issues.append(f"❌ [{node_idx}] {node.get('type','?')} 存在 {desc}——引擎不支持")


def check_image_key(key, issues, node_idx, context, img_dir):
    """检查图片 key 是否有效"""
    if not key or key == "?":
        issues.append(f"❌ [{node_idx}] {context} 图片 key 为 '{key}'——这是占位符，需要替换为实际 key")
        return False
    # 如果在 img-dir 且有图片文件，检查是否存在
    if img_dir:
        for ext in [".webp", ".png", ".jpg", ".jpeg"]:
            path = os.path.join(img_dir, key + ext)
            if os.path.exists(path):
                return True
        issues.append(f"⚠️  [{node_idx}] {context} 图片 key '{key}' 在 {img_dir} 中未找到对应文件")
        return False
    return True


def validate(script_path, img_dir=None):
    with open(script_path) as f:
        script = json.load(f)

    issues = []
    img_keys_used = set()
    node_types_used = set()

    for i, node in enumerate(script):
        node_idx = f"#{i}"
        t = node.get("type", "")
        node_types_used.add(t)

        if not check_type(node, issues, node_idx):
            continue

        schema = NODE_SCHEMA.get(t, {})
        check_fields(node, issues, node_idx, schema)

        # 检查图片 key
        for key_field in ["bg", "src", "image", "photo"]:
            key = node.get(key_field)
            if key:
                img_keys_used.add(key)
                check_image_key(key, issues, node_idx, f"{t}.{key_field}", img_dir)

        # choice 选项检查
        if t == "choice" and "options" in node:
            for j, opt in enumerate(node["options"]):
                opt_schema = schema.get("option_schema", {})
                for f in opt_schema.get("required", []):
                    if f not in opt:
                        issues.append(f"❌ [{node_idx}] choice.options[{j}] 缺少必填字段 '{f}'")
                for f in opt:
                    if f not in opt_schema.get("allowed", []):
                        issues.append(f"⚠️  [{node_idx}] choice.options[{j}] 有不支持的字段 '{f}'")
                if opt_schema.get("needs_score"):
                    if "score" not in opt and "affinity_effect" not in opt:
                        issues.append(f"⚠️  [{node_idx}] choice.options[{j}] 既无 'score' 也无 'affinity_effect'——理解度不会增长")

        # hero 节点检查：title vs dialog 字段混淆
        if t == "hero":
            if "dialog" in node and "title" not in node:
                issues.append(f"❌ [{node_idx}] hero 节点用了 'dialog' 字段，但引擎读的是 'title'——脚本中应改用 'title'")
            if node.get("dialog") and node.get("title"):
                issues.append(f"⚠️  [{node_idx}] hero 节点同时有 'dialog' 和 'title'——引擎只认 'title'")

    # 汇总报告
    print(f"=" * 60)
    print(f"  VNS 数据格式校验 (Quality Gate A)")
    print(f"  剧本: {os.path.basename(script_path)}")
    print(f"  节点: {len(script)} 个")
    print(f"  类型: {sorted(node_types_used)}")
    print(f"  图片引用: {len(img_keys_used)} 个独立 key")
    print(f"=" * 60)

    if not issues:
        print(f"\n✅ 通过！0 个问题")
        return True

    print(f"\n{'='*60}")
    print(f"  发现 {len(issues)} 个问题：")
    print(f"{'='*60}")
    for issue in issues:
        print(f"  {issue}")

    errors = [i for i in issues if i.startswith("❌")]
    warnings = [i for i in issues if i.startswith("⚠️")]

    print(f"\n  严重: {len(errors)} | 警告: {len(warnings)}")
    if errors:
        print(f"❌ Gate A FAILED — 请修复严重问题后再 assemble")
        return False
    else:
        print(f"⚠️  Gate A PASSED WITH WARNINGS — 建议修复警告")
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VNS 剧本数据格式校验")
    parser.add_argument("script", help="剧本 JSON 文件路径")
    parser.add_argument("--img-dir", help="图片目录（选填，用于检查图片文件是否存在）")
    args = parser.parse_args()
    success = validate(args.script, args.img_dir)
    sys.exit(0 if success else 1)
