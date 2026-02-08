import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.xxx.xxx', username='root', password='password', timeout=15)

# Check if test script still running
_, o1, _ = ssh.exec_command('pgrep -f run_test.sh 2>/dev/null | head -5', timeout=10)
pids = o1.read().decode().strip()
print(f"Test script PIDs: {pids if pids else 'DONE'}")

# Read results
_, o2, _ = ssh.exec_command('cat /root/test_results.txt', timeout=30)
content = o2.read().decode(errors='replace')
print(f"\n{'='*60}")
print("TEST RESULTS:")
print('='*60)
print(content)

# Check backend for query-related logs
_, o3, _ = ssh.exec_command('cd /root/LocalAIChatBox && docker compose logs backend --tail=40 2>&1 | grep -iE "query|error|exception|local|global|hybrid|EMPTY" | tail -20', timeout=20)
logs = o3.read().decode(errors='replace')
print(f"\n{'='*60}")
print("QUERY LOGS:")
print('='*60)
print(logs)

ssh.close()

# Save
with open(r'C:\Users\ATK\Desktop\LocalAIChatBox\final_results.txt', 'w', encoding='utf-8') as ff:
    ff.write(content)
print("\nSaved to final_results.txt")
