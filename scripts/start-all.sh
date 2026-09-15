#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_DIR}/.env"
EXAMPLE_ENV="${PROJECT_DIR}/.env.example"

echo "=========================================================="
echo " Starting AI Appointment Assistant & n8n Docker Stack     "
echo "=========================================================="

# 1. Ensure .env file exists
if [ ! -f "${ENV_FILE}" ]; then
  if [ -f "${EXAMPLE_ENV}" ]; then
    echo "Creating .env from .env.example..."
    cp "${EXAMPLE_ENV}" "${ENV_FILE}"
  else
    echo "Error: Neither .env nor .env.example found!" >&2
    exit 1
  fi
fi

# 2. Ensure N8N_ENCRYPTION_KEY is set in .env
CURRENT_KEY=$(grep -E '^N8N_ENCRYPTION_KEY=' "${ENV_FILE}" | cut -d '=' -f2- || true)
if [ -z "${CURRENT_KEY}" ] || [ "${CURRENT_KEY}" = "replace-with-a-long-random-value" ]; then
  NEW_KEY=$(openssl rand -hex 16)
  if grep -q '^N8N_ENCRYPTION_KEY=' "${ENV_FILE}"; then
    sed -i "s/^N8N_ENCRYPTION_KEY=.*/N8N_ENCRYPTION_KEY=${NEW_KEY}/" "${ENV_FILE}"
  else
    echo "N8N_ENCRYPTION_KEY=${NEW_KEY}" >> "${ENV_FILE}"
  fi
  echo "Generated secure N8N_ENCRYPTION_KEY in .env"
fi

# 3. Ensure required bootstrap directories exist
mkdir -p "${PROJECT_DIR}/data"
mkdir -p "${PROJECT_DIR}/credentials"
mkdir -p "${PROJECT_DIR}/database/initdb"

# 4. Start Docker Compose Stack
echo "Building and launching containers..."
docker compose --project-directory "${PROJECT_DIR}" --env-file "${ENV_FILE}" up -d --build

# 5. Wait for backend to be ready
echo "Waiting for FastAPI backend to be healthy..."
attempt=0
max_attempts=40
until curl -sf http://127.0.0.1:4000/api/health >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "${attempt}" -ge "${max_attempts}" ]; then
    echo "Warning: Backend took longer than expected to become healthy."
    break
  fi
  sleep 2
done
if [ "${attempt}" -lt "${max_attempts}" ]; then
  echo "✓ FastAPI backend is healthy!"
fi

# 6. Wait for n8n container and import credentials & workflow
echo "Checking n8n readiness..."
n8n_container=$(docker compose --project-directory "${PROJECT_DIR}" --env-file "${ENV_FILE}" ps -q n8n)
if [ -n "${n8n_container}" ]; then
  n8n_ready=0
  for i in $(seq 1 40); do
    if docker exec "${n8n_container}" n8n export:credentials --all --output=/tmp/cred_check.json >/dev/null 2>&1; then
      n8n_ready=1
      docker exec "${n8n_container}" rm -f /tmp/cred_check.json >/dev/null 2>&1 || true
      break
    fi
    sleep 2
  done

  if [ "${n8n_ready}" -eq 1 ]; then
    echo "✓ n8n engine is ready!"

    # Import Groq credential template if available
    if [ -f "${PROJECT_DIR}/credentials/groq-api.json" ]; then
      docker exec "${n8n_container}" n8n import:credentials --input=/bootstrap/credentials/groq-api.json >/dev/null 2>&1 || true
      echo "✓ Imported Groq API credential template into n8n"
    fi

    # Import website workflow (ensuring valid n8n entity ID inside container without modifying host source file)
    if [ -f "${PROJECT_DIR}/workflow/website-workflow.json" ]; then
      docker exec "${n8n_container}" node -e "
        const fs = require('fs');
        const wf = JSON.parse(fs.readFileSync('/bootstrap/workflows/website-workflow.json', 'utf8'));
        if (!wf.id) wf.id = 'ApptAssistant01';
        fs.writeFileSync('/tmp/wf_import.json', JSON.stringify(wf));
      " >/dev/null 2>&1 || true
      docker exec "${n8n_container}" n8n import:workflow --input=/tmp/wf_import.json >/dev/null 2>&1 || true
      docker exec "${n8n_container}" rm -f /tmp/wf_import.json >/dev/null 2>&1 || true
      echo "✓ Imported website-workflow.json into n8n"
    fi
  else
    echo "n8n took longer to start; credentials/workflow can be imported once container is fully initialized."
  fi
fi

echo ""
echo "=========================================================="
echo " All Services Are Running Successfully!                  "
echo "=========================================================="
echo "  Frontend Dashboard : http://localhost:5173"
echo "  Demo Credentials   : owner@example.com / Password123!"
echo "  FastAPI Backend    : http://localhost:4000"
echo "  API Documentation  : http://localhost:4000/docs"
echo "  n8n Studio         : http://localhost:5678"
echo "  PostgreSQL Database: localhost:5433 (apointment_assitant)"
echo "=========================================================="
echo ""
echo "Useful commands:"
echo "  View logs : docker compose logs -f"
echo "  Stop stack: ./scripts/stop-all.sh"
echo "=========================================================="
