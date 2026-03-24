FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    flex \
    bison \
    libboost-all-dev \
    ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clonar servidor
RUN git clone https://github.com/rcsoccersim/rcssserver.git

WORKDIR /app/rcssserver

# Compilar
RUN mkdir build && cd build && cmake .. && make -j4

WORKDIR /app/rcssserver/build

# Comando por defecto (opcional)
CMD ["./rcssserver", "server::port=6000"]