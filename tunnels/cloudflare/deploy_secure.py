import os
import subprocess
import time
import requests

# --- CONFIGURATION & SECRETS ---
CLOUDFLARE_TUNNEL_TOKEN = "YOUR_CLOUDFLARE_TUNNEL_TOKEN_HERE" # Paste your persistent Tunnel Token from the Cloudflare Zero Trust Dashboard here
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
send_log("Starting Zero Trust setup... Installing zstd and Ollama framework.")
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
send_log("Pre-warming both chat and embedding models into GPU VRAM (Total ~30GB)...")

# 1. Pre-warm the primary Chat model
os.system('curl -s -X POST http://localhost:11434/api/generate -d \'{"model": "qwen3.6:latest", "keep_alive": -1, "options": {"num_ctx": 131072}}\'')

# 2. Pre-warm the secondary Embedding model
os.system('curl -s -X POST http://localhost:11434/api/embed -d \'{"model": "qwen3-embedding:latest", "input": "System initialization pre-warm", "keep_alive": -1}\'')

send_log("VRAM Pre-warm complete! both chat and embedding models are locked and loaded.")
# ----------------------------------

send_log("Model download complete! Setting up Cloudflare network tunnel...")

# 4. Connect Cloudflare Zero Trust Daemon
os.system("wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb")
os.system("dpkg -i cloudflared-linux-amd64.deb")

# Boot the tunnel using your secure token
tunnel_process = subprocess.Popen(
    ["cloudflared", "tunnel", "run", "--token", CLOUDFLARE_TUNNEL_TOKEN],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

# Small grace period for network handshake
time.sleep(5)

# 5. Broadcast success message
requests.post(
    f"https://ntfy.sh/{NTFY_CHANNEL}", 
    data="🚀 ZERO TRUST SERVER IS LIVE! Your persistent custom domain is now routing traffic to Kaggle GPUs.".encode(encoding='utf-8')
)

# --- THE INSTANT KILL SWITCH (Streaming) ---
send_log("Zero Trust Daemon active. Listening for SHUTDOWN_GPU signal...")

try:
    # Open continuous stream to the ntfy raw channel
    response = requests.get(f"https://ntfy.sh/{NTFY_CHANNEL}/raw", stream=True)
    
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if "SHUTDOWN_GPU" in decoded_line:
                requests.post(
                    f"https://ntfy.sh/{NTFY_CHANNEL}", 
                    data="[KAGGLOG]: Kill switch activated! Tearing down Zero Trust infrastructure...".encode('utf-8')
                )
                # Cleanup processes before hard exit
                tunnel_process.terminate()
                os._exit(0) 
except:
    pass