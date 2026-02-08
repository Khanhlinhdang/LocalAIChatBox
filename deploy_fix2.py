import paramiko, time, json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.165.202', username='root', password='Che.Autotradingkit0123pro')
print('Connected!')

def run(cmd, timeout=30):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out + err

# Check if the build actually ran/completed
print("=== DOCKER IMAGES ===")
print(run('docker images | grep localai'))

# Check containers
print("\n=== CONTAINERS ===")
print(run('docker ps --format "table {{.Names}}\t{{.Status}}" | head -10'))

# Rebuild and restart backend
print("\n=== REBUILDING BACKEND ===")
transport = ssh.get_transport()
chan = transport.open_session()
chan.set_combine_stderr(True)
chan.exec_command('cd /root/LocalAIChatBox && docker compose build --no-cache backend')
# Read output with proper timeout
start = time.time()
out = b""
while time.time() - start < 600:
    if chan.recv_ready():
        data = chan.recv(65536)
        out += data
        # Print progress
        lines = data.decode(errors='replace').strip().split('\n')
        for l in lines[-3:]:
            if l.strip():
                print(f"  ... {l.strip()[-80:]}")
    if chan.exit_status_ready():
        while chan.recv_ready():
            out += chan.recv(65536)
        break
    time.sleep(2)

exit_code = chan.recv_exit_status()
print(f"\nBuild exit code: {exit_code}")
if exit_code != 0:
    print("BUILD FAILED! Last output:")
    print(out.decode(errors='replace')[-3000:])
else:
    print("Build succeeded!")

# Restart backend
print("\n=== RESTARTING ===")
print(run('cd /root/LocalAIChatBox && docker compose up -d backend', timeout=60))

# Wait for healthy
print("=== WAITING FOR HEALTHY ===")
for i in range(20):
    time.sleep(10)
    status = run('docker inspect --format="{{.State.Health.Status}}" ragchat-backend').strip()
    print(f"  [{(i+1)*10}s] {status}")
    if status == "healthy":
        break

# Check endpoints
print("\n=== API HEALTH ===")
print(run('curl -s http://localhost:81/api/health'))

print("\n=== LIGHTRAG HEALTH ===")
print(run('curl -s http://localhost:81/api/lightrag/health'))

# Backend logs
print("\n=== BACKEND LOGS (last 25) ===")
print(run('docker logs ragchat-backend --tail 25 2>&1'))

ssh.close()
print("\nDone!")
