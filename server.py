import asyncio

from aiohttp import web

from spoofbot.adapter import HarCache
from spoofbot.replay import ReplayApplication, get_server_ssl_ctx


async def start_server():
    with HarCache('test.har', mode='r') as cache:
        app = ReplayApplication(cache)
        runner = web.AppRunner(app)
        await runner.setup()
        ssl_ctx = get_server_ssl_ctx()
        site = web.TCPSite(runner, 'localhost', 8080, ssl_context=ssl_ctx)
        await site.start()

        while True:
            print("Waiting...")
            await asyncio.sleep(3600)


asyncio.run(start_server())

exit()
app = web.Application()
web.run_app(app, host='127.0.0.1', port=8001)
