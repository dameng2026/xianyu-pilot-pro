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
                "security": "xtls",
                "xtlsSettings": {
                    "minVersion": "1.2"
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

config_json = json.dumps(config, indent=2)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, port, username, look_for_keys=True, allow_agent=True)
    
    # Write config file
    cmd = f'cat > /usr/local/etc/xray/config.json << "ENDOFFILE"\n{config_json}\nENDOFFILE'
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    err = stderr.read().decode()
    if err: print("Stderr:", err)
    print("Config written, exit:", exit_status)
    
    # Check config JSON validity
    stdin, stdout, stderr = ssh.exec_command("/usr/local/bin/xray run -test -config /usr/local/etc/xray/config.json")
    while not stdout.channel.exit_status_ready():
        pass
    out = stdout.read().decode()
    err = stderr.read().decode()
    print("Test output:", out)
    if err: print("Test stderr:", err)

    # Restart Xray
    stdin, stdout, stderr = ssh.exec_command("systemctl restart xray && systemctl enable xray")
    exit_status = stdout.channel.recv_exit_status()
    print("Restart exit:", exit_status)
    
    # Check status
    stdin, stdout, stderr = ssh.exec_command("systemctl status xray --no-pager -l | head -20")
    while not stdout.channel.exit_status_ready():
        pass
    print(stdout.read().decode())
    
    # Check firewall
    stdin, stdout, stderr = ssh.exec_command("ufw status 2>/dev/null || echo 'ufw not active'")
    while not stdout.channel.exit_status_ready():
        pass
    print(stdout.read().decode())
    
    # Test listening
    stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 16778")
    while not stdout.channel.exit_status_ready():
        pass
    print("Listening check:", stdout.read().decode())

finally:
    ssh.close()