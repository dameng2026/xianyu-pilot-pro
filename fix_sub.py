import paramiko
import base64

host = "154.9.254.86"
port = 22
username = "root"

uuid = "6ea8b415-02ba-4760-8421-e00a1d323950"
server = "154.9.254.86"
port_num = 16778
public_key = "7dAENDOApB3V6lHjzYkeRRSdRvFYfpJBXmp_Px3rRAQ"
short_id = "6ba85179"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, port, username, look_for_keys=True, allow_agent=True)
    sftp = ssh.open_sftp()
    
    # 1. Write Clash Meta YAML config
    clash_yaml = """# Port
port: 7890
socks-port: 7891
mixed-port: 7892
allow-lan: false
mode: Rule
log-level: info
external-controller: 127.0.0.1:9090

proxies:
  - name: US-REALITY
    type: vless
    server: REPLACE_SERVER
    port: REPLACE_PORT
    uuid: REPLACE_UUID
    tls: true
    servername: www.microsoft.com
    flow: xtls-rprx-vision
    reality-opts:
      public-key: REPLACE_PUBKEY
      short-id: REPLACE_SID
    skip-cert-verify: true
    udp: true

proxy-groups:
  - name: Proxy
    type: select
    proxies:
      - US-REALITY
      - DIRECT
  - name: YouTube
    type: select
    proxies:
      - US-REALITY
      - DIRECT

rules:
  - DOMAIN-SUFFIX,google.com,Proxy
  - DOMAIN-SUFFIX,youtube.com,YouTube
  - DOMAIN-SUFFIX,openai.com,Proxy
  - DOMAIN-SUFFIX,github.com,Proxy
  - DOMAIN-SUFFIX,stackoverflow.com,Proxy
  - DOMAIN-KEYWORD,netflix,Proxy
  - MATCH,DIRECT
""".replace("REPLACE_SERVER", server).replace("REPLACE_PORT", str(port_num)).replace("REPLACE_UUID", uuid).replace("REPLACE_PUBKEY", public_key).replace("REPLACE_SID", short_id)
    
    with sftp.open("/var/www/sub/clash.yaml", "w") as f:
        f.write(clash_yaml)
    print("clash.yaml created")
    
    # 2. Create v2rayN compatible subscription (base64 single link)
    link = f"vless://{uuid}@{server}:{port_num}?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.microsoft.com&fp=chrome&pbk={public_key}&sid={short_id}&type=tcp&headerType=none#US-REALITY"
    b64 = base64.b64encode(link.encode()).decode()
    
    with sftp.open("/var/www/sub/v2rayn.txt", "w") as f:
        f.write(b64)
    print("v2rayn.txt created")
    
    # 3. Update Nginx config to serve everything properly
    nginx_conf = """server {
    listen 80;
    server_name _;
    
    root /var/www/sub;
    index index.html;
    
    # Clash Meta subscription
    location /clash.yaml {
        alias /var/www/sub/clash.yaml;
        default_type text/yaml;
    }
    
    # Standard v2rayN subscription (base64)
    location /sub {
        alias /var/www/sub/v2rayn.txt;
        default_type text/plain;
    }
    
    # Web info page
    location / {
        try_files $uri $uri/ /index.html;
    }
}"""
    
    with sftp.open("/etc/nginx/sites-enabled/default", "w") as f:
        f.write(nginx_conf)
    print("Nginx config updated")
    sftp.close()
    
    # Test and reload
    stdin, stdout, stderr = ssh.exec_command("nginx -t 2>&1")
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode() + stderr.read().decode()
    print("Nginx test:", out.strip())
    
    if exit_status == 0:
        stdin, stdout, stderr = ssh.exec_command("systemctl reload nginx 2>&1")
        stdout.channel.recv_exit_status()
        print("Nginx reloaded")
    
    # Verify endpoints
    for ep in ["/", "/sub", "/clash.yaml"]:
        stdin, stdout, stderr = ssh.exec_command(f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:80{ep} 2>&1")
        code = stdout.read().decode().strip()
        print(f"  http://154.9.254.86{ep} -> {code}")

finally:
    ssh.close()

print()
print("=" * 60)
print("订阅地址（Clash Verge 导入）:")
print("=" * 60)
print("  http://154.9.254.86/clash.yaml")
print()
print("订阅地址（v2rayN / Nekoray 等）:")
print("  http://154.9.254.86/sub")
print()
print("手动配置参数：")
print(f"  协议: VLESS + REALITY + XTLS-Vision")
print(f"  地址: {server}")
print(f"  端口: {port_num}")
print(f"  UUID: {uuid}")
print(f"  PublicKey: {public_key}")
print(f"  ShortId: {short_id}")
print(f"  Flow: xtls-rprx-vision")
print(f"  SNI: www.microsoft.com")