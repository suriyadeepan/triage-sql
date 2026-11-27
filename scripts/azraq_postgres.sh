#!/usr/bin/env bash
set -euo pipefail

container_name="triage-sql-azraq-postgres"
volume_name="triage-sql-azraq-postgres-data"
image="postgres:18.7-bookworm@sha256:e742a2668255221388004f3a42b6150a2103f5054ab3a4a93ae9e4f01e551c35"
port="${AZRAQ_PG_PORT:-55432}"
database_password="${POSTGRES_PASSWORD:-azraq_local_only}"
action="${1:-start}"

case "$action" in
  start)
    if docker container inspect "$container_name" >/dev/null 2>&1; then
      docker start "$container_name" >/dev/null
    else
      docker volume create "$volume_name" >/dev/null
      docker run --detach \
        --name "$container_name" \
        --env POSTGRES_USER=azraq \
        --env "POSTGRES_PASSWORD=$database_password" \
        --env POSTGRES_DB=azraq \
        --publish "127.0.0.1:$port:5432" \
        --volume "$volume_name:/var/lib/postgresql" \
        "$image" >/dev/null
    fi

    ready=0
    for _ in {1..60}; do
      if docker exec "$container_name" pg_isready --username=azraq --dbname=azraq >/dev/null 2>&1; then
        ready=1
        break
      fi
      sleep 1
    done
    if [[ "$ready" != 1 ]]; then
      printf '%s\n' 'PostgreSQL did not become ready within 60 seconds.' >&2
      exit 1
    fi
    printf 'PostgreSQL 18.7 is ready on 127.0.0.1:%s (database azraq).\n' "$port"
    ;;
  stop)
    docker stop "$container_name" >/dev/null
    printf '%s\n' 'PostgreSQL container stopped; its named data volume was retained.'
    ;;
  status)
    docker container inspect "$container_name" --format '{{.State.Status}}'
    ;;
  *)
    printf 'Usage: %s {start|stop|status}\n' "$0" >&2
    exit 2
    ;;
esac
