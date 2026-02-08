"""Quick fix: set LDR_ALLOW_UNENCRYPTED, test import, then rebuild properly."""
import paramiko
import time
from vps_infor import ip, username, password

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(ip, username=username, password=password)

def run(cmd, timeout=300):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out + ("\n" + err if err else "")

# Test with env var
print("=== Test LDR with unencrypted mode ===")
test = run('''docker exec -e LDR_ALLOW_UNENCRYPTED=true ragchat-backend python -c "
import sys
sys.path.insert(0, '/app/app')
import os
os.environ['LDR_ALLOW_UNENCRYPTED'] = 'true'
from local_deep_research.api.research_functions import quick_summary
print('SUCCESS: LDR imported!')
" 2>&1''')
print(test)

if 'SUCCESS' in test:
    print("\n=== LDR imports work! Uploading fixed files and restarting ===")
else:
    print("\n=== Still failing, checking what else is needed ===")
    # Check more specific errors
    test2 = run('''docker exec -e LDR_ALLOW_UNENCRYPTED=true ragchat-backend python -c "
import sys, traceback
sys.path.insert(0, '/app/app')
import os
os.environ['LDR_ALLOW_UNENCRYPTED'] = 'true'
try:
    from local_deep_research.api.research_functions import quick_summary
    print('OK')
except Exception as e:
    traceback.print_exc()
" 2>&1''')
    print(test2)

# Upload fixed files
sftp = ssh.open_sftp()
import os
base = os.path.dirname(os.path.abspath(__file__))

print("\n-- Uploading ldr_service.py (with LDR_ALLOW_UNENCRYPTED) --")
sftp.put(
    os.path.join(base, 'backend', 'app', 'ldr_service.py'),
    '/root/LocalAIChatBox/backend/app/ldr_service.py'
)

print("-- Uploading docker-compose.yml --")
sftp.put(
    os.path.join(base, 'docker-compose.yml'),
    '/root/LocalAIChatBox/docker-compose.yml'
)

print("-- Uploading requirements.txt --")
sftp.put(
    os.path.join(base, 'backend', 'requirements.txt'),
    '/root/LocalAIChatBox/backend/requirements.txt'
)

sftp.close()

# Rebuild backend with proper requirements
print("\n=== Rebuilding backend with all deps ===")
print(run("cd /root/LocalAIChatBox && docker compose stop backend"))
time.sleep(3)
print(run("docker rmi localaichatbox-backend:latest --force 2>/dev/null || true"))

print("Building (this takes a few minutes)...")
transport = ssh.get_transport()
chan = transport.open_session()
chan.set_combine_stderr(True)
chan.exec_command("cd /root/LocalAIChatBox && docker compose build backend")
out = b""
start = time.time()
while time.time() - start < 900:
    if chan.recv_ready():
        data = chan.recv(65536)
        out += data
        lines = data.decode(errors='replace').strip().split('\n')
        for l in lines[-2:]:
            if l.strip():
                print(f"  {l.strip()}")
    if chan.exit_status_ready():
        while chan.recv_ready():
            out += chan.recv(65536)
        break
    time.sleep(1)

code = chan.recv_exit_status()
if code != 0:
    print(f"BUILD FAILED (exit {code})")
    print(out.decode(errors='replace')[-500:])
else:
    print("Build OK!")

print("\n-- Starting backend --")
print(run("cd /root/LocalAIChatBox && docker compose up -d backend"))
time.sleep(20)

# Verify
print("\n=== Health checks ===")
print("Backend:", run("curl -sf http://localhost:8001/api/health | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[\"status\"])'"))
print("LDR:", run("curl -sf http://localhost:8001/api/ldr/health"))
print("Containers:", run("docker ps --format '{{.Names}} {{.Status}}' | grep ragchat"))

ssh.close()
print("\nDone!")
