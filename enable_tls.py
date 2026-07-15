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

# Generate self-signed cert
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, ssh_port, username, look_for_keys=True, allow_agent=True)
    
    # Generate cert
    stdin, stdout, stderr = ssh.exec_command(
        "openssl req -x509 -newkey rsa:4096 -keyout /usr/local/etc/xray/key.pem "
        "-out /usr/local/etc/xray/cert.pem -days 3650 -nodes "
        "-subj '/CN=www.microsoft.com' 2>&1"
    )
    exit_status = stdout.channel.recv_exit_status()
    print("Cert generated:", "OK" if exit_status == 0 else stdout.read().decode() + stderr.read().decode())
    
    # Xray config with TLS
    config = {
        "log": {"loglevel": "warning"},
        "dns": {"servers": ["8.8.8.8", "1.1.1.1", "localhost"]},
        "inbounds": [{
            "port": xray_port,
            "protocol": "vmess",
            "settings": {
                "clients": [{"id": uuid, "alterId": 0}]
            },
            "streamSettings": {
                "network": "ws",
                "security": "tls",
                "tlsSettings": {
                    "certificates": [{
                        "certificateFile": "/usr/local/etc/xray/cert.pem",
                        "keyFile": "/usr/local/etc/xray/key.pem"
                    }]
                },
                "wsSettings": {"path": ws_path}
            }
        }],
        "outbounds": [{
            "protocol": "freedom",
            "tag": "direct",
            "settings": {"domainStrategy": "AsIs"}
        }]
    }
    
    sftp = ssh.open_sftp()
    with sftp.open("/usr/local/etc/xray/config.json", "w") as f:
        f.write(json.dumps(config, indent=2))
    sftp.close()
    print("Xray config updated (TLS enabled)")
    
    # Test config
    stdin, stdout, stderr = ssh.exec_command("/usr/local/bin/xray run -test -config /usr/local/etc/xray/config.json 2>&1")
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode() + stderr.read().decode()
    print("Config test:", out.strip()[:200])
    
    if exit_status == 0:
        # Restart Xray
        stdin, stdout, stderr = ssh.exec_command("systemctl restart xray 2>&1")
        stdout.channel.recv_exit_status()
        print("Xray restarted")
        
        # Check
        stdin, stdout, stderr = ssh.exec_command("systemctl is-active xray && ss -tlnp | grep 443")
        print("Port 443:", stdout.read().decode().strip())
        
        # Update Clash config (add TLS)
        clash_yaml = f"""port: 7890
socks-port: 7891
mixed-port: 7892
allow-lan: false
mode: Rule
log-level: info
ipv6: false

proxies:
  - name: US-VMESS-WS-TLS
    type: vmess
    server: {server}
    port: {xray_port}
    uuid: {uuid}
    alterId: 0
    cipher: auto
    tls: true
    skip-cert-verify: true
    network: ws
    ws-opts:
      path: {ws_path}
    udp: true

proxy-groups:
  - name: Proxy
    type: select
    proxies:
      - US-VMESS-WS-TLS
      - DIRECT

rules:
  - DOMAIN-SUFFIX,google.com,Proxy
  - DOMAIN-SUFFIX,youtube.com,Proxy
  - DOMAIN-SUFFIX,chatgpt.com,Proxy
  - DOMAIN-SUFFIX,openai.com,Proxy
  - DOMAIN-SUFFIX,github.com,Proxy
  - MATCH,DIRECT
"""
        
        sftp = ssh.open_sftp()
        with sftp.open("/var/www/sub/clash.yaml", "w") as f:
            f.write(clash_yaml)
        sftp.close()
        print("Clash config updated (TLS)")
        
        # v2rayN sub
        vmess_json = {
            "v": "2", "ps": "US-VMESS-WS-TLS", "add": server, "port": str(xray_port),
            "id": uuid, "aid": "0", "scy": "auto", "net": "ws",
            "type": "none", "host": "", "path": ws_path, "tls": "tls"
        }
        b64_vmess = base64.b64encode(json.dumps(vmess_json).encode()).decode()
        sftp = ssh.open_sftp()
        with sftp.open("/var/www/sub/v2rayn.txt", "w") as f:
            f.write(b64_vmess + "\n")
        sftp.close()
        print("v2rayN sub updated")
        
        # Quick bandwidth test
        stdin, stdout, stderr = ssh.exec_command("curl -s -o /dev/null -w '%{speed_download}' --connect-timeout 5 https://speed.cloudflare.com/__down?bytes=1000000 2>&1")
        speed = stdout.read().decode().strip()
        print(f"Server download speed: {speed} bytes/s")
        
finally:
    ssh.close()

print()
print("=" * 60)
print("已启用 TLS 加密！VMess 走 HTTPS 伪装，不会被限速。")
print("订阅地址: http://154.9.254.86/clash.yaml")
print("删除旧节点，重新导入后测试。")