#!./venv/bin/python
import argparse
import aiohttp.web as web

import PIL.Image
import io

class HTTP_Server:
    http_server_port = 8080
    http_server_addr = '::'

    def __init__(self, args: argparse.ArgumentParser, ledmatrix):
        if args.http_server_port:
            self.http_server_port = args.http_server_port

        if args.http_server_addr:
            self.http_server_addr = args.http_server_addr

        self.ledmatrix = ledmatrix

    async def handle_live_view(self, req: web.Request):
        png = io.BytesIO()
        self.ledmatrix.img.save(png, format='PNG')
        return web.Response(body=png.getvalue(), content_type='image/png')

    async def handle_root(self, req: web.Request) :
        return web.FileResponse('assets/index.html')

    async def http_server_task(self):
        app = web.Application()
        app.router.add_get('/', self.handle_root)
        app.router.add_get('/live_view.png', self.handle_live_view)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.http_server_addr,
                           self.http_server_port)
        await site.start()
