import paramiko
import json
import urllib.parse
import base64

host = "154.9.254.86"
port = 22
username = "root"

uuid = "0a2cc1cd-e0ae-46f5-84e8-abbcb8960e05"
server = "154.9.254.86"
port_vmess = 8080
path = "/vmess"

# VMess over WebSocket config
config = {
    "log": {
        "loglevel": "warning"
    },
    "inbounds": [
        {
            "port": port_vmess,
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
                    "path": path
                }
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
    
    # Write config
    sftp = ssh.open_sftp()
    with sftp.open("/usr/local/etc/xray/config.json", "w") as f:
        f.write(json.dumps(config, indent=2))
    sftp.close()
    print("VMess+WS config written")
    
    # Restart Xray
    stdin, stdout, stderr = ssh.exec_command("systemctl restart xray")
    exit_status = stdout.channel.recv_exit_status()
    print("Xray restarted")
    
    # Check status
    stdin, stdout, stderr = ssh.exec_command("systemctl is-active xray && ss -tlnp | grep 8080")
    print(stdout.read().decode())
    
    # Generate Clash config
    clash_yaml = f"""port: 7890
socks-port: 7891
mixed-port: 7892
allow-lan: false
mode: Rule
log-level: info
ipv6: false

proxies:
  - name: US-VMESS-WS
    type: vmess
    server: {server}
    port: {port_vmess}
    uuid: {uuid}
    alterId: 0
    cipher: auto
    tls: false
    network: ws
    path: {path}

proxy-groups:
  - name: Proxy
    type: select
    proxies:
      - US-VMESS-WS
      - DIRECT

rules:
  - DOMAIN-SUFFIX,google.com,Proxy
  - DOMAIN-SUFFIX,youtube.com,Proxy
  - DOMAIN-SUFFIX,openai.com,Proxy
  - MATCH,DIRECT
"""
    
    sftp = ssh.open_sftp()
    with sftp.open("/var/www/sub/clash.yaml", "w") as f:
        f.write(clash_yaml)
    print("Clash config updated")
    
    # Generate v2rayN subscription
    vmess_json = {
        "v": "2",
        "ps": "US-VMESS-WS",
        "add": server,
        "port": str(port_vmess),
        "id": uuid,
        "aid": "0",
        "scy": "auto",
        "net": "ws",
        "type": "none",
        "host": "",
        "path": path,
        "tls": "none"
    }
    b64_vmess = base64.b64encode(json.dumps(vmess_json).encode()).decode()
    with sftp.open("/var/www/sub/v2rayn.txt", "w") as f:
        f.write(b64_vmess + "\n")
    print("v2rayN subscription updated")
    
    sftp.close()
    
    # Verify
    print("\n=== Final info ===")
    print(f"Server: {server}:{port_vmess}")
    print(f"UUID: {uuid}")
    print(f"Network: WebSocket, Path: {path}")
    print()
    print("Clash subscription: http://{server}/clash.yaml")

finally:
    ssh.close()