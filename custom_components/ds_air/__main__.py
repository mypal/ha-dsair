import socket

from .ctrl_enum import EnumCmdType
from .param import HandShakeParam
from .decoder import decoder

HOST = '192.168.1.110'
PORT = 8008

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    try:
        s.connect((HOST, PORT))
        s.sendall(HandShakeParam().to_string())
        data = s.recv(1024)
        print(repr(data))
        while data:
            res, buf = decoder(data)
            print(res)
            data = buf
    finally:
        s.close()
