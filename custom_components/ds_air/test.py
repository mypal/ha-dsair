import socket
import struct

HOST = '192.168.1.110'
PORT = 8008

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    st = struct.pack('<BHB', 2, 0, 3)
    print('packed')
    s.sendall(st)
    print('sent')
    data = s.recv(1024)
    print(repr(data))

