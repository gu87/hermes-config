#!/usr/bin/env python3
"""
Convert 内斯塔's task_regenerate_N.json (chapter-nested format)
to gen.py batch format (flat [{out, prompt, size?, quality?}]).

Usage:
  python3 task_to_batch.py task_regenerate_18.json -o gen_batch_18.json --size 1024x1024 --quality high
"""
import json, argparse

def convert(input_path, output_path, default_size="1024x1024", default_quality="high"):
    with open(input_path) as f:
        data = json.load(f)

    # Support both chapter-nested and direct array format
    chapters = data.get("chapters", data if isinstance(data, list) else [])

    batch = []
    for ch in chapters:
        images = ch.get("images", [ch] if "output" in ch else [])
        for img in images:
            if "output" not in img:
                continue
            batch.append({
                "out": img["output"],
                "prompt": img["prompt"],
                "size": img.get("size", default_size),
                "quality": img.get("quality", default_quality)
            })

    with open(output_path, "w") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)

    print(f"[ok] {len(batch)} tasks written to {output_path}")
    return batch

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert task package to gen.py batch format")
    parser.add_argument("input", help="task_regenerate_N.json file")
    parser.add_argument("-o", "--output", default="gen_batch.json", help="output batch file")
    parser.add_argument("--size", default="1024x1024", help="default image size")
    parser.add_argument("--quality", default="high", help="default image quality")
    args = parser.parse_args()
    convert(args.input, args.output, args.size, args.quality)
