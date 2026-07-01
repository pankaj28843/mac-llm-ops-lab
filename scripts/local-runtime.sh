#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="${MAC_LLM_OPS_PID_DIR:-$ROOT_DIR/artifacts/runtime/pids}"
LOG_DIR="${MAC_LLM_OPS_LOG_DIR:-$ROOT_DIR/artifacts/runtime/logs}"

DOCS_HOST="${DOCS_HOST:-127.0.0.1}"
DOCS_PORT="${DOCS_PORT:-28080}"
DOCS_PID_FILE="${DOCS_PID_FILE:-$PID_DIR/mkdocs.pid}"
NATIVE_API_PID_FILE="${NATIVE_API_PID_FILE:-$PID_DIR/model-backed-api.pid}"
VLLM_MLX_PID_FILE="${VLLM_MLX_PID_FILE:-$PID_DIR/vllm-mlx.pid}"

MAC_LLM_OPS_START_DOCS="${MAC_LLM_OPS_START_DOCS:-true}"
MAC_LLM_OPS_START_TIMEOUT_SECONDS="${MAC_LLM_OPS_START_TIMEOUT_SECONDS:-180}"
MAC_LLM_OPS_DOWN_KILL_PORTS="${MAC_LLM_OPS_DOWN_KILL_PORTS:-28080 28020 28100 28000}"

mkdir -p "$PID_DIR" "$LOG_DIR"

usage() {
  cat <<'EOF'
Usage:
  scripts/local-runtime.sh <start|start-docker|stop|stop-managed|stop-docker-vllm|stop-ports|status>

Environment:
  MAC_LLM_OPS_START_DOCS=true|false     Start MkDocs on make up.
  MAC_LLM_OPS_START_TIMEOUT_SECONDS=180 Seconds to wait for host listeners.
  MAC_LLM_OPS_DOWN_KILL_PORTS="..."     Project host ports to clean on down.
EOF
}

pid_is_running() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

read_pid_file() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    tr -d '[:space:]' < "$pid_file"
  fi
}

start_service() {
  local name="$1"
  local pid_file="$2"
  local log_file="$3"
  local port="$4"
  shift 4

  local existing_pid
  existing_pid="$(read_pid_file "$pid_file")"
  if pid_is_running "$existing_pid"; then
    printf '%s already running: pid %s\n' "$name" "$existing_pid"
    return 0
  fi

  rm -f "$pid_file"
  uv run python scripts/start-detached.py \
    --pid-file "$pid_file" \
    --log-file "$log_file" \
    --cwd "$ROOT_DIR" \
    -- "$@"

  local started_pid
  started_pid="$(read_pid_file "$pid_file")"
  local deadline=$((SECONDS + MAC_LLM_OPS_START_TIMEOUT_SECONDS))
  local listener_pid=""

  while (( SECONDS < deadline )); do
    if [[ -n "$port" ]]; then
      listener_pid="$(project_listener_pid_for_port "$port")"
    fi

    if [[ -n "$listener_pid" ]]; then
      printf '%s\n' "$listener_pid" > "$pid_file"
      printf 'started %s: pid %s, log %s\n' "$name" "$listener_pid" "$log_file"
      return 0
    fi

    if ! pid_is_running "$started_pid"; then
      rm -f "$pid_file"
      printf 'failed to start %s; see %s\n' "$name" "$log_file" >&2
      return 1
    fi

    sleep 1
  done

  rm -f "$pid_file"
  printf 'timed out waiting for %s on port %s; see %s\n' "$name" "$port" "$log_file" >&2
  return 1
}

stop_pid_file() {
  local name="$1"
  local pid_file="$2"
  local pid
  pid="$(read_pid_file "$pid_file")"

  if ! pid_is_running "$pid"; then
    rm -f "$pid_file"
    printf '%s not running\n' "$name"
    return 0
  fi

  terminate_pid "$name" "$pid"
  rm -f "$pid_file"
}

project_process_command() {
  local pid="$1"
  ps -p "$pid" -o command= 2>/dev/null || true
}

is_project_host_process() {
  local command="$1"
  [[ "$command" == *"$ROOT_DIR"* ]] && return 0
  [[ "$command" == *"mkdocs serve"* ]] && return 0
  [[ "$command" == *"mac_llm_ops_lab.cli:app"* ]] && return 0
  [[ "$command" == *"run-model-backed-api.sh"* ]] && return 0
  [[ "$command" == *"run-vllm-mlx-backend.sh"* ]] && return 0
  [[ "$command" == *"vllm-mlx serve"* ]] && return 0
  [[ "$command" == *"vllm_mlx"* ]] && return 0
  return 1
}

project_listener_pid_for_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi

  local pid
  for pid in $pids; do
    local command
    command="$(project_process_command "$pid")"
    if is_project_host_process "$command"; then
      printf '%s\n' "$pid"
      return 0
    fi
  done
}

terminate_pid() {
  local name="$1"
  local pid="$2"

  if ! pid_is_running "$pid"; then
    return 0
  fi

  printf 'stopping %s: pid %s\n' "$name" "$pid"
  kill "$pid" 2>/dev/null || true

  local attempt
  for attempt in 1 2 3 4 5; do
    if ! pid_is_running "$pid"; then
      return 0
    fi
    sleep 1
  done

  printf 'force stopping %s: pid %s\n' "$name" "$pid"
  kill -9 "$pid" 2>/dev/null || true
}

