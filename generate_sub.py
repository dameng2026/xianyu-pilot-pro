import urllib.parse
import base64

uuid = "6ea8b415-02ba-4760-8421-e00a1d323950"
server = "154.9.254.86"
port_num = 16778
public_key = "7dAENDOApB3V6lHjzYkeRRSdRvFYfpJBXmp_Px3rRAQ"
short_id = "6ba85179"

params = {
    "encryption": "none",
    "flow": "xtls-rprx-vision",
    "security": "reality",
    "sni": "www.microsoft.com",
    "fp": "chrome",
    "pbk": public_key,
    "sid": short_id,
    "type": "tcp",
    "headerType": "none"
}

query = urllib.parse.urlencode(params)
link = f"vless://{uuid}@{server}:{port_num}?{query}#US-REALITY"

print("=" * 60)
print("【1】VLESS 分享链接（直接导入客户端）:")
print("=" * 60)
print(link)
print()

# Base64 encoded subscription (standard format for v2rayN etc.)
b64_link = base64.b64encode(link.encode()).decode()
print("=" * 60)
print("【2】Base64 订阅链接（用于 v2rayN / Nekoray 等）:")
print("=" * 60)
print("http://" + server + ":16778/sub")
print()
print("（将上述地址填入客户端的订阅地址栏即可）")
print()

print("=" * 60)
print("【3】手动配置参数")
print("=" * 60)
print(f"协议:     VLESS")
print(f"地址:     {server}")
print(f"端口:     {port_num}")
print(f"UUID:     {uuid}")
print(f"Flow:     xtls-rprx-vision")
print(f"加密:     none")
print(f"传输:     tcp")
print(f"安全:     reality")
print(f"SNI:      www.microsoft.com")
print(f"指纹:     chrome")
print(f"PublicKey: {public_key}")
print(f"ShortId:  {short_id}")
print()
print("推荐客户端: v2rayNG (Android), Nekoray (PC),")
print("            Clash Meta, Stash (iOS), Sing-box")
print()

print("=" * 60)
print("【4】Clash Meta 配置片段")
print("=" * 60)
print("""proxies:
  - name: US-REALITY
    type: vless
    server: """ + server + """
    port: """ + str(port_num) + """
    uuid: """ + uuid + """
    flow: xtls-rprx-vision
    udp: true
    tls: true
    servername: www.microsoft.com
    client-fingerprint: chrome
    reality-opts:
      public-key: """ + public_key + """
      short-id: """ + short_id + """
    skip-cert-verify: true""")