"""Files, data, and HTTP nodes."""
from __future__ import annotations

import json

from engine.registry import ParamSpec, register


@register(
    type="files.read_csv",
    label="Read CSV/Excel",
    category="Files & Data",
    params=[
        ParamSpec("path", "File path", "string", placeholder="data.csv or data.xlsx"),
        ParamSpec("variable", "Store rows in variable", "string", default="rows"),
    ],
    description="Read a CSV or Excel file into a variable (list of row dicts).",
)
def read_csv(ctx, params, node):
    import pandas as pd

    path = params.get("path", "")
    var = (params.get("variable") or "rows").strip()
    if path.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    rows = df.to_dict(orient="records")
    ctx.vars[var] = rows
    ctx.vars[var + "_count"] = len(rows)
    ctx.log(f"Read {len(rows)} rows from {path}", "info", node_id=node["id"])
    return "next"


@register(
    type="files.write_csv",
    label="Write CSV/Excel",
    category="Files & Data",
    params=[
        ParamSpec("variable", "Variable holding rows", "string", default="rows"),
        ParamSpec("path", "Save to file", "string", placeholder="out.csv or out.xlsx"),
    ],
    description="Write a list-of-dicts variable to a CSV or Excel file.",
)
def write_csv(ctx, params, node):
    import pandas as pd

    var = (params.get("variable") or "rows").strip()
    path = params.get("path", "out.csv")
    data = ctx.vars.get(var, [])
    df = pd.DataFrame(data if isinstance(data, list) else [data])
    if path.lower().endswith((".xlsx", ".xls")):
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False)
    ctx.log(f"Wrote {len(df)} rows to {path}", "info", node_id=node["id"])
    return "next"


@register(
    type="files.write_text",
    label="Write Text File",
    category="Files & Data",
    params=[
        ParamSpec("path", "File path", "string", placeholder="output.txt"),
        ParamSpec("content", "Content", "text", placeholder="Supports {{variables}}"),
        ParamSpec("append", "Append instead of overwrite", "bool", default=False),
    ],
    description="Write text to a file.",
)
def write_text(ctx, params, node):
    path = params.get("path", "output.txt")
    content = params.get("content", "")
    mode = "a" if str(params.get("append")).lower() in ("true", "1", "yes") else "w"
    with open(path, mode, encoding="utf-8") as fh:
        fh.write(content)
    ctx.log(f"Wrote {len(content)} chars to {path}", "info", node_id=node["id"])
    return "next"


@register(
    type="files.http_request",
    label="HTTP Request",
    category="Files & Data",
    params=[
        ParamSpec("method", "Method", "select", default="GET",
                  options=["GET", "POST", "PUT", "DELETE", "PATCH"]),
        ParamSpec("url", "URL", "string", placeholder="https://api.example.com/data"),
        ParamSpec("body", "JSON body (optional)", "text", placeholder='{"key": "value"}'),
        ParamSpec("variable", "Store response in variable", "string", default="response"),
    ],
    description="Call an HTTP/REST API and store the response.",
)
def http_request(ctx, params, node):
    import requests

    method = (params.get("method") or "GET").upper()
    url = params.get("url", "")
    var = (params.get("variable") or "response").strip()
    body = params.get("body", "").strip()

    kwargs = {}
    if body:
        try:
            kwargs["json"] = json.loads(body)
        except json.JSONDecodeError:
            kwargs["data"] = body

    resp = requests.request(method, url, timeout=30, **kwargs)
    try:
        value = resp.json()
    except ValueError:
        value = resp.text
    ctx.vars[var] = value
    ctx.vars[var + "_status"] = resp.status_code
    ctx.log(f"{method} {url} -> {resp.status_code}", "info", node_id=node["id"])
    return "next"
