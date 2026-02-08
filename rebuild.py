"""Continue deployment - rebuild and test"""
import paramiko, json, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.xxx.xxx', username='root', password='password')

def run(cmd, timeout=600):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip()

# Verify config
print("=== Config verification ===")
print(run("grep 'LIGHTRAG_LLM_MODEL' /root/LocalAIChatBox/docker-compose.yml"))
print(run("grep 'LIGHTRAG_NUM_CTX' /root/LocalAIChatBox/docker-compose.yml"))
print(run("grep 'LLM_TIMEOUT' /root/LocalAIChatBox/docker-compose.yml"))
print(run("grep 'llama3.2' /root/LocalAIChatBox/backend/app/lightrag_service.py"))

# Clear storage
print("\n=== Clear + Rebuild ===")
print(run("rm -rf /root/LocalAIChatBox/data/lightrag_storage/* && echo cleared"))
print(run("cd /root/LocalAIChatBox && docker compose stop backend 2>&1 | tail -1"))
time.sleep(3)

# Get current backend image id
img = run("docker images --filter reference='*backend*' -q | head -1")
if img:
    print(f"Removing image {img}...")
    run(f"docker rmi {img} --force 2>/dev/null || true")

print("Building...")
build = run("cd /root/LocalAIChatBox && docker compose build backend 2>&1 | tail -3", timeout=600)
print(build)

print("Starting...")
run("cd /root/LocalAIChatBox && docker compose up -d backend 2>&1")
time.sleep(15)

# Check
containers = run("docker ps --format '{{.Names}} {{.Status}}' | grep ragchat")
print(f"\n{containers}")

health = run("curl -s http://localhost:81/api/lightrag/health")
print(f"\nHealth: {health}")

ssh.close()
print("\nRebuild done!")
