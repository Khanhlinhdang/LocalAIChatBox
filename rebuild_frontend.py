import paramiko, time, json
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.165.202', username='root', password='Che.Autotradingkit0123pro')
print('Connected! Rebuilding frontend...')

cmds = [
    ('cd /root/LocalAIChatBox && docker compose build frontend 2>&1 | tail -5', 300),
    ('cd /root/LocalAIChatBox && docker compose up -d --no-deps --force-recreate frontend 2>&1', 60),
    ('sleep 3 && docker compose -f /root/LocalAIChatBox/docker-compose.yml restart nginx 2>&1', 30),
]
for cmd, timeout in cmds:
    print(f'\n>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip(): print(out.strip()[:2000])
    if err.strip(): print(err.strip()[:500])

print('\nWaiting 10s...')
time.sleep(10)

stdin, stdout, stderr = ssh.exec_command('docker ps --format "table {{.Names}}\t{{.Status}}" --filter name=ragchat', timeout=10)
print(stdout.read().decode())
ssh.close()
print('Done!')
