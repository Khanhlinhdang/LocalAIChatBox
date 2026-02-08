import paramiko, json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.165.202', username='root', password='Che.Autotradingkit0123pro')
print('Connected!')

def run(cmd):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    return stdout.read().decode() + stderr.read().decode()

# 1. Containers
print("=== CONTAINERS ===")
print(run('docker ps --format "table {{.Names}}\t{{.Status}}" | head -10'))

# 2. Backend version
print("=== API HEALTH ===")
h = run('curl -s http://localhost:81/api/health')
print(h[:200])

print("\n=== LIGHTRAG HEALTH ===")
print(run('curl -s http://localhost:81/api/lightrag/health'))

# 3. Check migration ran
print("\n=== BACKEND LOGS (tail 25) ===")
print(run('docker logs ragchat-backend --tail 25 2>&1'))

# 4. Test auth + insert
login = run('curl -s -X POST http://localhost:81/api/auth/login -H "Content-Type: application/json" -d \'{"username":"admin","password":"admin123"}\'')
token = json.loads(login).get("access_token", "")
print(f"\n=== TOKEN: {token[:20]}... ===")

# 5. Clear old failed docs
AUTH = f"Authorization: Bearer {token}"
print("\n=== CLEAR OLD DOCS ===")
print(run(f'curl -s -X DELETE http://localhost:81/api/lightrag/documents -H "{AUTH}"'))

# 6. Insert test text
print("\n=== INSERT TEXT ===")
print(run(f'curl -s -X POST http://localhost:81/api/lightrag/documents/text -H "Content-Type: application/json" -H "{AUTH}" -d \'{{"text": "Python is a programming language. Machine Learning uses Python libraries like TensorFlow and PyTorch.", "description": "Python ML"}}\''))

ssh.close()
print("\nDone!")
