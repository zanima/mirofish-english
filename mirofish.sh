#!/usr/bin/env bash
# MiroFish management script
# Usage: ./mirofish.sh [start|stop|restart|status|logs]

set -e

COMPOSE_FILE="$(cd "$(dirname "$0")" && pwd)/docker-compose.yml"
SERVICE="mirofish"

ensure_docker() {
  if ! docker info &>/dev/null; then
    echo "Docker is not running. Starting Docker Desktop..."
    open -a "Docker"
    echo -n "Waiting for Docker"
    for i in $(seq 1 30); do
      sleep 2
      if docker info &>/dev/null; then
        echo " ready."
        return
      fi
      echo -n "."
    done
    echo ""
    echo "Error: Docker did not start in time. Please open Docker Desktop manually and try again."
    exit 1
  fi
}

case "$1" in
  start)
    ensure_docker
    echo "Starting MiroFish..."
    docker compose -f "$COMPOSE_FILE" up -d
    echo "MiroFish is running at http://localhost:3000"
    ;;
  stop)
    ensure_docker
    echo "Stopping MiroFish..."
    docker compose -f "$COMPOSE_FILE" down
    echo "MiroFish stopped."
    ;;
  restart)
    ensure_docker
    echo "Restarting MiroFish..."
    docker compose -f "$COMPOSE_FILE" down
    docker compose -f "$COMPOSE_FILE" up -d
    echo "MiroFish restarted at http://localhost:3000"
    ;;
  status)
    ensure_docker
    docker compose -f "$COMPOSE_FILE" ps
    ;;
  logs)
    ensure_docker
    docker compose -f "$COMPOSE_FILE" logs -f "$SERVICE"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}"
    exit 1
    ;;
esac
