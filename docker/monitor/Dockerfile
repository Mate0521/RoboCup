FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Bogota

RUN apt-get update && apt-get install -y --fix-missing \
    build-essential cmake git flex bison libfl-dev \
    libboost-all-dev qtbase5-dev \
    xvfb x11vnc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone https://github.com/rcsoccersim/rcssmonitor.git
WORKDIR /app/rcssmonitor
RUN mkdir build && cd build && cmake .. && make -j4

COPY start_monitor.sh /start_monitor.sh
RUN chmod +x /start_monitor.sh
CMD ["/start_monitor.sh"]