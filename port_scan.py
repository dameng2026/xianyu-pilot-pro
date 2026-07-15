import paramiko

host = "154.9.254.86"
port = 22
username = "root"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, port, username, look_for_keys=True, allow_agent=True)
    
    cmd = """
for p in 80 443 8080 18080 3006 5174 12401; do
  timeout 3 bash -c "echo > /dev/tcp/1.12.66.249/$p" 2>/dev/null && echo "Port $p: OPEN" || echo "Port $p: CLOSED"
done
"""
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err: print("Stderr:", err)

finally:
    ssh.close()