#!/bin/bash
#
#  MobilityData 2026
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Reclaims the Docker resources left behind by the local database stack.
#
# Why this exists: each git worktree runs its own Compose project, and each
# project creates its own bridge network. Docker's default address pool only has
# room for about 31 networks, so worktrees that are deleted - or simply never
# torn down - eventually exhaust it and every `docker compose up` fails with
# "all predefined address pools have been fully subnetted", which surfaces as a
# flood of connection errors from liquibase, db-gen and the populate scripts.
#
# This script is deliberately scoped. By default it touches only the Compose
# project of the worktree you run it from. `--all` additionally reclaims
# resources of OTHER worktrees, but only ones that are demonstrably idle: it
# never removes a network that still has a container attached, and never removes
# anything from a project that has a running container. It does not run
# `docker network prune`, which would also remove unrelated non-Compose networks.
#
# Usage:
#   ./docker-localdb-cleanup.sh              # this worktree's stack only
#   ./docker-localdb-cleanup.sh --volumes    # ... and delete its database data
#   ./docker-localdb-cleanup.sh --all        # ... plus idle leftovers of other worktrees
#   ./docker-localdb-cleanup.sh --dry-run    # show what would be removed

set -u

SCRIPT_PATH="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"

REMOVE_VOLUMES=false
SWEEP_ALL=false
DRY_RUN=false

display_usage() {
  printf "\nReclaims Docker resources left behind by the local database stack.\n\n"
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  --volumes   Also delete this worktree's database volumes (destroys local data)."
  echo "  --all       Also reclaim idle leftovers from other worktrees' projects."
  echo "              Removes only: (a) networks declared by this repo's compose"
  echo "              file with no container attached, and (b) finished liquibase"
  echo "              / schemaspy job containers. Never touches a project that has"
  echo "              something running, and never removes a database container."
  echo "  --dry-run   Report what would be removed without removing it."
  echo "  --help      Display help content."
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --volumes) REMOVE_VOLUMES=true; shift ;;
    --all)     SWEEP_ALL=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    --help)    display_usage ;;
    *) echo "Unknown option: $1" >&2; display_usage ;;
  esac
done

run() {
  if [ "$DRY_RUN" = true ]; then
    echo "  [dry-run] $*"
  else
    "$@" >/dev/null 2>&1
  fi
}

# shellcheck source=./worktree-env.sh
source "$SCRIPT_PATH/worktree-env.sh"
worktree_env_compose_args

PROJECT="${COMPOSE_PROJECT_NAME:-mobility-feed-api}"

echo "==> Tearing down this worktree's stack (project: $PROJECT)"
if [ "$REMOVE_VOLUMES" = true ]; then
  echo "    including its database volumes"
  run docker compose "${WORKTREE_COMPOSE_ARGS[@]}" down --remove-orphans --volumes
else
  run docker compose "${WORKTREE_COMPOSE_ARGS[@]}" down --remove-orphans
fi

if [ "$SWEEP_ALL" != true ]; then
  echo "==> Done. Other worktrees were not touched (use --all to reclaim idle leftovers)."
  exit 0
fi

# A project is "busy" if it currently has a running container. Those are skipped
# entirely, so a worktree you are actively working in is never disturbed.
busy_projects="$(docker ps --format '{{.Label "com.docker.compose.project"}}' | sort -u)"
is_busy() {
  [ -n "$1" ] && printf '%s\n' "$busy_projects" | grep -Fxq "$1"
}

# Only this repo's one-shot job containers. Restricting by image keeps the sweep
# away from other projects that happen to use Compose: a stray postgres/postgis
# container belongs to whoever created it and holds state, so it is never
# touched here - only the disposable migration/report jobs are.
echo "==> Reclaiming finished one-shot job containers"
for image in liquibase/liquibase andrewjones/schemaspy-postgres:latest; do
  for cid in $(docker ps -a --filter status=exited --filter status=created --filter "ancestor=$image" --format '{{.ID}}'); do
    proj="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$cid" 2>/dev/null)"
    [ -z "$proj" ] && continue        # not a Compose container - leave it alone
    if is_busy "$proj"; then
      continue
    fi
    name="$(docker inspect -f '{{.Name}}' "$cid" 2>/dev/null | sed 's#^/##')"
    echo "    removing container $name (project: $proj)"
    run docker rm "$cid"
  done
done

echo "==> Reclaiming unused networks created by this repo's compose file"
# Filtered to the network declared in docker-compose.yaml ("local"), so unrelated
# Compose projects and hand-made networks are out of scope.
for net in $(docker network ls --filter label=com.docker.compose.network=local --format '{{.Name}}'); do
  proj="$(docker network inspect -f '{{index .Labels "com.docker.compose.project"}}' "$net" 2>/dev/null)"
  if is_busy "$proj"; then
    continue
  fi
  attached="$(docker network inspect -f '{{len .Containers}}' "$net" 2>/dev/null)"
  if [ "${attached:-0}" != "0" ]; then
    echo "    skipping $net ($attached container(s) still attached)"
    continue
  fi
  echo "    removing network $net"
  run docker network rm "$net"
done

echo "==> Done."
