"""Insert doc and monitor"""
import paramiko, json, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.xxx.xxx', username='root', password='password')

def cmd(c):
    _, o, _ = ssh.exec_command(c, timeout=120)
    return o.read().decode().strip()

# Token
token = cmd("""python3 -c "import urllib.request,json;r=urllib.request.Request('http://localhost:81/api/auth/login',data=json.dumps({'username':'admin','password':'admin123'}).encode(),headers={'Content-Type':'application/json'},method='POST');print(json.loads(urllib.request.urlopen(r).read())['access_token'])" """)
AUTH = f"Authorization: Bearer {token}"
print(f"Token OK")

# Insert
r = cmd(f"""curl -s -X POST http://localhost:81/api/lightrag/documents/text -H "{AUTH}" -H "Content-Type: application/json" -d '{{"text":"Python is a programming language created by Guido van Rossum in 1991. Google created TensorFlow for machine learning. PyTorch was developed by Meta.","description":"test"}}'""")
print(f"Insert: {r}")

# Monitor - 10s intervals
for i in range(40):
    time.sleep(10)
    try:
        d = json.loads(cmd(f'curl -s http://localhost:81/api/lightrag/documents -H "{AUTH}"'))
        h = json.loads(cmd('curl -s http://localhost:81/api/lightrag/health'))
        s = [x["status"] for x in d.get("documents", [])]
        n, e = h.get("graph_nodes", 0), h.get("graph_edges", 0)
    except:
        s, n, e = ["?"], "?", "?"
    print(f"[{(i+1)*10}s] {s} n={n} e={e}")
    
    if all(x in ["processed","failed"] for x in s) and s:
        if n > 0:
            print(f"\n*** {n} NODES, {e} EDGES ***")
            q = cmd(f"""curl -s -X POST http://localhost:81/api/lightrag/query -H "{AUTH}" -H "Content-Type: application/json" -d '{{"query":"What is Python?","mode":"hybrid"}}'""")
            print(q[:500])
        else:
            l = cmd("docker logs ragchat-backend --tail 20 2>&1 | grep -i 'convert\\|tree\\|entity\\|extract\\|chunk' | tail -10")
            print(f"Logs: {l}")
            o = cmd("python3 -c \"import json;c=json.load(open('/root/LocalAIChatBox/data/lightrag_storage/kv_store_llm_response_cache.json'));[print(v.get('return','')[:800]) for k,v in c.items() if 'extract' in k]\"")
            print(f"LLM: {o}")
        break
ssh.close()
