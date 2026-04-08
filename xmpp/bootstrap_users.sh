#!/bin/sh
set -eu

XMPP_DOMAIN="${XMPP_DOMAIN:-xmpp.local}"

# Format: user:password, space-separated
XMPP_USERS="${XMPP_USERS:-orchestrator:orchestrator123 calendar_agent:calendar123 maps_agent:maps123 bot_bridge:botbridge123}"

for entry in $XMPP_USERS; do
  user="${entry%%:*}"
  pass="${entry#*:}"

  if ejabberdctl check_account "$user" "$XMPP_DOMAIN" >/dev/null 2>&1; then
    echo "already exists: ${user}@${XMPP_DOMAIN}"
  else
    echo "creating: ${user}@${XMPP_DOMAIN}"
    ejabberdctl register "$user" "$XMPP_DOMAIN" "$pass"
  fi
done

echo "registered users:"
ejabberdctl registered_users "$XMPP_DOMAIN" | sort
