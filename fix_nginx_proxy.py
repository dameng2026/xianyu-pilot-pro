import paramiko

host = "154.9.254.86"
port = 22
username = "root"
china_backend = "1.12.66.249:18080"
remote_userweb = "/var/www/user-web"
remote_adminweb = "/var/www/admin-web"

# Simplified Nginx config - direct proxy for /vmess with no restrictive checks
nginx_config = f"""# Port 80: Subscription + VMess WS proxy
server {{
    listen 80;
    server_name _;
    
    # VMess WebSocket endpoint - proxy to Xray
    location /vmess {{
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400s;
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

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, port, username, look_for_keys=True, allow_agent=True)
    sftp = ssh.open_sftp()
    
    with sftp.open("/etc/nginx/sites-enabled/nginx-full.conf", "w") as f:
        f.write(nginx_config)
    sftp.close()
    print("Nginx config updated")
    
    # Test and reload
    stdin, stdout, stderr = ssh.exec_command("nginx -t 2>&1")
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode() + stderr.read().decode()
    print("Nginx test:", out.strip())
    
    if exit_status == 0:
        stdin, stdout, stderr = ssh.exec_command("systemctl reload nginx")
        stdout.channel.recv_exit_status()
        print("Nginx reloaded")
        
        # Verify Xray can serve VMess (test direct connection)
        stdin, stdout, stderr = ssh.exec_command("curl -v http://127.0.0.1:8080/vmess 2>&1 | head -10")
        result = stdout.read().decode() + stderr.read().decode()
        print("Xray direct test:", result[:200])
        
        # Verify Nginx proxy
        stdin, stdout, stderr = ssh.exec_command("curl -sv http://127.0.0.1:80/vmess 2>&1 | head -15")
        result = stdout.read().decode() + stderr.read().decode()
        print("Nginx proxy test:", result[:300])
    
finally:
    ssh.close()

print()
print("更新完成！请重新导入订阅: http://154.9.254.86/clash.yaml")