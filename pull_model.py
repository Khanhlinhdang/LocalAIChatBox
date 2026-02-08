"""Pull llama3.2:3b in background, then deploy"""
import paramiko, json, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.xxx.xxx', username='root', password='password')

def run(cmd, timeout=120):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out)
    return out

# Check if llama3.2:3b already pulled
print("Checking existing models...")
models = run("curl -s http://localhost:11434/api/tags")
if "llama3.2:3b" in models:
    print("llama3.2:3b already available!")
else:
    print("Pulling llama3.2:3b in background...")
    # Pull in background using nohup
    ssh.exec_command("nohup curl -s http://localhost:11434/api/pull -d '{\"name\": \"llama3.2:3b\", \"stream\": false}' --max-time 600 > /tmp/pull_result.txt 2>&1 &")
    
    # Monitor pull progress
    for i in range(60):  # up to 10 min
        time.sleep(10)
        result = run("cat /tmp/pull_result.txt 2>/dev/null || echo 'still pulling...'")
        if 'still pulling' not in result and result:
            print(f"Pull complete: {result[:100]}")
            break
        # Also check via tags
        tags = run("curl -s http://localhost:11434/api/tags 2>/dev/null")
        if "llama3.2:3b" in tags:
            print("llama3.2:3b is now available!")
            break
        print(f"[{(i+1)*10}s] Still pulling...")

# Verify
print("\nFinal model list:")
run("curl -s http://localhost:11434/api/tags | python3 -c \"import sys,json; [print(f'  {m[\\\"name\\\"]}: {m[\\\"size\\\"]/1e9:.1f}GB') for m in json.load(sys.stdin)['models']]\"")

ssh.close()
print("\nModel pull phase done!")
