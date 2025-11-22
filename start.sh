#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

SCENARIO="${1:-normal}"
PORT="${PORT:-8501}"

echo "==> Starting EV Charge WS Demo"
echo "    Scenario: ${SCENARIO}"
echo "    Dashboard port: ${PORT}"

# Python venv
if [ ! -d ".venv" ]; then
  echo "==> Creating virtualenv .venv"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing dependencies"
pip install -q --upgrade pip
pip install -q -r requirements.txt

mkdir -p data .pids

# Start server
echo "==> Launching server.py"
python server.py > data/server.log 2>&1 &
echo $! > .pids/server.pid

sleep 1

# Start station with scenario
echo "==> Launching station.py --scenario ${SCENARIO}"
python station.py --scenario "${SCENARIO}" > data/station.log 2>&1 &
echo $! > .pids/station.pid

# Start streamlit dashboard
echo "==> Launching Streamlit dashboard on http://localhost:${PORT}"
streamlit run streamlit_app.py --server.port "${PORT}" > data/streamlit.log 2>&1 &
echo $! > .pids/streamlit.pid

echo "==> All processes launched."
echo "    - Server log:    $(pwd)/data/server.log"
echo "    - Station log:   $(pwd)/data/station.log"
echo "    - Streamlit log: $(pwd)/data/streamlit.log"
echo "==> To stop everything: ./stop.sh"
