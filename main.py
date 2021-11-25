from spoofbot import Firefox, Windows
from spoofbot.adapter import ArchiveCache
from spoofbot.adapter.har import HarCache
from spoofbot.util import load_flows


def main():
    browser = Firefox(ff_version=(91, 0), os=Windows(x64=False))
    with HarCache('test.har', mode='r+') as har_adapter:
        har_adapter.prepare_session(browser)
        try:
            browser.navigate('http://wuxiaworld.com')
        finally:
            har_adapter.har_file.save()
    exit()

    browser = Firefox(ff_version=(91, 0), os=Windows(x64=False))
    mitm_cache = ArchiveCache(load_flows('mitm.flows'))
    browser.adapter = mitm_cache
    browser.do_not_track = True
    browser.navigate('http://mitm.it/', headers={
        'Cache-Control': 'max-age=0',
    })


if __name__ == '__main__':
    main()
