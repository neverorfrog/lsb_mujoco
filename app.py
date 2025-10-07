from flask import Flask, render_template_string
import os

app = Flask(__name__)

# Configuration from environment variables
CONNECTION_NAME = os.getenv("CONNECTION_NAME", "lsb5")
SERVICE_NAME = os.getenv("SERVICE_NAME", f"MJPC Lab {CONNECTION_NAME.upper()}")
SERVICE_DESCRIPTION = os.getenv(
    "SERVICE_DESCRIPTION", "MuJoCo Model Predictive Control Simulation"
)

# VNC Configuration
VNC_PORT = os.getenv("VNC_PORT", "5901")
NOVNC_PORT = os.getenv("NOVNC_PORT", "6901")

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

        .loading-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.8) 100%);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 500;
            transition: opacity 0.5s ease;
        }

        .spinner {
            width: 48px;
            height: 48px;
            border: 3px solid rgba(255,255,255,0.2);
            border-top: 3px solid {{primary_color}};
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 24px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .loading-text {
            font-size: 16px;
            font-weight: 500;
            margin-bottom: 8px;
            color: white;
        }

        .loading-subtitle {
            font-size: 13px;
            opacity: 0.7;
            text-align: center;
            max-width: 300px;
            line-height: 1.4;
        }

        .error-state {
            display: none;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100%;
            text-align: center;
            padding: 40px;
        }

        .error-state.visible {
            display: flex;
        }

        .error-icon {
            font-size: 48px;
            margin-bottom: 16px;
            opacity: 0.6;
        }

        .error-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 8px;
            color: #ff6b6b;
        }

        .error-message {
            font-size: 14px;
            opacity: 0.8;
            margin-bottom: 20px;
            max-width: 400px;
            line-height: 1.5;
        }

        .control-btn {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            color: white;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .control-btn:hover {
            background: rgba(255,255,255,0.2);
            border-color: rgba(255,255,255,0.3);
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
                <span>Lab Ready</span>
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
        <div id="loading" class="loading-overlay">
            <div class="spinner"></div>
            <div class="loading-text">Initializing Lab Environment</div>
            <div class="loading-subtitle">
                Starting MJPC simulation and establishing VNC connection...
            </div>
        </div>

        <div id="error" class="error-state">
            <div class="error-icon">⚠️</div>
            <div class="error-title">Connection Failed</div>
            <div class="error-message">
                Unable to connect to the lab environment. The VNC service may still be starting up.
            </div>
            <button class="control-btn" onclick="reloadVNC()">Try Again</button>
        </div>

        <iframe id="vnc-frame" class="vnc-frame" style="display: none;"></iframe>
    </div>

    <script>
        let vncLoadTimeout;

        function initializeVNC() {
            const frame = document.getElementById('vnc-frame');
            const loading = document.getElementById('loading');
            const error = document.getElementById('error');

            // Reset states
            loading.style.display = 'flex';
            error.classList.remove('visible');
            frame.style.display = 'none';

            // Use window.location.hostname to connect to the LSB container's IP
            // This resolves to the actual container IP (e.g., 10.8.0.5) instead of localhost
            const vncUrl = 'http://' + window.location.hostname + ':{{novnc_port}}/vnc.html?autoconnect=true&resize=scale&quality=9&compression=2';
            console.log('Connecting to VNC at:', vncUrl);

            frame.src = vncUrl;

            // Set timeout for connection
            vncLoadTimeout = setTimeout(() => {
                if (frame.style.display === 'none') {
                    showError();
                }
            }, 15000);

            frame.onload = function() {
                clearTimeout(vncLoadTimeout);
                // Give noVNC time to establish connection
                setTimeout(() => {
                    loading.style.opacity = '0';
                    setTimeout(() => {
                        loading.style.display = 'none';
                        frame.style.display = 'block';
                    }, 500);
                }, 2000);
            };

            frame.onerror = function() {
                clearTimeout(vncLoadTimeout);
                showError();
            };
        }

        function showError() {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('error').classList.add('visible');
        }

        function toggleFullscreen() {
            const frame = document.getElementById('vnc-frame');
            if (document.fullscreenElement) {
                document.exitFullscreen();
            } else if (frame.style.display !== 'none') {
                frame.requestFullscreen().catch(err => {
                    console.log('Fullscreen failed:', err);
                });
            }
        }


        function reloadVNC() {
            clearTimeout(vncLoadTimeout);
            initializeVNC();
        }

        // Initialize when page loads
        document.addEventListener('DOMContentLoaded', function() {
            initializeVNC();
        });

        // Handle fullscreen changes
        document.addEventListener('fullscreenchange', function() {
            // You could add fullscreen-specific styling here if needed
        });

        // Click outside to hide connection info
        document.addEventListener('click', function(event) {
            const info = document.getElementById('connection-info');
            const infoButton = event.target.closest('.control-btn');

            if (connectionInfoVisible && !info.contains(event.target) &&
                (!infoButton || !infoButton.textContent.includes('Info'))) {
                info.classList.remove('visible');
                connectionInfoVisible = false;
            }
        });
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(
        HTML_PAGE,
        service_name=SERVICE_NAME,
        service_description=SERVICE_DESCRIPTION,
        vnc_port=VNC_PORT,
        novnc_port=NOVNC_PORT,
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
        "vnc_ports": {"direct": int(VNC_PORT), "web": int(NOVNC_PORT)},
    }


@app.route("/status")
def status():
    """Endpoint for monitoring the lab status"""
    import subprocess

    try:
        # Check if VNC server is running
        vnc_running = (
            subprocess.run(
                ["pgrep", "-f", "Xvnc.*:1"], capture_output=True, text=True
            ).returncode
            == 0
        )

        # Check if websockify is running
        websockify_running = (
            subprocess.run(
                ["pgrep", "-f", f"websockify.*{NOVNC_PORT}"],
                capture_output=True,
                text=True,
            ).returncode
            == 0
        )

        # Check if MJPC binary exists
        mjpc_available = (
            subprocess.run(
                ["test", "-f", "/app/mujoco_mpc/build/bin/mjpc"], capture_output=True
            ).returncode
            == 0
        )

        return {
            "service": SERVICE_NAME,
            "connection_name": CONNECTION_NAME,
            "services": {
                "vnc_server": vnc_running,
                "websockify": websockify_running,
                "mjpc_binary": mjpc_available,
            },
            "ports": {"vnc": VNC_PORT, "novnc": NOVNC_PORT, "webapp": "5000"},
            "overall_status": "healthy"
            if all([vnc_running, websockify_running, mjpc_available])
            else "degraded",
        }
    except Exception as e:
        return {"service": SERVICE_NAME, "overall_status": "error", "error": str(e)}


if __name__ == "__main__":
    print(f"Starting {SERVICE_NAME}")
    print(f"Direct VNC: port {VNC_PORT}")
    print(f"Web VNC: port {NOVNC_PORT}")
    app.run(host="0.0.0.0", port=5000, debug=False)
