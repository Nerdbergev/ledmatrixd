#!./venv/bin/python
import asyncio
import gzip
from logging import critical, debug, error, info, warning
from pathlib import Path
from tempfile import NamedTemporaryFile

import PIL.BdfFontFile
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import PIL.PcfFontFile
import datetime

# this maxes arithmetic around the 4 tuples used for regions (boxes in PIL parlance)
# a little easier

class Box:
    def __init__(self, left, top, right=None, bottom=None, size=None, width=None, height=None):
        self.left = left
        self.top = top

        if size is not None:
            width, height = size

        if right is None:
            self.right = width + left
        else:
            self.right = right

        if bottom is None:
            self.bottom = height + top
        else:
            self.bottom = bottom

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
    def size(self):
        return self.img_arr[0].size

    @property
    def width(self):
        return self.img_arr[0].size[0]

    @property
    def height(self):
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

    def __init__(self, box: Box, text: str, font: PIL.ImageFont.ImageFont, dx=1.0, transparent=False):
        self.box = box
        self.update_txt(text, font, dx)
        self.x_offs = 0.0
        self.dx = dx
        self.transparent = transparent

        self.anim_box = None
        self.anim_iter = None

        info(f'New TextScrollCanvas at {self.box}: {text}')

    def place_animation(self, x, y, anim):
        self.anim_box = Box(x, y, size=anim.size)
        self.anim_iter = iter(anim)

    def remove_animation(self):
        self.anim_box = None
        self.anim_iter = None

    def update_txt(self, s, fnt:PIL.ImageFont.ImageFont, dx):
        bbox = fnt.getbbox(s) # left, top, right, bottom
        txt_width = bbox[2]- bbox[0]

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

        if self.transparent:
            mask = crop_img
        else:
            mask = None

        dst.paste(crop_img, self.box.topleft, mask)

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
        td_1min = datetime.timedelta(minutes=1)
        ts_now = datetime.datetime.now().astimezone()
        ts_next = None

        self.canvases = [
            TextScrollCanvas(Box(0, 0, self.width, self.height),
                             'Hallo Nerdberg!', self.fonts[0], +0.5),
            None  # will be replaced by a clock
        ]

        anim = SquareAnimation(Path('pacman_20x20_right_to_left.png'))
        self.canvases[0].place_animation(100, 0, anim)

        while self.matrix_hw.running:

            ts_now = datetime.datetime.now().astimezone()
            if ts_next is None or ts_now > ts_next:
                ts_next = ts_now.replace(microsecond=0, second=0) + td_1min
                time_str = ts_now.strftime('%B, %d %Y, %H:%M')
                self.canvases[1] = TextScrollCanvas(Box(80, 12, width=40, height=9),
                                                    time_str, self.fonts[1], 0.2, True)

            self.img.paste((0x00, ), [0, 0, self.width, self.height])

            for canvas in self.canvases:
                canvas.stamp_into(self.img)
                canvas.tick()

            self.matrix_hw.update(self.img)
            if self.canvases:
                await asyncio.sleep(1.0/60)  # 60 Hz
            else:
                await asyncio.sleep(1.0)

