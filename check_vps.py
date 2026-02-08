import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('194.59.165.202', username='root', password='Che.Autotradingkit0123pro')
print('Connected!')

# 1. Test direct Ollama connectivity from backend
_, stdout, _ = ssh.exec_command('docker exec ragchat-backend curl -s http://ollama:11434/api/tags')
print("=== OLLAMA MODELS (from backend) ===")
print(stdout.read().decode()[:500])

# 2. Test a quick LLM call from backend
_, stdout, _ = ssh.exec_command('docker exec ragchat-backend python3 -c "import ollama; c=ollama.Client(host=\'http://ollama:11434\'); r=c.chat(model=\'llama3.1\', messages=[{\'role\':\'user\',\'content\':\'say hello in 5 words\'}]); print(r[\'message\'][\'content\'])" 2>&1')
print("\n=== DIRECT LLM TEST ===")
print(stdout.read().decode())

# 3. Test embed from backend
_, stdout, _ = ssh.exec_command('docker exec ragchat-backend python3 -c "import ollama; c=ollama.Client(host=\'http://ollama:11434\'); r=c.embed(model=\'nomic-embed-text:latest\', input=[\'test\']); print(\'Embed dim:\', len(r[\'embeddings\'][0]))" 2>&1')
print("\n=== DIRECT EMBED TEST ===")
print(stdout.read().decode())

# 4. Get more detailed error logs
_, stdout, _ = ssh.exec_command('docker logs ragchat-backend 2>&1 | grep -A5 "timeout\\|ERROR\\|error.*LLM\\|Worker" | tail -30')
print("\n=== TIMEOUT ERROR DETAILS ===")
print(stdout.read().decode())

# 5. Check the insert processing logs more carefully
_, stdout, _ = ssh.exec_command('docker logs ragchat-backend 2>&1 | grep -i "insert\\|chunk\\|entity\\|extract\\|doc-" | tail -20')
print("\n=== INSERT/PROCESSING LOGS ===")
print(stdout.read().decode())

ssh.close()
print("\nDone!")
