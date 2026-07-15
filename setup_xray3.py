import paramiko
import json

host = "154.9.254.86"
port = 22
username = "root"

config = {
    "log": {
        "loglevel": "warning"
    },
    "inbounds": [
        {
            "port": 16778,
            "protocol": "vless",
            "settings": {
                "clients": [
                    {
                        "id": "6ea8b415-02ba-4760-8421-e00a1d323950",
                        "flow": "xtls-rprx-vision"
                    }
                ],
                "decryption": "none"
            },
            "streamSettings": {
                "network": "tcp",
                "security": "reality",
                "realitySettings": {
                    "dest": "www.microsoft.com:443",
                    "serverNames": ["www.microsoft.com", "www.bing.com"],
                    "privateKey": "6B1aGxKv5qL0hoYg01IZeWuZQ3hIiyzVpYSvGeyIGWI",
                    "shortIds": ["6ba85179"]
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls"]
            }
        }
    ],
    "outbounds": [
        {
            "protocol": "freedom",
            "tag": "direct"
        }
    ]
}

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, port, username, look_for_keys=True, allow_agent=True)
    
    # Write config via SFTP
    sftp = ssh.open_sftp()
    with sftp.open("/usr/local/etc/xray/config.json", "w") as f:
        f.write(json.dumps(config, indent=2))
    sftp.close()
    print("Config file written via SFTP")
    
    # Test config
    stdin, stdout, stderr = ssh.exec_command("/usr/local/bin/xray run -test -config /usr/local/etc/xray/config.json")
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    err = stderr.read().decode()
    print("Config test:", out.strip()[:200])
    if err: print("Err:", err.strip()[:200])
    
    if exit_status == 0:
        # Restart Xray
        stdin, stdout, stderr = ssh.exec_command("systemctl restart xray && systemctl enable xray")
        x = stdout.channel.recv_exit_status()
        print("Restart Xray:", "OK" if x == 0 else f"FAIL ({x})")
        
        # Check status
        stdin, stdout, stderr = ssh.exec_command("systemctl is-active xray")
        x = stdout.channel.recv_exit_status()
        print(f"Xray status: {stdout.read().decode().strip()}")
        
        # Check listening
        stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 16778")
        x = stdout.channel.recv_exit_status()
        print("Port 16778:", stdout.read().decode().strip() or "NOT LISTENING")
        
        # Firewall
        stdin, stdout, stderr = ssh.exec_command("ufw status 2>/dev/null || echo 'ufw not installed'")
        x = stdout.channel.recv_exit_status()
        fw = stdout.read().decode().strip()
        print("Firewall:", fw)
        
        # If ufw is active, open port
        if "active" in fw.lower():
            stdin, stdout, stderr = ssh.exec_command("ufw allow 16778/tcp comment 'Xray VLESS REALITY'")
            x = stdout.channel.recv_exit_status()
            print("UFW rule added:", "OK" if x == 0 else "FAIL")
    else:
        print("Config test failed!")

finally:
    ssh.close()