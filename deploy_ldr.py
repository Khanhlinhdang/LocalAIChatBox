"""
Deploy LDR integration to VPS.
Push code changes, rebuild backend & frontend, verify health.
"""
import paramiko
import time
import sys
import os

from vps_infor import ip, username, password

VPS_DIR = "/root/LocalAIChatBox"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print(f"Connecting to {ip}...")
ssh.connect(ip, username=username, password=password, timeout=30)
print("Connected!")

sftp = ssh.open_sftp()


def run(cmd, timeout=300):
    """Run SSH command and return output."""
    print(f"  > {cmd[:120]}...")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if err and "WARNING" not in err.upper():
        # Only show non-warning errors
        err_short = err[:500]
        if err_short:
            print(f"  STDERR: {err_short}")
    return out


def run_long(cmd, timeout=900):
    """Run long SSH command with live output."""
    print(f"  > {cmd[:120]}...")
    transport = ssh.get_transport()
    chan = transport.open_session()
    chan.set_combine_stderr(True)
    chan.exec_command(cmd)
    out = b""
    start = time.time()
    while time.time() - start < timeout:
        if chan.recv_ready():
            data = chan.recv(65536)
            out += data
            # Print last few lines
            lines = data.decode(errors='replace').strip().split('\n')
            for line in lines[-3:]:
                if line.strip():
                    print(f"    {line.strip()}")
        if chan.exit_status_ready():
            # Read remaining
            while chan.recv_ready():
                out += chan.recv(65536)
            break
        time.sleep(1)
    
    exit_code = chan.recv_exit_status()
    return out.decode(errors='replace').strip(), exit_code


def upload_file(local_path, remote_path):
    """Upload a file via SFTP."""
    try:
        print(f"  Uploading {os.path.basename(local_path)} -> {remote_path}")
        sftp.put(local_path, remote_path)
        return True
    except Exception as e:
        print(f"  Upload failed: {e}")
        return False


def upload_directory(local_dir, remote_dir):
    """Upload a directory recursively."""
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        run(f"mkdir -p {remote_dir}")

    for item in os.listdir(local_dir):
        local_path = os.path.join(local_dir, item)
        remote_path = f"{remote_dir}/{item}"

        if os.path.isdir(local_path):
            # Skip __pycache__ etc
            if item in ('__pycache__', '.git', 'node_modules', '.venv'):
                continue
            upload_directory(local_path, remote_path)
        else:
            if item.endswith('.pyc'):
                continue
            upload_file(local_path, remote_path)


# ==============================================================
print("\n=== STEP 1: Push code changes to VPS ===")

base = os.path.dirname(os.path.abspath(__file__))

# Upload backend files
print("\n-- Backend service files --")
for f in ['ldr_service.py', 'ldr_routes.py']:
    upload_file(
        os.path.join(base, 'backend', 'app', f),
        f"{VPS_DIR}/backend/app/{f}"
    )

# Upload main.py (updated with LDR router)
upload_file(
    os.path.join(base, 'backend', 'app', 'main.py'),
    f"{VPS_DIR}/backend/app/main.py"
)

# Upload requirements.txt
upload_file(
    os.path.join(base, 'backend', 'requirements.txt'),
    f"{VPS_DIR}/backend/requirements.txt"
)

# Upload docker-compose.yml
upload_file(
    os.path.join(base, 'docker-compose.yml'),
    f"{VPS_DIR}/docker-compose.yml"
)

# Upload LDR source directory
print("\n-- LDR source code (this may take a minute) --")
ldr_local = os.path.join(base, 'backend', 'app', 'local_deep_research')
ldr_remote = f"{VPS_DIR}/backend/app/local_deep_research"
# Create dir first
run(f"mkdir -p {ldr_remote}")
upload_directory(ldr_local, ldr_remote)

# Upload frontend files
print("\n-- Frontend files --")
upload_file(
    os.path.join(base, 'frontend', 'src', 'api.js'),
    f"{VPS_DIR}/frontend/src/api.js"
)
upload_file(
    os.path.join(base, 'frontend', 'src', 'pages', 'DeepResearchPage.jsx'),
    f"{VPS_DIR}/frontend/src/pages/DeepResearchPage.jsx"
)

print("\n=== STEP 2: Rebuild backend ===")

print("\n-- Stopping backend --")
print(run(f"cd {VPS_DIR} && docker compose stop backend"))
time.sleep(3)

print("\n-- Removing old backend image --")
print(run("docker rmi localaichatbox-backend:latest --force 2>/dev/null || echo 'no old image'"))

print("\n-- Building backend (this takes 2-5 min) --")
out, code = run_long(f"cd {VPS_DIR} && docker compose build backend", timeout=900)
if code != 0:
    print(f"\nBuild failed with exit code {code}")
    print(out[-1000:])
    ssh.close()
    sys.exit(1)
print("Backend build complete!")

print("\n-- Starting backend --")
print(run(f"cd {VPS_DIR} && docker compose up -d backend"))
time.sleep(15)

print("\n=== STEP 3: Rebuild frontend ===")

print("\n-- Stopping frontend --")
print(run(f"cd {VPS_DIR} && docker compose stop frontend"))
time.sleep(2)

print("\n-- Removing old frontend image --")
print(run("docker rmi localaichatbox-frontend:latest --force 2>/dev/null || echo 'no old image'"))

print("\n-- Building frontend (this takes 1-3 min) --")
out, code = run_long(f"cd {VPS_DIR} && docker compose build frontend", timeout=600)
if code != 0:
    print(f"\nFrontend build failed with exit code {code}")
    print(out[-1000:])
else:
    print("Frontend build complete!")

print("\n-- Starting frontend --")
print(run(f"cd {VPS_DIR} && docker compose up -d frontend"))
time.sleep(10)

# Restart nginx
print("\n-- Restarting nginx --")
print(run(f"cd {VPS_DIR} && docker compose restart nginx"))
time.sleep(5)

print("\n=== STEP 4: Verify deployment ===")

# Check containers
print("\n-- Container status --")
containers = run("docker ps --format '{{.Names}} {{.Status}}' | grep ragchat")
print(containers)

# Check backend health
print("\n-- Backend health --")
health = run("curl -sf http://localhost:8001/api/health || echo 'HEALTH CHECK FAILED'")
print(health)

# Check LDR health
print("\n-- LDR health --")
ldr_health = run("curl -sf http://localhost:8001/api/ldr/health || echo 'LDR NOT AVAILABLE'")
print(ldr_health)

# Check LDR strategies
print("\n-- LDR strategies --")
strategies = run("curl -sf http://localhost:8001/api/ldr/strategies | head -c 200 || echo 'STRATEGIES FAILED'")
print(strategies)

# Check backend logs for errors
print("\n-- Backend logs (last 30 lines) --")
logs = run("docker logs ragchat-backend --tail 30 2>&1")
print(logs)

sftp.close()
ssh.close()
print("\n=== DEPLOYMENT COMPLETE ===")
