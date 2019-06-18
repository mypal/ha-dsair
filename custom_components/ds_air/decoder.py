import struct


def decoder(b):
    if b[0] != 2:
        print(b[0])
        return None

    length = struct.unpack('<H', b[1:3])[0]
    if length == 0 or len(b) - 4 < length or struct.unpack('<B', b[length + 3:length + 4])[0] != 3:
        if length == 0:
            print('heartbeat:' + b)
        else:
            print('exception:' + b)
        return None

    return result_factory(struct.unpack('<BHBBBBIBIBH' + str(length - 16) + 'sB', b[:length + 4])), b[length + 4:]


def result_factory(data):
    r1, length, r2, r3, sub_body_ver, r4, cnt, dev_type, dev_id, need_ack, cmd_type, subbody, r5 = data
    print(length, sub_body_ver, dev_type, dev_id, need_ack, cmd_type, subbody)
    return None
