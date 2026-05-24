#!/usr/bin/env bash
# 用法:
#   ./start.sh start          启动 api + worker + web
#   ./start.sh stop           停止全部
#   ./start.sh restart        重启
#   ./start.sh status         查看状态
#   ./start.sh migrate        仅数据库迁移
#   ./start.sh seed           导入种子数据
#   ./start.sh build-web      仅构建前端（不启动）
#
# 环境变量:
#   ENV_FILE      默认 .env.production
#   CONDA_ENV     默认 wcguess

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env.production}"
CONDA_ENV="${CONDA_ENV:-wcguess}"
API_DIR="$ROOT/services/api"
WEB_DIR="$ROOT/apps/web"
RUN_DIR="$ROOT/.run"
LOG_DIR="$ROOT/logs"

API_PID="$RUN_DIR/api.pid"
WORKER_PID="$RUN_DIR/worker.pid"
WEB_PID="$RUN_DIR/web.pid"

mkdir -p "$RUN_DIR" "$LOG_DIR"

load_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "[错误] 缺少 $ENV_FILE，请先: cp .env.production.example .env.production"
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
}

conda_activate() {
  if [[ -n "${CONDA_PREFIX:-}" && "${CONDA_DEFAULT_ENV:-}" == "$CONDA_ENV" ]]; then
    return 0
  fi
  if [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
  elif [[ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
  elif [[ -f "/opt/conda/etc/profile.d/conda.sh" ]]; then
    # shellcheck disable=SC1091
    source "/opt/conda/etc/profile.d/conda.sh"
  else
    eval "$(conda shell.bash hook)"
  fi
  conda activate "$CONDA_ENV"
}

is_running() {
  local pid_file=$1
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid=$(cat "$pid_file")
  kill -0 "$pid" 2>/dev/null
}

stop_one() {
  local name=$1
  local pid_file=$2
  if is_running "$pid_file"; then
    local pid
    pid=$(cat "$pid_file")
    echo "[停止] $name (pid $pid)"
    kill "$pid" 2>/dev/null || true
    sleep 1
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
}

cmd_stop() {
  stop_one "web" "$WEB_PID"
  stop_one "worker" "$WORKER_PID"
  stop_one "api" "$API_PID"
  echo "[完成] 已停止"
}

cmd_migrate() {
  load_env
  conda_activate
  cd "$API_DIR"
  echo "[迁移] alembic upgrade head"
  alembic upgrade head
}

cmd_seed() {
  load_env
  conda_activate
  cd "$API_DIR"
  echo "[种子] python -m app.scripts.seed"
  python -m app.scripts.seed
}

cmd_build_web() {
  load_env
  cd "$WEB_DIR"
  if [[ -z "${NEXT_PUBLIC_API_URL:-}" ]]; then
    echo "[错误] .env.production 中未设置 NEXT_PUBLIC_API_URL"
    exit 1
  fi
  echo "[构建] 前端 NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL"
  npm ci
  npm run build
  echo "[完成] 前端已构建"
}

start_api() {
  if is_running "$API_PID"; then
    echo "[跳过] api 已在运行 (pid $(cat "$API_PID"))"
    return
  fi
  conda_activate
  cd "$API_DIR"
  echo "[启动] api → http://127.0.0.1:8000  日志: $LOG_DIR/api.log"
  nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 \
    >>"$LOG_DIR/api.log" 2>&1 &
  echo $! >"$API_PID"
}

start_worker() {
  if is_running "$WORKER_PID"; then
    echo "[跳过] worker 已在运行 (pid $(cat "$WORKER_PID"))"
    return
  fi
  conda_activate
  cd "$API_DIR"
  echo "[启动] worker  日志: $LOG_DIR/worker.log"
  nohup arq app.workers.settings.WorkerSettings \
    >>"$LOG_DIR/worker.log" 2>&1 &
  echo $! >"$WORKER_PID"
}

start_web() {
  if is_running "$WEB_PID"; then
    echo "[跳过] web 已在运行 (pid $(cat "$WEB_PID"))"
    return
  fi
  cd "$WEB_DIR"
  if [[ ! -d "$WEB_DIR/.next" ]]; then
    echo "[提示] 未检测到 .next，先执行构建..."
    cmd_build_web
  fi
  echo "[启动] web → http://127.0.0.1:3000  日志: $LOG_DIR/web.log"
  nohup npm run start -- -H 127.0.0.1 -p 3000 \
    >>"$LOG_DIR/web.log" 2>&1 &
  echo $! >"$WEB_PID"
}

cmd_start() {
  load_env
  cmd_migrate
  start_api
  sleep 1
  start_worker
  start_web
  sleep 2
  cmd_status
}

cmd_status() {
  check_one() {
    local name=$1
    local pid_file=$2
    local url=${3:-}
    if is_running "$pid_file"; then
      echo "  $name: 运行中 (pid $(cat "$pid_file"))${url:+  $url}"
    else
      echo "  $name: 未运行"
    fi
  }
  echo "进程状态:"
  check_one "api" "$API_PID" "http://127.0.0.1:8000/health"
  check_one "worker" "$WORKER_PID"
  check_one "web" "$WEB_PID" "http://127.0.0.1:3000"
}

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \?//'
}

main() {
  local cmd="${1:-start}"
  case "$cmd" in
    start) cmd_start ;;
    stop) cmd_stop ;;
    restart) cmd_stop; cmd_start ;;
    status) cmd_status ;;
    migrate) load_env; cmd_migrate ;;
    seed) cmd_seed ;;
    build-web) load_env; cmd_build_web ;;
    -h | help) usage ;;
    *)
      echo "未知命令: $cmd"
      usage
      exit 1
      ;;
  esac
}

main "${@:-start}"
