#!./venv/bin/python
import asyncio
import gzip
import json
import logging
from argparse import ArgumentParser
from logging import critical, debug, error, info, warning
from pathlib import Path
from tempfile import NamedTemporaryFile

import asyncio_mqtt
import PIL.BdfFontFile
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import PIL.PcfFontFile
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
        for k in arr:
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


class LedMatrix:
    def __init__(self, width, height, hw):
        self.width = width
        self.height = height
        self.hw = hw

        self.fonts = list()
        self.animations = dict()

        self.curr_img = None
        self.curr_anim = None  # (animation iterator, x_offs, y_offs)

    def add_animation(self, fn):
        self.animations.append(SquareAnimation(fn))

    def add_font(self, fn):
        if not isinstance(fn, Path):
            filename = Path(fn)

        font = None
        if '.bdf' in fn.suffixes:
            constr = PIL.BdfFontFile.BdfFontFile
        elif '.pcf' in fn.suffixes:
            constr = PIL.PcfFontFile.PcfFontFile
        elif '.pil' in fn.suffixes:
            font = PIL.ImageFont.load(fn)
        else:
            raise RuntimeError(f'Unknown font format for {fn}.')

        if font is None:
            if '.gz' in fn.suffixes:
                fp = gzip.open(fn)
            else:
                fp = fn.open('rb')

            with NamedTemporaryFile('wb', suffix='.pil') as pilf:
                ff = constr(fp)
                ff.save(pilf.name)
                font = PIL.ImageFont.load(pilf.name)

        info(f'Adding font {fn}.')
        self.fonts.append(font)

    async def main_loop(self):
        pacman = SquareAnimation('pacman_20x20_right_to_left.png')
        pacman_iter = iter(pacman)

        s = 'Hello NerdBerg!'
        fnt = self.fonts[0]
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


async def mqtt_task_coro(args, matrix):
    async with asyncio_mqtt.Client(args.mqtt_host) as client:
        await client.subscribe(args.mqtt_subscribe)
        while True:
            async with client.unfiltered_messages() as messages:
                async for msg in messages:
                    info(f'MQTT message on topic {msg.topic}: {msg.payload}')
                    try:
                        obj = json.loads(msg.payload)
                    except Exception as exc:
                        err_obj = {'result': 'error', 'error': repr(exc)}
                        err_str = json.dumps(err_obj)
                        error(
                            f'Exception {repr(exc)} while decoding json object.')
                        await client.publish(args.mqtt_publish, err_str, qos=1)


def main():
    parser = ArgumentParser()
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Be quiet (logging level: warning)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Be verbose (logging level: debug)')

    grp = parser.add_argument_group('Hardware')

    grp.add_argument('-W', '--width', type=int, default=120,
                     help='LED panel width [def:%(default)d]')
    grp.add_argument('-H', '--height', type=int, default=20,
                     help='LED panel height [def:%(default)d]')

    grp = parser.add_argument_group('Graphics')

    grp.add_argument('-f', '--font', nargs='+', type=Path, metavar='pil/bdf',
                     help='Add font file(s).')

    grp.add_argument('-a', '--animation', nargs='+', type=Path, metavar='png',
                     help='Add animation(s).')

    grp = parser.add_argument_group('MQTT', 'Options for MQTT communication.')

    grp.add_argument('-M', '--mqtt-host', type=str, metavar='hostname',
                     help='MQTT Server Name (or address), default: no mqtt server used')
    grp.add_argument('-s', '--mqtt-subscribe', type=str, metavar='topic', default='ledmatrix/cmd',
                     help='Topic to subscribe to for commands. [def: %(default)s]')
    grp.add_argument('-p', '--mqtt-publish', type=str, metavar='topic', default='ledmatrix/result',
                     help='Topit to publish results to for results. [def: %(default)s]')

    args = parser.parse_args()

    log_lvl = logging.INFO
    if args.verbose:
        log_lvl = logging.DEBUG
    if args.quiet:
        log_lvl = logging.WARNING

    logging.basicConfig(level=log_lvl, format='%(asctime)s %(message)s')

    loop = asyncio.new_event_loop()

    hw = hw_pygame.HW_PyGame(loop, args.width, args.height)
    mx = LedMatrix(args.width, args.height, hw)

    mqtt_task = None
    if args.mqtt_host is not None:
        mqtt_task = loop.create_task(mqtt_task_coro(args, mx))

    if args.font:
        for fn in args.font:
            mx.add_font(fn)

    if args.animation:
        for fn in args.animation:
            mx.add_animation(fn)

    try:
        loop.run_until_complete(mx.main_loop())
        # here the mqtt_task will crash, as the loop has been closed already
        # we have to fix this later
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
