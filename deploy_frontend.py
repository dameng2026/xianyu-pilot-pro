import paramiko
import os

host = "154.9.254.86"
port = 22
username = "root"
china_backend = "1.12.66.249:18080"

local_userweb = r"g:\源码\xianyu-assistant-package-temp\apps\user-web\dist"
local_adminweb = r"g:\源码\xianyu-assistant-package-temp\apps\admin-web\dist"

remote_userweb = "/var/www/user-web"
remote_adminweb = "/var/www/admin-web"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

def sftp_ensure_dir(sftp, path):
    try:
        sftp.stat(path)
    except FileNotFoundError:
        sftp.mkdir(path)

def sftp_upload_dir(sftp, local_dir, remote_dir):
    for root, dirs, files in os.walk(local_dir):
        rel_path = os.path.relpath(root, local_dir)
        remote_path = os.path.join(remote_dir, rel_path).replace("\\", "/")
        sftp_ensure_dir(sftp, remote_path)
        
        for file in files:
            local_file = os.path.join(root, file)
            remote_file = os.path.join(remote_path, file).replace("\\", "/")
            sftp.put(local_file, remote_file, confirm=False)

try:
    ssh.connect(host, port, username, look_for_keys=True, allow_agent=True)
    sftp = ssh.open_sftp()
    
    # Create remote directories
    for d in [remote_userweb, remote_adminweb]:
        try:
            sftp.stat(d)
        except FileNotFoundError:
            sftp.mkdir(d)
            print(f"Created: {d}")
    
    print("\n=== Uploading user-web (前台) ===")
    sftp_upload_dir(sftp, local_userweb, remote_userweb)
    
    print("\n=== Uploading admin-web (后台管理) ===")
    sftp_upload_dir(sftp, local_adminweb, remote_adminweb)
    
    sftp.close()
    print("\nUpload completed!")
    
    # Write Nginx config
    nginx_conf = f"""# user-web (前台) - port 81
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

# admin-web (后台管理) - port 82
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
    
    # Write Nginx config
    sftp = ssh.open_sftp()
    with sftp.open("/etc/nginx/sites-enabled/user-web.conf", "w") as f:
        f.write(nginx_conf)
    sftp.close()
    print("Nginx config written")
    
    # Remove default Nginx config (we already have sub on port 80)
    stdin, stdout, stderr = ssh.exec_command("rm -f /etc/nginx/sites-enabled/default")
    exit_status = stdout.channel.recv_exit_status()
    
    # Test and reload Nginx
    stdin, stdout, stderr = ssh.exec_command("nginx -t 2>&1")
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode() + stderr.read().decode()
    print("Nginx test:", out.strip())
    
    if exit_status == 0:
        stdin, stdout, stderr = ssh.exec_command("systemctl reload nginx 2>&1 || systemctl restart nginx 2>&1")
        exit_status = stdout.channel.recv_exit_status()
        out = stdout.read().decode() + stderr.read().decode()
        print("Nginx reload:", "OK" if exit_status == 0 else out.strip())
    else:
        print("Nginx config test FAILED, please check")
    
    # Verify services
    stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep -E ':8[012] '")
    exit_status = stdout.channel.recv_exit_status()
    print("\nListening ports:")
    print(stdout.read().decode().strip())
    
    stdin, stdout, stderr = ssh.exec_command("curl -s -o /dev/null -w '%{http_code}' http://localhost:81/ 2>&1")
    code1 = stdout.read().decode().strip()
    
    stdin, stdout, stderr = ssh.exec_command("curl -s -o /dev/null -w '%{http_code}' http://localhost:82/ 2>&1")
    code2 = stdout.read().decode().strip()
    
    stdin, stdout, stderr = ssh.exec_command("curl -s -o /dev/null -w '%{http_code}' http://localhost:80/sub 2>&1")
    code3 = stdout.read().decode().strip()
    
    print(f"\nAccess check: user-web=:{code1} admin-web=:{code2} sub=:{code3}")

finally:
    ssh.close()