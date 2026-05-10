#!/usr/bin/env bash
# Start backend and frontend for local development.
# Run from project root: ./scripts/start-dev.sh

set -e
cd "$(dirname "$0")/.."

echo "=== ReloPass local dev ==="

# Backend
if ! lsof -i :8000 > /dev/null 2>&1; then
  echo "Starting backend on http://localhost:8000 ..."
  source backend/.venv/bin/activate
  python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
  BACKEND_PID=$!
  sleep 3
  if curl -s http://localhost:8000/health > /dev/null; then
    echo "Backend OK"
  else
    echo "Backend failed to start"
    exit 1
  fi
else
  echo "Backend already running on :8000"
fi

# Frontend
if ! lsof -i :5173 > /dev/null 2>&1; then
  echo "Starting frontend on http://localhost:5173 ..."
  (cd frontend && npm run dev) &
  echo "Frontend starting..."
else
  echo "Frontend already running on :5173"
fi

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop (or close this terminal)"
wait
