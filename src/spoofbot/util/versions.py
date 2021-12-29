import json
from datetime import datetime, timezone, timedelta
from itertools import islice
from random import choices

from dateutil.parser import parse
from pathlib import Path

import requests
from loguru import logger
from numpy.random import choice


def _get_cache(browser: str, update_after: timedelta) -> Path:
    p = Path('.spoofbot', browser)
    p.mkdir(parents=True, exist_ok=True)
    now = datetime.now(tz=timezone.utc)
    fs = list(p.glob('*.json'))
    if len(fs) == 0:
        logger.info(f"No cached version list for {browser} available. Downloading newest list.")
        return p / f"{int(now.timestamp())}.json"
    f = fs[0]
    timestamp = float(f.with_suffix('').name)
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    if now - date > update_after:
        logger.info(f"Cached version list for {browser} is outdated. Download new one.")
        f.unlink()
        return p / f"{int(now.timestamp())}.json"
    return f


def get_latest(versions: dict[datetime, tuple[int, ...]]) -> tuple[int, ...]:
    return versions[list(versions.keys())[0]]


def get_firefox_versions(update_after: timedelta = timedelta(days=1)) -> dict[datetime, tuple[int, int]]:
    cache = _get_cache('firefox', update_after)
    versions = {}
    if cache.exists():
        with open(cache, 'r') as fp:
            for date_str, ver in json.load(fp).items():
                versions[parse(date_str)] = tuple(map(int, ver))
    else:
        data = requests.get('https://product-details.mozilla.org/1.0/firefox.json').json()
        for _, value in sorted(data.get('releases', {}).items(), key=lambda kvp: parse(kvp[1]['date']), reverse=True):
            ver = value['version']
            if value['category'] in ['major', 'stability']:
                versions[parse(value['date'])] = tuple(map(int, ver.split('.')))
        with open(cache, 'w') as fp:
            json.dump({str(k): v for (k, v) in versions.items()}, fp)
    return versions


def get_chrome_versions(update_after: timedelta = timedelta(days=1)) -> dict[datetime, tuple[int, int]]:
    cache = _get_cache('chrome', update_after)
    versions = {}
    if cache.exists():
        with open(cache, 'r') as fp:
            for date_str, ver in json.load(fp).items():
                versions[parse(date_str)] = tuple(map(int, ver))
    else:
        data = requests.get('https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions/all/releases').json()
        for value in sorted(data.get('releases', []), key=lambda v: parse(v['serving']['startTime']), reverse=True):
            versions[parse(value['serving']['startTime'])] = tuple(map(int, value['version'].split('.')))
        with open(cache, 'w') as fp:
            json.dump({str(k): v for (k, v) in versions.items()}, fp)
    return versions


def get_versions_since(
        versions: dict[datetime, tuple[int, int]],
        date: datetime = datetime.now(tz=timezone.utc) - timedelta(days=180)
) -> dict[datetime, tuple[int, int]]:
    return {k: v for (k, v) in versions.items() if k > date}


def random_version(versions: dict[datetime, tuple[int, ...]]) -> tuple[int, ...]:
    candidates = list(islice(list(versions.values()), 9))
    candidates = list(map(lambda tpl: '-'.join(map(str, tpl)), candidates))
    return tuple(map(int, choice(candidates, p=[
        0.3, 0.2, 0.1, 0.1, 0.1, 0.05, 0.05, 0.05, 0.05
    ]).split('-')))
