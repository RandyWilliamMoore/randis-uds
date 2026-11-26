#!/bin/sh
set -e
cd /app
Xvfb :1 -screen 0 "${SCREEN_WIDTH:-1600}x${SCREEN_HEIGHT:-900}x24" -nolisten tcp &
i=0
while [ ! -e /tmp/.X11-unix/X1 ] && [ $i -lt 100 ]; do sleep 0.1; i=$((i+1)); done
openbox >/dev/null 2>&1 &
if [ -n "$VNC_PASSWORD" ]; then
  x11vnc -storepasswd "$VNC_PASSWORD" "$HOME/.vncpass" >/dev/null 2>&1
  set -- -rfbauth "$HOME/.vncpass"
else
  set -- -nopw
fi
x11vnc -display :1 -forever -shared -localhost -rfbport 5900 -quiet "$@" >/dev/null 2>&1 &
websockify --web /usr/share/novnc 6080 localhost:5900 >/dev/null 2>&1 &
export UDS_LAUNCH_TRIES="${UDS_LAUNCH_TRIES:-60,90,180}"
exec dbus-run-session -- sh -c '.venv/bin/python launch.py; cat data/launch.log; while [ -f data/app.lock ] && kill -0 "$(cat data/app.lock)" 2>/dev/null; do sleep 2; done'
