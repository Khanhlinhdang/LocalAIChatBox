import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.xxx.xxx', username='root', password='password', timeout=15)

# Check if script still running
_, o1, _ = ssh.exec_command('pgrep -f run_test.sh', timeout=10)
pids = o1.read().decode().strip()
print(f"Script PIDs: {pids}")

# Read the results file  
_, o2, _ = ssh.exec_command('wc -l /root/test_results.txt && cat /root/test_results.txt', timeout=30)
content = o2.read().decode(errors='replace')
print(f"Results file:\n{content}")

# Also check backend logs for more info
_, o3, _ = ssh.exec_command('cd /root/LocalAIChatBox && docker compose logs backend --tail=20 2>&1', timeout=30)
logs = o3.read().decode(errors='replace')
print(f"\nBackend logs:\n{logs[-2000:]}")

ssh.close()
