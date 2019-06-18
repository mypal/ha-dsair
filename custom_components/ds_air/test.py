import socket
import struct

HOST = '192.168.1.110'
PORT = 8008

# with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#     s.connect((HOST, PORT))
#     st = struct.pack('<BHBBBBIBIBHB', 2, 16, 13, 0, 0, 0, 1, 0, 0, 1, 40960, 3)
#     print('packed')
#     print(st)
#     s.sendall(st)
#     print('sent')
#     data = s.recv(1024)
#     print(repr(data))

a = (1, 2)
print(a)
