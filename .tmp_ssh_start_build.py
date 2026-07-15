import paramiko
import sys
import time

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('1.12.66.249', port=22, username='ubuntu', password='Slfasd123', timeout=20)

# Start build with nohup in background, redirect to log file
build_cmd = (
    'cd /home/ubuntu/project && '
    'nohup docker compose -f docker-compose.yml -f docker-compose.prod.yml '
    '--env-file .env.production build crawler-service crawler-worker '
    '> /tmp/crawler-build.log 2>&1 &'
)
print("=== Starting background build ===", flush=True)
stdin, stdout, stderr = client.exec_command(build_cmd, timeout=30)
stdout.channel.recv_exit_status()
print("Build started in background (PID on remote).", flush=True)

# Wait a moment and verify it started
time.sleep(3)
stdin, stdout, stderr = client.exec_command('ps aux | grep "docker compose" | grep -v grep | head -3', timeout=10)
out = stdout.read().decode()
print(f"Processes:\n{out}", flush=True)

client.close()
print("Done. Build running in background on remote server.", flush=True)
