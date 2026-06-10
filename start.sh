#!/usr/bin/env bash
# 用法:
#   ./start.sh start          启动 api + worker + web
#   ./start.sh stop           停止全部
#   ./start.sh restart        重启
#   ./start.sh status         查看状态
#   ./start.sh migrate        仅数据库迁移
#   ./start.sh seed           导入种子数据
#   ./start.sh sync-facts     从 football-data.org 同步数据概览（需 API Key）
#   ./start.sh sync-market    本地拉 Polymarket 写 .env 里的 DATABASE_URL（需翻墙）
#   ./start.sh reset-discussion [match_id]  清空某场合议，便于页面重新分析
#   ./start.sh import-matches 从 FIFA 脚本生成 seeds/matches.json
#   ./start.sh build-web      仅构建前端（不启动）
#   ./start.sh setup          仅创建 Conda 环境并安装依赖
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
    echo "[错误] 缺少 ${ENV_FILE}，请先: cp .env.production.example .env.production"
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
}

CONDA_BASE=""

find_conda_base() {
  if [[ -n "$CONDA_BASE" ]]; then
    echo "$CONDA_BASE"
    return 0
  fi
  local base=""
  if command -v conda &>/dev/null; then
    base="$(conda info --base 2>/dev/null || true)"
  fi
  if [[ -z "$base" ]]; then
    for d in "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/mambaforge" "/opt/conda"; do
      if [[ -f "$d/etc/profile.d/conda.sh" ]]; then
        base="$d"
        break
      fi
    done
  fi
  if [[ -z "$base" || ! -f "$base/etc/profile.d/conda.sh" ]]; then
    echo "[错误] 未找到 conda。请确认已安装 Miniconda，或执行: source ~/miniconda3/etc/profile.d/conda.sh" >&2
    return 1
  fi
  CONDA_BASE="$base"
  echo "$CONDA_BASE"
}

# 非交互 shell 必须先 source conda.sh，不能依赖 conda init / CONDA_SHLVL
conda_init() {
  local base
  base="$(find_conda_base)" || exit 1
  # shellcheck disable=SC1091
  source "$base/etc/profile.d/conda.sh"
}

conda_env_exists() {
  conda_init
  conda env list | tail -n +2 | awk '{print $1}' | sed 's/^\*//' | grep -Fxq "$CONDA_ENV"
}

cmd_setup() {
  conda_init
  if conda_env_exists; then
    echo "[Conda] 环境已存在: $CONDA_ENV"
  else
    echo "[Conda] 创建环境: $CONDA_ENV (Python 3.12)"
    conda create -n "$CONDA_ENV" python=3.12 pip -y
  fi
  conda activate "$CONDA_ENV"
  echo "[pip] 安装/更新依赖..."
  pip install -r "$API_DIR/requirements.txt"
  echo "[完成] 环境就绪: conda activate $CONDA_ENV"
}

ensure_conda_ready() {
  conda_init
  if ! conda env list | tail -n +2 | awk '{print $1}' | sed 's/^\*//' | grep -Fxq "$CONDA_ENV"; then
    echo "[提示] 未找到 Conda 环境 ${CONDA_ENV}，自动执行 setup..."
    cmd_setup
    return 0
  fi
  if [[ "${CONDA_DEFAULT_ENV:-}" != "$CONDA_ENV" ]]; then
    conda activate "$CONDA_ENV"
  fi
  cd "$API_DIR"
  if ! python -c "import alembic.config" 2>/dev/null; then
    echo "[pip] 依赖未装全，正在安装 requirements.txt ..."
    pip install -r "$API_DIR/requirements.txt"
  fi
}

# 项目内有 alembic/ 迁移目录，不可用 python -m alembic（会冲突）
run_alembic() {
  local alembic_bin
  alembic_bin="$(command -v alembic || true)"
  if [[ -z "$alembic_bin" ]]; then
    pip install alembic
    alembic_bin="$(command -v alembic)"
  fi
  if [[ -z "$alembic_bin" ]]; then
    echo "[错误] 找不到 alembic 命令，请执行: ./start.sh setup"
    exit 1
  fi
  "$alembic_bin" "$@"
}

conda_activate() {
  ensure_conda_ready
}

# 后台进程在独立 bash 里激活环境（避免 nohup 丢失 activate）
conda_bash_cmd() {
  local inner=$1
  local base
  base="$(find_conda_base)" || exit 1
  printf 'source %q/etc/profile.d/conda.sh && conda activate %q && cd %q && set -a && source %q && set +a && %s' \
    "$base" "$CONDA_ENV" "$API_DIR" "$ENV_FILE" "$inner"
}

