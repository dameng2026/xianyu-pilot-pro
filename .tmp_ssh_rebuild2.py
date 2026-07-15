import paramiko
import sys
import time

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('1.12.66.249', port=22, username='ubuntu', password='Slfasd123', timeout=20)

cmd = (
    'cd /home/ubuntu/project && '
    'docker compose -f docker-compose.yml -f docker-compose.prod.yml '
    '--env-file .env.production build crawler-service crawler-worker'
)
print(f"=== Building crawler images ===", flush=True)

transport = client.get_transport()
channel = transport.open_session()
channel.settimeout(900)  # 15 min timeout
channel.exec_command(cmd)

while True:
    made_progress = False
    while channel.recv_ready():
        chunk = channel.recv(65536).decode('utf-8', 'ignore')
        sys.stdout.write(chunk)
        sys.stdout.flush()
        made_progress = True
    while channel.recv_stderr_ready():
        chunk = channel.recv_stderr(65536).decode('utf-8', 'ignore')
        sys.stderr.write(chunk)
        sys.stderr.flush()
        made_progress = True
    if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
        break
    if not made_progress:
        time.sleep(1)

exit_code = channel.recv_exit_status()
print(f"\n=== Build exit code: {exit_code} ===", flush=True)

client.close()
