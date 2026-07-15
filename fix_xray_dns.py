import paramiko
import json

host = "154.9.254.86"
port = 22
username = "root"

uuid = "0a2cc1cd-e0ae-46f5-84e8-abbcb8960e05"

config = {
    "log": {
        "loglevel": "debug",
        "access": "/var/log/xray/access.log",
        "error": "/var/log/xray/error.log"
    },
    "dns": {
        "servers": [
            "8.8.8.8",
            "1.1.1.1",
            "localhost"
        ]
    },
    "inbounds": [
        {
            "port": 8080,
            "protocol": "vmess",
            "settings": {
                "clients": [
                    {
                        "id": uuid,
                        "alterId": 0
                    }
                ]
            },
            "streamSettings": {
                "network": "ws",
                "wsSettings": {
                    "path": "/vmess"
                }
            }
        }
    ],
    "outbounds": [
        {
            "protocol": "freedom",
            "tag": "direct",
            "settings": {
                "domainStrategy": "AsIs"
            }
        }
    ]
}

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, port, username, look_for_keys=True, allow_agent=True)
    
    sftp = ssh.open_sftp()
    with sftp.open("/usr/local/etc/xray/config.json", "w") as f:
        f.write(json.dumps(config, indent=2))
    sftp.close()
    print("Xray config updated with DNS + debug logging")
    
    # Test config
    stdin, stdout, stderr = ssh.exec_command("/usr/local/bin/xray run -test -config /usr/local/etc/xray/config.json 2>&1")
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode() + stderr.read().decode()
    print("Config test:", out.strip()[:200])
    
    if exit_status == 0:
        # Restart
        stdin, stdout, stderr = ssh.exec_command("systemctl restart xray 2>&1")
        exit_status = stdout.channel.recv_exit_status()
        print("Xray restarted")
        
        # Check status
        stdin, stdout, stderr = ssh.exec_command("systemctl is-active xray && sleep 1 && ss -tlnp | grep 8080")
        print(stdout.read().decode())
        
        # Check recent logs
        stdin, stdout, stderr = ssh.exec_command("sleep 2 && tail -20 /var/log/xray/error.log")
        print("Recent logs:\n" + stdout.read().decode())
    
finally:
    ssh.close()

print()
print("已更新 Xray 配置，添加了 DNS 服务器。请重新连接测试。")