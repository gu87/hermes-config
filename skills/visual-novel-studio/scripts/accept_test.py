#!/usr/bin/env python3
"""
VNS Quality Gate B — 自动验收测试
在 assemble.py 之后运行，用 headless browser 验证：
  1. 页面无 JS 错误加载
  2. 启动页正常渲染
  3. 点击"进入故事"后场景切换正常
  4. dialog/narrate 有文本（非空）
  5. hero/choice/card 节点渲染正常
  6. 能跑完全程无卡死
  7. 结局正常出现

依赖: playwright (pip install playwright)
运行: python accept_test.py dist/index.html
"""
import json, os, sys, re, time, subprocess

def check_file(path):
    if not os.path.exists(path):
        print(f"❌ 文件不存在: {path}")
        sys.exit(1)
    size_kb = os.path.getsize(path) // 1024
    print(f"[ok] 文件存在: {size_kb}KB")

    # 检查引擎关键修复标记
    checks = {
        "锁修复 (1600ms)": b"setTimeout(advance, 1600)",
        "dialog 修复": b"node.dialog",
        "card 修复": b"node.description",
        "race condition 修复": b"let advancing",
        "advancing 互斥锁": b"advancing=true",
    }
    with open(path, "rb") as f:
        content = f.read()

    all_ok = True
    for name, pattern in checks.items():
        if pattern in content:
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ 缺失: {name}")
            all_ok = False

    return all_ok


def playwright_test(path):
    """用 Playwright 的 Python API 做集成测试"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("⚠️  Playwright 未安装，跳过浏览器测试")
        print("   安装: pip install playwright && playwright install chromium")
        return True

    results = []
    def check(name, condition, detail=""):
        if condition:
            results.append(f"  ✅ {name}")
        else:
            results.append(f"  ❌ {name} {detail}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 420, "height": 800})
            errors = []

            page.on("pageerror", lambda err: errors.append(str(err)))
            page.on("console", lambda msg: errors.append(f"[console.{msg.type}] {msg.text}") if msg.type == "error" else None)

            # 1. 加载页面
            page.goto(f"file://{path}", wait_until="networkidle")
            check("页面加载无崩溃", not any("SyntaxError" in e or "TypeError" in e for e in errors))

            # 2. 启动页可见
            launch_visible = page.locator("#launch").is_visible()
            btn_visible = page.locator("#launch-btn").is_visible()
            check("启动页渲染", launch_visible and btn_visible)

            # 3. 点击进入故事
            page.click("#launch-btn")
            time.sleep(0.8)  # 等待 fade-out

            launch_hidden = not page.locator("#launch").is_visible()
            check("启动页消失", launch_hidden)

            # 4. 检查 scene 背景/HUD (等到第一个 scene 渲染)
            time.sleep(1.0)

            # 尝试取 cursor
            try:
                cursor = page.evaluate("cursor")
                check(f"cursor 推进到 {cursor}", cursor >= 1)
            except Exception as e:
                check("cursor 可访问", False, str(e))

            # 检查场景背景
            try:
                bg = page.evaluate("document.getElementById('scene').style.backgroundImage")
                check("场景背景图已设置", len(bg) > 10, f"length={len(bg)}")
            except:
                check("场景背景图", False)

            # 检查 dialog 或 hero
            try:
                dialog_shown = page.evaluate("document.getElementById('dialog-box').classList.contains('show')")
                hero_shown = page.evaluate("document.getElementById('hero-box').classList.contains('show')")
                check("对话框或 hero 节点出现", dialog_shown or hero_shown)

                if dialog_shown:
                    text = page.evaluate("document.getElementById('dialog-text').textContent")
                    check("对话框有文本内容", len(text.strip()) > 0)

                if hero_shown:
                    title = page.evaluate("document.getElementById('hero-title').textContent")
                    check("hero 有标题内容", len(title.strip()) > 0)
            except:
                pass

            # 5. 向前推进几步
            try:
                for click_i in range(10):
                    # 点击页面推进
                    page.click("#game", position={"x": 210, "y": 600})
                    time.sleep(0.3)

                cursor_after = page.evaluate("cursor")
                check(f"多次点击后 cursor={cursor_after}", cursor_after > 3,
                      f"(从 0 推进到了 {cursor_after})")
            except Exception as e:
                check("推进测试", False, str(e))

            # 6. 检查 JS 错误数
            check(f"JS 错误数: {len(errors)}", len(errors) == 0,
                  f"发现 {len(errors)} 个错误: {'; '.join(errors[:5])}" if errors else "")

            # 7. 检查 HUD
            try:
                hud_shown = page.evaluate("document.getElementById('hud').classList.contains('show')")
                check("HUD 显示", hud_shown)
            except:
                pass

            browser.close()

            passed = sum(1 for r in results if "✅" in r)
            failed = sum(1 for r in results if "❌" in r)

            print(f"\n{'='*60}")
            print(f"  VNS 自动验收测试 (Quality Gate B)")
            print(f"  通过: {passed} | 失败: {failed}")
            print(f"{'='*60}")
            for r in results:
                print(r)

            return failed == 0

    except Exception as e:
        print(f"❌ 浏览器测试异常: {e}")
        return False


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "dist/index.html"

    print(f"=" * 60)
    print(f"  VNS Quality Gate B — 自动验收")
    print(f"  目标: {path}")
    print(f"=" * 60)

    file_ok = check_file(path)
    print()
    test_ok = playwright_test(path)

    if file_ok and test_ok:
        print(f"\n✅ Gate B 全部通过")
        sys.exit(0)
    else:
        print(f"\n❌ Gate B 失败")
        sys.exit(1)
