"""Test the online conversations API endpoint."""
import json
import urllib.request

url = "http://localhost:12401/api/v1/messages/online-conversations?account_id=1&limit=10"
req = urllib.request.Request(url)
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode('utf-8'))
    print(f"Response code: {data.get('code')}")
    conversations = data.get('data', {}).get('conversations', [])
    print(f"Conversations returned: {len(conversations)}")
    for c in conversations[:10]:
        avatar = c.get('buyerAvatar') or ''
        cover = c.get('goodsCoverPic') or ''
        title = c.get('goodsTitle') or ''
        print(f"  sid={c.get('sid')} name={c.get('peerUserName')} "
              f"avatar={'YES' if avatar else 'NO'} "
              f"goodsId={c.get('goodsId')} "
              f"title={title[:30]} "
              f"cover={'YES' if cover else 'NO'}")
        if avatar:
            print(f"    avatar_url={avatar[:80]}")
