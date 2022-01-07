#!./venv/bin/python
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


# given an iterable object, return
# 0, 1, .., N-2, N-1, N-2, .. 1; repeat if endless=True
def ping_pong_iter(it, endless=False):
    arr = list()

    while True:
        for k in it:
            arr.append(k)
            yield k
        for k in arr[-2:0:-1]:
            yield k
        if not endless:
            break


class SquareAnimation:
    def __init__(self, fn):
        img = PIL.Image.open(fn)  # assume N squares sz * sz
        imgsz = img.size[1]  # width and height of a square
        N = img.size[0] // img.size[1]  # number of squares

        self.img_arr = []  # store individual tiles, cropped out
        for j in range(N):
            # left, top, right, bottom
            rect = [imgsz * j, 0, imgsz*(j+1), imgsz]
            self.img_arr.append(img.crop(rect))

    def __iter__(self):
        return ping_pong_iter(self.img_arr, True)


def handle_http(req):
    pass


async def main_loop(args, hw):
    pacman = iter(SquareAnimation('pacman_20x20_right_to_left.png'))

    s = 'Hello NerdBerg!'

#    Pixel Font, create from unifont.bdf
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

        img.paste(next(pacman), (f_width + args.width, 0))
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

    info('Cleaning up hw (pygame will segfault)...')
    hw.stop()


if __name__ == '__main__':
    main()
