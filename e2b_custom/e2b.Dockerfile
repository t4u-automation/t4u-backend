# E2B Template with Playwright + VNC Desktop pre-installed
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99

# Install all dependencies in one layer (including xterm, xdotool)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    tmux \
    xvfb \
    x11vnc \
    fluxbox \
    scrot \
    xterm \
    xdotool \
    net-tools \
    git \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install playwright httpx websockify

# Create user workspace
RUN mkdir -p /home/user/.cache/ms-playwright
WORKDIR /home/user

# Install Chromium with proper paths
ENV PLAYWRIGHT_BROWSERS_PATH=/home/user/.cache/ms-playwright
ENV HOME=/home/user

RUN playwright install chromium
RUN playwright install-deps chromium

# Download noVNC to permanent location (not /tmp which gets cleared)
RUN git clone --depth 1 https://github.com/novnc/noVNC.git /home/user/novnc

# Create startup script for desktop services
RUN echo '#!/bin/bash\n\
export DISPLAY=:99\n\
nohup Xvfb :99 -screen 0 1280x720x24 > /tmp/xvfb.log 2>&1 &\n\
sleep 2\n\
nohup fluxbox > /tmp/fluxbox.log 2>&1 &\n\
sleep 1\n\
nohup x11vnc -display :99 -forever -shared -nopw -rfbport 5900 > /tmp/vnc.log 2>&1 &\n\
sleep 1\n\
cd /home/user/novnc && nohup websockify --web . --daemon 0.0.0.0:6080 localhost:5900 > /tmp/websockify.log 2>&1 &\n\
echo "Desktop services started"\n\
' > /home/user/start_desktop.sh && chmod +x /home/user/start_desktop.sh
