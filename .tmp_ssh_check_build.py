import paramiko

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('1.12.66.249', port=22, username='ubuntu', password='Slfasd123', timeout=20)

# Check build log - last 30 lines
stdin, stdout, stderr = client.exec_command('tail -30 /tmp/crawler-build.log', timeout=30)
out = stdout.read().decode()
print("=== Build log (last 30 lines) ===", flush=True)
print(out, flush=True)

# Check if build process is still running
stdin, stdout, stderr = client.exec_command('ps aux | grep "docker compose" | grep -v grep | head -3', timeout=10)
out = stdout.read().decode()
print("=== Build process still running? ===", flush=True)
if out.strip():
    print("YES - still running", flush=True)
else:
    print("NO - build finished", flush=True)

# Check if new images exist
stdin, stdout, stderr = client.exec_command('docker images | grep -iE "crawler"', timeout=10)
out = stdout.read().decode()
print("=== Docker images ===", flush=True)
print(out, flush=True)

client.close()
