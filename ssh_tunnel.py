# ssh_tunnel.py
import subprocess
import socket

def is_port_in_use(port=5432):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0

def start_ssh_tunnel():
    if is_port_in_use(5432):
        print("🔁 Tunnel already active on port 5432, skipping...")
        return

    print("🔐 Starting SSH tunnel...")
    cmd = [
        "ssh", "-N", "-f",  # -N: no shell, -f: background
        "-o", "StrictHostKeyChecking=no",
        "-o", "ExitOnForwardFailure=yes",
        "-L", "5432:localhost:5432",
        "adt2025SS@194.95.221.127", "-p", "22"
    ]
    try:
        subprocess.check_call(cmd)
        print("✅ SSH tunnel started")
    except subprocess.CalledProcessError as e:
        print("❌ Failed to start SSH tunnel")
        raise e
