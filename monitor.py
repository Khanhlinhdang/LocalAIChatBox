import paramiko, json, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.xxx.xxx', username='root', password='password')

def run(cmd, timeout=300):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip()

# Get token
token = run("""python3 -c "
import urllib.request, json
req = urllib.request.Request('http://localhost:81/api/auth/login', 
    data=json.dumps({'username':'admin','password':'admin123'}).encode(),
    headers={'Content-Type':'application/json'}, method='POST')
resp = urllib.request.urlopen(req)
print(json.loads(resp.read())['access_token'])
" """)
AUTH = f"Authorization: Bearer {token}"
print(f"Token: {token[:20]}...")

# Check if the insert from deploy script worked
docs = run(f'curl -s http://localhost:81/api/lightrag/documents -H "{AUTH}"')
print(f"\nDocuments: {docs}")

health = run('curl -s http://localhost:81/api/lightrag/health')
print(f"\nHealth: {health}")

# Check backend logs for recent activity
logs = run('docker logs ragchat-backend --tail 30 2>&1 | grep -v "GET /api/health"')
print(f"\nRecent logs:\n{logs}")

# Check memory
mem = run('free -h')
print(f"\nMemory:\n{mem}")

# Check ollama
ps = run('curl -s http://localhost:11434/api/ps')
print(f"\nOllama models loaded: {ps}")

# If no documents, insert one
docs_data = json.loads(docs) if docs else {"documents": []}
if not docs_data.get("documents"):
    print("\n--- No documents found, inserting test doc ---")
    insert = run(f'''curl -s -X POST http://localhost:81/api/lightrag/documents/text \
      -H "{AUTH}" \
      -H "Content-Type: application/json" \
      -d '{{"text": "Python is a programming language. Google uses TensorFlow.", "description": "test_doc"}}'
    ''', timeout=300)
    print(f"Insert result: {insert}")
    
    # Monitor processing
    for i in range(12):  # Check every 30s for 6 minutes
        time.sleep(30)
        status = run(f'curl -s http://localhost:81/api/lightrag/documents -H "{AUTH}"')
        h = run('curl -s http://localhost:81/api/lightrag/health')
        mem_line = run("free -h | grep Mem")
        oll = run('curl -s http://localhost:11434/api/ps | python3 -c "import sys,json; d=json.load(sys.stdin); print([(m[\"name\"],m.get(\"context_length\")) for m in d.get(\"models\",[])])" 2>/dev/null')
        
        status_data = json.loads(status) if status else {}
        health_data = json.loads(h) if h else {}
        
        doc_statuses = [d.get("status") for d in status_data.get("documents", [])]
        nodes = health_data.get("graph_nodes", 0)
        edges = health_data.get("graph_edges", 0)
        
        print(f"\n[{(i+1)*30}s] Docs: {doc_statuses} | Graph: {nodes} nodes, {edges} edges | Models: {oll} | {mem_line}")
        
        if all(s in ["processed", "failed"] for s in doc_statuses) and doc_statuses:
            print(f"\n{'='*60}")
            if "processed" in doc_statuses:
                print("SUCCESS! Document processed!")
            else:
                print("FAILED - all documents failed")
                err = run('docker logs ragchat-backend --tail 50 2>&1 | grep -i "error\|fail\|timeout" | tail -10')
                print(f"Errors: {err}")
            break
else:
    print(f"\nExisting documents found: {[d.get('status') for d in docs_data['documents']]}")
    if any(d.get('status') == 'processing' for d in docs_data['documents']):
        print("Still processing, monitoring...")
        for i in range(12):
            time.sleep(30)
            status = run(f'curl -s http://localhost:81/api/lightrag/documents -H "{AUTH}"')
            h = run('curl -s http://localhost:81/api/lightrag/health')
            status_data = json.loads(status) if status else {}
            health_data = json.loads(h) if h else {}
            doc_statuses = [d.get("status") for d in status_data.get("documents", [])]
            nodes = health_data.get("graph_nodes", 0)
            print(f"[{(i+1)*30}s] Docs: {doc_statuses} | Graph: {nodes} nodes")
            if all(s in ["processed", "failed"] for s in doc_statuses):
                break

ssh.close()
print("\nDone!")
