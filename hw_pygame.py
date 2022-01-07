#!./venv/bin/python
import asyncio
from logging import critical, debug, error, info, warning

import PIL.Image
import pygame


class HW_PyGame:
    def __init__(self, loop, width, height):
        self.loop = loop
        self.width, self.height = width, height
        self.running = True

        pygame.init()
        self.window = pygame.display.set_mode((3*self.width, 3*self.height))
        self.evt_consumer = loop.create_task(self._evt_consumer_coro())

    # stop the 'HW'
    def stop(self):
        self.running = False
        pygame.quit()

    async def _evt_consumer_coro(self):
        while self.running:
            event = pygame.event.poll()
            if event.type == pygame.locals.NOEVENT:
                await asyncio.sleep(0.01)
                continue
            debug(f'pygame Event {repr(event)} received.')
            if event.type == pygame.locals.QUIT:
                info('Window has been closed, exiting.')
                self.running = False
            if event.type == pygame.locals.KEYUP and event.key == pygame.locals.K_ESCAPE:
                info('ESC has been presed, exiting.')
                self.running = False

    # update pixel matrix from PIL Image
    def update(self, img):
        if img.mode != '1':
            img = img.convert('1')

        rect = pygame.Rect(0, 0, 3*self.width, 3*self.height)
        pygame.draw.rect(self.window, (0x55, 0x55, 0x55), rect)

        # this is very, very inefficient
        for x in range(min(self.width, img.size[0])):
            for y in range(min(self.height, img.size[1])):
                if img.getpixel((x, y)):
                    col = (0xff, 0xff, 0xff)
                else:
                    col = (0, 0, 0)
                rect = pygame.Rect(x*3, y*3, 3, 3)
                pygame.draw.rect(self.window, col, rect)

        pygame.display.flip()
