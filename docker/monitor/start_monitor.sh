#!/bin/bash
# Arrancar pantalla virtual
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99

# Arrancar VNC server (sin contraseña para simplicidad interna)
x11vnc -display :99 -nopw -forever -quiet &

# Esperar que el servidor esté listo
sleep 3

# Arrancar monitor
/app/rcssmonitor/build/rcssmonitor --server-host=rcssserver --server-port=6000