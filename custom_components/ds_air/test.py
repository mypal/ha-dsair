from ds_air_service.display import display
from ds_air_service.decoder import decoder

list = [
    '0227000d00000011f4cf2d00000000000001a015000211000d000000020000000000000000000100020303',
]


def show(s):
    if s[0] == 'D':
        s = s[6:]
    b = bytes.fromhex(s)
    while b:
        r, b = decoder(b)
        print(display(r))


# show(list[0])
