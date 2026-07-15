import paramiko
import os

host = "154.9.254.86"
port = 22
username = "root"

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
        parent = os.path.dirname(path)
        if parent and parent != path:
            sftp_ensure_dir(sftp, parent)
        sftp.mkdir(path)

def upload_dir(sftp, local_dir, remote_dir):
    count = 0
    for root, dirs, files in os.walk(local_dir):
        rel_path = os.path.relpath(root, local_dir)
        remote_path = os.path.join(remote_dir, rel_path).replace("\\", "/")
        sftp_ensure_dir(sftp, remote_path)
        
        for file in files:
            local_file = os.path.join(root, file)
            remote_file = os.path.join(remote_path, file).replace("\\", "/")
            sftp.put(local_file, remote_file)
            count += 1
    return count

try:
    ssh.connect(host, port, username, look_for_keys=True, allow_agent=True)
    sftp = ssh.open_sftp()
    
    print("Uploading user-web (前台)...")
    n = upload_dir(sftp, local_userweb, remote_userweb)
    print(f"  {n} files uploaded")
    
    print("Uploading admin-web (后台管理)...")
    n = upload_dir(sftp, local_adminweb, remote_adminweb)
    print(f"  {n} files uploaded")
    
    sftp.close()
    
    # Test
    for port_ep in [("81", "user-web"), ("82", "admin-web")]:
        stdin, stdout, stderr = ssh.exec_command(f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{port_ep[0]}/ 2>&1")
        code = stdout.read().decode().strip()
        print(f"http://154.9.254.86:{port_ep[0]}/ -> {code} ({port_ep[1]})")

finally:
    ssh.close()