"""Debug LDR import on VPS"""
import paramiko
from vps_infor import ip, username, password

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(ip, username=username, password=password)

def run(cmd, timeout=60):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out + "\n" + err if err else out

# Test import chain
print("=== Testing LDR import chain ===")

# Step 1: Test basic import
cmd = 'docker exec ragchat-backend python -c "import sys; sys.path.insert(0, \\"/app/app\\"); from local_deep_research.api.research_functions import quick_summary; print(\\\"OK\\\")"'
print("Test 1 - Direct import:")
print(run(cmd))

# Step 2: Check what fails
cmd2 = 'docker exec ragchat-backend python -c "import sys; sys.path.insert(0, \\"/app/app\\"); from local_deep_research.settings.manager import SettingsManager; print(\\\"SettingsManager OK\\\")"'
print("\nTest 2 - SettingsManager:")
print(run(cmd2))

# Step 3: Try importing sqlalchemy_utc
cmd3 = 'docker exec ragchat-backend python -c "import sqlalchemy_utc; print(\\\"sqlalchemy_utc OK\\\")"'
print("\nTest 3 - sqlalchemy_utc:")
print(run(cmd3))

# Step 4: Try pip install
cmd4 = 'docker exec ragchat-backend pip list 2>/dev/null | grep -i utc'
print("\nTest 4 - Installed UTC packages:")
print(run(cmd4))

# Step 5: Check full traceback
cmd5 = '''docker exec ragchat-backend python -c "
import sys, traceback
sys.path.insert(0, '/app/app')
try:
    from local_deep_research.api.research_functions import quick_summary
    print('SUCCESS')
except Exception as e:
    traceback.print_exc()
" 2>&1'''
print("\nTest 5 - Full traceback:")
print(run(cmd5))

ssh.close()
