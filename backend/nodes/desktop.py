"""Desktop UI automation nodes (powered by pyautogui).

These drive the real mouse/keyboard, so they only work on a machine with a
desktop session (not headless servers). pyautogui is imported lazily.
"""
from __future__ import annotations

from engine.registry import ParamSpec, register


@register(
    type="desktop.launch_app",
    label="Launch Application",
    category="Desktop",
    params=[ParamSpec("path", "Executable / command", "string", placeholder="notepad.exe")],
    description="Start a desktop application.",
)
def launch_app(ctx, params, node):
    import subprocess

    path = params.get("path", "")
    subprocess.Popen(path, shell=True)
    ctx.log(f"Launched {path}", "info", node_id=node["id"])
    return "next"


@register(
    type="desktop.type_keys",
    label="Type Keys",
    category="Desktop",
    params=[ParamSpec("text", "Text to type", "text", placeholder="Supports {{variables}}")],
    description="Type text using the keyboard into the focused window.",
)
def type_keys(ctx, params, node):
    import pyautogui

    text = params.get("text", "")
    pyautogui.typewrite(text, interval=0.02)
    ctx.log(f"Typed {len(text)} chars", "info", node_id=node["id"])
    return "next"


@register(
    type="desktop.hotkey",
    label="Press Hotkey",
    category="Desktop",
    params=[ParamSpec("keys", "Keys (e.g. ctrl+s)", "string", placeholder="ctrl+s")],
    description="Press a key combination (e.g. ctrl+s, alt+tab, enter).",
)
def hotkey(ctx, params, node):
    import pyautogui

    keys = [k.strip() for k in (params.get("keys") or "").split("+") if k.strip()]
    if keys:
        pyautogui.hotkey(*keys)
    ctx.log(f"Pressed {'+'.join(keys)}", "info", node_id=node["id"])
    return "next"


@register(
    type="desktop.click_xy",
    label="Click at Position",
    category="Desktop",
    params=[
        ParamSpec("x", "X", "number", default=0),
        ParamSpec("y", "Y", "number", default=0),
    ],
    description="Move the mouse to (x, y) and click.",
)
def click_xy(ctx, params, node):
    import pyautogui

    x = int(float(params.get("x", 0) or 0))
    y = int(float(params.get("y", 0) or 0))
    pyautogui.click(x, y)
    ctx.log(f"Clicked at ({x}, {y})", "info", node_id=node["id"])
    return "next"
