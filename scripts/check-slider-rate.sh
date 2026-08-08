#!/usr/bin/env bash
# 线上滑块求解成功率定时检查（生产主机 cron 用，只读）。
# 统计口径与后台 KPI 一致：排除 timeout/precheck_rejected/service_unavailable/
# browser_crashed/stale_terminated/cookie_invalid/account_inactive/account_disabled。
# 任一口径（今天/近7天）成功率 < 70% 时退出码为 1。
set -uo pipefail

cd /home/ubuntu/project || exit 2
MYSQL_PWD=$(grep '^MYSQL_ROOT_PASSWORD=' .env.production | cut -d= -f2)

EXCLUDE="status IN ('timeout','precheck_rejected') OR COALESCE(failure_reason,'') IN ('service_unavailable','browser_crashed','precheck_rejected','timeout','stale_terminated','cookie_invalid','account_inactive','account_disabled')"
FAIL_EXCLUDE="COALESCE(failure_reason,'') NOT IN ('service_unavailable','browser_crashed','precheck_rejected','timeout','stale_terminated','cookie_invalid','account_inactive','account_disabled')"

mysql_one() {
  docker exec -i xianyu-admin-mysql mysql -uroot -p"$MYSQL_PWD" \
    xianyu_assistant_admin -N -e "$1" 2>/dev/null | tr '\n' ' '
}

KPI_SQL="SELECT SUM(CASE WHEN NOT ($EXCLUDE) THEN 1 ELSE 0 END), SUM(status='success'), SUM(status='fail' AND $FAIL_EXCLUDE) FROM xianyu_captcha_solve_record WHERE COALESCE(deleted,0)=0 AND"

today=$(mysql_one "$KPI_SQL created_at >= CURDATE()")
week=$(mysql_one "$KPI_SQL created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)")

echo "[$(date '+%F %T')] today=[$today] week=[$week]"

rate_of() {
  local fields=$1
  local total ok fail rate
  read -r total ok fail <<<"$fields"
  total=${total:-0}; ok=${ok:-0}; fail=${fail:-0}
  if [ "$total" -le 0 ]; then
    echo "0"
    return 0
  fi
  rate=$((ok * 100 / total))
  echo "$rate"
}

today_rate=$(rate_of "$today")
week_rate=$(rate_of "$week")
echo "[$(date '+%F %T')] today_rate=${today_rate}% week_rate=${week_rate}%"

[ "$today_rate" -ge 70 ] && [ "$week_rate" -ge 70 ]
