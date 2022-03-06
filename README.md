# Spoofbot
Web bot for spoofing browser behaviour when using python requests.
Supports Firefox and Chrome browser on most generic Windows, MacOS and Linux spoofing.

## Example usage
```py
from spoofbot.browser import Chrome
from spoofbot.adapter import FileCache

browser = Chrome()
browser.adapter = FileCache()

browser.navigate('https://httpbin.org/')
spec = browser.get('https://httpbin.org/spec.json').json()
print(spec['info']['description'])
# A simple HTTP Request & Response Service.<br/> <br/> <b>Run locally: </b> <code>$ docker run -p 80:80 kennethreitz/httpbin</code>
headers = browser.navigate(
    'https://httpbin.org/headers',
    headers={'Accept': 'mime/type'}
)[0].json()
print(headers['headers']['Accept'])
# mime/type
```

## Browsers

`spoofbot` allows for useragents to be generate using information like the platform and browser version. Currently, only Firefox and Chrome are supported, but through inheritance one can add more browsers. The browser classes are derived from the `requests.Session` class and extend it by additional features.

### Brotli encoding

Firefox indicates that brotli encoding (`br`) is acceptable, but that might lead to issues when parsing the responses. It is possible to change that default header:

```py
from spoofbot.browser import Firefox

ff = Firefox()
ff._accept_encoding = ['deflate', 'gzip']  # brotli (br) is cumbersome
``` 

### Request timeout for lower server load

The browsers have an automatic request delay built in which can be controlled with the `request_timeout` and `honor_timeout`. After requests have been made, `did_wait` and `waiting_period` provide further information.

## Cache adapters

For more info refer to [the adapter module](src/spoofbot/adapter).

### File Cache

Using `FileCache`, one can store responses (without metadata such as headers or cookies) in the filesystem. The cache indicates whether the last made request got a cache hit. If there is a request that should be cached that cannot be adequately stored with only hostname and path, one can specify and alternative url to use instead of the request's prior to the request using the adapter's `next_request_cache_url`
property. This is also supported when deleting the last request from the cache. By using the `backup` method, the cache will backup the subsequent requests' original cached responses inside a new `Backup` object. If it is then determined that the backup should be restored, the `restore_all`/`restore` methods can be used. The backup process can be stopped explicitly with `stop_backup` or by using a `with` block on the
backup object.

### HAR Cache

Using `HarCache`, one is able to load `.har` and [MITMProxy](https://mitmproxy.org/)
flow files to use as cache. This cache does not make actual HTTP requests to the net,
but fails if no matching request could be found. It can be specified whether matching a
request should be strict (must match all headers) or not. When matching for requests,
one can toggle rules to use (such as matching headers, header order or post data) when
looking for a match using the adapter's properties.

## Example usage

Please take a look at the [tests](tests). Take note that the loggers provide helpful data when testing from matches in the cache on the `DEBUG` level.

### Tips

Turn off logging of other libraries:

```py
import logging

logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
logging.getLogger('chardet.charsetprober').setLevel(logging.INFO)
logging.getLogger('chardet.universaldetector').setLevel(logging.INFO)
```