FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --fix-missing --no-install-recommends \
    build-essential \
    cmake \
    git \
    flex \
    bison \
    libfl-dev \
    libboost-all-dev \
    ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN git clone https://github.com/rcsoccersim/rcssserver.git

WORKDIR /app/rcssserver

RUN mkdir build && cd build && cmake .. && make -j4

WORKDIR /app/rcssserver/build

CMD ["./rcssserver", "server::port=6000"]
