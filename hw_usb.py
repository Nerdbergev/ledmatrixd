#!/usr/bin/python
import usb.core
import ledpanel_tools
import usb.core

class HW_USB:
    def __init__(self):
        self.dev = usb.core.find(idVendor=0x4e65, idProduct=0x7264)
        if self.dev is None :
            raise FileNotFoundError()
        self.dev.set_configuration()
        self.running = True

    # stop the 'HW'
    def stop(self):
        pass

    def update(self, img):
        self.dev.ctrl_transfer(0x40, 0)
        output = ledpanel_tools.image_to_ledpanel_bytes(img)
        self.dev.write(0x01, output)
