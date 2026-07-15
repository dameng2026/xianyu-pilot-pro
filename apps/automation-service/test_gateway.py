"""Test through Java gateway and directly to Python"""
import urllib.request
import json
import sys

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
print("=== Test 1: Direct Python service (12401) ===")
try:
    req = urllib.request.Request(
        'http://localhost:12401/api/msg/context',
        data=data,
        headers={'Content-Type': 'application/json', 'X-Internal-Token': 'dev-only-internal-api-token-change-me-32-chars', 'X-Internal-Tenant-Id': '1'}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    result = json.loads(resp.read().decode('utf-8'))
    msgs = result.get('data', {}).get('messages', [])
    total = result.get('data', {}).get('total', 0)
    print(f'  code={result.get("code")}, total={total}, messages_count={len(msgs)}')
    if msgs:
        for m in msgs[:3]:
            print(f'  - id={m.get("id")} sid={m.get("sid")} content={m.get("msgContent","")[:40]}')
except Exception as e:
    print(f'  ERROR: {e}')

# Test 2: Through Java gateway
print("\n=== Test 2: Through Java gateway (18080) ===")
try:
    req = urllib.request.Request(
        'http://localhost:18080/api/msg/context',
        data=data,
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer test', 'Cookie': 'admin-token=test'}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    result = json.loads(resp.read().decode('utf-8'))
    msgs = result.get('data', {}).get('messages', [])
    total = result.get('data', {}).get('total', 0)
    print(f'  code={result.get("code")}, total={total}, messages_count={len(msgs)}')
    if msgs:
        for m in msgs[:3]:
            print(f'  - id={m.get("id")} sid={m.get("sid")} content={m.get("msgContent","")[:40]}')
except Exception as e:
    print(f'  ERROR: {e}')

# Test 3: Online conversations through Java gateway
print("\n=== Test 3: Conversations through Java gateway ===")
try:
    req = urllib.request.Request(
        'http://localhost:18080/api/msg/online/conversations?xianyuAccountId=1&limit=10',
        headers={'Authorization': 'Bearer test', 'Cookie': 'admin-token=test'}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    result = json.loads(resp.read().decode('utf-8'))
    conversations = result.get('data', [])
    print(f'  Conversations count: {len(conversations)}')
    for c in conversations[:5]:
        print(f'  - sid={c.get("sid")} peerUserId={c.get("peerUserId")} peerUserName={c.get("peerUserName")}')
except Exception as e:
    print(f'  ERROR: {e}')