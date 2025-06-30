# cleanup_tunnel.py
import subprocess
import os
from dotenv import load_dotenv

load_dotenv()

PORT = os.getenv("LOCAL_TUNNEL_PORT", "5433")  # fallback if not in .env

def close_tunnels(port: str = PORT):
    """
    Kill any SSH tunnel processes using -N -f with the target port.
    """
    try:
        # Find matching SSH processes
        result = subprocess.run(
            ["pgrep", "-af", f"ssh .*{port}:localhost"],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split("\n")

        killed = 0
        for line in lines:
            if line and f"{port}:localhost" in line and "-N" in line:
                pid = line.split()[0]
                subprocess.run(["kill", pid])
                print(f"🛑 Killed tunnel process: {pid} ({line})")
                killed += 1

        if killed == 0:
            print(f"✅ No SSH tunnel found on port {port}.")
    except Exception as e:
        print("⚠️ Error cleaning up tunnels:", e)

if __name__ == "__main__":
    close_tunnels()
