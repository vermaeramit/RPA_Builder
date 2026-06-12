# Backend: FastAPI engine + Playwright (Chromium pre-installed in this base image).
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

WORKDIR /app

# Install Python deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY . .

# Entrypoint starts a virtual display (so browser automation works headless or not)
# then launches the API. Single uvicorn worker on purpose: the in-process scheduler
# must not run in multiple workers (it would fire each schedule more than once).
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
