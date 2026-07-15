$js = Get-Content 'g:\源码\xianyu-assistant-package-temp\_eval_msg.js' -Raw
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($js))
agent-browser eval -b $b64
