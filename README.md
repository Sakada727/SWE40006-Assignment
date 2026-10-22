# SWE40006 DevOps Pipeline: URL Shortener

A Flask URL shortener (with a small per-user task list) delivered through a four-environment
DevOps pipeline: GitHub, GitHub Actions, a containerised Test/Staging tier, and a production
EC2 instance backed by Amazon RDS for PostgreSQL. Built for SWE40006 Software Deployment and
Evolution by Chanresmey Samrith, Sakada Seu and Chyheang Chhour.

## Application

Users register and log in, paste a long `http` or `https` address, and receive a six-character
short link. Anyone who opens `/s/<code>` is redirected to the original address and the link's
click count increases. Each user sees and deletes only their own links and tasks. The same
operations are available as a JSON API under `/api/links` and `/api/tasks`.

`GET /health` runs a real database query and returns the commit the running image was built
from, for example `{"status": "ok", "database": "ok", "version": "<git sha>"}`. It returns
HTTP 503 if the database is unreachable, which makes a broken deploy fail its health check and
roll back. The page footer shows the same version, so a change can be traced from commit to
production.

## Environments

| Environment | Where it runs | Role |
|---|---|---|
| Code repository | GitHub (`develop` and `main`, changes merged by pull request) | Source, workflow, image registry (GHCR) |
| CI/Build | GitHub-hosted runner (Ubuntu 24.04), new VM per job | Unit tests, coverage gate, Docker image build |
| Test/Staging | Docker on a GitHub-hosted runner with its own PostgreSQL, then a staging EC2 instance | Integration and Playwright end-to-end tests against the built image |
| Production | EC2 instance running the image, Amazon RDS for PostgreSQL | Public application |

## Pipeline (`.github/workflows/ci.yml`)

1. **Testing**: installs `requirements-dev.txt` and runs the unit suite with a coverage gate of 85%.
2. **Staging (CI runner)**: builds the image once, tagged with the commit SHA, and runs it beside
   a fresh PostgreSQL container. The integration suite runs against a separate test database and
   the Playwright suite drives the running container in Chromium. Only an image that passes is
   pushed to GHCR.
3. **Deploy to staging server** (pushes to `develop` and `main`): pulls that same image onto the
   staging EC2, health-checks it (rolling back on failure) and runs the end-to-end suite against it.
4. **Deploy to production** (pushes to `main`): pulls the same image onto the production EC2,
   health-checks it with automatic rollback, then checks from outside AWS that production reports
   the expected commit and a working database.

Required repository secrets: `EC2_HOST`, `EC2_SSH_KEY`, `DATABASE_URL`, `SECRET_KEY` (production)
and `EC2_HOST_STAGING`, `EC2_SSH_KEY_STAGING`, `DATABASE_URL_STAGING`, `SECRET_KEY_STAGING`
(staging). Adding required reviewers to the `production` environment turns the final stage into a
manual approval gate.

## Running locally

```bash
docker compose up --build          # app on http://localhost:8080 with PostgreSQL
```

Or without Docker (uses SQLite):

```bash
pip install -r requirements-dev.txt
python app.py                      # development server on http://localhost:8080
```

## Tests

| Suite | Folder | Needs | Command |
|---|---|---|---|
| Unit | `Tests/unit`, `Tests/test_app.py` | nothing (in-memory SQLite) | `pytest -m "not integration and not e2e"` |
| Integration | `Tests/integration` | PostgreSQL; database name must contain `test` | `TEST_DATABASE_URL=postgresql://app:app@localhost:5432/apptest pytest Tests/integration -m integration` |
| End-to-end | `Tests/e2e` | the app running, `python -m playwright install chromium` | `E2E_BASE_URL=http://localhost:8080 pytest Tests/e2e -m e2e` |

In CI the integration suite fails rather than skips if no database is configured, so a
misconfigured pipeline cannot pass with zero tests run.

## Monitoring

The container runs gunicorn, which writes one JSON line per request to stdout, including
`latency_ms`. With the container's logs shipped to CloudWatch Logs, a metric filter on
`{ $.latency_ms = * }` turns this into an HTTP latency metric beside the CloudWatch agent's CPU,
memory, disk and network metrics.
