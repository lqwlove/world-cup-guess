#!/usr/bin/env bash
# 从服务器彻底移除 world-cup-guess 部署
#
# 用法:
#   ./uninstall.sh                    # 交互式（默认只停服务，其余逐步确认）
#   ./uninstall.sh --all              # 停服务 + Nginx + Conda 环境 + 删除项目目录
#   ./uninstall.sh --all --yes        # 同上，跳过确认
#   ./uninstall.sh --dry-run --all    # 仅打印将执行的操作
#
# 环境变量（与 start.sh 一致）:
#   ENV_FILE      默认 .env.production
#   CONDA_ENV     默认 wcguess
#   NGINX_SITE    默认 world-cup-guess
#
# 注意:
#   - 不会卸载系统级 PostgreSQL / Redis（常为宝塔共用服务）
#   - 删库需单独加 --drop-db（会 DROP DATABASE，慎用）
#   - 删项目目录后本脚本自身也会被删除

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env.production}"
CONDA_ENV="${CONDA_ENV:-wcguess}"
NGINX_SITE="${NGINX_SITE:-world-cup-guess}"

DO_STOP=0
DO_NGINX=0
DO_CONDA=0
DO_DROP_DB=0
DO_REMOVE_DIR=0
DRY_RUN=0
ASSUME_YES=0

usage() {
  sed -n '2,18p' "$0" | sed 's/^# \?//'
  echo ""
  echo "选项:"
  echo "  --stop              停止 api / worker / web（默认在 --all 时包含）"
  echo "  --nginx             移除 Nginx 站点配置并重载"
  echo "  --conda             删除 Conda 环境 \$CONDA_ENV"
  echo "  --drop-db           删除 .env.production 中 DATABASE_URL 对应的数据库（危险）"
  echo "  --remove-dir        删除整个项目目录 \$ROOT"
  echo "  --all               等同于 --stop --nginx --conda --remove-dir"
  echo "  --yes, -y           跳过确认"
  echo "  --dry-run           只打印，不执行"
  echo "  -h, --help          显示帮助"
}

log() { echo "[卸载] $*"; }
warn() { echo "[警告] $*" >&2; }

confirm() {
  local msg=$1
  if [[ $ASSUME_YES -eq 1 ]]; then
    return 0
  fi
  local ans
  read -r -p "${msg} [y/N] " ans
  ans="$(echo "$ans" | tr '[:upper:]' '[:lower:]')"
  [[ "$ans" == "y" || "$ans" == "yes" ]]
}

run() {
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[dry-run] $*"
  else
    log "$*"
    eval "$@"
  fi
}

parse_args() {
  if [[ $# -eq 0 ]]; then
    DO_STOP=1
    return
  fi
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --stop) DO_STOP=1 ;;
      --nginx) DO_NGINX=1 ;;
      --conda) DO_CONDA=1 ;;
      --drop-db) DO_DROP_DB=1 ;;
      --remove-dir) DO_REMOVE_DIR=1 ;;
      --all)
        DO_STOP=1
        DO_NGINX=1
        DO_CONDA=1
        DO_REMOVE_DIR=1
        ;;
      --yes | -y) ASSUME_YES=1 ;;
      --dry-run) DRY_RUN=1 ;;
      -h | --help)
        usage
        exit 0
        ;;
      *)
        echo "未知参数: $1" >&2
        usage
        exit 1
        ;;
    esac
    shift
  done
}

stop_services() {
  if [[ -x "$ROOT/start.sh" ]]; then
    run "\"$ROOT/start.sh\" stop"
  else
    warn "未找到 start.sh，尝试手动释放端口 3000 / 8000"
    for port in 3000 8000; do
      if command -v lsof &>/dev/null; then
        local pids
        pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
        if [[ -n "$pids" ]]; then
          run "kill $pids 2>/dev/null || true"
        fi
      fi
    done
  fi
  run "rm -rf \"$ROOT/.run\" \"$ROOT/logs\""
}

remove_nginx() {
  local avail="/etc/nginx/sites-available/${NGINX_SITE}"
  local enabled="/etc/nginx/sites-enabled/${NGINX_SITE}"
  local need_reload=0

  if [[ -f "$enabled" || -L "$enabled" ]]; then
    if confirm "移除 Nginx 站点 ${NGINX_SITE}?"; then
      run "sudo rm -f \"$enabled\""
      need_reload=1
    fi
  else
    log "Nginx sites-enabled 无 ${NGINX_SITE}，跳过"
  fi

  if [[ -f "$avail" ]]; then
    if [[ $ASSUME_YES -eq 1 ]] || confirm "删除 ${avail}?"; then
      run "sudo rm -f \"$avail\""
      need_reload=1
    fi
  fi

  if [[ $need_reload -eq 1 ]]; then
    run "sudo nginx -t"
    run "sudo systemctl reload nginx 2>/dev/null || sudo nginx -s reload"
  fi
}

