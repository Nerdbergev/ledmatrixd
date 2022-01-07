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

import hw_pygame  # dummy hw


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

        self.img_arr = []  # store individual tiles, cropped out
        for j in range(n_phases):
            # left, top, right, bottom
            rect = [self.imgsz * j, 0, self.imgsz*(j+1), self.imgsz]
            self.img_arr.append(img.crop(rect))

    def __iter__(self):
        return ping_pong_iter(self.img_arr, True)


class LedMatrix:
    def __init__(self, width, height, matrix_hw):
        self.width = width
        self.height = height
        self.matrix_hw = matrix_hw

        self.fonts = list()
        self.animations = list()

        self.curr_img = None
        self.curr_dx = 0
        self.curr_anim = None  # (animation iterator, x_offs, y_offs)

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

    def update_txt(self, s, fontnum=0):
        fnt = self.fonts[fontnum]
        txt_width, _ = fnt.getsize(s)

        # option 1, <space> <text> <space>, makes sure that there
        # is a period where the whole matrix is empty before/after text is shown

        img_width = txt_width + 2 * self.width - 1
        img_height = self.height

        img = PIL.Image.new(mode='L', size=(img_width, img_height))
        drw = PIL.ImageDraw.Draw(img)
        drw.text((self.width, 0), s, font=fnt, fill=(0xff, ))

        self.curr_img = img
        self.curr_dx = 0

    async def main_loop(self):

        self.update_txt('Hallo Nerdberg!')

        while self.matrix_hw.running:
            if self.curr_img is None:
                await asyncio.sleep(1.0)
                continue

            await asyncio.sleep(1.0/60)  # 60 Hz

            if self.curr_anim:
                anim_iter, anim_x, anim_y = self.curr_anim
                self.curr_img.paste(next(anim_iter), (anim_x, anim_y))

            self.matrix_hw.update(self.curr_img.crop(
                (self.curr_dx, 0, self.curr_dx+self.width, self.curr_img.size[1])))

            self.curr_dx += 1
            if self.curr_dx >= self.curr_img.size[0] - self.width:
                self.curr_dx = 0


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

    matrix_hw = hw_pygame.HW_PyGame(loop, args.width, args.height)
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
