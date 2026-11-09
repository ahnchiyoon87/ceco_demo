#!/bin/sh
set -eu
case "${PORTAL_CONTROL_TOKEN:-}" in
  ''|CHANGE_ME|*[!a-f0-9]*) echo 'Portal control token is not configured.' >&2; exit 1;;
esac
if [ "${#PORTAL_CONTROL_TOKEN}" -lt 32 ]; then exit 1; fi
umask 077
mkdir -p /etc/nginx/snippets
printf 'proxy_set_header X-Portal-Token "%s";\n' "$PORTAL_CONTROL_TOKEN" > /etc/nginx/snippets/portal-token.conf
# Runtime only: the host gate password never enters the frontend build or URL.
case "${FUXA_GATE_URL:-}" in
  http://host.docker.internal:[0-9]*) ;;
  *) echo 'Operator gate URL is not configured.' >&2; exit 1;;
esac
test -n "${HMI_GATE_USER:-}" && test -n "${HMI_GATE_PASSWORD:-}"
gate_auth=$(printf '%s:%s' "$HMI_GATE_USER" "$HMI_GATE_PASSWORD" | base64 | tr -d '\n')
printf 'set $operator_gate "%s";\nproxy_set_header Authorization "Basic %s";\n' "$FUXA_GATE_URL" "$gate_auth" > /etc/nginx/snippets/operator-gate.conf