conda_init() {
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
    warn "未找到 conda，跳过 Conda 环境删除"
    return 1
  fi
  # shellcheck disable=SC1091
  source "$base/etc/profile.d/conda.sh"
  return 0
}

remove_conda_env() {
  if ! conda_init; then
    return 0
  fi
  if ! conda env list | tail -n +2 | awk '{print $1}' | sed 's/^\*//' | grep -Fxq "$CONDA_ENV"; then
    log "Conda 环境 ${CONDA_ENV} 不存在，跳过"
    return 0
  fi
  if confirm "删除 Conda 环境 ${CONDA_ENV}?"; then
    run "conda env remove -n \"$CONDA_ENV\" -y"
  fi
}

parse_db_url() {
  local url=$1
  python3 - "$url" <<'PY'
import sys
from urllib.parse import urlparse, unquote
u = urlparse(sys.argv[1])
db = (u.path or "").lstrip("/")
print(u.hostname or "localhost")
print(u.port or 5432)
print(unquote(u.username or ""))
print(unquote(u.password or ""))
print(db)
PY
}

drop_database() {
  if [[ ! -f "$ENV_FILE" ]]; then
    warn "无 ${ENV_FILE}，无法解析数据库"
    return 0
  fi
  # shellcheck disable=SC1090
  set -a && source "$ENV_FILE" && set +a
  local sync_url="${DATABASE_URL_SYNC:-}"
  if [[ -z "$sync_url" && -n "${DATABASE_URL:-}" ]]; then
    sync_url="${DATABASE_URL/postgresql+asyncpg:/postgresql:}"
    sync_url="${sync_url/postgresql+psycopg:/postgresql:}"
  fi
  if [[ -z "$sync_url" ]]; then
    warn "未配置 DATABASE_URL_SYNC，跳过删库"
    return 0
  fi

  local host port user pass dbname
  host="$(parse_db_url "$sync_url" | sed -n '1p')"
  port="$(parse_db_url "$sync_url" | sed -n '2p')"
  user="$(parse_db_url "$sync_url" | sed -n '3p')"
  pass="$(parse_db_url "$sync_url" | sed -n '4p')"
  dbname="$(parse_db_url "$sync_url" | sed -n '5p')"

  if [[ -z "$dbname" ]]; then
    warn "无法解析数据库名，跳过删库"
    return 0
  fi

  warn "将 DROP DATABASE \"${dbname}\"（不可恢复！）"
  if ! confirm "确认删除数据库 ${dbname}?"; then
    return 0
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[dry-run] dropdb ${dbname} @ ${host}:${port}"
    return 0
  fi

  export PGPASSWORD="$pass"
  log "断开 ${dbname} 上的连接..."
  psql -h "$host" -p "$port" -U "$user" -d postgres -v ON_ERROR_STOP=1 -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${dbname}' AND pid <> pg_backend_pid();" \
    2>/dev/null || true
  log "DROP DATABASE ${dbname}"
  psql -h "$host" -p "$port" -U "$user" -d postgres -v ON_ERROR_STOP=1 -c \
    "DROP DATABASE IF EXISTS \"${dbname}\";"
  unset PGPASSWORD
}

remove_project_dir() {
  warn "将永久删除目录: ${ROOT}"
  if ! confirm "确认删除整个项目目录?"; then
    return 0
  fi
  local parent name
  parent="$(dirname "$ROOT")"
  name="$(basename "$ROOT")"
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[dry-run] rm -rf \"${ROOT}\""
    return 0
  fi
  cd "$parent"
  rm -rf "$name"
  log "已删除 ${ROOT}"
}

main() {
  parse_args "$@"

  if [[ $DO_STOP -eq 0 && $DO_NGINX -eq 0 && $DO_CONDA -eq 0 && $DO_DROP_DB -eq 0 && $DO_REMOVE_DIR -eq 0 ]]; then
    usage
    exit 1
  fi

  echo "============================================"
  echo " world-cup-guess 卸载"
  echo " 项目目录: ${ROOT}"
  echo "============================================"

  if [[ $DO_STOP -eq 1 ]]; then
    log "1/5 停止服务..."
    stop_services
  fi

  if [[ $DO_NGINX -eq 1 ]]; then
    log "2/5 移除 Nginx..."
    remove_nginx
  fi

  if [[ $DO_CONDA -eq 1 ]]; then
    log "3/5 移除 Conda 环境..."
    remove_conda_env
  fi

  if [[ $DO_DROP_DB -eq 1 ]]; then
    log "4/5 删除数据库..."
    drop_database
  fi

  if [[ $DO_REMOVE_DIR -eq 1 ]]; then
    log "5/5 删除项目目录..."
    remove_project_dir
    exit 0
  fi

  log "完成。PostgreSQL / Redis 服务未卸载（若为宝塔共用请保留）。"
  log "若需删库: ./uninstall.sh --drop-db"
  log "若需删代码: ./uninstall.sh --remove-dir"
}

main "$@"
