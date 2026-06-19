import os
import requests
import base64
from flask import Flask, request, Response
from dotenv import load_dotenv


load_dotenv()
REMOTE_HOST = os.getenv("REMOTE_HOST")

app = Flask(__name__)

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def universal_proxy(path):
    if not REMOTE_HOST:
        return "Error: REMOTE_HOST variable not found in your local .env file.", 500

    target_url = f"{REMOTE_HOST.rstrip('/')}/{path}"
    
    # 1. Duplicate incoming headers
    headers = {key: value for (key, value) in request.headers if key.lower() != 'host'}
    
    # 2. INJECT NGROK BYPASS HEADER
    headers["ngrok-skip-browser-warning"] = "true"

    # 3. INJECT BASIC AUTHENTICATION HEADER (Conditional)
    # The proxy automatically detects if you are running in Protected Mode
    username = os.getenv("AUTH_USER")
    password = os.getenv("AUTH_PASS")
    
    if username and password:
        auth_string = f"{username}:{password}"
        b64_auth = base64.b64encode(auth_string.encode()).decode()
        headers["Authorization"] = f"Basic {b64_auth}"

    try:
        remote_response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            stream=True
        )
        
        # Strip hop-by-hop headers to prevent Flask streaming crashes
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = {
            name: value for name, value in remote_response.headers.items()
            if name.lower() not in excluded_headers
        }

        return Response(
            remote_response.iter_content(chunk_size=1024), 
            status=remote_response.status_code, 
            headers=response_headers
        )
        
    except requests.exceptions.RequestException as e:
        return f"Proxy Error: Unable to reach remote host. Details: {str(e)}", 502

if __name__ == '__main__':
    print(f"📡 SECURED ShadowGPU Proxy Online!")
    print(f"🔗 Intercepting: http://localhost:11434 -> Forwarding to: {REMOTE_HOST}")
    app.run(host='127.0.0.1', port=11434, debug=False)