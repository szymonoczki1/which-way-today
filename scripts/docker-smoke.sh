#!/usr/bin/env bash
# End-to-end check of the Docker setup: build, start, probe, restart, clean up.
#
#   scripts/docker-smoke.sh [repo_dir]
#
# Uses its own compose project name and non-default host ports (override with
# BACKEND_PORT / FRONTEND_PORT), so it never touches your dev containers, your
# local backend on :8000, or their data. Everything it creates (containers,
# volume, images) is removed at the end.
set -euo pipefail

REPO_DIR="$(cd "${1:-$(dirname "$0")/..}" && pwd)"
export BACKEND_PORT="${BACKEND_PORT:-8010}"
export FRONTEND_PORT="${FRONTEND_PORT:-5180}"
export COMPOSE_PROJECT_NAME="whichway-smoke"
API="http://localhost:${BACKEND_PORT}"
WEB="http://localhost:${FRONTEND_PORT}"

compose() { docker compose --project-directory "$REPO_DIR" -f "$REPO_DIR/docker-compose.yml" "$@"; }
fail() { echo "FAIL: $*" >&2; compose logs --tail=40 >&2 || true; exit 1; }
pass() { echo "ok   $*"; }
cleanup() { compose down -v --rmi local --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT

wait_healthy() {
  for _ in $(seq 1 60); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$(compose ps -q backend)" 2>/dev/null)" = healthy ] && return 0
    sleep 1
  done
  return 1
}

echo "== building and starting (backend :$BACKEND_PORT, frontend :$FRONTEND_PORT) from $REPO_DIR"
cleanup
compose up --build -d --wait --wait-timeout 180 >/dev/null || fail "compose up"

wait_healthy || fail "backend never became healthy"
pass "backend container reports healthy"

[ "$(curl -sf "$API/health")" = '{"status":"ok"}' ] || fail "GET /health"
pass "GET /health"

html="$(curl -sf "$WEB/")" || fail "frontend not reachable"
grep -q "<title>Which Way Today?</title>" <<<"$html" || fail "frontend index.html"
pass "frontend serves index.html"

# SPA fallback: unknown paths must still get the app, not nginx's 404.
curl -sf "$WEB/some/deep/link" | grep -q "<title>Which Way Today?</title>" || fail "SPA fallback"
pass "frontend falls back to index.html for unknown paths"

js_path="$(grep -o '/assets/index-[^"]*\.js' <<<"$html" | head -1)"
[ -n "$js_path" ] || fail "no JS bundle referenced in index.html"
# grep -c reads to EOF; grep -q could exit early and SIGPIPE curl under pipefail.
[ "$(curl -sf "$WEB$js_path" | grep -c "$API")" -gt 0 ] || fail "bundle does not contain VITE_API_URL=$API"
pass "bundle has the browser-reachable API URL baked in ($API)"

allow="$(curl -s -o /dev/null -D - -X OPTIONS "$API/trips" \
  -H "Origin: $WEB" -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type' | tr -d '\r' |
  awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}')"
[ "$allow" = "$WEB" ] || fail "CORS preflight from $WEB (got '$allow')"
pass "CORS allows the Docker frontend origin"

trip='{"name":"Smoke","origin_address":"A","origin_lat":54.35,"origin_lon":18.64,"destination_address":"B","destination_lat":54.37,"destination_lon":18.61,"usual_departure_time":null}'
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/trips" -H 'Content-Type: application/json' -d "$trip")"
[ "$code" = 201 ] || fail "POST /trips returned $code (DB not writable?)"
pass "POST /trips writes to the SQLite volume"

compose exec -T backend test -s /data/whichway.db || fail "no database file on the /data volume"
# Recreate (not restart) the container: a restart keeps its writable layer, so
# data would survive even without the named volume.
compose up -d --force-recreate --wait backend >/dev/null || fail "recreating backend"
wait_healthy || fail "backend unhealthy after recreate"
[ "$(curl -sf "$API/trips" | grep -c '"name":"Smoke"')" -gt 0 ] || fail "trip lost after recreating the container"
pass "trip survives recreating the backend container (named volume)"

user="$(compose exec -T backend id -u)" || fail "exec into backend"
[ "$user" != 0 ] || fail "backend runs as root"
pass "backend runs as non-root (uid $user)"

echo "== all Docker smoke checks passed"
