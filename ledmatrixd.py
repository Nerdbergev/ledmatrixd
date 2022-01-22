#!./venv/bin/python
import asyncio
import gzip
import json
import logging
from argparse import ArgumentParser
from logging import critical, debug, error, info, warning
from pathlib import Path
from tempfile import NamedTemporaryFile
import sys

import asyncio_mqtt
import PIL.BdfFontFile
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import PIL.PcfFontFile


# this maxes arithmetic around the 4 tuples used for regions (boxes in PIL parlance)
# a little easier
class Box:
    def __init__(self, left, top, right=None, bottom=None, width=None, height=None):
        self.left = left
        self.top = top
        self.right = right if right is not None else width + left
        self.bottom = bottom if bottom is not None else height + top

    def __repr__(self):
        return f'(#box {self.left},{self.top},{self.right},{self.bottom})'

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top

    @property
    def box(self):
        return self.left, self.top, self.right, self.bottom

    @property
    def size(self):
        return self.right - self.left, self.bottom - self.top

    @property
    def topleft(self):
        return self.left, self.top


# given an iterable object, return
# 0, 1, .., N-2, N-1, N-2, .. 1; repeat if endless=True
def ping_pong_iter(src_iter, endless=False):
    arr = list()

    # first round, keep a copy

    for k in src_iter:
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
    def __init__(self, filename):
        img = PIL.Image.open(filename)  # assume N squares sz * sz
        self.imgsz = img.size[1]  # width and height of a square
        n_phases = img.size[0] // img.size[1]  # number of squares

        self.img_arr = []  # store individual tiles, croped out
        for j in range(n_phases):
            # left, top, right, bottom
            rect = [self.imgsz * j, 0, self.imgsz*(j+1), self.imgsz]
            self.img_arr.append(img.crop(rect))

    @property
    def width(self) :
        return self.img_arr[0].size[0]

    @property
    def height(self) :
        return self.img_arr[0].size[1]

    def __iter__(self):
        return ping_pong_iter(self.img_arr, True)


class Canvas:
    def __init__(self):
        pass

    def stamp_into(self, dst):
        pass

    def tick(self):
        pass


class TextScrollCanvas(Canvas):

    def __init__(self, box: Box, text: str, font: PIL.ImageFont.ImageFont, dx=1.0):
        self.box = box
        self.update_txt(text, font, dx)
        self.x_offs = 0.0
        self.dx = dx

        self.anim_box = None
        self.anim_iter = None

        info(f'New TextScrollCanvas at {self.box}: {text}')

    def place_animation(self, x, y, anim):
        self.anim_box = Box(x, y, width=anim.width, height=anim.height)
        self.anim_iter = iter(anim)

    def remove_animation(self):
        self.anim_box = None
        self.anim_iter = None

    def update_txt(self, s, fnt, dx):
        txt_width, _ = fnt.getsize(s)

        # option 1, <space> <text> <space>, makes sure that there
        # is a period where the whole matrix is empty before/after text is shown

        img_width = txt_width + 2 * self.box.width - 1

        self.img = PIL.Image.new(mode='L', size=(img_width, self.box.height))
        drw = PIL.ImageDraw.Draw(self.img)
        drw.text((self.box.width, 0), s, font=fnt, fill=(0xff, ))

        self.x_offs = 1.0
        self.dx = dx

    def stamp_into(self, dst: PIL.Image):
        x_offs_int = int(self.x_offs)

        crop_img = self.img.crop(Box(
            x_offs_int,
            0,
            width=self.box.width,
            height=self.box.height
        ).box)
        dst.paste(crop_img, self.box.topleft)

    def tick(self):
        if self.dx == 0.0:
            return

        if self.anim_iter:
            self.img.paste(next(self.anim_iter), self.anim_box.box)

        self.x_offs += self.dx

        if self.dx > 0.0:
            while self.x_offs >= self.img.size[0] - self.box.width:
                self.x_offs -= self.img.size[0] - self.box.width
        if self.dx < 0.0:
            while self.x_offs < 0:
                self.x_offs += self.img.size[0] - self.box.width


