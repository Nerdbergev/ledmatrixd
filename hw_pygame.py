#!/usr/bin/python
import asyncio
from logging import critical, debug, error, info, warning

import PIL.Image
import pygame

# inspired by
# https://github.com/AlexElvers/pygame-with-asyncio/blob/master/main.py


class HW_PyGame:
    def __init__(self, loop, width, height):
        self.loop = loop
        self.width, self.height = width, height
        self.running = True

        # we'll get pygame events out of this queue
        self.event_queue = asyncio.Queue()

        pygame.init()
        self.window = pygame.display.set_mode((3*self.width, 3*self.height))
        self.pygame_thread = loop.run_in_executor(
            None, self._pygame_thread_fct)

        # events will be consumed by this task
        self.evt_consumer = loop.create_task(self._evt_consumer_coro())

    # stop the 'HW'
    def stop(self):
        self.pygame_thread.cancel()
        pygame.quit()  # this segfaults ;-)

    # this runs in a seperate thread
    def _pygame_thread_fct(self):
        while True:
            event = pygame.event.wait()
            asyncio.run_coroutine_threadsafe(
                self.event_queue.put(event), loop=self.loop)

    # this runs within the asyncio framework
    async def _evt_consumer_coro(self):
        while True:
            event = await self.event_queue.get()
            if event.type == pygame.locals.QUIT:
                info('Window has been closed, exiting.')
                self.running = False
                break
            if event.type == pygame.locals.KEYUP and event.key == pygame.locals.K_ESCAPE:
                info('ESC has been presed, exiting.')
                self.running = False
                break

    # update pixel matrix from PIL Image
    def update(self, img):
        if img.mode != '1':
            img = img.convert('1')

        rect = pygame.Rect(0, 0, 3*self.width, 3*self.height)
        pygame.draw.rect(self.window, (0x55, 0x55, 0x55), rect)

        for x in range(min(self.width, img.size[0])):
            for y in range(min(self.height, img.size[1])):
                if img.getpixel((x, y)):
                    col = (0xff, 0xff, 0xff)
                else:
                    col = (0, 0, 0)
                rect = pygame.Rect(x*3, y*3, 3, 3)
                pygame.draw.rect(self.window, col, rect)

        pygame.display.flip()
