#!./venv/bin/python
import argparse
import aiohttp.web as web

class HTTP_Server :
    http_server_port = 8080
    http_server_addr = '::'

    def __init__(self, args:argparse.ArgumentParser, ledmatrix) :
        if args.http_server_port :
            self.http_server_port = args.http_server_port

        if args.http_server_addr :
            self.http_server_addr = args.http_server_addr

    async def http_server_task(self) :
        app = web.Application()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.http_server_addr, self.http_server_port)
        await site.start()
