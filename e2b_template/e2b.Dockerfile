# E2B Custom Template with VNC desktop and all dependencies pre-installed
FROM ubuntu:22.04

# Set environment
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tmux \
    xvfb \
    x11vnc \
    fluxbox \
    scrot \
    python3 \
    python3-pip \
    curl \
    wget \
    git \
    net-tools \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install --no-cache-dir \
    playwright \
    httpx

# Install Playwright browsers
RUN playwright install chromium && \
    playwright install-deps chromium

# Create workspace
RUN mkdir -p /home/user /var/log/supervisor
WORKDIR /home/user

# Create supervisor config for desktop services
RUN echo '[supervisord]\n\
nodaemon=true\n\
logfile=/var/log/supervisor/supervisord.log\n\
pidfile=/var/run/supervisord.pid\n\
\n\
[program:xvfb]\n\
command=Xvfb :99 -screen 0 1280x720x24\n\
autorestart=true\n\
stdout_logfile=/var/log/supervisor/xvfb.log\n\
stderr_logfile=/var/log/supervisor/xvfb.err\n\
\n\
[program:fluxbox]\n\
command=fluxbox\n\
environment=DISPLAY=":99"\n\
autorestart=true\n\
stdout_logfile=/var/log/supervisor/fluxbox.log\n\
stderr_logfile=/var/log/supervisor/fluxbox.err\n\
\n\
[program:x11vnc]\n\
command=x11vnc -display :99 -forever -shared -nopw\n\
autorestart=true\n\
stdout_logfile=/var/log/supervisor/vnc.log\n\
stderr_logfile=/var/log/supervisor/vnc.err\n\
' > /etc/supervisor/conf.d/desktop.conf

# Expose VNC port
EXPOSE 5900

# Start supervisor to manage desktop services
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]

