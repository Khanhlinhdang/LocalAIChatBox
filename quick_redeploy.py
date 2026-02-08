import paramiko, time, json
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.165.202', username='root', password='Che.Autotradingkit0123pro')
print('Connected! Quick redeploy...')

cmds = [
    'cd /root/LocalAIChatBox && git pull',
    'cd /root/LocalAIChatBox && docker compose build backend 2>&1 | tail -5',
    'cd /root/LocalAIChatBox && docker compose up -d backend 2>&1',
]
for cmd in cmds:
    print(f'\n>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip()[:2000])
    if err.strip(): print(err.strip()[:500])

print('\nWaiting 15s for backend to start...')
time.sleep(15)

stdin, stdout, stderr = ssh.exec_command('docker logs ragchat-backend --tail 20 2>&1', timeout=15)
print(stdout.read().decode()[:2000])

stdin, stdout, stderr = ssh.exec_command('curl -s http://localhost:8001/api/health', timeout=10)
print('\nHealth:', stdout.read().decode()[:300])

ssh.close()
print('\nDone!')
