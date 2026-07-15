"""Test the Python API directly."""
import json
import urllib.request

# Call Python API directly
url = "http://localhost:12401/api/msg/online/conversations?xianyuAccountId=1&pageSize=10&tenantId=1"
req = urllib.request.Request(url, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print(f"Response code: {data.get('code')}")
        conversations = data.get('data', {}).get('conversations', [])
        print(f"Conversations returned: {len(conversations)}")
        for c in conversations[:5]:
            avatar = c.get('buyerAvatar') or ''
            cover = c.get('goodsCoverPic') or ''
            title = c.get('goodsTitle') or ''
            print(f"  sid={c.get('sid')} name={c.get('peerUserName')} "
                  f"avatar={'YES' if avatar else 'NO'} "
                  f"goodsId={c.get('goodsId')} "
                  f"title={str(title)[:30]} "
                  f"cover={'YES' if cover else 'NO'}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} {e.reason}")
    print(f"Response: {e.read().decode('utf-8')[:500]}")
except Exception as e:
    print(f"Failed: {e}")
