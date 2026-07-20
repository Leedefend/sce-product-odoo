#!/usr/bin/env bash
set -euo pipefail

project="${CI_PROJECT_NAME:-}"
workspace="${GITHUB_WORKSPACE:-}"
runner_temp="${RUNNER_TEMP:-}"
run_id="${GITHUB_RUN_ID:-}"

if [[ ! "${project}" =~ ^sc-prof-[0-9]+$ ]]; then
  echo "[self_hosted_cleanup] invalid project scope" >&2
  exit 2
fi
if [[ -z "${workspace}" || "${workspace}" == "/" || "${workspace}" == "${HOME:-}" ]]; then
  echo "[self_hosted_cleanup] invalid workspace scope" >&2
  exit 2
fi

if command -v docker >/dev/null 2>&1; then
  docker compose -p "${project}" down -v --remove-orphans >/dev/null 2>&1 || true
  docker ps -aq --filter "label=com.docker.compose.project=${project}" |
    xargs -r docker rm -f >/dev/null 2>&1 || true
  docker volume ls -q --filter "label=com.docker.compose.project=${project}" |
    xargs -r docker volume rm -f >/dev/null 2>&1 || true
  docker network ls -q --filter "label=com.docker.compose.project=${project}" |
    xargs -r docker network rm >/dev/null 2>&1 || true
fi

if [[ -n "${runner_temp}" && -d "${runner_temp}" && -n "${run_id}" ]]; then
  find "${runner_temp}" -mindepth 1 -maxdepth 1 \
    -name "sce-ci-${run_id}-*" -exec rm -rf -- {} +
fi

find "${workspace}" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
echo "[self_hosted_cleanup] PASS project=${project}"
