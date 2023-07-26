#!/usr/bin/python
import usb.core
import PIL.Image
import struct

def bitflip(v):
    v = ((v & 0xffff0000) >> 16) | ((v & 0x0000ffff) << 16)
    v = ((v & 0xff00ff00) >> 8) | ((v & 0x00ff00ff) << 8)
    v = ((v & 0xf0f0f0f0) >> 4) | ((v & 0x0f0f0f0f) << 4)
    v = ((v & 0xcccccccc) >> 2) | ((v & 0x33333333) << 2)
    return ((v & 0xaaaaaaaa) >> 1) | ((v & 0x55555555) << 1)


def image_to_ledpanel_bytes(img: PIL.Image, old_format=False) -> bytes:

    if img.mode != '1':
        img = img.convert('1')

    if not old_format :
        return img.tobytes()

    ret = bytearray()

    # number of bytes, number of u32 words, zeros to pad
    bytes_row = (img.size[0] + 7) // 8
    u32_row = (bytes_row + 3) // 4
    zero_pad = bytes([0 for i in range(u32_row*4 - bytes_row)])

    for offs in range(0, len(bitdata), bytes_row):
        # 32bit words, but with wront byteorder, MSB of first byte
        # is first pixel!
        rowdata = bitdata[offs:offs+bytes_row] + zero_pad
        u32words = [bitflip(v) for v in struct.unpack(f'>{u32_row}I', rowdata)]
        ret += struct.pack(f'<{u32_row}I', *u32words)

    return bytes(ret)


class HW_USB:
    def __init__(self):
        self.dev = usb.core.find(idVendor=0x4e65, idProduct=0x7264)
        if self.dev is None:
            raise FileNotFoundError()
        self.dev.set_configuration()
        self.running = True

    # stop the 'HW'
    def stop(self):
        pass

    def update(self, img):
        self.dev.ctrl_transfer(0x40, 0)
        output = image_to_ledpanel_bytes(img)
        self.dev.write(0x01, output)
