import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.165.202', username='root', password='Che.Autotradingkit0123pro')

# Container status
stdin, stdout, stderr = ssh.exec_command('docker ps -a --format "table {{.Names}}\t{{.Status}}"', timeout=30)
print(stdout.read().decode())

# Health check
stdin, stdout, stderr = ssh.exec_command('curl -s http://localhost:8001/api/health', timeout=15)
print('Health:', stdout.read().decode()[:500])

# Backend logs
stdin, stdout, stderr = ssh.exec_command('docker logs ragchat-backend --tail 30 2>&1', timeout=15)
print('\nBackend logs:')
print(stdout.read().decode()[:3000])
ssh.close()
