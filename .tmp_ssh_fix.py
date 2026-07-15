import paramiko
import sys

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('1.12.66.249', port=22, username='ubuntu', password='Slfasd123', timeout=20)

# Step 1: Check current Dockerfile
print("=== Step 1: Current production Dockerfile ===")
stdin, stdout, stderr = client.exec_command('cat /home/ubuntu/project/apps/crawler-service/Dockerfile', timeout=30)
print(stdout.read().decode())

# Step 2: Update Dockerfile to use v1.61.1-jammy (matching package.json playwright 1.61.1)
# Using jammy to stay consistent with the existing base; noble would also work but jammy is safer for minimal change
new_dockerfile = """FROM mcr.microsoft.com/playwright:v1.61.1-jammy

WORKDIR /app

COPY package*.json ./
RUN npm ci --no-audit --no-fund

COPY . .

RUN npm run build

ENV NODE_ENV=production
ENV HEADLESS=true
ENV PORT=3001

CMD ["node", "dist/server.js"]
"""

sftp = client.open_sftp()
dockerfile_path = '/home/ubuntu/project/apps/crawler-service/Dockerfile'
with sftp.open(dockerfile_path, 'w') as f:
    f.write(new_dockerfile)
sftp.close()
print("=== Step 2: Dockerfile updated to v1.61.1-jammy ===")

# Verify
stdin, stdout, stderr = client.exec_command('cat /home/ubuntu/project/apps/crawler-service/Dockerfile', timeout=30)
print(stdout.read().decode())

client.close()
print("Done. Ready to rebuild.")