stop_known_project_processes() {
  if ! command -v pgrep >/dev/null 2>&1; then
    return 0
  fi

  local patterns=(
    "mkdocs serve"
    "mac_llm_ops_lab.cli:app"
    "run-model-backed-api.sh"
    "run-vllm-mlx-backend.sh"
    "vllm-mlx serve"
    "vllm_mlx"
  )

  local pattern
  for pattern in "${patterns[@]}"; do
    local pids
    pids="$(pgrep -f "$pattern" 2>/dev/null || true)"
    if [[ -z "$pids" ]]; then
      continue
    fi

    local pid
    for pid in $pids; do
      if [[ "$pid" == "$$" || "$pid" == "$PPID" ]]; then
        continue
      fi

      local command
      command="$(project_process_command "$pid")"
      if is_project_host_process "$command"; then
        terminate_pid "project host process" "$pid"
      fi
    done
  done
}

stop_port_listeners() {
  local port
  for port in $MAC_LLM_OPS_DOWN_KILL_PORTS; do
    local pids
    pids="$(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -z "$pids" ]]; then
      continue
    fi

    local pid
    for pid in $pids; do
      local command
      command="$(project_process_command "$pid")"
      if is_project_host_process "$command"; then
        printf 'stopping project host listener on port %s: pid %s\n' "$port" "$pid"
        terminate_pid "project host listener on port $port" "$pid"
      else
        printf 'leaving non-project listener on port %s: pid %s %s\n' "$port" "$pid" "$command"
      fi
    done
  done
}

stop_docker_vllm_containers() {
  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi

  local rows
  rows="$(
    docker ps \
      --format '{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Command}}' \
      2>/dev/null || true
  )"
  if [[ -z "$rows" ]]; then
    return 0
  fi

  while IFS=$'\t' read -r container_id container_name image command; do
    local haystack
    haystack="$(printf '%s %s %s\n' "$container_name" "$image" "$command" | tr '[:upper:]' '[:lower:]')"
    if [[ "$haystack" =~ vllm|vllm_mlx|vllm-mlx|mlx ]]; then
      printf 'stopping docker vllm/mlx container: %s %s\n' "$container_name" "$container_id"
      docker stop "$container_id" >/dev/null
    fi
  done <<< "$rows"
}

docker_is_running() {
  command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

start_docker_desktop() {
  if docker_is_running; then
    return 0
  fi
  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi

  printf 'starting Docker Desktop\n'
  docker desktop start >/dev/null 2>&1 || true

  local attempt
  for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    if docker_is_running; then
      return 0
    fi
    sleep 2
  done

  printf 'Docker Desktop did not become ready\n' >&2
  return 1
}

print_service_status() {
  local name="$1"
  local pid_file="$2"
  local port="$3"
  local pid
  pid="$(read_pid_file "$pid_file")"

  if pid_is_running "$pid"; then
    printf '  %-18s running pid=%s port=%s\n' "$name" "$pid" "$port"
  else
    printf '  %-18s stopped port=%s\n' "$name" "$port"
  fi
}

start_services() {
  start_service \
    "vllm-mlx" \
    "$VLLM_MLX_PID_FILE" \
    "$LOG_DIR/vllm-mlx.log" \
    "${VLLM_MLX_PORT:-28100}" \
    scripts/run-vllm-mlx-backend.sh
  start_service \
    "model-backed-api" \
    "$NATIVE_API_PID_FILE" \
    "$LOG_DIR/model-backed-api.log" \
    "${API_PORT:-28020}" \
    scripts/run-model-backed-api.sh

  if [[ "$MAC_LLM_OPS_START_DOCS" == "true" ]]; then
    start_service \
      "mkdocs" \
      "$DOCS_PID_FILE" \
      "$LOG_DIR/mkdocs.log" \
      "$DOCS_PORT" \
      uv run mkdocs serve --no-livereload -a "$DOCS_HOST:$DOCS_PORT"
  fi
}

stop_managed_services() {
  stop_pid_file "model-backed-api" "$NATIVE_API_PID_FILE"
  stop_pid_file "vllm-mlx" "$VLLM_MLX_PID_FILE"
  stop_pid_file "mkdocs" "$DOCS_PID_FILE"
  stop_known_project_processes
}

status_services() {
  printf 'Project-managed host services:\n'
  print_service_status "mkdocs" "$DOCS_PID_FILE" "$DOCS_PORT"
  print_service_status "model-backed-api" "$NATIVE_API_PID_FILE" "${API_PORT:-28020}"
  print_service_status "vllm-mlx" "$VLLM_MLX_PID_FILE" "${VLLM_MLX_PORT:-28100}"
}

case "${1:-}" in
  start)
    start_services
    ;;
  start-docker)
    start_docker_desktop
    ;;
  stop)
    stop_managed_services
    stop_docker_vllm_containers
    stop_port_listeners
    ;;
  stop-managed)
    stop_managed_services
    ;;
  stop-docker-vllm)
    stop_docker_vllm_containers
    ;;
  stop-ports)
    stop_port_listeners
    ;;
  status)
    status_services
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage
    exit 2
    ;;
esac
