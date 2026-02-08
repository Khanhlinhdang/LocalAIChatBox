import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.165.202', username='root', password='Che.Autotradingkit0123pro')
print('Connected!')

# Step 1: Pull latest code
print("=== GIT PULL ===")
_, stdout, stderr = ssh.exec_command('cd /root/LocalAIChatBox && git pull')
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err)

# Step 2: Rebuild backend only (frontend unchanged)
print("\n=== REBUILD BACKEND ===")
channel = ssh.get_transport().open_session()
channel.set_combine_stderr(True)
channel.exec_command('cd /root/LocalAIChatBox && docker compose build --no-cache backend 2>&1 | tail -20')
output = b""
while True:
    if channel.recv_ready():
        output += channel.recv(65536)
    if channel.exit_status_ready():
        while channel.recv_ready():
            output += channel.recv(65536)
        break
    time.sleep(1)
print(output.decode()[-2000:])

# Step 3: Restart
print("\n=== RESTART BACKEND ===")
_, stdout, stderr = ssh.exec_command('cd /root/LocalAIChatBox && docker compose up -d backend')
time.sleep(5)
print(stdout.read().decode())
print(stderr.read().decode())

# Step 4: Wait for healthcheck  
print("\n=== WAITING FOR HEALTHY ===")
for i in range(30):
    time.sleep(10)
    _, stdout, _ = ssh.exec_command('docker inspect --format="{{.State.Health.Status}}" ragchat-backend 2>/dev/null')
    status = stdout.read().decode().strip()
    print(f"  [{i*10}s] Status: {status}")
    if status == "healthy":
        break

# Step 5: Check health endpoints
_, stdout, _ = ssh.exec_command('curl -s http://localhost:81/api/health')
print("\n=== API HEALTH ===")
print(stdout.read().decode())

_, stdout, _ = ssh.exec_command('curl -s http://localhost:81/api/lightrag/health')
print("\n=== LIGHTRAG HEALTH ===")
print(stdout.read().decode())

# Step 6: Check backend logs
_, stdout, _ = ssh.exec_command('docker logs ragchat-backend --tail 20 2>&1')
print("\n=== BACKEND LOGS ===")
print(stdout.read().decode())

ssh.close()
print("\nDone!")
