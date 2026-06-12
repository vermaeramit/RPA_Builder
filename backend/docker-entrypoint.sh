#!/bin/bash
set -e

# Start a virtual X display so Playwright can run even with headless=False,
# and desktop nodes don't crash on a missing DISPLAY.
if command -v Xvfb >/dev/null 2>&1; then
  Xvfb :99 -screen 0 1920x1080x24 >/dev/null 2>&1 &
  export DISPLAY=:99
fi

exec uvicorn main:app --host 0.0.0.0 --port 8000
