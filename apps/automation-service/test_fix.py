"""Test the fix with verbose output"""
import urllib.request
import json
import ssl

payload = {
    'xianyuAccountId': 1,
    'sid': '62491400847',
    'sId': '62491400847',
    'sessionId': '62491400847',
    'peerUserId': '2211422464341',
    'limit': 50,
    'offset': 0
}
data = json.dumps(payload).encode('utf-8')

# Test 1: Direct Python call
print("=== Test 1: Direct Python service (12401) with internal headers ===")
try:
    req = urllib.request.Request(
        'http://localhost:12401/api/msg/context',
        data=data,
        headers={
            'Content-Type': 'application/json',
            'X-Internal-Token': 'dev-only-internal-api-token-change-me-32-chars',
            'X-Internal-Tenant-Id': '1'
        }
    )
    resp = urllib.request.urlopen(req, timeout=10)
    result = json.loads(resp.read().decode('utf-8'))
    code = result.get("code")
    data_resp = result.get("data", {})
    messages = data_resp.get("messages", [])
    total = data_resp.get("total", 0)
    print(f'  code={code}, total={total}, messages_count={len(messages)}')
    if messages:
        for m in messages[:5]:
            print(f'  - id={m.get("id")} sid={m.get("sid")} content={m.get("msgContent","")[:50]}')
    else:
        print(f'  data keys: {result.get("data", {}).keys() if result.get("data") else "None"}')
        print(f'  full response: {json.dumps(result, ensure_ascii=False)[:300]}')
except Exception as e:
    print(f'  ERROR: {e}')

print("\n=== Test 2: Health check ===")
try:
    req = urllib.request.Request('http://localhost:12401/health')
    resp = urllib.request.urlopen(req, timeout=5)
    print(f'  {resp.read().decode()}')
except Exception as e:
    print(f'  ERROR: {e}')