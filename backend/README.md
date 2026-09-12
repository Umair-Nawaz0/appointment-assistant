# FastAPI backend

This is the Python backend for Appointment Assistant. It preserves the existing
`/api` contract used by the React dashboard and connects to the PostgreSQL
database configured in the project-root `.env`.

## Run with Uvicorn

From the project root:

```bash
backend/.venv/bin/uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 4000
```

Or from the `backend` directory:

```bash
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 4000
```

API health: <http://127.0.0.1:4000/api/health>

Interactive documentation: <http://127.0.0.1:4000/docs>

## Fresh installation

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Run the test suite against a test PostgreSQL database with:

```bash
.venv/bin/pytest -q tests
```
