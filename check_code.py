import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.165.202', username='root', password='Che.Autotradingkit0123pro')
print('Connected!')

def run(cmd):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    return stdout.read().decode() + stderr.read().decode()

# Check code in git repo
print("=== GIT LOG (last 3) ===")
print(run('cd /root/LocalAIChatBox && git log --oneline -3'))

# Check code on disk
print("\n=== database.py migration check ===")
print(run('cd /root/LocalAIChatBox && grep "Phase 6" backend/app/database.py'))

print("\n=== main.py version check ===")
print(run('cd /root/LocalAIChatBox && grep "6.0.0" backend/app/main.py'))

# Check code in container
print("\n=== container database.py ===")
print(run('docker exec ragchat-backend grep "Phase 6" /app/app/database.py'))

print("\n=== container main.py version ===")
print(run('docker exec ragchat-backend grep "6.0.0" /app/app/main.py'))

print("\n=== container lightrag_service.py LLM_TIMEOUT ===")
print(run('docker exec ragchat-backend grep "LLM_TIMEOUT" /app/app/lightrag_service.py'))

print("\n=== container LLM_TIMEOUT env ===")
print(run('docker exec ragchat-backend env | grep LLM_TIMEOUT'))

# Check docker image creation time
print("\n=== IMAGE AGE ===")
print(run('docker images localaichatbox-backend --format "{{.CreatedAt}}"'))

ssh.close()
print("\nDone!")
