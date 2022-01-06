#!/usr/bin/python
import asyncio
import logging
from argparse import ArgumentParser
from logging import critical, debug, error, info, warning
from pathlib import Path

import aiohttp
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import PIL.BdfFontFile
import pygame
import pygame.locals

import hw_pygame  # dummy hw


class LED_Schild:
    def __init__(self, width, height, hw):
        self.width = width
        self.height = height
        self.hw = hw

        self.src_images = list()
        self.src_image_ix = None
        self.offset_x = 0

    def tick(self):
        pass


def handle_http(req):
    pass


async def main_loop(args, hw):
    #    img = PIL.Image.open('../subway_led_panel_stm32f103/test/test_1200x20.png')

    s = 'Hello NerdBerg, this is a test! äöpßz'

#    TrueType
#    fnt = PIL.ImageFont.truetype('arial.ttf', size=args.height)
#    left, top, f_width, f_height = fnt.getbbox(s)


#    Pixel Font
    unifont_pil = Path('./unifont.pil')
    if not unifont_pil.exists():
        unifont_bdf = Path('/usr/share/fonts/misc/unifont.bdf')
        ff = PIL.BdfFontFile.BdfFontFile(unifont_bdf.open('rb'))
        ff.save(unifont_pil)

    fnt = PIL.ImageFont.load(unifont_pil)
    f_width, f_height = fnt.getsize(s)

    width = max(f_width + 2*args.width, args.width)
    height = max(f_height, args.height)

    img = PIL.Image.new(mode='L', size=(width, height))
    drw = PIL.ImageDraw.Draw(img)
    drw.text((args.width, 0), s, font=fnt, fill=(0xff,))

    dx = 0
    while hw.running:
        await asyncio.sleep(1.0/60)  # 60 Hz
        hw.update(img.crop((dx, 0, dx+args.width, img.size[1])))

        dx += 1
        if dx >= img.size[0] - args.width:
            dx = 0


def main():
    parser = ArgumentParser()
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Be quiet (logging level: warning)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Be verbose (logging level: debug)')
    parser.add_argument('-W', '--width', type=int, default=120,
                        help='LED panel width [def:%(default)d]')
    parser.add_argument('-H', '--height', type=int, default=20,
                        help='LED panel height [def:%(default)d]')

    parser.add_argument('-P', '--http-server-port', type=int, default=None)

    args = parser.parse_args()

    log_lvl = logging.INFO
    if args.verbose:
        log_lvl = logging.DEBUG
    if args.quiet:
        log_lvl = logging.WARNING

    logging.basicConfig(level=log_lvl, format='%(asctime)s %(message)s')

    loop = asyncio.new_event_loop()
    if args.http_server_port is not None:
        app = aiohttp.web.Application()
        app.add_routes([aiohttp.web.get('/', handle_http)])
        runner = aiohttp.web.AppRunner(app)
        loop.run_until_complete(runner.setup())
        site = aiohttp.web.TCPSite(runner, '0.0.0.0', args.http_server_port)
        loop.run_until_complete(site.start())

    # hardware output
    hw = hw_pygame.HW_PyGame(loop, args.width, args.height)

    try:
        loop.run_until_complete(main_loop(args, hw))
    except KeyboardInterrupt:
        pass

    info('Cleaning up hw...')
    hw.stop()


if __name__ == '__main__':
    main()
