$pages = @(
    "/admin/user-permission/users",
    "/admin/billing/plans",
    "/admin/billing/payment-config",
    "/admin/billing/licenses",
    "/admin/xianyu-business/accounts",
    "/admin/xianyu-business/goods",
    "/admin/xianyu-business/orders",
    "/admin/xianyu-business/messages",
    "/admin/xianyu-business/delivery",
    "/admin/xianyu-business/auto-reply",
    "/admin/xianyu-business/kami",
    "/admin/ai/model-config",
    "/admin/ai/monitor",
    "/admin/ai/usage",
    "/admin/ai/token",
    "/admin/ai/rag",
    "/admin/ai/sensitive-words",
    "/admin/data-stats/hot-goods",
    "/admin/risk-notify/channels",
    "/admin/risk-notify/notify-logs",
    "/admin/risk-notify/risk-events",
    "/admin/risk-notify/alerts",
    "/admin/ops/settings",
    "/admin/ops/audit-logs",
    "/admin/ops/client-errors",
    "/admin/ops/runtime",
    "/admin/ops/backups",
    "/admin/ops/files",
    "/admin/ops/versions"
)

$results = @()
foreach ($p in $pages) {
    $url = "http://localhost:3006/#$p"
    agent-browser --session admin open $url | Out-Null
    agent-browser --session admin wait 1500 | Out-Null
    $js = @"
(() => {
      const title = document.title;
      const errs = [];
      document.querySelectorAll('.el-message--error, .el-notification__content, [class*=\"error-message\"]').forEach(e => {
        const t = e.textContent.trim();
        if (t && t.length > 5 && t.length < 300) errs.push(t);
      });
      const emptyHints = [];
      document.querySelectorAll('.el-empty__description, .el-table__empty-text, [class*=\"empty\"]').forEach(e => {
        const t = e.textContent.trim();
        if (t && t.length > 2) emptyHints.push(t);
      });
      return JSON.stringify({title: title, errs: errs.slice(0, 3), emptyHints: emptyHints.slice(0,3)});
    })()
"@
    $encoded = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($js))
    $r = agent-browser --session admin eval -b $encoded 2>&1
    $results += [PSCustomObject]@{Page=$p; Result=$r}
}
$results | ForEach-Object { Write-Host "==== $($_.Page) ===="; Write-Host $_.Result; Write-Host "" }
