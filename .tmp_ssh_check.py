import paramiko
import sys

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('1.12.66.249', port=22, username='ubuntu', password='Slfasd123', timeout=20)

cmds = [
    'docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" | grep -iE "crawler|CONTAINER"',
    'docker images | grep -iE "crawler|playwright"',
    'cd /home/ubuntu/project && grep -A8 "crawler-service:" docker-compose.yml | head -12',
    'cd /home/ubuntu/project && grep -A8 "crawler-worker:" docker-compose.yml | head -12',
]
for cmd in cmds:
    print(f'=== {cmd} ===')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print(out)
    if err:
        print('STDERR:', err)
    print()

client.close()
