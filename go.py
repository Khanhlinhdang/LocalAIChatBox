import paramiko, json, time, sys

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('194.59.xxx.xxx', username='root', password='password')
    
    def cmd(c):
        _, o, _ = ssh.exec_command(c, timeout=120)
        return o.read().decode().strip()
    
    # Check backend running
    ps = cmd("docker ps --filter name=ragchat-backend --format '{{.Status}}'")
    print(f"Backend: {ps}", flush=True)
    
    h = cmd("curl -s http://localhost:81/api/lightrag/health")
    print(f"Health: {h}", flush=True)
    
    # Login
    token = cmd("python3 -c \"import urllib.request,json;r=urllib.request.Request('http://localhost:81/api/auth/login',data=json.dumps({'username':'admin','password':'admin123'}).encode(),headers={'Content-Type':'application/json'},method='POST');print(json.loads(urllib.request.urlopen(r).read())['access_token'])\"")
    if not token or len(token) < 10:
        print(f"Token failed: {token}", flush=True)
        ssh.close()
        return
    A = f"Authorization: Bearer {token}"
    print(f"Token: OK", flush=True)
    
    # Check docs
    docs = cmd(f'curl -s http://localhost:81/api/lightrag/documents -H "{A}"')
    print(f"Docs: {docs}", flush=True)
    
    # Insert if empty
    d = json.loads(docs) if docs else {"documents": []}
    if not d.get("documents"):
        print("Inserting...", flush=True)
        r = cmd(f'curl -s -X POST http://localhost:81/api/lightrag/documents/text -H "{A}" -H "Content-Type: application/json" -d \'{{"text":"Python is a programming language created by Guido van Rossum. Google created TensorFlow for ML. PyTorch is by Meta.","description":"test"}}\'')
        print(f"Result: {r}", flush=True)
    
    # Monitor
    for i in range(30):
        time.sleep(10)
        try:
            dd = json.loads(cmd(f'curl -s http://localhost:81/api/lightrag/documents -H "{A}"'))
            hh = json.loads(cmd('curl -s http://localhost:81/api/lightrag/health'))
            ss = [x["status"] for x in dd.get("documents", [])]
            nn = hh.get("graph_nodes", 0)
            ee = hh.get("graph_edges", 0)
        except Exception as ex:
            ss = [str(ex)]
            nn = ee = 0
        print(f"[{(i+1)*10}s] {ss} n={nn} e={ee}", flush=True)
        
        if all(x in ["processed","failed"] for x in ss) and ss:
            if nn > 0:
                print(f"*** SUCCESS: {nn} nodes ***", flush=True)
            else:
                l = cmd("docker logs ragchat-backend --tail 15 2>&1 | grep -i 'convert\\|tree\\|entity\\|extract\\|chunk 1' | tail -8")
                print(f"Logs:\n{l}", flush=True)
                o = cmd("python3 -c \"import json;c=json.load(open('/root/LocalAIChatBox/data/lightrag_storage/kv_store_llm_response_cache.json'));[print(v.get('return','')[:600]) for k,v in c.items() if 'extract' in k]\"")
                print(f"LLM output:\n{o}", flush=True)
            break
    
    ssh.close()

if __name__ == "__main__":
    main()
