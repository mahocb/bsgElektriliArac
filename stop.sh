#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Stopping EV Charge WS Demo"

kill_safe () {
  local name="$1"
  local file=".pids/${name}.pid"
  if [ -f "${file}" ]; then
    local pid
    pid=$(cat "${file}" || true)
    if [ -n "${pid}" ] && ps -p "${pid}" > /dev/null 2>&1; then
      echo " - Killing ${name} (pid ${pid})"
      kill "${pid}" || true
      sleep 0.5
      if ps -p "${pid}" > /dev/null 2>&1; then
        echo "   Force killing ${name}"
        kill -9 "${pid}" || true
      fi
    else
      echo " - ${name} not running"
    fi
    rm -f "${file}"
  else
    echo " - No pid file for ${name}"
  fi
}

kill_safe "station"
kill_safe "server"
kill_safe "streamlit"

echo "==> Stopped. (You can delete .pids/ and check logs in data/)"
