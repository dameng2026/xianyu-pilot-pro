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

link = f"vless://{uuid}@{server}:{port_num}?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.microsoft.com&fp=chrome&pbk={public_key}&sid={short_id}&type=tcp&headerType=none#US-REALITY"

b64_content = base64.b64encode(link.encode()).decode()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, port, username, look_for_keys=True, allow_agent=True)
    
    # Install Nginx (non-interactive)
    print("Installing Nginx...")
    stdin, stdout, stderr = ssh.exec_command("DEBIAN_FRONTEND=noninteractive apt-get install -y nginx", timeout=120)
    exit_status = stdout.channel.recv_exit_status()
    print("Nginx installed:", "OK" if exit_status == 0 else f"FAIL ({exit_status})")
    if exit_status != 0:
        err = stderr.read().decode()
        print("Error:", err[-500:] if len(err) > 500 else err)
    
    # Create sub directory
    stdin, stdout, stderr = ssh.exec_command("mkdir -p /var/www/sub")
    stdout.channel.recv_exit_status()
    
    # Write subscription file
    sftp = ssh.open_sftp()
    with sftp.open("/var/www/sub/sub.txt", "w") as f:
        f.write(link + "\n")
    sftp.close()
    
    # Write link for v2rayN
    sftp = ssh.open_sftp()
    with sftp.open("/var/www/sub/index.html", "w") as f:
        f.write("""<!DOCTYPE html>
<html>
<head><title>Subscription</title><meta charset="utf-8"></head>
<body style="font-family:monospace;padding:20px">
<h2>Node Info</h2>
<div style="background:#f0f0f0;padding:10px;border-radius:4px;word-break:break-all">""" + link + """</div>
<h2>Config Parameters</h2>
<pre>
Protocol:  VLESS + REALITY + XTLS-Vision
Address:   """ + server + """
Port:      """ + str(port_num) + """
UUID:      """ + uuid + """
Flow:      xtls-rprx-vision
SNI:       www.microsoft.com
PublicKey: """ + public_key + """
ShortId:   """ + short_id + """
</pre>
</body>
</html>""")
    sftp.close()
    print("Subscription files written")
    
    # Create Nginx config for sub
    nginx_conf = """server {
    listen 80;
    server_name _;
    
    # Subscription endpoint
    location /sub {
        alias /var/www/sub;
        default_type text/plain;
        index sub.txt;
    }
    
    location / {
        root /var/www/sub;
        index index.html;
    }
}
"""
    sftp = ssh.open_sftp()
    with sftp.open("/etc/nginx/sites-enabled/default", "w") as f:
        f.write(nginx_conf)
    sftp.close()
    
    # Reload Nginx
    stdin, stdout, stderr = ssh.exec_command("nginx -t && systemctl reload nginx || systemctl restart nginx")
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    err = stderr.read().decode()
    print("Nginx test:", out.strip())
    if err: print("Nginx err:", err.strip()[:200])
    
    # Check Nginx status
    stdin, stdout, stderr = ssh.exec_command("systemctl is-active nginx && ss -tlnp | grep ':80 '")
    exit_status = stdout.channel.recv_exit_status()
    print("Nginx status:", stdout.read().decode().strip())
    
finally:
    ssh.close()

print()
print("=" * 60)
print("订阅地址（填入客户端订阅栏）:")
print("=" * 60)
print(f"http://{server}/sub")
print()
print("订阅内容（Base64 编码的 VLESS 链接）:")
print(b64_content)
print()
print("用手机/电脑客户端访问 http://" + server + "/sub 即可看到配置信息页")