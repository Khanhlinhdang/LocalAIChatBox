"""Fix missing LDR dependencies on VPS."""
import paramiko
import time
from vps_infor import ip, username, password

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(ip, username=username, password=password)

def run(cmd, timeout=300):
    print(f"  > {cmd[:120]}...")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    result = out
    if err:
        result += "\n" + err
    return result

# Install missing LDR deps in the container
print("=== Installing missing LDR dependencies ===")

# Critical missing packages from LDR's pyproject.toml
missing_packages = [
    "sqlalchemy-utc",
    "flask",
    "flask-cors",
    "flask-socketio",
    "flask-wtf",
    "flask-login",
    "flask-limiter",
    "tiktoken",
    "lxml",
    "pydantic-settings",
    "tenacity",
    "aiohttp",
    "methodtools",
    "click",
]

pkg_str = " ".join(missing_packages)
print(f"\nInstalling: {pkg_str}")
result = run(f"docker exec ragchat-backend pip install {pkg_str}", timeout=300)
print(result[-500:])  # print last 500 chars

# Test import again
print("\n=== Testing LDR import ===")
test_cmd = '''docker exec ragchat-backend python -c "
import sys
sys.path.insert(0, '/app/app')
try:
    from local_deep_research.api.research_functions import quick_summary
    print('SUCCESS: quick_summary imported')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()
" 2>&1'''
print(run(test_cmd))

# If still failing, try to find what else is missing
print("\n=== Testing deeper imports ===")
test_cmd2 = '''docker exec ragchat-backend python -c "
import sys
sys.path.insert(0, '/app/app')
try:
    from local_deep_research.config.llm_config import get_llm
    print('SUCCESS: get_llm imported')
except Exception as e:
    print(f'FAILED: {e}')
" 2>&1'''
print(run(test_cmd2))

test_cmd3 = '''docker exec ragchat-backend python -c "
import sys
sys.path.insert(0, '/app/app')
try:
    from local_deep_research.config.search_config import get_search
    print('SUCCESS: get_search imported')
except Exception as e:
    print(f'FAILED: {e}')
" 2>&1'''
print(run(test_cmd3))

# Restart backend to pick up new packages
print("\n=== Restarting backend ===")
print(run("cd /root/LocalAIChatBox && docker compose restart backend"))
time.sleep(15)

# Final LDR health check
print("\n=== LDR Health Check ===")
print(run("curl -sf http://localhost:8001/api/ldr/health"))

ssh.close()
print("\nDone!")