is_running() {
  local pid_file=$1
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid=$(cat "$pid_file")
  kill -0 "$pid" 2>/dev/null
}

port_listen_pids() {
  local port=$1
  if command -v lsof &>/dev/null; then
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
    return 0
  fi
  if command -v fuser &>/dev/null; then
    fuser -n tcp "$port" 2>/dev/null | tr -s ' ' '\n' | grep -E '^[0-9]+$' || true
    return 0
  fi
  echo "[警告] 未找到 lsof/fuser，无法检测端口 $port" >&2
}

free_port() {
  local port=$1
  local label=${2:-服务}
  local pids
  pids="$(port_listen_pids "$port" | tr '\n' ' ' | xargs echo 2>/dev/null || true)"
  [[ -n "$pids" && "$pids" != " " ]] || return 0
  echo "[停止] 释放 ${label} 端口 ${port} (pid ${pids})"
  for pid in $pids; do
    kill "$pid" 2>/dev/null || true
  done
  sleep 1
  for pid in $pids; do
    kill -9 "$pid" 2>/dev/null || true
  done
}

wait_port_free() {
  local port=$1
  local i
  for i in 1 2 3 4 5; do
    local busy
    busy="$(port_listen_pids "$port" | head -1)"
    [[ -z "$busy" ]] && return 0
    sleep 1
  done
  echo "[错误] 端口 ${port} 仍被占用。可手动执行:"
  echo "       lsof -tiTCP:${port} -sTCP:LISTEN | xargs kill -9"
  return 1
}

stop_one() {
  local name=$1
  local pid_file=$2
  local port=${3:-}
  if [[ -f "$pid_file" ]]; then
    local pid
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
      echo "[停止] $name (pid $pid)"
      # nohup bash 启动时，子进程 node/npm 可能仍存活
      if command -v pkill &>/dev/null; then
        pkill -P "$pid" 2>/dev/null || true
      fi
      kill "$pid" 2>/dev/null || true
      sleep 1
      if command -v pkill &>/dev/null; then
        pkill -9 -P "$pid" 2>/dev/null || true
      fi
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
  rm -f "$pid_file"
  if [[ -n "$port" ]]; then
    free_port "$port" "$name"
    wait_port_free "$port"
  fi
}

cmd_stop() {
  stop_one "web" "$WEB_PID" 3000
  stop_one "worker" "$WORKER_PID"
  stop_one "api" "$API_PID" 8000
  echo "[完成] 已停止"
}

cmd_migrate() {
  load_env
  ensure_conda_ready
  echo "[迁移] alembic upgrade head"
  run_alembic upgrade head
}

cmd_import_matches() {
  echo "[赛程] 根据 FIFA 官网数据生成 seeds/matches.json"
  python3 "$ROOT/scripts/import_fifa_matches.py"
}

cmd_seed() {
  load_env
  ensure_conda_ready
  echo "[种子] python -m app.scripts.seed"
  python -m app.scripts.seed
}

