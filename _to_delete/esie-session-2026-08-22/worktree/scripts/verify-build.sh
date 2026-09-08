#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "${ROOT_DIR}/package.json" ]]; then
  echo "ERROR: package.json not found at repo root."
  exit 1
fi

if [[ ! -f "${ROOT_DIR}/frontend/package.json" ]]; then
  echo "ERROR: frontend/package.json not found."
  exit 1
fi

echo "Installing frontend dependencies..."
npm --prefix "${ROOT_DIR}/frontend" ci

echo "Building frontend..."
npm --prefix "${ROOT_DIR}/frontend" run build

if [[ ! -d "${ROOT_DIR}/frontend/dist" ]]; then
  echo "ERROR: frontend/dist not found after build."
  exit 1
fi

echo "Build verified: frontend/dist exists."
