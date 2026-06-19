import os
import requests
import base64
from flask import Flask, request, Response
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Pre-load targets to verify environment configuration on boot
REMOTE_HOST_LLM = os.getenv("REMOTE_HOST_LLM")
REMOTE_HOST_EMB = os.getenv("REMOTE_HOST_EMB")

# Pre-compute the shared Basic Auth header once on startup
username = os.getenv("AUTH_USER")
password = os.getenv("AUTH_PASS")
AUTH_HEADER = None

if username and password:
    auth_string = f"{username}:{password}"
    b64_auth = base64.b64encode(auth_string.encode()).decode()
    AUTH_HEADER = f"Basic {b64_auth}"

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def distributed_secure_proxy(path):
    # 1. Inspect the incoming endpoint path to determine target node criteria
    if path in ["api/embeddings", "api/embed", "v1/embeddings"]:
        remote_host = REMOTE_HOST_EMB
        node_tag = "🎯 NODE-B [EMBEDDING]"
    else:
        remote_host = REMOTE_HOST_LLM
        node_tag = "💬 NODE-A [LLM]"

    # Catch missing environment variables gracefully
    if not remote_host:
        return f"Proxy Error: Target URL for {node_tag} is not defined in your .env file.", 500

    # Build full destination target URL
    target_url = f"{remote_host.rstrip('/')}/{path}"
    print(f"{node_tag} Routing target: {request.method} -> {target_url}")

    # 2. Duplicate incoming request headers
    headers = {key: value for (key, value) in request.headers if key.lower() != 'host'}
    
    # 3. Inject critical Ngrok bypass header
    headers["ngrok-skip-browser-warning"] = "true"

    # 4. Inject the shared Basic Authentication header if present
    if AUTH_HEADER:
        headers["Authorization"] = AUTH_HEADER

    try:
        # Forward payload downstream to targeted Kaggle cluster instance
        remote_response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            stream=True
        )
        
        # Strip hop-by-hop transmission headers to prevent Flask streaming crashes
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = {
            name: value for name, value in remote_response.headers.items()
            if name.lower() not in excluded_headers
        }

        # Stream response chunks live back to the local caller client
        return Response(
            remote_response.iter_content(chunk_size=1024), 
            status=remote_response.status_code, 
            headers=response_headers
        )
        
    except requests.exceptions.RequestException as e:
        return f"Proxy Network Error: Unable to bridge request to {node_tag}. Details: {str(e)}", 502

if __name__ == '__main__':
    print("=========================================================")
    print("📡 SECURED DISTRIBUTED SHADOWGPU PROXY ONLINE!")
    print(f"🔗 Local Port Bound : http://localhost:11434")
    print(f"🔄 Routing Topology : Inference  -> {REMOTE_HOST_LLM}")
    print(f"                      Embeddings -> {REMOTE_HOST_EMB}")
    print("=========================================================")
    app.run(host='127.0.0.1', port=11434, debug=False)