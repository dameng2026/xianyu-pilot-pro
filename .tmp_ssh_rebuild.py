import paramiko
import sys
import time

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('1.12.66.249', port=22, username='ubuntu', password='Slfasd123', timeout=20)

# Rebuild and restart crawler-service and crawler-worker
# Use --no-deps to avoid touching other services, --force-recreate to ensure new image is used
cmd = (
    'cd /home/ubuntu/project && '
    'docker compose -f docker-compose.yml -f docker-compose.prod.yml '
    '--env-file .env.production build crawler-service crawler-worker'
)
print(f"=== Building crawler-service and crawler-worker images ===")
print(f"Command: {cmd}")
print("This may take several minutes...")
print()

stdin, stdout, stderr = client.exec_command(cmd, timeout=600)
stdout.channel.recv_exit_status()

# Stream output
while True:
    made_progress = False
    while stdout.channel.recv_ready():
        chunk = stdout.channel.recv(65536).decode('utf-8', 'ignore')
        print(chunk, end='')
        made_progress = True
    while stdout.channel.recv_stderr_ready():
        chunk = stdout.channel.recv_stderr(65536).decode('utf-8', 'ignore')
        print(chunk, end='')
        made_progress = True
    if stdout.channel.exit_status_ready() and not stdout.channel.recv_ready() and not stdout.channel.recv_stderr_ready():
        break
    if not made_progress:
        time.sleep(0.5)

exit_code = stdout.channel.recv_exit_status()
print(f"\n=== Build exit code: {exit_code} ===")

client.close()
