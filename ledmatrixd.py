#!./venv/bin/python
import asyncio
import json
import logging
from argparse import ArgumentParser
from logging import critical, debug, error, info, warning
from pathlib import Path

import asyncio_mqtt
from http_server import HTTP_Server

from ledmatrix import Box, SquareAnimation, Canvas, TextScrollCanvas, LedMatrix

# this maxes arithmetic around the 4 tuples used for regions (boxes in PIL parlance)
# a little easier


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

                        if obj['command'] == 'write':
                            canvas = TextScrollCanvas(
                                Box(0, 0, size=matrix.size), obj['text'], matrix.fonts[0])
                            matrix.canvases[0] = canvas

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

    grp.add_argument('-S', '--simulation', action='store_true',
                     help='Simulate with pyGame')

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

    grp = parser.add_argument_group('HTTP Server', 'Option for the HTTP server.')
    grp.add_argument('-t', '--http-server-port', type=int,
                           help='TCP port the HTTP server listens to.')
    grp.add_argument('-A', '--http-server-addr', type=str, default='::',
                           help='IP address the HTTP server listens to [def:%(default)s]')

    args = parser.parse_args()

    log_lvl = logging.INFO
    if args.verbose:
        log_lvl = logging.DEBUG
    if args.quiet:
        log_lvl = logging.WARNING

    logging.basicConfig(level=log_lvl, format='%(asctime)s %(message)s')

    loop = asyncio.new_event_loop()

    if args.simulation:
        import hw_pygame
        matrix_hw = hw_pygame.HW_PyGame(loop, args.width, args.height)
    else:
        import hw_usb
        matrix_hw = hw_usb.HW_USB()

    led_matrix = LedMatrix(args.width, args.height, matrix_hw)

    if args.mqtt_host is not None:
        loop.create_task(mqtt_task_coro(args, led_matrix))

    if args.http_server_port :
        http_server = HTTP_Server(args, led_matrix)
        loop.create_task(http_server.http_server_task())

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
