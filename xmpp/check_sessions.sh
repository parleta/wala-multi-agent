#!/usr/bin/env bash
set -euo pipefail

XMPP_CONTAINER="${XMPP_CONTAINER:-wala-xmpp}"

docker exec "$XMPP_CONTAINER" ejabberdctl connected_users | sort
