import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.165.202', username='root', password='Che.Autotradingkit0123pro')
print('Connected!')

def run(cmd):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    return stdout.read().decode() + stderr.read().decode()

print(run('docker ps --format "table {{.Names}}\t{{.Status}}" | head -10'))
print("\n--- Image ---")
print(run('docker images localaichatbox-backend --format "{{.ID}} {{.CreatedAt}}"'))
print("\n--- Version in container ---")
print(run('docker exec ragchat-backend grep "LightRAG Edition" /app/app/main.py 2>&1'))
print("\n--- Phase 6 migration ---")
print(run('docker exec ragchat-backend grep "Phase 6" /app/app/database.py 2>&1'))
print("\n--- LLM_TIMEOUT ---")
print(run('docker exec ragchat-backend grep "LLM_TIMEOUT" /app/app/lightrag_service.py 2>&1'))
print("\n--- API Health ---")
print(run('curl -s http://localhost:81/api/health | head -1'))
print("\n--- Startup logs ---")
print(run('docker logs ragchat-backend 2>&1 | head -10'))

ssh.close()
