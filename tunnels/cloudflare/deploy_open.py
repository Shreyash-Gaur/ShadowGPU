import os
import subprocess
import time
import re
import requests

# --- CONFIGURATION ---
NTFY_CHANNEL = "YOUR_NTFY_CHANNEL"  # Matches your local .env

def send_log(message):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_CHANNEL}", 
            data=f"[KAGGLOG]: {message}".encode(encoding='utf-8')
        )
    except:
        pass

# 1. Install System Dependencies
send_log("Starting setup... Installing zstd and Ollama framework.")
os.system("apt-get update && apt-get install -y zstd")
os.system("curl -fsSL https://ollama.com/install.sh | sh")

# 2. Start Ollama (WITH SECURITY BYPASS & VRAM LOCK)
send_log("Booting up local Ollama background server...")
os.environ["OLLAMA_CONTEXT_LENGTH"] = "131072"
os.environ["OLLAMA_HOST"] = "0.0.0.0"
os.environ["OLLAMA_ORIGINS"] = "*"
os.environ["OLLAMA_KEEP_ALIVE"] = "-1"  # Locks models into the dual T4 GPUs

subprocess.Popen(["ollama", "serve"])
time.sleep(10)

# 3. Pull the Models Sequential Sequence
send_log("ATTENTION: Starting 24GB Qwen 3.6 model download. This will take 3-5 minutes...")
os.system("ollama pull qwen3.6:latest")

send_log("ATTENTION: Pulling secondary Qwen Embedding model...")
os.system("ollama pull qwen3-embedding:latest")

# --- PRE-WARM THE VRAM ---
send_log("Pre-warming chat model into GPU VRAM (Total ~30GB)...")

os.system('curl -s -X POST http://localhost:11434/api/generate -d \'{"model": "qwen3.6:latest", "keep_alive": -1, "options": {"num_ctx": 131072}}\'')

send_log("VRAM Pre-warm complete! Chat model is locked and loaded.")
# ----------------------------------

send_log("Model download complete! Setting up Cloudflare network tunnel...")

# 4. Connect Cloudflare Quick Tunnel
os.system("wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb")
os.system("dpkg -i cloudflared-linux-amd64.deb")

# Start the tunnel pointing directly to Ollama's local port
tunnel_process = subprocess.Popen(
    ["cloudflared", "tunnel", "--url", "http://localhost:11434"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

# Parse the real-time stream logs to capture the trycloudflare URL
public_url = ""
for line in tunnel_process.stdout:
    match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
    if match:
        public_url = match.group(0)
        break

# 5. Broadcast final active URL to your local proxy listener
if public_url:
    requests.post(
        f"https://ntfy.sh/{NTFY_CHANNEL}", 
        data=f"🚀 SERVER IS LIVE! Connect your local API here: {public_url}".encode(encoding='utf-8')
    )
else:
    send_log("❌ Critical Error: Cloudflare failed to generate a public URL endpoint.")

# --- THE INSTANT KILL SWITCH (Streaming) ---
send_log("Server is up. Listening for SHUTDOWN_GPU signal...")

try:
    # Open continuous stream to the ntfy raw channel
    response = requests.get(f"https://ntfy.sh/{NTFY_CHANNEL}/raw", stream=True)
    
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if "SHUTDOWN_GPU" in decoded_line:
                requests.post(
                    f"https://ntfy.sh/{NTFY_CHANNEL}", 
                    data="[KAGGLOG]: Kill switch activated! Shutting down GPUs safely...".encode('utf-8')
                )
                # Terminate the cloudflared process before hard exiting
                tunnel_process.terminate()
                os._exit(0) 
except:
    pass