FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:1 \
    VNC_PORT=5901 \
    HOME=/app \
    VNC_COL_DEPTH=24

ARG USE_LOCAL_MJPC=false
RUN apt-get update && apt-get install -y \
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

RUN apt-get update && \
    (apt-get install -y resolvconf || true) && \
    dpkg --configure -a || true && \
    rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/novnc/noVNC.git /usr/share/novnc && \
    ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html

COPY --chown=root:root ./mujoco_mpc /app/mujoco_mpc

RUN ulimit -n 4096 && \
    if [ "${USE_LOCAL_MJPC}" = "true" ] && [ -d /app/mujoco_mpc ]; then \
        echo "Using local mujoco_mpc"; \
    else \
        rm -rf /app/mujoco_mpc && \
        git clone https://github.com/google-deepmind/mujoco_mpc /app/mujoco_mpc; \
    fi && \
    cd /app/mujoco_mpc && \
    mkdir -p build && cd build && \
    cmake .. \
        -DCMAKE_BUILD_TYPE=Release \
        -G Ninja \
        -DCMAKE_C_COMPILER=clang-12 \
        -DCMAKE_CXX_COMPILER=clang++-12 \
        -DMJPC_BUILD_GRPC_SERVICE:BOOL=OFF && \
    cmake --build . && \
    chmod +x /app/mujoco_mpc/build/bin/* && \
    echo "MJPC build completed"

RUN (apt-get autoremove -y || true) && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/*
RUN useradd -ms /bin/bash default && \
    usermod -aG sudo default && \
    echo "default ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers && \
    mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix && \
    mkdir -p /app/.vnc && chown -R default:default /app/.vnc

COPY xstartup /app/.vnc/xstartup
COPY startup.sh register.sh app.py /app/
RUN chmod +x /app/.vnc/xstartup /app/startup.sh /app/register.sh

RUN python3 -m venv /app/venv && \
    . /app/venv/bin/activate && \
    pip install flask flask-sock psutil requests

EXPOSE 5901 6901 5000

ENTRYPOINT ["/bin/bash", "-c", "/app/startup.sh"]
