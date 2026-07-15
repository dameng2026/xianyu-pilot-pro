$BASE = "http://127.0.0.1:18080"

Write-Host "=== Step 1: Login ===" -ForegroundColor Cyan
$testUser = $env:TEST_ADMIN_USERNAME
$testPassword = $env:TEST_ADMIN_PASSWORD
if ([string]::IsNullOrWhiteSpace($testUser) -or [string]::IsNullOrWhiteSpace($testPassword)) {
    Write-Host "[FAIL] TEST_ADMIN_USERNAME and TEST_ADMIN_PASSWORD are required" -ForegroundColor Red
    exit 1
}
$loginBody = @{ userName = $testUser; password = $testPassword } | ConvertTo-Json -Compress
try {
    $loginResp = Invoke-WebRequest -Uri "$BASE/admin-api/auth/login" -Method POST -Body $loginBody -ContentType "application/json" -UseBasicParsing -TimeoutSec 10
    $loginData = $loginResp.Content | ConvertFrom-Json
    $TOKEN = $loginData.data.token
    Write-Host "[OK] Login successful, token obtained" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Login failed: $($_.Exception.GetType().Name)" -ForegroundColor Red
    exit 1
}

$HEADERS = @{ Authorization = "Bearer $TOKEN" }

function Test-Endpoint($name, $url, $method = "GET") {
    try {
        $r = Invoke-WebRequest -Uri $url -Headers $HEADERS -Method $method -UseBasicParsing -TimeoutSec 15
        $bodyData = $r.Content | ConvertFrom-Json -ErrorAction Stop
        $code = $bodyData.code
        if ($code -eq 200) {
            Write-Host "[PASS] $name - HTTP $($r.StatusCode), code=$code" -ForegroundColor Green
        } else {
            Write-Host "[FAIL] $name - HTTP $($r.StatusCode), code=$code, msg=$($bodyData.msg)" -ForegroundColor Red
        }
    } catch {
        Write-Host "[FAIL] $name - Exception: $($_.Exception.GetType().Name)" -ForegroundColor Red
    }
}

Write-Host "`n=== Step 2: Test Fixed Endpoints ===" -ForegroundColor Cyan
Test-Endpoint "1.notifications/delivery-logs" "$BASE/admin-api/notifications/delivery-logs?current=1&size=5"
Test-Endpoint "2.modules/alerts/meta" "$BASE/admin-api/admin/modules/alerts/meta"
Test-Endpoint "3.modules/files/meta" "$BASE/admin-api/admin/modules/files/meta"
Test-Endpoint "4.dashboard/recent-events" "$BASE/admin-api/admin/dashboard/recent-events"
Test-Endpoint "5.modules/alerts/page" "$BASE/admin-api/admin/modules/alerts/page?current=1&size=5"
Test-Endpoint "6.modules/files/page" "$BASE/admin-api/admin/modules/files/page?current=1&size=5"
Test-Endpoint "7.hot-goods/refresh" "$BASE/admin-api/api/hot-goods/refresh?minSales=5" "POST"
Test-Endpoint "8.modules/users/meta" "$BASE/admin-api/admin/modules/users/meta"
Test-Endpoint "9.modules/goods/meta" "$BASE/admin-api/admin/modules/goods/meta"
Test-Endpoint "10.modules/orders/meta" "$BASE/admin-api/admin/modules/orders/meta"

Write-Host "`n=== Test Complete ===" -ForegroundColor Cyan
