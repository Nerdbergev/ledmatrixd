#!./venv/bin/python
import asyncio
import logging
from argparse import ArgumentParser
from logging import critical, debug, error, info, warning
from pathlib import Path
from tempfile import NamedTemporaryFile

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

    # first round, keep a copy
    for k in it:
        arr.append(k)
        yield k

    while True:
        # reverse back
        for k in arr[-2:0:-1]:
            yield k
        if not endless:
            break
        # forward again
        for k in arr :
            yield k


class SquareAnimation:
    def __init__(self, fn):
        img = PIL.Image.open(fn)  # assume N squares sz * sz
        self.imgsz = img.size[1]  # width and height of a square
        N = img.size[0] // img.size[1]  # number of squares

        self.img_arr = []  # store individual tiles, cropped out
        for j in range(N):
            # left, top, right, bottom
            rect = [self.imgsz * j, 0, self.imgsz*(j+1), self.imgsz]
            self.img_arr.append(img.crop(rect))

    def __iter__(self):
        return ping_pong_iter(self.img_arr, True)


def handle_http(req):
    pass


class LedMatrix :
    def __init__(self, width, height, hw) :
        self.width = width
        self.height = height
        self.hw = hw

        self.fonts = dict()

    def add_font(self, filename) :
        if not isinstance(filename, Path) :
            filename = Path(filename)

        name = filename.stem
        ff = None

        if filename.suffix.lower() == '.bdf' :
            with NamedTemporaryFile('wb', suffix='.pil') as pilf :
                info(f'Converting BDF fontfile {filename} to pil.')
                bdf = PIL.BdfFontFile.BdfFontFile(filename.open('rb'))
                bdf.save(pilf.name)
                ff = PIL.ImageFont.load(pilf.name)

        assert(ff)
        info(f'Adding font {name}.')
        self.fonts[name] = ff

    async def main_loop(self):
        pacman = SquareAnimation('pacman_20x20_right_to_left.png')
        pacman_iter = iter(pacman)

        s = 'Hello NerdBerg!'
        fnt = self.fonts['unifont']
        f_width, f_height = fnt.getsize(s)

        width = f_width + pacman.imgsz + 2*self.width
        height = max(f_height, self.height)

        img = PIL.Image.new(mode='L', size=(width, height))
        drw = PIL.ImageDraw.Draw(img)
        drw.text((self.width, 0), s, font=fnt, fill=(0xff,))

        dx = 0
        while self.hw.running:
            await asyncio.sleep(1.0/60)  # 60 Hz

            img.paste(next(pacman_iter), (f_width + self.width, 0))
            self.hw.update(img.crop((dx, 0, dx+self.width, img.size[1])))

            dx += 1
            if dx >= img.size[0] - self.width:
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
    mx = LedMatrix(args.width, args.height, hw)

    mx.add_font('/usr/share/fonts/misc/unifont.bdf')

    try:
        loop.run_until_complete(mx.main_loop())
    except KeyboardInterrupt:
        pass

    info('Cleaning up hw...')
    hw.stop()


if __name__ == '__main__':
    main()
