import paramiko
import json
import base64

host = "154.9.254.86"
port = 22
username = "root"
china_backend = "1.12.66.249:18080"
remote_userweb = "/var/www/user-web"
remote_adminweb = "/var/www/admin-web"

uuid = "0a2cc1cd-e0ae-46f5-84e8-abbcb8960e05"
server = "154.9.254.86"
ws_path = "/vmess"

# Update Nginx to proxy WebSocket to Xray on port 8080
nginx_config = f"""# Port 80: Subscription + VMess WS proxy
server {{
    listen 80;
    server_name _;
    
    # VMess WebSocket endpoint (proxy to Xray)
    location /vmess {{
        if ($http_upgrade != "websocket") {{
            return 404;
        }}
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }}
    
    # Clash Meta subscription
    location /clash.yaml {{
        alias /var/www/sub/clash.yaml;
        default_type text/yaml;
        add_header Cache-Control no-cache;
    }}
    
    # Standard subscription
    location /sub {{
        alias /var/www/sub/v2rayn.txt;
        default_type text/plain;
        add_header Cache-Control no-cache;
    }}
    
    root /var/www/sub;
    index index.html;
    
    location / {{
        try_files $uri $uri/ /index.html;
    }}
}}

# Port 81: user-web
server {{
    listen 81;
    server_name _;
    root {remote_userweb};
    index index.html;
    location / {{ try_files $uri $uri/ /index.html; }}
    location /api/ {{ proxy_pass http://{china_backend}/api/; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; }}
    location /ai/ {{ proxy_pass http://{china_backend}/ai/; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; }}
    location /bot/ {{ proxy_pass http://{china_backend}/bot/; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; }}
}}

# Port 82: admin-web
server {{
    listen 82;
    server_name _;
    root {remote_adminweb};
    index index.html;
    location / {{ try_files $uri $uri/ /index.html; }}
    location /admin-api/ {{ proxy_pass http://{china_backend}/admin-api/; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; }}
}}
"""

# Clash config - VMess + WS, port 80
clash_yaml = f"""port: 7890
socks-port: 7891
mixed-port: 7892
allow-lan: false
mode: Rule
log-level: info
ipv6: false

proxies:
  - name: US-VMESS-WS
    type: vmess
    server: {server}
    port: 80
    uuid: {uuid}
    alterId: 0
    cipher: auto
    network: ws
    ws-opts:
      path: {ws_path}
    udp: true

proxy-groups:
  - name: Proxy
    type: select
    proxies:
      - US-VMESS-WS
      - DIRECT

rules:
  - DOMAIN-SUFFIX,google.com,Proxy
  - DOMAIN-SUFFIX,youtube.com,Proxy
  - DOMAIN-SUFFIX,openai.com,Proxy
  - DOMAIN-SUFFIX,github.com,Proxy
  - MATCH,DIRECT
"""

# v2rayN subscription
vmess_json = {
    "v": "2",
    "ps": "US-VMESS-WS",
    "add": server,
    "port": "80",
    "id": uuid,
    "aid": "0",
    "scy": "auto",
    "net": "ws",
    "type": "none",
    "host": "",
    "path": ws_path,
    "tls": ""
}
b64_vmess = base64.b64encode(json.dumps(vmess_json).encode()).decode()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, port, username, look_for_keys=True, allow_agent=True)
    sftp = ssh.open_sftp()
    
    # Write Nginx config
    with sftp.open("/etc/nginx/sites-enabled/nginx-full.conf", "w") as f:
        f.write(nginx_config)
    sftp.close()
    print("Nginx config written")
    
    # Write clash.yaml
    sftp = ssh.open_sftp()
    with sftp.open("/var/www/sub/clash.yaml", "w") as f:
        f.write(clash_yaml)
    sftp.close()
    print("Clash config updated (port 80)")
    
    # Write v2rayN sub
    sftp = ssh.open_sftp()
    with sftp.open("/var/www/sub/v2rayn.txt", "w") as f:
        f.write(b64_vmess + "\n")
    sftp.close()
    print("v2rayN subscription updated")
    
    # Test Nginx and reload
    stdin, stdout, stderr = ssh.exec_command("nginx -t 2>&1")
    exit_status = stdout.channel.recv_exit_status()
    print("Nginx test:", stdout.read().decode() + stderr.read().decode())
    
    if exit_status == 0:
        stdin, stdout, stderr = ssh.exec_command("systemctl reload nginx 2>&1")
        stdout.channel.recv_exit_status()
        print("Nginx reloaded")
    
    # Verify Xray
    stdin, stdout, stderr = ssh.exec_command("systemctl is-active xray && ss -tlnp | grep -E ':80|:8080|:81|:82'")
    print("Services:\n" + stdout.read().decode())
    
    # Verify endpoints
    for ep in ["/clash.yaml", "/sub", "/"]:
        stdin, stdout, stderr = ssh.exec_command(f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:80{ep}")
        print(f"  http://{server}{ep} -> {stdout.read().decode().strip()}")

finally:
    ssh.close()

print()
print("=" * 60)
print("Clash Verge 订阅地址:")
print("  http://" + server + "/clash.yaml")
print()
print("节点信息:")
print(f"  协议: VMess + WebSocket")
print(f"  地址: {server}")
print(f"  端口: 80 (HTTP)")
print(f"  路径: {ws_path}")
print(f"  UUID: {uuid}")