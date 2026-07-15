# 触发 Spring Boot DevTools 自动重启
# 用法: 在 apps\core-api 目录执行 .\restart.ps1
# 效果: 修改 .trigger 文件的时间戳，触发 DevTools 重启
$triggerFile = "src\main\resources\.trigger"
if (Test-Path $triggerFile) {
    (Get-Item $triggerFile).LastWriteTime = Get-Date
    Write-Host "[OK] 已触发重启（修改了 .trigger 文件时间戳）" -ForegroundColor Green
} else {
    Write-Host "[ERR] 未找到 .trigger 文件" -ForegroundColor Red
}
