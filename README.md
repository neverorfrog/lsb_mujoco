# LSB MuJoCo - Lab Service Backend

A containerized lab service that provides remote access to GUI applications (MuJoCo MPC in this case) through a web interface with VNC integration.

## Architecture Overview

```
┌───────────────────────────────────────────────────────────┐
│  Browser (http://<VPN_IP>:5000)                           │
└────────────────────────┬──────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────────┐
│  Flask Web Application (Port 5000)                        │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  HTTP Routes:                                       │  │
│  │  • / - Main interface with styled UI                │  │
│  │  • /novnc/* - Proxy to noVNC static files           │  │
│  │  • /health - Health check endpoint                  │  │
│  │  • /status - Service status endpoint                │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  WebSocket Routes (flask-sock):                     │  │
│  │  • /novnc/websockify - Main WebSocket proxy         │  │
│  │  • /websockify - Compatibility route                │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────┬────────────────────────────────────┘
                       │
         ┌─────────────┴────────────────┐
         │                              │
         ▼                              ▼
┌─────────────────────┐      ┌─────────────────────────┐
│  Websockify         │      │  Direct VNC Connection  │
│  (Port 6901)        │      │  (Port 5901)            │
│                     │      │                         │
│  • Serves noVNC     │      │  Flask WebSocket ────►  │
│    static files     │      │  VNC Server (Xvnc)      │
│  • HTML/JS/CSS      │      │                         │
└─────────────────────┘      └──────────┬──────────────┘
                                        │
                                        ▼
                             ┌─────────────────────────┐
                             │  X11 Display :1         │
                             │  • Openbox WM           │
                             │  • Your GUI App         │
                             │    (MuJoCo MPC)         │
                             └─────────────────────────┘
```

## Key Components

### 1. **Flask Application** (`app.py`)
- **Purpose**: Main web interface and WebSocket proxy
- **Port**: 5000 (exposed via VPN)
- **Features**:
  - Serves custom HTML interface with branding
  - Proxies noVNC static files from internal websockify server
  - WebSocket proxy that connects browser directly to VNC server
  - Health and status monitoring endpoints

### 2. **VNC Server** (TigerVNC/Xvnc)
- **Purpose**: Provides virtual X11 display
- **Port**: 5901 (internal)
- **Configuration**:
  - No authentication (`-SecurityTypes None`)
  - Shared sessions (`-AlwaysShared=1`)
  - Blacklisting disabled for reconnections
  - Runs Openbox window manager

### 3. **Websockify**
- **Purpose**: Serves noVNC static files (HTML, JS, CSS) ONLY
- **Port**: 6901 (internal - accessed via Flask proxy)
- **What it does**: Acts as a static file server for `/usr/share/novnc/`
- **What it doesn't do**: We bypass its WebSocket proxying feature entirely
- **Why we keep it**: Convenient way to serve pre-packaged noVNC files
- **Could be replaced with**: Direct noVNC installation and Flask's `send_from_directory()`

### 4. **VPN Integration** (WireGuard)
- **Purpose**: Secure remote access
- **Registration**: Automated via `register.sh`
- **Firewall**: iptables rules for ports 5000 and 6901

## Data Flow

### HTTP Request (Static Files)
```
Browser Request
  → Flask (/novnc/vnc.html)
    → Flask proxies to http://localhost:6901/vnc.html
      → Websockify serves noVNC HTML/JS/CSS files
        → Browser receives and renders noVNC interface
```

### WebSocket Connection (VNC Stream)
```
Browser WebSocket (ws://VPN_IP:5000/novnc/websockify)
  → Flask WebSocket handler (flask-sock)
    → Direct TCP connection to VNC (port 5901)
      → RFB Protocol (Remote Framebuffer)
        → X11 Display (:1)
          → GUI Application renders
```

## Architecture Note: Why Two Ports?

**Port 5901 (VNC Server)**
- Raw VNC protocol (RFB)
- Flask WebSocket connects here directly
- This is where the actual desktop/application runs

**Port 6901 (Websockify)**
- **ONLY** used for HTTP requests to serve noVNC static files
- NOT used for WebSocket connections (that's Flask's job)
- Could be replaced with downloading noVNC separately

**Important**: Websockify's WebSocket-to-VNC proxy feature (its main purpose) is completely bypassed. We only use it as a convenient static file server. Flask handles all WebSocket connections directly to port 5901 to avoid double-framing issues.

## How to Adapt for Your GUI Application

### 1. Replace the GUI Application

In `startup.sh`, find the section that launches the application:

```bash
# --- START YOUR APPLICATION ---
echo "Starting your GUI application..."
export DISPLAY=:1

# Replace this with your application
/path/to/your/app &
APP_PID=$!

# Optional: Wait for window to appear
sleep 3
if wmctrl -l | grep -q "YourAppWindowTitle"; then
    echo "✅ Application window detected"
fi
```

### 2. Update Application Dependencies

In `Dockerfile`, replace MuJoCo build steps with your app dependencies:

