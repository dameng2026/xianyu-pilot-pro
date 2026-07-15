import paramiko

host = "154.9.254.86"
port = 22
username = "root"
china_backend = "1.12.66.249:18080"
remote_userweb = "/var/www/user-web"
remote_adminweb = "/var/www/admin-web"

nginx_config = f"""# Port 80: Subscription info page
server {{
    listen 80;
    server_name _;
    
    root /var/www/sub;
    index index.html;
    
    # Clash Meta subscription
    location /clash.yaml {{
        alias /var/www/sub/clash.yaml;
        default_type text/yaml;
        add_header Cache-Control no-cache;
    }}
    
    # Standard v2rayN subscription (base64)
    location /sub {{
        alias /var/www/sub/v2rayn.txt;
        default_type text/plain;
        add_header Cache-Control no-cache;
    }}
    
    # Web info page
    location / {{
        try_files $uri $uri/ /index.html;
    }}
}}

# Port 81: user-web (前台)
server {{
    listen 81;
    server_name _;
    root {remote_userweb};
    index index.html;
    
    location / {{
        try_files $uri $uri/ /index.html;
    }}
    
    location /api/ {{
        proxy_pass http://{china_backend}/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
    
    location /ai/ {{
        proxy_pass http://{china_backend}/ai/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
    
    location /bot/ {{
        proxy_pass http://{china_backend}/bot/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
}}

# Port 82: admin-web (后台管理)
server {{
    listen 82;
    server_name _;
    root {remote_adminweb};
    index index.html;
    
    location / {{
        try_files $uri $uri/ /index.html;
    }}
    
    location /admin-api/ {{
        proxy_pass http://{china_backend}/admin-api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
}}
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, port, username, look_for_keys=True, allow_agent=True)
    sftp = ssh.open_sftp()
    
    # Write full nginx config
    with sftp.open("/etc/nginx/sites-enabled/nginx-full.conf", "w") as f:
        f.write(nginx_config)
    print("Full nginx config written")
    
    # Remove old user-web.conf
    stdin, stdout, stderr = ssh.exec_command("rm -f /etc/nginx/sites-enabled/user-web.conf")
    stdout.channel.recv_exit_status()
    
    # Test and reload
    stdin, stdout, stderr = ssh.exec_command("nginx -t 2>&1")
    exit_status = stdout.channel.recv_exit_status()
    print("Nginx test:", stdout.read().decode() + stderr.read().decode())
    
    if exit_status == 0:
        stdin, stdout, stderr = ssh.exec_command("systemctl reload nginx 2>&1")
        stdout.channel.recv_exit_status()
        print("Nginx reloaded")
        
        # Check listening
        stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep -E ':80|:81|:82'")
        exit_status = stdout.channel.recv_exit_status()
        print("Listening ports:")
        print(stdout.read().decode())
        
        # Test curl
        for ep in ["/clash.yaml", "/", "/sub"]:
            stdin, stdout, stderr = ssh.exec_command(f"curl -s -o /dev/null -w '%{{http_code}}' http://0.0.0.0{ep} 2>&1")
            code = stdout.read().decode().strip()
            print(f"http://154.9.254.86{ep} -> {code}")

finally:
    ssh.close()