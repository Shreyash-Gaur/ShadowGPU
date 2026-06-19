import os
import subprocess
import time
import requests

# --- SECRETS ---
NGROK_TOKEN = "YOUR_NGROK_TOKEN"  # <--- Your ngrok token!
NTFY_CHANNEL = "YOUR_NTFY_CHANNEL" # <--- Your ntfy channel!

def send_log(message):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_CHANNEL}", 
            data=f"[KAGGLOG]: {message}".encode(encoding='utf-8')
        )
    except:
        pass

# 1. Install System Dependencies
send_log("Starting setup... Installing zstd and Ollama.")
os.system("apt-get update && apt-get install -y zstd")
os.system("curl -fsSL https://ollama.com/install.sh | sh")
os.system("pip install pyngrok")

# 2. Start Ollama (WITH SECURITY BYPASS & VRAM LOCK)
send_log("Booting up local Ollama background server...")
os.environ["OLLAMA_CONTEXT_LENGTH"] = "131072"
os.environ["OLLAMA_HOST"] = "0.0.0.0"
os.environ["OLLAMA_ORIGINS"] = "*"
os.environ["OLLAMA_KEEP_ALIVE"] = "-1"  # <--- Permanently locks Qwen 3.6 into the dual T4 GPUs!

subprocess.Popen(["ollama", "serve"])
time.sleep(10)

# 3. Pull the model
send_log("ATTENTION: Starting 24GB Qwen 3.6 model download. This will take 3-5 minutes...")
os.system("ollama pull qwen3.6:latest")

# --- PRE-WARM THE VRAM ---
send_log("Pre-warming chat model into GPU VRAM (Total ~30GB)...")

os.system('curl -s -X POST http://localhost:11434/api/generate -d \'{"model": "qwen3.6:latest", "keep_alive": -1, "options": {"num_ctx": 131072}}\'')

send_log("VRAM Pre-warm complete! Chat model is locked and loaded.")
# ----------------------------------

send_log("Model download complete! Setting up network tunnel...")

# 4. Connect Ngrok
from pyngrok import ngrok
ngrok.set_auth_token(NGROK_TOKEN)
send_log("Establishing secured Ngrok tunnel...")

# Add basic_auth to lock down the tunnel from the outside internet
tunnel = ngrok.connect(
    11434, 
    "http", 
    host_header="localhost",
    basic_auth=["YOUR_AUTH_USERNAME:YOUR_AUTH_PASSWORD"]  # <--- SECURITY LOCKDOWN
)

public_url = tunnel.public_url

# 5. Final success message
requests.post(
    f"https://ntfy.sh/{NTFY_CHANNEL}", 
    data=f"🚀 SERVER IS LIVE! Connect your local API here: {public_url}".encode(encoding='utf-8')
)

# --- THE INSTANT KILL SWITCH (Streaming for Node A) ---
# CHANGED: Phrasing altered so it does not contain the trigger word
send_log("Server is up. Watching for LLM_TERMINATE command...")

try:
    response = requests.get(f"https://ntfy.sh/{NTFY_CHANNEL}/raw", stream=True)
    
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            # CHANGED: Unique trigger key for Node A
            if "SHUTDOWN_LLM_NODE" in decoded_line:
                requests.post(
                    f"https://ntfy.sh/{NTFY_CHANNEL}", 
                    data="[NODE-A: LLM]: Kill switch activated! Shutting down LLM GPUs safely...".encode('utf-8')
                )
                os._exit(0) 
except:
    pass