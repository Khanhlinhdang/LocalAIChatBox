import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.xxx.xxx', username='root', password='password')
print('Connected!')

def run(cmd, timeout=120):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode() + stderr.read().decode()

# Step 1: Stop backend, remove old image, rebuild
print("=== STOP BACKEND ===")
print(run('cd /root/LocalAIChatBox && docker compose stop backend'))

print("\n=== REMOVE OLD IMAGE ===") 
print(run('docker rmi localaichatbox-backend:latest --force'))

print("\n=== REBUILD (this takes ~2 min) ===")
transport = ssh.get_transport()
chan = transport.open_session()
chan.set_combine_stderr(True)
chan.exec_command('cd /root/LocalAIChatBox && docker compose build backend')
out = b""
start = time.time()
while time.time() - start < 600:
    if chan.recv_ready():
        data = chan.recv(65536)
        out += data
    if chan.exit_status_ready():
        while chan.recv_ready():
            out += chan.recv(65536)
        break
    time.sleep(2)
exit_code = chan.recv_exit_status()
# Print just last few lines
lines = out.decode(errors='replace').strip().split('\n')
for l in lines[-10:]:
    print(f"  {l.strip()}")
print(f"\nBuild exit code: {exit_code}")

if exit_code != 0:
    print("BUILD FAILED!")
    print(out.decode(errors='replace')[-3000:])
else:
    # Step 2: Start with new image
    print("\n=== START BACKEND ===")
    print(run('cd /root/LocalAIChatBox && docker compose up -d backend', timeout=120))
    
    # Step 3: Wait for healthy
    print("\n=== WAITING FOR HEALTHY ===")
    for i in range(20):
        time.sleep(10)
        status = run('docker inspect --format="{{.State.Health.Status}}" ragchat-backend').strip()
        print(f"  [{(i+1)*10}s] {status}")
        if status == "healthy":
            break
    
    # Step 4: Verify
    print("\n=== IMAGE DATE ===")
    print(run('docker images localaichatbox-backend --format "{{.CreatedAt}}"'))
    
    print("\n=== VERSION IN CONTAINER ===")
    print(run('docker exec ragchat-backend grep "6.0.0" /app/app/main.py'))
    
    print("\n=== PHASE 6 MIGRATION ===")
    print(run('docker exec ragchat-backend grep "Phase 6" /app/app/database.py'))
    
    print("\n=== LLM_TIMEOUT IN SERVICE ===")
    print(run('docker exec ragchat-backend grep "LLM_TIMEOUT" /app/app/lightrag_service.py'))
    
    print("\n=== API HEALTH ===")
    print(run('curl -s http://localhost:81/api/health'))
    
    print("\n=== STARTUP LOGS ===")
    print(run('docker logs ragchat-backend 2>&1 | head -25'))

ssh.close()
print("\nDone!")