```dockerfile
# Install your application dependencies
RUN apt-get update && apt-get install -y \
    your-app-dependencies \
    && rm -rf /var/lib/apt/lists/*

# Copy or build your application
COPY your-app /app/your-app
# OR
RUN git clone https://github.com/your/app /app/your-app && \
    cd /app/your-app && \
    make install
```

### 3. Customize the Web Interface

In `app.py`, update the branding:

```python
# Configuration from environment variables
CONNECTION_NAME = os.getenv("CONNECTION_NAME", "your-lab-name")
SERVICE_NAME = os.getenv("SERVICE_NAME", f"Your Lab {CONNECTION_NAME.upper()}")
SERVICE_DESCRIPTION = os.getenv("SERVICE_DESCRIPTION", "Your Application Description")

# Styling
PRIMARY_COLOR = os.getenv("PRIMARY_COLOR", "#8bc34a")
BG_GRADIENT_START = os.getenv("BG_GRADIENT_START", "#1b5e20")
BG_GRADIENT_END = os.getenv("BG_GRADIENT_END", "#388e3c")
```

### 4. Update Environment Variables

In `docker-compose.yml`:

```yaml
environment:
  DISPLAY: ":1"
  CONNECTION_NAME: "your-lab"
  PRIMARY_COLOR: "#your-color"
  BG_GRADIENT_START: "#your-gradient-start"
  BG_GRADIENT_END: "#your-gradient-end"
```

## File Structure

```
lsb_mujoco/
├── Dockerfile              # Container image definition
├── docker-compose.yml      # Service orchestration
├── app.py                  # Flask web application
├── startup.sh             # Container startup script
├── setup.sh               # Environment setup
├── register.sh            # VPN registration
├── xstartup               # VNC session startup
└── mujoco_mpc/            # Your application (replace this)
```

## Requirements

### System Dependencies (Installed in Container)
```
- TigerVNC Server
- Openbox Window Manager
- Python 3.10+
- Flask + flask-sock
- Websockify
- WireGuard (for VPN)
```

### Python Dependencies
```
flask
flask-sock
psutil
requests
```

## Building and Running

### Build
```bash
docker compose build
```

### Run
```bash
docker compose up -d
```

### View Logs
```bash
docker logs lsb_mujoco -f
```

### Stop
```bash
docker compose down
```

## Configuration

### VNC Settings
Edit in `startup.sh`:
```bash
Xvnc "$DISPLAY" \
  -depth 24 \              # Color depth
  -geometry "1920x1080" \  # Screen resolution
  -SecurityTypes None \    # No password
  -AlwaysShared=1 \       # Allow multiple connections
  -BlacklistTimeout=0 \   # Disable reconnection blacklist
  -BlacklistThreshold=0
```

### Flask Settings
Edit in `app.py`:
```python
VNC_PORT = "5901"              # VNC server port
WEBSOCKIFY_PORT = "6901"       # noVNC static files port
```

### Firewall Rules
Edit in `startup.sh`:
```bash
iptables -I INPUT -i wg0 -p tcp --dport 5000 -j ACCEPT  # Flask
iptables -I INPUT -i wg0 -p tcp --dport 6901 -j ACCEPT  # noVNC files
```

## Troubleshooting

### WebSocket Connection Fails
1. Check VNC server is running: `docker exec lsb_mujoco pgrep Xvnc`
2. Check Flask logs: `docker logs lsb_mujoco | grep WebSocket`
3. Verify VNC blacklisting is disabled in startup.sh

### Application Not Visible
1. Verify DISPLAY is set: `echo $DISPLAY` should be `:1`
2. Check X11 is running: `docker exec lsb_mujoco ps aux | grep Xvnc`
3. List windows: `docker exec lsb_mujoco env DISPLAY=:1 wmctrl -l`

### VPN Connection Issues
1. Check WireGuard: `docker exec lsb_mujoco wg show`
2. Verify IP: `docker exec lsb_mujoco ip addr show wg0`
3. Test ping: `docker exec lsb_mujoco ping -c 3 10.128.0.1`

## Security Considerations

1. **No VNC Authentication**: Currently uses `-SecurityTypes None` - add authentication if needed
2. **VPN Required**: Service is only accessible through WireGuard VPN
3. **Firewall**: iptables rules restrict access to VPN interface only
4. **No TLS**: HTTP only - add reverse proxy with TLS for production

## Key Design Decisions

### Why Flask-Sock?
- Simple WebSocket support for Flask's development server
- No need for complex WSGI servers (gunicorn/eventlet)
- Handles WebSocket framing automatically

### Why Direct VNC Connection?
- Connecting through websockify created double WebSocket framing
- Direct TCP to VNC (port 5901) is simpler and more reliable
- Websockify still used for serving noVNC static files

### Why Disable VNC Blacklisting?
- TigerVNC blacklists IPs after rapid reconnections
- WebSocket reconnection attempts triggered blacklist
- Disabled with `-BlacklistTimeout=0 -BlacklistThreshold=0`

## Credits

- **noVNC**: HTML5 VNC client (https://novnc.com)
- **TigerVNC**: High-performance VNC server
- **Flask-Sock**: WebSocket extension for Flask
- **MuJoCo MPC**: Example GUI application (https://github.com/google-deepmind/mujoco_mpc)
