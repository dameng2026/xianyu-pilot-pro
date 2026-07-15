import paramiko

host = "154.9.254.86"
port = 22
username = "root"

uuid = "6ea8b415-02ba-4760-8421-e00a1d323950"
server = "154.9.254.86"
port_num = 16778
public_key = "7dAENDOApB3V6lHjzYkeRRSdRvFYfpJBXmp_Px3rRAQ"
short_id = "6ba85179"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, port, username, look_for_keys=True, allow_agent=True)
    sftp = ssh.open_sftp()
    
    # Full Clash Meta config (some clients require port/allow-lan header)
    clash_proxies = f"""port: 7890
socks-port: 7891
mixed-port: 7892
allow-lan: false
mode: Rule
log-level: info
ipv6: false

proxies:
  - name: US-REALITY
    type: vless
    server: {server}
    port: {port_num}
    uuid: {uuid}
    flow: xtls-rprx-vision
    tls: true
    servername: www.microsoft.com
    client-fingerprint: chrome
    reality-opts:
      public-key: {public_key}
      short-id: {short_id}
    skip-cert-verify: true
    udp: true

proxy-groups:
  - name: Proxy
    type: select
    proxies:
      - US-REALITY
      - DIRECT

rules:
  - MATCH,Proxy"""

    with sftp.open("/var/www/sub/clash.yaml", "w") as f:
        f.write(clash_proxies)
    print("clash.yaml written")
    
    # Verify content
    stdin, stdout, stderr = ssh.exec_command("cat /var/www/sub/clash.yaml")
    print(stdout.read().decode())
    
finally:
    ssh.close()