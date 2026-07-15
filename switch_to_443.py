import paramiko
import json
import base64

host = "154.9.254.86"
ssh_port = 22
username = "root"

uuid = "0a2cc1cd-e0ae-46f5-84e8-abbcb8960e05"
server = "154.9.254.86"
xray_port = 443
ws_path = "/vmess"

config = {
    "log": {
        "loglevel": "warning"
    },
    "dns": {
        "servers": ["8.8.8.8", "1.1.1.1", "localhost"]
    },
    "inbounds": [
        {
            "port": xray_port,
            "protocol": "vmess",
            "settings": {
                "clients": [{"id": uuid, "alterId": 0}]
            },
            "streamSettings": {
                "network": "ws",
                "wsSettings": {"path": ws_path}
            }
        }
    ],
    "outbounds": [
        {
            "protocol": "freedom",
            "tag": "direct",
            "settings": {"domainStrategy": "AsIs"}
        }
    ]
}

# Clash Meta config
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
    port: {xray_port}
    uuid: {uuid}
    alterId: 0
    cipher: auto
    network: ws
    ws-opts:
      path: {ws_path}
    udp: true

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
  - DOMAIN-SUFFIX,github.com,Proxy
  - MATCH,DIRECT
"""

# v2rayN subscription
vmess_json = {
    "v": "2", "ps": "US-VMESS-WS", "add": server, "port": str(xray_port),
    "id": uuid, "aid": "0", "scy": "auto", "net": "ws",
    "type": "none", "host": "", "path": ws_path, "tls": ""
}
b64_vmess = base64.b64encode(json.dumps(vmess_json).encode()).decode()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, ssh_port, username, look_for_keys=True, allow_agent=True)
    sftp = ssh.open_sftp()
    
    # Write Xray config
    with sftp.open("/usr/local/etc/xray/config.json", "w") as f:
        f.write(json.dumps(config, indent=2))
    
    # Write Clash config
    with sftp.open("/var/www/sub/clash.yaml", "w") as f:
        f.write(clash_yaml)
    
    # Write v2rayN sub
    with sftp.open("/var/www/sub/v2rayn.txt", "w") as f:
        f.write(b64_vmess + "\n")
    
    sftp.close()
    print("Configs updated")
    
    # Restart Xray
    stdin, stdout, stderr = ssh.exec_command("systemctl restart xray 2>&1")
    exit_status = stdout.channel.recv_exit_status()
    print("Xray restarted")
    
    # Check
    stdin, stdout, stderr = ssh.exec_command("systemctl is-active xray && ss -tlnp | grep -E ':443|:80|:8080'")
    print("Ports:\n" + stdout.read().decode())
    
    # Verify Xray direct
    stdin, stdout, stderr = ssh.exec_command("curl -s -o /dev/null -w '%{http_code}' --connect-timeout 3 http://127.0.0.1:443/vmess 2>&1")
    print("Xray on 443 response:", stdout.read().decode().strip())
    
    # Verify clash.yaml
    stdin, stdout, stderr = ssh.exec_command("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:80/clash.yaml")
    print("Clash.yaml:", stdout.read().decode().strip())

finally:
    ssh.close()

print()
print("=" * 60)
print("已切换：Xray 直连 443 端口，不再经过 Nginx 代理")
print()
print("订阅地址: http://" + server + "/clash.yaml")
print(f"节点: VMess+WS, {server}:{xray_port}, path={ws_path}")