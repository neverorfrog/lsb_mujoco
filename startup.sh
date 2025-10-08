#!/usr/bin/env bash

set -eou pipefail

handle_error() {
    echo "ERROR: $1"
    sleep 30
    exit 1
}

trap 'handle_error "Startup failed at line $LINENO"' ERR

echo "==================================="
echo "MJPC Lab Container Starting"
echo "==================================="

# --- VNC SETUP ---
echo ""
echo ">>> Setting up VNC environment"
pkill -f Xvnc || true
pkill -f vncserver || true
pkill -f websockify || true
sleep 2

export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
if rm -f "$XAUTHORITY" 2>/dev/null && touch "$XAUTHORITY" 2>/dev/null; then
    chmod 600 "$XAUTHORITY"
else
    export XAUTHORITY="/tmp/.Xauthority"
    rm -f "$XAUTHORITY" || true
    touch "$XAUTHORITY"
    chmod 600 "$XAUTHORITY"
fi

chmod +x "$HOME/.vnc/xstartup"

# --- START VNC ---
echo ""
echo ">>> Starting VNC Server"
export DISPLAY=:1
Xvnc "$DISPLAY" \
  -depth "$VNC_COL_DEPTH" \
  -geometry "1920x1080" \
  -SecurityTypes None \
  -AlwaysShared=1 \
  -localhost=no \
  -rfbport 5901 \
  -BlacklistTimeout=0 \
  -BlacklistThreshold=0 \
  -desktop "MJPC Desktop" &
VNC_PID=$!
sleep 5

if ! kill -0 $VNC_PID 2>/dev/null; then
    handle_error "VNC Server failed to start"
fi

# --- START DESKTOP ---
echo ""
echo ">>> Starting desktop session"
bash "$HOME/.vnc/xstartup" &
sleep 3

# --- VPN REGISTRATION ---
echo ""
echo ">>> Registering with VPN"
if ! /app/register.sh --client lsb5; then
    echo "❌ VPN registration failed"
    handle_error "VPN registration failed"
fi

# Wait for VPN
VPN_READY=false
for i in {1..30}; do
    if ip addr show wg0 >/dev/null 2>&1; then
        VPN_IP=$(ip addr show wg0 | grep 'inet ' | awk '{print $2}' | cut -d'/' -f1)
        echo "✅ VPN interface UP with IP: $VPN_IP"
        VPN_READY=true
        break
    fi
    echo "Waiting for wg0... ($i/30)"
    sleep 1
done

if [ "$VPN_READY" = false ]; then
    handle_error "VPN interface failed"
fi

# --- START WEBSOCKIFY ON PORT 5000 ---
echo ""
echo ">>> Starting websockify on port 6901"
websockify --web=/usr/share/novnc/ 0.0.0.0:6901 localhost:5901 &
WEBSOCKIFY_PID=$!
sleep 3

if netstat -tulpn | grep -q ':6901'; then
    echo "✅ Websockify is listening on port 6901"
else
    handle_error "Websockify failed to start on port 6901"
fi

# --- Start Flask webapp ---
echo "Starting Flask webapp on port 5000..."
cd /app
. /app/venv/bin/activate
python /app/app.py &
FLASK_PID=$!
sleep 3

if netstat -tulpn | grep -q ':5000'; then
    echo "✅ Flask is listening on port 5000"
else
    handle_error "Flask failed to start on port 5000"
fi

# --- FIREWALL ---
echo ""
echo ">>> Configuring firewall"
iptables -I INPUT -i wg0 -p tcp --dport 5000 -j ACCEPT
iptables -I INPUT -i wg0 -p tcp --dport 6901 -j ACCEPT
iptables -I INPUT -i wg0 -m state --state ESTABLISHED,RELATED -j ACCEPT
echo "✅ Firewall configured"

# --- SUMMARY ---
echo ""
echo "==================================="
echo "STARTUP COMPLETE"
echo "==================================="
echo "Services:"
echo "  • VNC Server:    PID $VNC_PID (port 5901)"
echo "  • Websockify:    PID $WEBSOCKIFY_PID (port 6901)"
echo "  • Flask:         PID $FLASK_PID (port 5000)"
echo ""
echo "Access: http://$VPN_IP:5000"
echo "==================================="

# Monitor services
check_services() {
    if ! kill -0 $VNC_PID 2>/dev/null; then
        echo "ERROR: VNC stopped"
        handle_error "VNC stopped"
    fi
    if ! kill -0 $WEBSOCKIFY_PID 2>/dev/null; then
        echo "ERROR: Websockify stopped"
        handle_error "Websockify stopped"
    fi
}

cleanup() {
    echo "Shutting down..."
    kill $WEBSOCKIFY_PID $VNC_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

echo ">>> Monitoring services"
while true; do
    check_services
    sleep 10
done