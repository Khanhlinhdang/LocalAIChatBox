import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.165.202', username='root', password='Che.Autotradingkit0123pro')
print('Connected!')

def run(cmd):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    return stdout.read().decode() + stderr.read().decode()

# Check memory
print("=== MEMORY ===")
print(run('free -h'))

# Check dmesg for OOM
print("\n=== OOM KILLS ===")
print(run('dmesg | grep -i "oom\\|killed" | tail -5'))

# Check Ollama models loaded
print("\n=== OLLAMA PS ===")
print(run('docker exec ragchat-ollama ollama ps'))

# Check disk space
print("\n=== DISK SPACE ===")
print(run('df -h / | tail -1'))

ssh.close()
