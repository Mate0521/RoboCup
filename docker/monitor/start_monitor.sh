#!/bin/bash

# Limpiar locks previos (clave para Docker restart)
rm -f /tmp/.X99-lock

# Arrancar pantalla virtual
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99

# Esperar a que X levante correctamente
sleep 2

# Arrancar VNC
x11vnc -display :99 -nopw -forever -quiet &

# Esperar
sleep 2

# Ejecutar monitor
/app/rcssmonitor/build/rcssmonitor --server-host=rcssserver --server-port=6000
