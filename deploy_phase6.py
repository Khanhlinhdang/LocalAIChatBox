"""Deploy to VPS - Full automated deploy with LightRAG Phase 6"""
import paramiko
import time
import json

HOST = '194.59.165.202'
USER = 'root'
PASSWORD = 'Che.Autotradingkit0123pro'

def run_ssh(ssh, cmd, timeout=1800):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip():
        print(out.strip()[:2000])
    if err.strip():
        for line in err.strip().split('\n')[:20]:
            if line.strip():
                print(f"  {line}")
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD)
    print(f"Connected to {HOST}!")
    
    # Step 1: Pull latest
    print("\n=== STEP 1: Pull latest code ===")
    run_ssh(ssh, 'cd /root/LocalAIChatBox && git pull')
    
    # Step 2: Create data dirs
    print("\n=== STEP 2: Create data directories ===")
    run_ssh(ssh, 'mkdir -p /root/LocalAIChatBox/data/{vector_store,documents,parser_output,lightrag_storage}')
    run_ssh(ssh, 'chmod -R 777 /root/LocalAIChatBox/data/')
    
    # Step 3: Stop old
    print("\n=== STEP 3: Stop old containers ===")
    run_ssh(ssh, 'cd /root/LocalAIChatBox && docker compose down --remove-orphans 2>&1', timeout=120)
    
    # Step 4: Clean init containers
    print("\n=== STEP 4: Clean init containers ===")
    run_ssh(ssh, 'docker rm -f ragchat-ollama-init ragchat-data-init 2>/dev/null || true')
    
    # Step 5: Build backend
    print("\n=== STEP 5: Build backend (may take 5-10 minutes) ===")
    run_ssh(ssh, 'cd /root/LocalAIChatBox && docker compose build --no-cache backend 2>&1', timeout=900)
    
    # Step 6: Build frontend
    print("\n=== STEP 6: Build frontend ===")
    run_ssh(ssh, 'cd /root/LocalAIChatBox && docker compose build --no-cache frontend 2>&1', timeout=600)
    
    # Step 7: Start everything
    print("\n=== STEP 7: docker compose up -d ===")
    run_ssh(ssh, 'cd /root/LocalAIChatBox && docker compose up -d 2>&1')
    
    # Step 8: Monitor
    print("\n=== STEP 8: Monitoring startup ===")
    for i in range(60):
        time.sleep(10)
        out, _ = run_ssh(ssh, 'docker ps -a --format "table {{.Names}}\t{{.Status}}" 2>/dev/null')
        
        lines = out.strip().split('\n')
        status_map = {}
        for line in lines[1:]:
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                status_map[parts[0]] = parts[1]
        
        print(f"\n--- Check #{i+1} ---")
        for name, status in sorted(status_map.items()):
            print(f"  {name}: {status}")
        
        backend_healthy = '(healthy)' in status_map.get('ragchat-backend', '')
        nginx_up = 'Up' in status_map.get('ragchat-nginx', '')
        
        if backend_healthy and nginx_up:
            print("\n  ALL SERVICES READY!")
            break
        
        # Show backend logs periodically
        if i > 0 and i % 4 == 0:
            print("\n  --- backend logs ---")
            run_ssh(ssh, 'docker logs ragchat-backend --tail 10 2>&1')
    
    # Step 9: Final health check
    print("\n=== STEP 9: Health check ===")
    time.sleep(5)
    out, _ = run_ssh(ssh, 'curl -s http://localhost:8001/api/health 2>/dev/null')
    try:
        health = json.loads(out)
        print(f"  Status: {health.get('status')}")
        print(f"  Version: {health.get('version')}")
    except:
        print("  (could not parse health)")
    
    # Check LightRAG health
    out, _ = run_ssh(ssh, 'curl -s http://localhost:8001/api/lightrag/health 2>/dev/null')
    try:
        lhealth = json.loads(out)
        print(f"  LightRAG initialized: {lhealth.get('initialized')}")
        print(f"  Graph nodes: {lhealth.get('graph_nodes', 0)}")
        print(f"  Graph edges: {lhealth.get('graph_edges', 0)}")
    except:
        print("  (LightRAG health check pending)")
    
    # Step 10: Final status 
    print("\n=== STEP 10: Final container status ===")
    run_ssh(ssh, 'docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null')
    
    # Backend logs
    print("\n=== Backend logs (last 30) ===")
    run_ssh(ssh, 'docker logs ragchat-backend --tail 30 2>&1')
    
    ssh.close()
    print(f"\n{'='*60}")
    print("DEPLOYMENT COMPLETE!")
    print(f"Access: http://{HOST}:81")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
