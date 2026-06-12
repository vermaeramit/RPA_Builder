"""Web browser automation nodes (powered by Playwright).

The browser/page live in ctx.resources so a flow can: open a browser once,
perform many steps, then close it. Playwright is imported lazily so the rest of
the app runs even before `playwright install` has been run.
"""
from __future__ import annotations

from engine.registry import ParamSpec, register


def _get_page(ctx):
    page = ctx.resources.get("page")
    if page is None:
        raise RuntimeError("No open browser. Add an 'Open Browser' step first.")
    return page


@register(
    type="web.open_browser",
    label="Open Browser",
    category="Web",
    params=[ParamSpec("headless", "Run headless (no window)", "bool", default=False)],
    description="Launch a Chromium browser for the flow to drive.",
)
def open_browser(ctx, params, node):
    from playwright.sync_api import sync_playwright

    headless = str(params.get("headless")).lower() in ("true", "1", "yes")
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    page = browser.new_page()
    ctx.resources.update({"playwright": pw, "browser": browser, "page": page})
    ctx.log(f"Browser launched (headless={headless})", "info", node_id=node["id"])
    return "next"


@register(
    type="web.goto",
    label="Go to URL",
    category="Web",
    params=[ParamSpec("url", "URL", "string", placeholder="https://example.com")],
    description="Navigate the browser to a URL.",
)
def goto(ctx, params, node):
    page = _get_page(ctx)
    url = params.get("url", "")
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    page.goto(url, wait_until="load")
    ctx.log(f"Navigated to {url}", "info", node_id=node["id"])
    return "next"


@register(
    type="web.click",
    label="Click Element",
    category="Web",
    params=[ParamSpec("selector", "CSS / text selector", "string", placeholder="#submit  or  text=Login")],
    description="Click the first element matching the selector.",
)
def click(ctx, params, node):
    page = _get_page(ctx)
    selector = params.get("selector", "")
    page.click(selector, timeout=15000)
    ctx.log(f"Clicked {selector}", "info", node_id=node["id"])
    return "next"


@register(
    type="web.type",
    label="Type Text",
    category="Web",
    params=[
        ParamSpec("selector", "Selector", "string", placeholder="#email"),
        ParamSpec("text", "Text", "string", placeholder="Supports {{variables}}"),
    ],
    description="Type text into an input field.",
)
def type_text(ctx, params, node):
    page = _get_page(ctx)
    selector = params.get("selector", "")
    text = params.get("text", "")
    page.fill(selector, text, timeout=15000)
    ctx.log(f"Typed into {selector}", "info", node_id=node["id"])
    return "next"


@register(
    type="web.extract_text",
    label="Extract Text",
    category="Web",
    params=[
        ParamSpec("selector", "Selector", "string", placeholder="h1"),
        ParamSpec("variable", "Store in variable", "string", placeholder="title"),
    ],
    description="Read an element's text into a variable for later steps.",
)
def extract_text(ctx, params, node):
    page = _get_page(ctx)
    selector = params.get("selector", "")
    var = (params.get("variable") or "").strip()
    value = page.inner_text(selector, timeout=15000)
    if var:
        ctx.vars[var] = value
    ctx.log(f"Extracted {selector} -> {value!r}", "info", node_id=node["id"])
    return "next"


@register(
    type="web.screenshot",
    label="Screenshot",
    category="Web",
    params=[ParamSpec("path", "Save to file", "string", default="screenshot.png")],
    description="Capture a full-page screenshot to a file.",
)
def screenshot(ctx, params, node):
    page = _get_page(ctx)
    path = params.get("path", "screenshot.png")
    page.screenshot(path=path, full_page=True)
    ctx.log(f"Saved screenshot to {path}", "info", node_id=node["id"])
    return "next"


@register(
    type="web.close_browser",
    label="Close Browser",
    category="Web",
    description="Close the browser and release it.",
)
def close_browser(ctx, params, node):
    ctx.cleanup()
    ctx.resources.pop("page", None)
    ctx.log("Browser closed", "info", node_id=node["id"])
    return "next"
