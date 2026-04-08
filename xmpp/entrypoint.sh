#!/bin/sh
set -eu

MARKER_FILE="/home/ejabberd/database/.users_bootstrapped"
rm -f "$MARKER_FILE"

term_handler() {
  if [ -n "${EJABBERD_PID:-}" ]; then
    kill -TERM "$EJABBERD_PID" 2>/dev/null || true
    wait "$EJABBERD_PID" 2>/dev/null || true
  fi
  exit 0
}

trap term_handler INT TERM

ejabberdctl foreground &
EJABBERD_PID=$!

attempt=0
until ejabberdctl status >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -gt 120 ]; then
    echo "ERROR: ejabberd did not become ready in time"
    kill -TERM "$EJABBERD_PID" 2>/dev/null || true
    wait "$EJABBERD_PID" 2>/dev/null || true
    exit 1
  fi
  sleep 1
done

/bootstrap/bootstrap_users.sh

touch "$MARKER_FILE"

echo "XMPP bootstrap complete"

wait "$EJABBERD_PID"
