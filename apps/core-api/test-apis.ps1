$token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwidXNlck5hbWUiOiJhZG1pbiIsInJvbGVzIjoiUl9TVVBFUixSX0FETUlOIiwiaWF0IjoxNzgyNjk3OTI3LCJleHAiOjE3ODI3ODQzMjd9.1fgJbLQSceQHJ0_k_dqAIlV6bR8RDE70Q24oquekrBg"
$h = @{ Authorization = "Bearer $token" }

Write-Host "==== /admin-api/admin/dashboard/summary ===="
curl.exe -s -H "Authorization: Bearer $token" "http://localhost:18080/admin-api/admin/dashboard/summary"

Write-Host "`n==== /admin-api/admin/dashboard/trend ===="
curl.exe -s -H "Authorization: Bearer $token" "http://localhost:18080/admin-api/admin/dashboard/trend"

Write-Host "`n==== /admin-api/admin/dashboard/recent-events ===="
curl.exe -s -H "Authorization: Bearer $token" "http://localhost:18080/admin-api/admin/dashboard/recent-events"

Write-Host "`n==== /admin-api/admin/menus ===="
curl.exe -s -H "Authorization: Bearer $token" "http://localhost:18080/admin-api/admin/menus"

Write-Host "`n==== /admin-api/admin/modules/notify-channels/meta ===="
curl.exe -s -H "Authorization: Bearer $token" "http://localhost:18080/admin-api/admin/modules/notify-channels/meta"

Write-Host "`n==== /admin-api/admin/modules/risk-events/meta ===="
curl.exe -s -H "Authorization: Bearer $token" "http://localhost:18080/admin-api/admin/modules/risk-events/meta"

Write-Host "`n==== /admin-api/admin/modules/users/page ===="
curl.exe -s -H "Authorization: Bearer $token" "http://localhost:18080/admin-api/admin/modules/users/page?current=1&size=5"

Write-Host "`n==== /admin-api/admin/modules/notify-channels/page ===="
curl.exe -s -H "Authorization: Bearer $token" "http://localhost:18080/admin-api/admin/modules/notify-channels/page?current=1&size=5"

Write-Host "`n==== /admin-api/admin/modules/risk-events/page ===="
curl.exe -s -H "Authorization: Bearer $token" "http://localhost:18080/admin-api/admin/modules/risk-events/page?current=1&size=5"

Write-Host "`n==== /admin-api/operation-logs?current=1&size=5 ===="
curl.exe -s -H "Authorization: Bearer $token" "http://localhost:18080/admin-api/operation-logs?current=1&size=5"

Write-Host "`n==== /admin-api/notifications/delivery-logs?current=1&size=5 ===="
curl.exe -s -H "Authorization: Bearer $token" "http://localhost:18080/admin-api/notifications/delivery-logs?current=1&size=5"

Write-Host "`n==== /admin-api/monitor/ai ===="
curl.exe -s -H "Authorization: Bearer $token" "http://localhost:18080/admin-api/monitor/ai"
