from aiohttp import web

from spoofbot import Firefox, Windows
from spoofbot.adapter import MitmProxyCache
from spoofbot.adapter.har import HarCache
from spoofbot.util import load_flows


def main():
    browser = Firefox(ff_version=(91, 0), os=Windows(x64=False))
    # with HarCache('test_data/chrome_full.har') as har_adapter:
    #     with open('test.har', 'w') as fp:
    #         har_adapter.har_file.save(fp, indent='  ')
    # exit(0)

    with HarCache('test.har', mode='r+') as har_adapter:
        har_adapter.prepare_session(browser)
        try:
            browser.navigate('http://wuxiaworld.com')
        finally:
            har_adapter.har_file.save()
    exit()

    browser = Firefox(ff_version=(91, 0), os=Windows(x64=False))
    mitm_cache = MitmProxyCache(load_flows('mitm.flows'))
    browser.adapter = mitm_cache
    browser.do_not_track = True
    browser.navigate('http://mitm.it/', headers={
        'Cache-Control': 'max-age=0',
    })


async def start_server():
    app = web.Application()
    setattr(app, '_handle', _handle)
    setattr(app, '_make_request', _make_request)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 8001)
    await site.start()
    print("Started")


if __name__ == '__main__':
    # loop = asyncio.get_event_loop()
    # tasks = []
    # with HarCache('test.har', mode='r+') as har_adapter:
    #     # coroutine = loop.create_server(lambda: http.Http,
    #     #                                bindaddr,
    #     #                                port)
    #     # server = loop.run_until_complete(coroutine)
    #     asyncio.run(start_server())
    #     # ReplayHTTPServer(har_adapter)
    #     print('yep')
    #     asyncio.run(ProxyServer().serve())
    #     # tasks.append(loop.create_task(
    #     #     asyncio.run(ProxyServer().serve())
    #     # ))
    #     asyncio.gather(*tasks)
    # exit()
    main()
