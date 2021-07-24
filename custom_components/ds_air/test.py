from ds_air_service.display import display
from ds_air_service.decoder import decoder

list = [
    '0x021e000d0000000100000000000000000000a0323032313037323232323335313603',
]


def show(s):
    b = bytes.fromhex(s[2:])
    while b:
        r, b = decoder(b)
        print(display(r))


# show(list[1])
