from ds_air_service.decoder import decoder
from ds_air_service.display import display

list = [
    # '0212000d000000010000000000000000001000000103',
    # '0211000d0000000500000000000000000001000203',
]


def show(s):
    if s[0] == "D":
        s = s[6:]
    print(s)
    b = bytes.fromhex(s)
    while b:
        r, b = decoder(b)
        print(display(r))


for i in list:
    show(i)

import socket


def connect():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("192.168.1.213", 8008))
    s.sendall(bytes.fromhex("0210000d0001000100000000000000000100a003"))
    s.sendall(bytes.fromhex("0213000d00010005000000000000000001300001ffff03"))
    "0x02 1300 0d00 0100 05000000 000000000001300001ffff03"
    "0x02 1300 0d00 0100 02000000 000000000001300001ffff03"
    while True:
        data = s.recv(1024)
        print("0x" + data.hex())


# connect()
