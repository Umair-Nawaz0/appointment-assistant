#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "Stopping AI Appointment Assistant & n8n Docker Stack..."
docker compose --project-directory "${PROJECT_DIR}" down "$@"
echo "Stack stopped successfully."
