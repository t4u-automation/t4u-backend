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
RUN pip3 install playwright httpx websockify pyjwt cryptography requests

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

# Copy Firebase JWT validation plugin
COPY validate_firebase_jwt.py /home/user/validate_firebase_jwt.py
RUN chmod +x /home/user/validate_firebase_jwt.py
# Ensure Python can import it
RUN python3 -m py_compile /home/user/validate_firebase_jwt.py

# Create startup script for desktop services
RUN echo '#!/bin/bash\n\
export DISPLAY=:99\n\
# Start Xvfb\n\
nohup Xvfb :99 -screen 0 1280x720x24 > /tmp/xvfb.log 2>&1 &\n\
sleep 2\n\
# Start fluxbox\n\
nohup fluxbox > /tmp/fluxbox.log 2>&1 &\n\
sleep 1\n\
# Start x11vnc\n\
nohup x11vnc -display :99 -forever -shared -nopw -rfbport 5900 > /tmp/vnc.log 2>&1 &\n\
sleep 1\n\
# Start websockify with Firebase JWT plugin\n\
cd /home/user/novnc\n\
PYTHONPATH=/home/user websockify --web . --token-plugin=validate_firebase_jwt.TokenPlugin 0.0.0.0:6080 > /tmp/websockify.log 2>&1 &\n\
WS_PID=$!\n\
sleep 3\n\
# Verify websockify started\n\
if ps -p $WS_PID > /dev/null 2>&1; then\n\
    echo "Desktop services started (websockify PID: $WS_PID)"\n\
else\n\
    echo "WARNING: websockify may have failed, check /tmp/websockify.log"\n\
    tail -20 /tmp/websockify.log 2>&1 || echo "No logs found"\n\
fi\n\
' > /home/user/start_desktop.sh && chmod +x /home/user/start_desktop.sh
