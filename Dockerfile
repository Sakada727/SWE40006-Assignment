FROM python:3.12-slim

# No .pyc files, and logs appear immediately in `docker logs`
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime dependencies first so this layer is cached until requirements.txt changes.
# Test tools (pytest, Playwright) live in requirements-dev.txt and are not installed here.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# .dockerignore keeps tests, the workflow, .git and any local .env out of the image
COPY . .

# Run as a non-root user
RUN useradd --create-home appuser
USER appuser

EXPOSE 8080

# Uses the app's /health route, which also checks the database
# (python is used because the slim image has no curl)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# The commit this image was built from. The pipeline passes it as a build argument,
# and /health and the page footer report it. Declared last so it does not invalidate
# the cached dependency layers above.
ARG GIT_SHA=dev
ENV GIT_SHA=${GIT_SHA}

# DATABASE_URL and SECRET_KEY are supplied at run time, not baked into the image
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
