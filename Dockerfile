FROM ubuntu:22.04

# Environment setup - these rarely change so put them early
ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:1 \
    VNC_PORT=5901 \
    HOME=/app \
    VNC_COL_DEPTH=24

# Optional: use local `mujoco_mpc` folder from build context instead of cloning from GitHub.
ARG USE_LOCAL_MJPC=false

# ===== PACKAGE INSTALLATION LAYER (cached unless packages change) =====
# Install system dependencies (excluding resolvconf initially)
RUN apt-get update && apt-get install -y \
    # VNC server packages
    tigervnc-standalone-server \
    tigervnc-common \
    xterm \
    xauth \
    xfonts-base \
    xinit \
    ca-certificates \
    openbox \
    python3-websockify \
    sudo \
    wmctrl \
    # MJPC dependencies
    build-essential \
    llvm-12 \
    git \
    cmake \
    ninja-build \
    clang-12 \
    zlib1g-dev \
    libgl1-mesa-dev \
    libxinerama-dev \
    libxcursor-dev \
    libxrandr-dev \
    libxi-dev \
    # Lsb specific dependencies
    openssh-server \
    iproute2 \
    supervisor \
    postgresql-client \
    python3 \
    python3-venv \
    python3-pip \
    wireguard-tools \
    iptables \
    curl \
    jq \
    iputils-ping \
    net-tools \
    bash \
    coreutils \
    gcc \
    python3-dev \
    musl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install resolvconf separately and handle Docker conflicts
RUN apt-get update && \
    (apt-get install -y resolvconf || true) && \
    dpkg --configure -a || true && \
    rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/novnc/noVNC.git /usr/share/novnc && \
    ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html

# ===== MJPC BUILD  =====
# Build MJPC during Docker build (as root) to avoid runtime issues
# If the build sets USE_LOCAL_MJPC=true, copy the local folder into the image. Otherwise clone from GitHub.
COPY --chown=root:root ./mujoco_mpc /app/mujoco_mpc

RUN echo "Building MJPC during Docker build..." && \
        ulimit -n 4096 && \
        if [ "${USE_LOCAL_MJPC}" = "true" ] && [ -d /app/mujoco_mpc ]; then \
            echo "Using local /app/mujoco_mpc provided in the build context"; \
        else \
            echo "Local mujoco_mpc not provided or USE_LOCAL_MJPC!=true, cloning from GitHub" && \
            rm -rf /app/mujoco_mpc && \
            git clone https://github.com/google-deepmind/mujoco_mpc /app/mujoco_mpc; \
        fi && \
        cd /app/mujoco_mpc && \
        mkdir -p build && \
        cd build && \
        cmake .. \
            -DCMAKE_BUILD_TYPE=Release \
            -G Ninja \
            -DCMAKE_C_COMPILER=clang-12 \
            -DCMAKE_CXX_COMPILER=clang++-12 \
            -DMJPC_BUILD_GRPC_SERVICE:BOOL=OFF && \
        cmake --build . && \
        chmod +x /app/mujoco_mpc/build/bin/* && \
        echo "MJPC build completed successfully"

# Clean up build dependencies and caches (handle resolvconf conflicts)
RUN (apt-get autoremove -y || true) && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/*

# ===== USER SETUP =====
# Create user and setup sudo
RUN useradd -ms /bin/bash default && \
    usermod -aG sudo default && \
    echo "default ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Create necessary directories
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix && \
    mkdir -p /app/.vnc && chown -R default:default /app/.vnc

# ===== COPY STATIC FILES =====
COPY xstartup /app/.vnc/xstartup
RUN chmod +x /app/.vnc/xstartup
COPY setup.sh startup.sh register.sh app.py /app/
RUN chmod +x /app/setup.sh /app/startup.sh /app/register.sh /app/app.py

# ===== WEBAPP =====
RUN python3 -m venv /app/venv
RUN . /app/venv/bin/activate && pip install flask flask-socketio eventlet psutil
EXPOSE 5901 6901

# Use supervisor to run multiple services
ENTRYPOINT ["/bin/bash", "-c", "sleep 10 && /app/setup.sh && /app/startup.sh"]
