import paramiko, json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.xxx.xxx', username='root', password='password')
print('Connected!')

def run(cmd, timeout=30):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out, err

# Check backend logs for insert activity
out, _ = run('docker logs ragchat-backend --tail 40 2>&1')
print("=== BACKEND LOGS ===")
print(out)

# Login and check docs
out, _ = run('curl -s -X POST http://localhost:81/api/auth/login -H "Content-Type: application/json" -d \'{"username":"admin","password":"admin123"}\'')
token = json.loads(out).get("access_token", "")
AUTH = f"Authorization: Bearer {token}"

# Raw documents response
out, _ = run(f'curl -s http://localhost:81/api/lightrag/documents -H "{AUTH}"')
print("\n=== RAW DOCUMENTS RESPONSE ===")
print(repr(out[:500]))

# LightRAG health
out, _ = run('curl -s http://localhost:81/api/lightrag/health')
print("\n=== LIGHTRAG HEALTH ===")
print(out)

# Check graph
out, _ = run(f'curl -s "http://localhost:81/api/lightrag/graphs?limit=10" -H "{AUTH}"')
print("\n=== GRAPH ===")
print(out[:500])

ssh.close()
print("\nDone!")
