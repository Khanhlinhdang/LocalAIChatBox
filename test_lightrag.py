import paramiko, json, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.165.202', username='root', password='Che.Autotradingkit0123pro')
print('Connected!')

def run(cmd, timeout=120):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode() + stderr.read().decode()

# Login
login = run('curl -s -X POST http://localhost:81/api/auth/login -H "Content-Type: application/json" -d \'{"username":"admin","password":"admin123"}\'')
token = json.loads(login).get("access_token", "")
AUTH = f"Authorization: Bearer {token}"
print(f"Token: {token[:20]}...")

# Clear old docs
print("\n=== CLEAR OLD DATA ===")
print(run(f'curl -s -X DELETE http://localhost:81/api/lightrag/documents -H "{AUTH}"'))

# Insert a short text
print("\n=== INSERT TEXT ===")
result = run(f'''curl -s -X POST http://localhost:81/api/lightrag/documents/text \
  -H "Content-Type: application/json" \
  -H "{AUTH}" \
  -d '{{"text": "Python is a programming language created by Guido van Rossum. TensorFlow is a machine learning framework developed by Google. PyTorch is developed by Meta.", "description": "Tech Overview"}}'
''')
print(result)

# Wait and monitor processing
print("\n=== MONITORING PROCESSING ===")
for i in range(24):
    time.sleep(10)
    docs = run(f'curl -s http://localhost:81/api/lightrag/documents -H "{AUTH}"')
    try:
        doc_data = json.loads(docs)
        if "documents" in doc_data and doc_data["documents"]:
            doc = doc_data["documents"][0]
            status = doc.get("status", "unknown")
            print(f"  [{(i+1)*10}s] Doc status: {status} | name: {doc.get('name','?')}")
            if status == "processed":
                print("  PROCESSING COMPLETE!")
                break
            elif status == "failed":
                print("  PROCESSING FAILED!")
                # Check detailed error
                print(run('docker logs ragchat-backend --tail 10 2>&1'))
                break
        else:
            print(f"  [{(i+1)*10}s] No documents found")
    except Exception as e:
        print(f"  [{(i+1)*10}s] Parse error: {e}")

# Check graph after processing
print("\n=== GRAPH DATA ===")
graph = run(f'curl -s "http://localhost:81/api/lightrag/graphs?limit=20" -H "{AUTH}"')
try:
    g = json.loads(graph)
    print(f"  Nodes: {g.get('total_nodes', 0)}, Edges: {g.get('total_edges', 0)}")
    if g.get('nodes'):
        for n in g['nodes'][:5]:
            print(f"    Node: {n.get('id','?')} ({n.get('entity_type','?')})")
except:
    print(graph[:500])

# Check labels
print("\n=== LABELS ===")
print(run(f'curl -s http://localhost:81/api/lightrag/graph/label/list -H "{AUTH}"'))

# Test query
print("\n=== QUERY (naive) ===")
q_result = run(f'''curl -s -X POST http://localhost:81/api/lightrag/query \
  -H "Content-Type: application/json" \
  -H "{AUTH}" \
  -d '{{"query": "What is Python?", "mode": "naive"}}'
''', timeout=300)
print(q_result[:500])

# Check LightRAG health
print("\n=== LIGHTRAG HEALTH ===")
print(run('curl -s http://localhost:81/api/lightrag/health'))

ssh.close()
print("\nDone!")
