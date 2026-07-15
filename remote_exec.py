import paramiko

host = "154.9.254.86"
port = 22
username = "root"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, port, username, look_for_keys=True, allow_agent=True)
    
    print("Connected, updating apt...")
    stdin, stdout, stderr = ssh.exec_command("apt-get update -y", timeout=300)
    
    print("\nOutput:")
    while not stdout.channel.exit_status_ready():
        line = stdout.readline()
        if line:
            print(line.rstrip())
    
    exit_status = stdout.channel.recv_exit_status()
    err = stderr.read().decode()
    if err:
        print("\nStderr:")
        print(err)
    
    print(f"\nExit status: {exit_status}")
    
finally:
    ssh.close()