class LedMatrix:
    def __init__(self, width, height, matrix_hw=None):
        self.width = width
        self.height = height
        self.matrix_hw = matrix_hw

        self.img = PIL.Image.new('L', size=(self.width, self.height))

        self.canvases = list()
        self.animations = list()
        self.fonts = list()

    def add_animation(self, filename):
        self.animations.append(SquareAnimation(filename))

    def add_font(self, filename):
        if not isinstance(filename, Path):
            filename = Path(filename)

        font = None
        if '.bdf' in filename.suffixes:
            constr = PIL.BdfFontFile.BdfFontFile
        elif '.pcf' in filename.suffixes:
            constr = PIL.PcfFontFile.PcfFontFile
        elif '.pil' in filename.suffixes:
            font = PIL.ImageFont.load(filename)
        else:
            raise RuntimeError(f'Unknown font format for {filename}.')

        if font is None:
            if '.gz' in filename.suffixes:
                reader = gzip.open(filename)
            else:
                reader = filename.open('rb')

            with NamedTemporaryFile('wb', suffix='.pil') as pil_font_file:
                raw_font_file = constr(reader)
                raw_font_file.save(pil_font_file.name)
                font = PIL.ImageFont.load(pil_font_file.name)

        info(f'Adding font {filename}.')
        self.fonts.append(font)

    async def main_loop(self):
        self.canvases = [
            TextScrollCanvas(Box(0, 0, self.width, self.height),
                             'Hallo Nerdberg!', self.fonts[0], +0.5),
            TextScrollCanvas(Box(80, 12, width=40, height=8),
                             'This scrolls backwards.', self.fonts[1], -0.8)
        ]

        anim = SquareAnimation(Path('pacman_20x20_right_to_left.png'))
        self.canvases[0].place_animation(100, 0, anim)

        while self.matrix_hw.running:
            self.img.paste((0x00, ), [0, 0, self.width, self.height])
            for canvas in self.canvases:
                canvas.stamp_into(self.img)
                canvas.tick()
            self.matrix_hw.update(self.img)
            if self.canvases:
                await asyncio.sleep(1.0/60)  # 60 Hz
            else:
                await asyncio.sleep(1.0)

async def mqtt_task_coro(args, matrix):
    async with asyncio_mqtt.Client(args.mqtt_host) as client:
        await client.subscribe(args.mqtt_subscribe)
        while True:
            async with client.unfiltered_messages() as messages:
                async for msg in messages:
                    info(f'MQTT message on topic {msg.topic}: {msg.payload}')
                    try:
                        obj = json.loads(msg.payload)
                        info(f'Received json object: {repr(obj)}.')
                        matrix.update_txt(obj['text'])

                    except Exception as exc:
                        err_obj = {'result': 'error', 'error': repr(exc)}
                        err_str = json.dumps(err_obj)
                        error(
                            f'Exception {repr(exc)} while handling command object.')
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

    grp.add_argument('-S','--simulation', action='store_true', help='Simulate with pyGame') 

    grp = parser.add_argument_group('Graphics')

    grp.add_argument('-f', '--font', nargs='*', type=Path, metavar='pil/bdf',
                     help='Add font file(s).')

    grp.add_argument('-a', '--animation', nargs='*', type=Path, metavar='png',
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

    if args.simulation :
        import hw_pygame
        matrix_hw = hw_pygame.HW_PyGame(loop, args.width, args.height)
    else :
        import hw_usb
        matrix_hw = hw_usb.HW_USB()

    led_matrix = LedMatrix(args.width, args.height, matrix_hw)

    if args.mqtt_host is not None:
        loop.create_task(mqtt_task_coro(args, led_matrix))

    if args.font:
        for fn in args.font:
            led_matrix.add_font(fn)

    if args.animation:
        for fn in args.animation:
            led_matrix.add_animation(fn)

    try:
        loop.run_until_complete(led_matrix.main_loop())
        # here the mqtt_task will crash, as the loop has been closed already
        # we have to fix this later
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()

