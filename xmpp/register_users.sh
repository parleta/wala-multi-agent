#!/usr/bin/env bash
set -euo pipefail

XMPP_CONTAINER="${XMPP_CONTAINER:-wala-xmpp}"
XMPP_DOMAIN="${XMPP_DOMAIN:-xmpp.local}"

declare -a USERS=(
  "orchestrator:orchestrator123"
  "calendar_agent:calendar123"
  "maps_agent:maps123"
  "bot_bridge:botbridge123"
)

for entry in "${USERS[@]}"; do
  user="${entry%%:*}"
  pass="${entry#*:}"

  if docker exec "$XMPP_CONTAINER" ejabberdctl check_account "$user" "$XMPP_DOMAIN" >/dev/null 2>&1; then
    echo "already exists: ${user}@${XMPP_DOMAIN}"
  else
    echo "creating: ${user}@${XMPP_DOMAIN}"
    docker exec "$XMPP_CONTAINER" ejabberdctl register "$user" "$XMPP_DOMAIN" "$pass"
  fi
done

echo
echo "registered users:"
docker exec "$XMPP_CONTAINER" ejabberdctl registered_users "$XMPP_DOMAIN" | sort
