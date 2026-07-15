"""Test the API through the Java gateway with authentication."""
import json
import urllib.request

# Step 1: Login to get token
login_url = "http://localhost:18080/api/login/login"
login_data = json.dumps({"username": "demo", "password": "123456"}).encode('utf-8')
login_req = urllib.request.Request(login_url, data=login_data, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(login_req, timeout=10) as resp:
        login_resp = json.loads(resp.read().decode('utf-8'))
        print(f"Login response code: {login_resp.get('code')}")
        token = login_resp.get('data', {}).get('token', '')
        if not token:
            print(f"Login failed: {login_resp}")
            exit(1)
        print(f"Got token: {token[:20]}...")
except Exception as e:
    print(f"Login failed: {e}")
    exit(1)

# Step 2: Call online conversations API
api_url = "http://localhost:18080/api/msg/online/conversations?xianyuAccountId=1&pageSize=10"
api_req = urllib.request.Request(api_url, headers={
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
})
try:
    with urllib.request.urlopen(api_req, timeout=30) as resp:
        api_resp = json.loads(resp.read().decode('utf-8'))
        print(f"\nAPI response code: {api_resp.get('code')}")
        data = api_resp.get('data', {})
        conversations = data.get('conversations', [])
        print(f"Conversations returned: {len(conversations)}")
        for c in conversations[:10]:
            avatar = c.get('buyerAvatar') or c.get('avatarUrl') or ''
            cover = c.get('goodsCoverPic') or c.get('coverPic') or ''
            title = c.get('goodsTitle') or c.get('product') or ''
            print(f"  sid={c.get('sid')} name={c.get('peerUserName')} "
                  f"avatar={'YES' if avatar else 'NO'} "
                  f"goodsId={c.get('goodsId')} "
                  f"title={str(title)[:30]} "
                  f"cover={'YES' if cover else 'NO'}")
            if avatar:
                print(f"    avatar_url={avatar[:80]}")
            if cover:
                print(f"    cover_url={cover[:80]}")
except urllib.error.HTTPError as e:
    print(f"API HTTP Error: {e.code} {e.reason}")
    print(f"Response: {e.read().decode('utf-8')[:500]}")
except Exception as e:
    print(f"API test failed: {e}")
