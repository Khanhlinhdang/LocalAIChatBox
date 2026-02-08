import paramiko, time

HOST = '194.59.165.202'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username='root', password='Che.Autotradingkit0123pro')
print('Connected!')

# Check if docker is running
_, stdout, stderr = ssh.exec_command('docker ps -a --format "table {{.Names}}\t{{.Status}}" 2>&1', timeout=30)
out = stdout.read().decode()
err = stderr.read().decode()
print("Docker PS:", out[:1000])
if err:
    print("Stderr:", err[:500])

# Check disk space 
_, stdout, _ = ssh.exec_command('df -h / 2>&1')
print("Disk space:", stdout.read().decode()[:500])

# Try building backend in foreground with output
print("\n=== Building backend... ===")
_, stdout, stderr = ssh.exec_command('cd /root/LocalAIChatBox && docker compose build backend 2>&1', timeout=900)
out = stdout.read().decode()
err = stderr.read().decode()
if out:
    # Show last 50 lines
    lines = out.strip().split('\n')
    print('\n'.join(lines[-50:]))
if err:
    lines = err.strip().split('\n')
    print('\n'.join(lines[-30:]))

ssh.close()
print("\nDone!")
