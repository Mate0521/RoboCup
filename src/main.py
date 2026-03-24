import socket
import time

def connect():
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("rcssserver", 6000))
            print("Conectado!")
            return s
        except:
            print("Reintentando...")
            time.sleep(2)

def main():
    s = connect()

    while True:
        data = s.recv(1024)
        print(data)

if __name__ == "__main__":
    main()