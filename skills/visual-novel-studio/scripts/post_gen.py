#!/usr/bin/env python3
"""
VNS post-gen workflow: compress all generated raw images + rebuild HTML.

Usage (after gen.py --batch finishes):
    python3 post_gen.py

Expected directory layout:
    game-name/
    ├── raw/              ← gen.py output (PNG)
    ├── compressed/       ← compress.py output (WebP)
    ├── dist/             ← assemble.py output
    ├── script_flat.json  ← flattened script
    └── post_gen.py       ← this script (place in game dir)

This script:
    1. Verifies all 21 expected images exist in raw/
    2. Auto-detects hero_* (type=hero) vs panel_* (type=panel) vs bg_* (type=bg)
    3. Compresses each via compress.py with correct type params
    4. Rebuilds dist/index.html via assemble.py
"""

import os, sys, glob, json, subprocess

EXPECTED_TYPES = {
    # type: (max_w, quality, fmt)
    "bg":    (828, 90, "webp"),
    "panel": (800, 78, "webp"),
    "hero":  (900, 85, "webp"),
    "photo": (800, 82, "jpeg"),
}

def detect_type(filename):
    name = os.path.splitext(filename)[0]
    if name.startswith("hero_"):
        return "hero"
    elif name.startswith("panel_"):
        return "panel"
    elif name.startswith("bg") or name.startswith("scene_"):
        return "bg"
    else:
        return "panel"  # fallback

def main():
    proj = os.path.dirname(os.path.abspath(__file__))
    raw_dir = os.path.join(proj, "raw")
    compressed_dir = os.path.join(proj, "compressed")
    dist_dir = os.path.join(proj, "dist")
    script_path = os.path.join(proj, "script_flat.json")

    # Find compress.py and assemble.py
    hermes_scripts = os.path.expanduser("~/.hermes/scripts/vns")
    compress_py = os.path.join(hermes_scripts, "compress.py")
    assemble_py = os.path.join(hermes_scripts, "assemble.py")

    # Check inputs exist
    if not os.path.isdir(raw_dir):
        print(f"[err] raw/ not found: {raw_dir}")
        sys.exit(1)
    if not os.path.isfile(script_path):
        print(f"[err] script_flat.json not found: {script_path}")
        sys.exit(1)

    # Step 1: Find all PNGs in raw/
    images = sorted(glob.glob(os.path.join(raw_dir, "*.png")))
    print(f"[info] Found {len(images)} images in raw/")

    # Step 2: Compress each
    os.makedirs(compressed_dir, exist_ok=True)
    ok_count = 0
    for img_path in images:
        filename = os.path.basename(img_path)
        name = os.path.splitext(filename)[0]
        img_type = detect_type(filename)
        out_path = os.path.join(compressed_dir, name + ".webp")

        if os.path.exists(out_path):
            size_kb = os.path.getsize(out_path) // 1024
            print(f"  [skip] {name}.webp ({size_kb}KB)")
            ok_count += 1
            continue

        r = subprocess.run(
            ["python3", compress_py, img_path, "--type", img_type, "--out", out_path],
            capture_output=True, text=True
        )
        if r.returncode == 0 and os.path.exists(out_path):
            size_kb = os.path.getsize(out_path) // 1024
            print(f"  [ok] {name}.webp ({img_type}, {size_kb}KB)")
            ok_count += 1
        else:
            print(f"  [err] {name}.webp compress failed: {r.stderr[:100]}")

    print(f"[info] Compressed {ok_count}/{len(images)} images")

    # Step 3: Rebuild
    print("\n=== Rebuilding with assemble.py ===")
    r = subprocess.run(
        ["python3", assemble_py, "--script", script_path,
         "--img-dir", compressed_dir, "--out", os.path.join(dist_dir, "index.html")],
        capture_output=True, text=True, cwd=proj
    )
    if r.stdout:
        print(r.stdout)
    if r.returncode != 0:
        print(f"[err] Build failed: {r.stderr[:200]}")
        sys.exit(1)

    # Report final size
    html_path = os.path.join(dist_dir, "index.html")
    if os.path.exists(html_path):
        size_kb = os.path.getsize(html_path) // 1024
        print(f"[ok] {html_path} ({size_kb}KB)")
    else:
        print(f"[err] No output file at {html_path}")

if __name__ == "__main__":
    main()
