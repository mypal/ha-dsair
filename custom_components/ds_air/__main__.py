import socket

from .param import HandShakeParam
from .decoder import decoder

HOST = '192.168.1.110'
PORT = 8008

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    try:
        s.connect((HOST, PORT))
        s.sendall(HandShakeParam().to_string())
        while True:
            data = s.recv(1024)
            print('data:')
            print(repr(data))
            while data:
                res, buf = decoder(data)
                print('result:')
                print(res.__dict__)
                print('buffer:')
                print(repr(buf))
                data = buf
    finally:
        s.close()
