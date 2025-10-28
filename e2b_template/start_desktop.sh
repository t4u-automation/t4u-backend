#!/bin/bash
# Start desktop services using supervisor

# Start supervisor (manages all desktop services)
/usr/bin/supervisord -c /etc/supervisor/supervisord.conf

# Keep running
tail -f /dev/null

