import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.165.202', username='root', password='Che.Autotradingkit0123pro')
print('Connected!')

def run(cmd, timeout=60):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode() + stderr.read().decode()

# Force recreate backend
print("=== FORCE RECREATE BACKEND ===")
print(run('cd /root/LocalAIChatBox && docker compose up -d --force-recreate backend', timeout=120))

# Wait for healthy
print("\n=== WAITING FOR HEALTHY ===")
for i in range(20):
    time.sleep(10)
    status = run('docker inspect --format="{{.State.Health.Status}}" ragchat-backend').strip()
    print(f"  [{(i+1)*10}s] {status}")
    if status == "healthy":
        break

# Check version
print("\n=== API HEALTH ===")
print(run('curl -s http://localhost:81/api/health'))

print("\n=== LIGHTRAG HEALTH ===")
print(run('curl -s http://localhost:81/api/lightrag/health'))

# Check migration log
print("\n=== BACKEND STARTUP LOGS ===")
print(run('docker logs ragchat-backend 2>&1 | head -30'))

ssh.close()
print("\nDone!")
