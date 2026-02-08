import paramiko, time, json

HOST = '194.59.165.202'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username='root', password='Che.Autotradingkit0123pro')
print('Connected!')

def run(cmd, t=900):
    print(f"\n>>> {cmd}")
    transport = ssh.get_transport()
    channel = transport.open_session()
    channel.set_combine_stderr(True)
    channel.exec_command(cmd)
    output = b""
    while True:
        if channel.recv_ready():
            data = channel.recv(4096)
            output += data
            # Print progress
            text = data.decode('utf-8', errors='replace')
            for line in text.split('\n'):
                if line.strip():
                    print(f"  {line.strip()[:120]}")
        if channel.exit_status_ready():
            # Drain remaining
            while channel.recv_ready():
                output += channel.recv(4096)
            break
        time.sleep(0.5)
    exit_code = channel.recv_exit_status()
    print(f"  [Exit: {exit_code}]")
    return output.decode('utf-8', errors='replace'), exit_code

# Build backend
print("\n=== Building backend ===")
out, code = run('cd /root/LocalAIChatBox && docker compose build backend', 900)

if code != 0:
    print("\nBuild failed! Checking error:")
    lines = out.strip().split('\n')
    for line in lines[-30:]:
        print(f"  {line}")
else:
    print("\n Backend build SUCCESS!")

# Build frontend
print("\n=== Building frontend ===")
out, code = run('cd /root/LocalAIChatBox && docker compose build frontend', 600)
if code != 0:
    print("\nFrontend build failed!")
    lines = out.strip().split('\n')
    for line in lines[-20:]:
        print(f"  {line}")
else:
    print("\n Frontend build SUCCESS!")

# Start everything
print("\n=== Starting ===")
run('cd /root/LocalAIChatBox && docker compose up -d', 120)

# Wait & monitor
print("\n=== Monitoring ===")
for i in range(40):
    time.sleep(15)
    out, _ = run('docker ps -a --format "table {{.Names}}\t{{.Status}}"', 15)
    
    if '(healthy)' in out and 'ragchat-backend' in out:
        backend_line = [l for l in out.split('\n') if 'ragchat-backend' in l]
        if backend_line and '(healthy)' in backend_line[0]:
            print("\n  BACKEND HEALTHY!")
            break
    
    if i % 3 == 0 and i > 0:
        print("  --- backend logs ---")
        run('docker logs ragchat-backend --tail 5 2>&1', 10)

# Health check
print("\n=== Health Check ===")
time.sleep(3)
out, _ = run('curl -s http://localhost:8001/api/health', 10)
try:
    h = json.loads(out.strip().split('\n')[-1])
    print(f"  Status: {h.get('status')}, Version: {h.get('version')}")
except:
    pass

out, _ = run('curl -s http://localhost:8001/api/lightrag/health', 10)
try:
    h = json.loads(out.strip().split('\n')[-1])
    print(f"  LightRAG: initialized={h.get('initialized')}, nodes={h.get('graph_nodes', 0)}, edges={h.get('graph_edges', 0)}")
except:
    pass

# Final status
print("\n=== Final Status ===")
run('docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"', 10)

# Backend logs
print("\n=== Backend Logs ===")
run('docker logs ragchat-backend --tail 25 2>&1', 10)

ssh.close()
print(f"\nDONE! Access: http://{HOST}:81")
