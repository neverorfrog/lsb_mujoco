#!/usr/bin/env bash

set -eou pipefail

# Function to handle errors and prevent infinite restarts
handle_error() {
    echo "ERROR: $1"
    echo "Sleeping for 30 seconds before exit to prevent rapid restart loops..."
    sleep 30
    exit 1
}

# Trap errors
trap 'handle_error "Startup script failed at line $LINENO"' ERR

echo "Setting up VNC environment..."

# --- 1. Clean up any existing X11 processes ---
pkill -f Xvnc || true
pkill -f vncserver || true
sleep 1

# --- 2. Fix X11 authority issues ---
echo "Setting up X11 authority..."
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
echo "Attempting to create Xauthority at: $XAUTHORITY"

if rm -f "$XAUTHORITY" 2>/dev/null && touch "$XAUTHORITY" 2>/dev/null; then
    chmod 600 "$XAUTHORITY"
else
    echo "Warning: cannot create $XAUTHORITY (permission denied). Falling back to /tmp/.Xauthority"
    export XAUTHORITY="/tmp/.Xauthority"
    rm -f "$XAUTHORITY" || true
    touch "$XAUTHORITY"
    chmod 600 "$XAUTHORITY"
fi

# --- 4. Setup xstartup ---
echo "Ensuring xstartup script is executable..."
chmod +x "$HOME/.vnc/xstartup"

# --- 5. Start VNC Server ---
echo "Starting Xvnc directly..."
export DISPLAY=:1
Xvnc "$DISPLAY" \
  -depth "$VNC_COL_DEPTH" \
  -geometry "1920x1080" \
  -SecurityTypes None \
  -AlwaysShared=1 \
  -localhost=no \
  -rfbport 5901 \
  -desktop "MJPC Desktop" &

VNC_PID=$!

# Wait for VNC server to start
sleep 5

# --- 6. Start websockify for web VNC access ---
echo "Starting websockify for web access..."
websockify --web=/usr/share/novnc/ 0.0.0.0:6901 localhost:5901 &
WEBSOCKIFY_PID=$!

# --- 7. Start the desktop session ---
echo "Starting desktop session..."
export DISPLAY=:1
bash "$HOME/.vnc/xstartup" &

# --- 8. Verify MJPC is accessible ---
echo "Verifying MJPC application..."
if [ ! -f "/app/mujoco_mpc/build/bin/mjpc" ]; then
    handle_error "MJPC binary not found"
fi

# --- 9. Start Flask webapp ---
echo "Starting Flask webapp on port 5000..."
cd /app
. /app/venv/bin/activate
python /app/app.py &
FLASK_PID=$!

# --- 10. Services started ---
echo "All services started:"
echo "  VNC Server: display $DISPLAY (port 5901)"
echo "  noVNC Web: port 6901"
echo "  Flask App: port 5000"

# Function to check if all services are running
check_services() {
    local all_good=true

    if ! kill -0 $VNC_PID 2>/dev/null; then
        echo "ERROR: VNC server (PID $VNC_PID) stopped"
        all_good=false
    fi

    if ! kill -0 $WEBSOCKIFY_PID 2>/dev/null; then
        echo "ERROR: Websockify (PID $WEBSOCKIFY_PID) stopped"
        all_good=false
    fi

    if ! kill -0 $FLASK_PID 2>/dev/null; then
        echo "WARNING: Flask app (PID $FLASK_PID) stopped, restarting..."
        cd /app
        . /app/venv/bin/activate
        python /app/app.py &
        FLASK_PID=$!
        echo "Flask app restarted with PID $FLASK_PID"
    fi

    if [ "$all_good" = false ]; then
        handle_error "Critical services stopped"
    fi
}

# Cleanup function
cleanup() {
    echo "Shutting down services..."
    kill $FLASK_PID $WEBSOCKIFY_PID $VNC_PID 2>/dev/null || true
    vncserver -kill $DISPLAY 2>/dev/null || true
    exit 0
}

# Register lsb
/app/register.sh --client lsb5

# Set trap for cleanup
trap cleanup SIGTERM SIGINT

# Monitor services and keep container alive
echo "Monitoring services... (Ctrl+C to stop)"
while true; do
    check_services
    sleep 10
done
