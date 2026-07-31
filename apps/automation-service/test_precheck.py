"""测试会话推荐接口。"""
import requests
import json

# 1. 先测试 recommend-conversations
url = 'http://localhost:12401/api/knowledge-base/recommend-conversations'
payload = {
    'userId': 1,
    'tenantId': 1,
    'accountId': 1,
    'limit': 20
}
headers = {
    'X-Internal-Token': 'dev-only-internal-api-token-change-me-32-chars',
    'X-Internal-Tenant-Id': '1',
    'Content-Type': 'application/json'
}
print('=== recommend-conversations ===')
r = requests.post(url, json=payload, headers=headers, timeout=60)
print('STATUS:', r.status_code)
d = r.json()
print('CODE:', d.get('code'))
print('MSG:', d.get('msg'))
data = d.get('data') or {}
conversations = data.get('conversations') or []
print('conversations count:', len(conversations))
recommendations = data.get('recommendations') or []
print('recommendations count:', len(recommendations))
print()
for i, c in enumerate(conversations[:5]):
    print(f'  conv[{i+1}] sid={c.get("sid")} peer={c.get("peerUserName")} goods={c.get("goodsTitle")} msgCount={c.get("messageCount")}')
print()
for i, rec in enumerate(recommendations[:5]):
    print(f'  rec[{i+1}] idx={rec.get("conversation_index")} value={rec.get("estimated_value")} reason={rec.get("reason")}')