cmd_sync_market() {
  ENV_FILE="$ROOT/.env"
  load_env
  ensure_conda_ready
  local extra=()
  local args=("$@")
  if [[ ${#args[@]} -gt 0 && ${args[0]} == "--" ]]; then
    args=("${args[@]:1}")
  fi
  if [[ ${#args[@]} -gt 0 ]]; then
    if [[ ${args[*]} != *"--api-url"* ]] && [[ -n ${MARKET_SYNC_API_URL:-} ]]; then
      extra+=(--api-url "$MARKET_SYNC_API_URL")
    fi
  else
    if [[ -n ${MARKET_SYNC_API_URL:-} ]]; then
      extra+=(--api-url "$MARKET_SYNC_API_URL")
    fi
  fi
  echo "[同步] Polymarket → market_snapshots ${args[*]:-（全部映射）}"
  cd "$API_DIR"
  python -m app.scripts.sync_polymarket_local ${extra[@]+"${extra[@]}"} ${args[@]+"${args[@]}"}
}

cmd_sync_facts() {
  load_env
  ensure_conda_ready
  if [[ -z "${FOOTBALL_DATA_API_KEY:-}" ]]; then
    echo "[错误] 请在 ${ENV_FILE} 中设置 FOOTBALL_DATA_API_KEY"
    echo "      注册: https://www.football-data.org/"
    exit 1
  fi
  echo "[同步] football-data.org → match_facts $*"
  cd "$API_DIR"
  python -m app.scripts.sync_football_facts "$@"
}

cmd_reset_discussion() {
  load_env
  ensure_conda_ready
  local match_id="${1:-fifa-400021443}"
  echo "[重置] 清空比赛 $match_id 的合议记录（墨西哥 vs 南非 默认 fifa-400021443）"
  cd "$API_DIR"
  python -m app.scripts.reset_match_discussion "$match_id"
}

cmd_build_web() {
  load_env
  cd "$WEB_DIR"
  if [[ -z "${NEXT_PUBLIC_API_URL:-}" ]]; then
    echo "[错误] .env.production 中未设置 NEXT_PUBLIC_API_URL"
    exit 1
  fi
  echo "[构建] 前端 NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL"
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
  npm run build
  if [[ ! -f "$WEB_DIR/.next/BUILD_ID" ]]; then
    echo "[错误] 前端构建失败，未生成 .next/BUILD_ID"
    exit 1
  fi
  echo "[完成] 前端已构建（含 _next/static，需 npm run start 或 ./start.sh start 提供访问）"
}

ensure_web_built() {
  load_env
  if [[ ! -f "$WEB_DIR/.next/BUILD_ID" ]]; then
    echo "[提示] 未构建前端，先执行 npm run build ..."
    cmd_build_web
    return
  fi
  if [[ ! -d "$WEB_DIR/.next/static" ]]; then
    echo "[提示] 缺少 .next/static，重新构建..."
    cmd_build_web
  fi
}

start_api() {
  if is_running "$API_PID"; then
    echo "[跳过] api 已在运行 (pid $(cat "$API_PID"))"
    return
  fi
  free_port 8000 "api"
  wait_port_free 8000
  if ! conda_env_exists; then
    cmd_setup
  fi
  echo "[启动] api → http://127.0.0.1:8000  日志: $LOG_DIR/api.log"
  local cmd
  cmd="$(conda_bash_cmd 'exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2')"
  nohup bash -c "$cmd" >>"$LOG_DIR/api.log" 2>&1 &
  echo $! >"$API_PID"
}

start_worker() {
  if is_running "$WORKER_PID"; then
    echo "[跳过] worker 已在运行 (pid $(cat "$WORKER_PID"))"
    return
  fi
  if ! conda_env_exists; then
    cmd_setup
  fi
  echo "[启动] worker  日志: $LOG_DIR/worker.log"
  local cmd
  cmd="$(conda_bash_cmd 'exec arq app.workers.settings.WorkerSettings')"
  nohup bash -c "$cmd" >>"$LOG_DIR/worker.log" 2>&1 &
  echo $! >"$WORKER_PID"
}

start_web() {
  if is_running "$WEB_PID"; then
    echo "[跳过] web 已在运行 (pid $(cat "$WEB_PID"))"
    return
  fi
  # pid 文件丢失时，旧 next 进程可能仍占 3000
  free_port 3000 "web"
  wait_port_free 3000
  ensure_web_built
  cd "$WEB_DIR"
  echo "[启动] web → http://127.0.0.1:3000  日志: $LOG_DIR/web.log"
  echo "       静态资源由 Next 提供: /_next/static/* （须保持本进程运行，不能只丢静态目录）"
  if command -v setsid &>/dev/null; then
    nohup setsid npm run start -- -H 127.0.0.1 -p 3000 \
      >>"$LOG_DIR/web.log" 2>&1 &
  else
    nohup npm run start -- -H 127.0.0.1 -p 3000 \
      >>"$LOG_DIR/web.log" 2>&1 &
  fi
  echo $! >"$WEB_PID"
}

cmd_start() {
  load_env
  if ! conda_env_exists; then
    cmd_setup
  else
    ensure_conda_ready
  fi
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
  if is_running "$WEB_PID"; then
    if curl -sf -o /dev/null "http://127.0.0.1:3000/" 2>/dev/null; then
      echo "  web 首页: 可访问"
    else
      echo "  web 首页: 无响应，查看 $LOG_DIR/web.log"
    fi
  fi
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
    sync-facts)
      shift
      cmd_sync_facts "$@"
      ;;
    sync-market)
      shift
      cmd_sync_market "$@"
      ;;
    reset-discussion)
      shift
      cmd_reset_discussion "$@"
      ;;
    import-matches) cmd_import_matches ;;
    build-web) load_env; cmd_build_web ;;
    setup) cmd_setup ;;
    -h | help) usage ;;
    *)
      echo "未知命令: $cmd"
      usage
      exit 1
      ;;
  esac
}

main "${@:-start}"
