from spoofbot.adapter.mitmproxy import MITMProxyCache, load_mitmproxy_flows

from spoofbot import Firefox, Windows


def main():
    browser = Firefox(ff_version=(91, 0), os=Windows(x64=False))
    mitm_cache = MITMProxyCache(load_mitmproxy_flows('/home/re/mitm'))
    browser.adapter = mitm_cache
    browser.do_not_track = True
    browser.navigate('http://mitm.it/', headers={
        'Cache-Control': 'max-age=0',
    })


if __name__ == '__main__':
    main()
