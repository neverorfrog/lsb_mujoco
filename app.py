from flask import Flask, render_template_string, request, Response
import requests
import os
from flask_sock import Sock
import socket as stdlib_socket

app = Flask(__name__)
sock = Sock(app)

# Configuration from environment variables
CONNECTION_NAME = os.getenv("CONNECTION_NAME", "lsb5")
SERVICE_NAME = os.getenv("SERVICE_NAME", f"MJPC Lab {CONNECTION_NAME.upper()}")
SERVICE_DESCRIPTION = os.getenv(
    "SERVICE_DESCRIPTION", "MuJoCo Model Predictive Control Simulation"
)

# VNC Configuration
VNC_PORT = os.getenv("VNC_PORT", "5901")
WEBSOCKIFY_PORT = "6901"

# Styling from environment
PRIMARY_COLOR = os.getenv("PRIMARY_COLOR", "#8bc34a")
BG_GRADIENT_START = os.getenv("BG_GRADIENT_START", "#1b5e20")
BG_GRADIENT_END = os.getenv("BG_GRADIENT_END", "#388e3c")

# HTML interface
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>{{service_name}}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, {{bg_start}} 0%, {{bg_end}} 100%);
            color: white;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            height: 100vh;
            overflow: hidden;
        }

        .header {
            background: rgba(0,0,0,0.4);
            padding: 12px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            backdrop-filter: blur(15px);
            border-bottom: 1px solid rgba(255,255,255,0.1);
            z-index: 1000;
            position: relative;
        }

        .service-info h1 {
            font-size: 22px;
            font-weight: 600;
            margin: 0;
            color: {{primary_color}};
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
        }

        .service-info p {
            font-size: 13px;
            margin: 3px 0 0 0;
            opacity: 0.85;
            font-weight: 400;
        }

        .status-controls {
            display: flex;
            gap: 15px;
            align-items: center;
        }

        .status-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 12px;
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            font-size: 13px;
            font-weight: 500;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: {{primary_color}};
            box-shadow: 0 0 8px {{primary_color}}50;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .control-group {
            display: flex;
            gap: 8px;
        }

        .control-btn {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            color: white;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            backdrop-filter: blur(10px);
            transition: all 0.2s ease;
        }

        .control-btn:hover {
            background: rgba(255,255,255,0.2);
            border-color: rgba(255,255,255,0.3);
            transform: translateY(-1px);
        }

        .control-btn:active {
            transform: translateY(0);
        }

        .main-container {
            height: calc(100vh - 57px);
            position: relative;
            background: #000;
        }

        .vnc-frame {
            width: 100%;
            height: 100%;
            border: none;
            background: #000;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="service-info">
            <h1>{{service_name}}</h1>
            <p>{{service_description}}</p>
        </div>

        <div class="status-controls">
            <div class="status-item">
                <div class="status-dot"></div>
                <span>Connected</span>
            </div>

            <div class="control-group">
                <button class="control-btn" onclick="toggleFullscreen()">
                    ⛶ Fullscreen
                </button>
                <button class="control-btn" onclick="reloadVNC()">
                    🔄 Reload
                </button>
            </div>
        </div>
    </div>

    <div class="main-container">
        <iframe id="vnc-frame" class="vnc-frame"></iframe>
    </div>

    <script>
        function initializeVNC() {
            const frame = document.getElementById('vnc-frame');
            
            // Load noVNC through Flask proxy
            const vncUrl = '/novnc/vnc.html?autoconnect=true&resize=scale&quality=9&compression=2&path=websockify';
            
            console.log('Loading noVNC through Flask proxy');
            frame.src = vncUrl;
        }

        function toggleFullscreen() {
            const frame = document.getElementById('vnc-frame');
            if (document.fullscreenElement) {
                document.exitFullscreen();
            } else {
                frame.requestFullscreen().catch(err => {
                    console.log('Fullscreen error:', err);
                });
            }
        }

        function reloadVNC() {
            const frame = document.getElementById('vnc-frame');
            frame.src = frame.src;
        }

        document.addEventListener('DOMContentLoaded', initializeVNC);
    </script>
</body>
</html>
"""


@app.route('/novnc/<path:path>')
def novnc_proxy(path):
    """Proxy noVNC static files from websockify"""
    target_url = f'http://127.0.0.1:{WEBSOCKIFY_PORT}/{path}'
    
    if request.query_string:
        target_url += '?' + request.query_string.decode('utf-8')
    
    try:
        resp = requests.get(target_url, stream=True, timeout=10)
        
        def generate():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        headers = {
            key: value for key, value in resp.headers.items()
            if key.lower() not in ['content-encoding', 'transfer-encoding', 'content-length']
        }
        
        return Response(generate(), status=resp.status_code, headers=headers)
        
    except requests.exceptions.ConnectionError:
        return "Cannot connect to noVNC service", 503
    except Exception as e:
        return f"Proxy error: {str(e)}", 500



def websockify_proxy_handler(ws):
    """WebSocket to VNC proxy - bidirectional forwarding"""
    from threading import Thread, Event
    
    backend = None
    try:
        backend = stdlib_socket.socket(stdlib_socket.AF_INET, stdlib_socket.SOCK_STREAM)
        backend.connect(('127.0.0.1', int(VNC_PORT)))
        print(f"WebSocket connected to VNC on port {VNC_PORT}")
        
        stop_event = Event()
        
        def forward_from_client():
            try:
                while not stop_event.is_set():
                    try:
                        data = ws.receive(timeout=1.0)
                        if data is None:
                            break
                        if isinstance(data, str):
                            data = data.encode('latin-1')
                        backend.sendall(data)
                    except:
                        break
            finally:
                stop_event.set()
        
        def forward_from_backend():
            try:
                backend.settimeout(1.0)
                while not stop_event.is_set():
                    try:
                        data = backend.recv(4096)
                        if not data:
                            break
                        ws.send(data)
                    except stdlib_socket.timeout:
                        continue
                    except:
                        break
            finally:
                stop_event.set()
        
        client_thread = Thread(target=forward_from_client, daemon=True)
        backend_thread = Thread(target=forward_from_backend, daemon=True)
        
        client_thread.start()
        backend_thread.start()
        
        client_thread.join()
        backend_thread.join()
        
        print("WebSocket closed")
        
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if backend:
            try:
                backend.close()
            except:
                pass


@sock.route('/novnc/websockify')
def novnc_websockify_proxy(ws):
    """WebSocket proxy to VNC"""
    return websockify_proxy_handler(ws)

@sock.route('/websockify')
def websockify_sock_proxy(ws):
    """WebSocket proxy to VNC (alternate path)"""
    return websockify_proxy_handler(ws)

@app.route("/")
def index():
    return render_template_string(
        HTML_PAGE,
        service_name=SERVICE_NAME,
        service_description=SERVICE_DESCRIPTION,
        primary_color=PRIMARY_COLOR,
        bg_start=BG_GRADIENT_START,
        bg_end=BG_GRADIENT_END,
    )


@app.route("/health")
def health():
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "connection": CONNECTION_NAME,
        "vnc_port": int(VNC_PORT),
    }


@app.route("/status")
def status():
    """Status endpoint"""
    import subprocess

    try:
        vnc_running = subprocess.run(
            ["pgrep", "-f", "Xvnc.*:1"], capture_output=True
        ).returncode == 0

        websockify_running = subprocess.run(
            ["pgrep", "-f", f"websockify.*{WEBSOCKIFY_PORT}"], capture_output=True
        ).returncode == 0

        mjpc_available = subprocess.run(
            ["test", "-f", "/app/mujoco_mpc/build/bin/mjpc"], capture_output=True
        ).returncode == 0

        all_healthy = all([vnc_running, websockify_running, mjpc_available])

        return {
            "service": SERVICE_NAME,
            "connection_name": CONNECTION_NAME,
            "services": {
                "vnc_server": vnc_running,
                "websockify": websockify_running,
                "mjpc_binary": mjpc_available,
            },
            "overall_status": "healthy" if all_healthy else "degraded",
        }
    except Exception as e:
        return {"service": SERVICE_NAME, "overall_status": "error", "error": str(e)}


if __name__ == "__main__":
    print(f"Starting {SERVICE_NAME}")
    print(f"Flask on port 5000, VNC on {VNC_PORT}, Websockify on {WEBSOCKIFY_PORT}")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)