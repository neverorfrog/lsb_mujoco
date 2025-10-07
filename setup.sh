#!/bin/bash
set -eou pipefail

echo "Setting up MJPC runtime environment..."

# Verify MJPC was built during Docker build
if [ ! -d "/app/mujoco_mpc" ]; then
    echo "ERROR: MJPC not found at /app/mujoco_mpc - Docker build may have failed"
    exit 1
fi

if [ ! -f "/app/mujoco_mpc/build/bin/mjpc" ]; then
    echo "ERROR: MJPC binary not found - build may have failed"
    exit 1
fi

# Set file descriptor limit for current session
ulimit -n 4096

# MJPC binary permissions are already set during Docker build
echo "MJPC binary permissions already configured during build"

echo "MJPC runtime setup completed successfully"
echo "MJPC binary location: /app/mujoco_mpc/build/bin/mjpc"

# Verify the binary works
cd /app/mujoco_mpc/build/bin
if ./mjpc --help >/dev/null 2>&1 || [ $? -eq 1 ]; then
    echo "MJPC binary verification successful"
else
    echo "Warning: MJPC binary may have issues, but continuing..."
fi

echo "Setup complete - ready for VPN registration and startup"
