"""Deploy to VPS - Full automated deploy with new docker-compose"""
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
        print(out.strip()[:3000])
    if err.strip():
        for line in err.strip().split('\n')[:30]:
            if line.strip():
                print(f"  {line}")
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD)
    print(f"Connected to {HOST}!")
    
    # Step 1: Pull latest code
    print("\n" + "="*60)
    print("STEP 1: Pull latest code")
    print("="*60)
    run_ssh(ssh, 'cd /root/LocalAIChatBox && git pull')
    
    # Step 2: Create data directories on host
    print("\n" + "="*60)
    print("STEP 2: Create data directories")
    print("="*60)
    run_ssh(ssh, 'mkdir -p /root/LocalAIChatBox/data/{vector_store,documents,parser_output,lightrag_storage}')
    run_ssh(ssh, 'chmod -R 777 /root/LocalAIChatBox/data/')
    
    # Step 3: Stop old containers
    print("\n" + "="*60)
    print("STEP 3: Stop old containers")
    print("="*60)
    run_ssh(ssh, 'cd /root/LocalAIChatBox && docker compose down --remove-orphans')
    
    # Step 4: Remove old init containers if they exist (so they re-run)
    print("\n" + "="*60)
    print("STEP 4: Clean init containers")
    print("="*60)
    run_ssh(ssh, 'docker rm -f ragchat-ollama-init ragchat-data-init 2>/dev/null || true')
    
    # Step 5: Build
    print("\n" + "="*60)
    print("STEP 5: Build images")
    print("="*60)
    run_ssh(ssh, 'cd /root/LocalAIChatBox && docker compose build backend frontend', timeout=600)
    
    # Step 6: Start everything
    print("\n" + "="*60)
    print("STEP 6: docker compose up -d")
    print("="*60)
    run_ssh(ssh, 'cd /root/LocalAIChatBox && docker compose up -d')
    
    # Step 7: Monitor startup
    print("\n" + "="*60)
    print("STEP 7: Monitoring startup...")
    print("="*60)
    
    for i in range(90):  # 15 min max
        time.sleep(10)
        out, _ = run_ssh(ssh, 'docker ps -a --format "table {{.Names}}\t{{.Status}}" 2>/dev/null')
        
        lines = out.strip().split('\n')
        status_map = {}
        for line in lines[1:]:
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                status_map[parts[0]] = parts[1]
        
        print(f"\n--- Status check #{i+1} ---")
        for name, status in sorted(status_map.items()):
            print(f"  {name}: {status}")
        
        # Check completion conditions
        ollama_init_done = status_map.get('ragchat-ollama-init', '').startswith('Exited (0)')
        data_init_done = status_map.get('ragchat-data-init', '').startswith('Exited (0)')
        backend_healthy = '(healthy)' in status_map.get('ragchat-backend', '')
        nginx_up = 'Up' in status_map.get('ragchat-nginx', '')
        
        if backend_healthy and nginx_up:
            print("\n  ALL SERVICES READY!")
            break
        
        if ollama_init_done:
            print("  [OK] Models pulled")
        if data_init_done:
            print("  [OK] Permissions set")
            
        # Show init logs periodically
        if i > 0 and i % 6 == 0:
            if not ollama_init_done:
                print("\n  --- ollama-init logs ---")
                run_ssh(ssh, 'docker logs ragchat-ollama-init --tail 3 2>&1')
    
    # Step 8: Final health check
    print("\n" + "="*60)
    print("STEP 8: Final health check")
    print("="*60)
    time.sleep(5)
    out, _ = run_ssh(ssh, 'curl -s http://localhost:8001/api/health 2>/dev/null')
    try:
        health = json.loads(out)
        print(f"\n  Status:  {health.get('status')}")
        print(f"  Version: {health.get('version')}")
        for svc, info in health.get('services', {}).items():
            if isinstance(info, dict):
                print(f"  {svc}: {info.get('status', info)}")
                for k, v in info.items():
                    if k != 'status':
                        print(f"    {k}: {v}")
            else:
                print(f"  {svc}: {info}")
    except:
        print("  (could not parse health response)")
    
    # Step 9: Final container status
    print("\n" + "="*60)
    print("STEP 9: Final container status")
    print("="*60)
    run_ssh(ssh, 'docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null')
    
    # Backend logs
    print("\n" + "="*60)
    print("Backend logs (last 20 lines):")
    print("="*60)
    run_ssh(ssh, 'docker logs ragchat-backend --tail 20 2>&1')
    
    ssh.close()
    print("\n" + "="*60)
    print("DEPLOYMENT COMPLETE!")
    print(f"Access: http://{HOST}:81")
    print("="*60)

if __name__ == '__main__':
    main()
