import paramiko, json, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.xxx.xxx', username='root', password='password')
print('Connected! Monitoring processing...')

def run(cmd, timeout=30):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode() + stderr.read().decode()

login = run('curl -s -X POST http://localhost:81/api/auth/login -H "Content-Type: application/json" -d \'{"username":"admin","password":"admin123"}\'')
token = json.loads(login).get("access_token", "")
AUTH = f"Authorization: Bearer {token}"

for i in range(30):
    time.sleep(20)
    docs = run(f'curl -s http://localhost:81/api/lightrag/documents -H "{AUTH}"')
    health = run('curl -s http://localhost:81/api/lightrag/health')
    mem = run('free -h | grep Mem').strip()
    
    try:
        d = json.loads(docs)
        h = json.loads(health)
        statuses = [doc['status'] for doc in d.get('documents', [])]
        nodes = h.get('graph_nodes', 0)
        edges = h.get('graph_edges', 0)
        print(f"  [{(i+1)*20}s] Docs: {statuses} | Graph: {nodes}N {edges}E | {mem}")
        
        if all(s in ['processed', 'failed'] for s in statuses):
            print("  Processing complete!")
            break
    except:
        print(f"  [{(i+1)*20}s] Checking...")

# Final results
print("\n=== FINAL GRAPH ===")
graph = run(f'curl -s "http://localhost:81/api/lightrag/graphs?limit=30" -H "{AUTH}"')
try:
    g = json.loads(graph)
    print(f"  Total: {g['total_nodes']} nodes, {g['total_edges']} edges")
    for n in g.get('nodes', [])[:10]:
        print(f"    [{n.get('entity_type','')}] {n.get('id','')} - {n.get('description','')[:60]}")
    for e in g.get('edges', [])[:10]:
        print(f"    {e.get('source','')} -> {e.get('target','')}  ({e.get('description','')[:40]})")
except:
    print(graph[:500])

print("\n=== BACKEND ERRORS ===")
errs = run('docker logs ragchat-backend --tail 20 2>&1 | grep -i "error\\|fail\\|killed\\|timeout" | tail -5')
print(errs if errs.strip() else "  No errors!")

ssh.close()
print("\nDone!")
