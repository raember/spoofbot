# Spoofbot
Web bot for spoofing browser behaviour when using python requests.
Supports Firefox and Chrome browser on most generic Windows, MacOS and Linux spoofing.

## Example usage
```py
browser = Chrome()
cache = CacheAdapter()
browser.mount('https://', cache)
browser.mount('http://', cache)

browser.navigate('https://httpbin.org/')
spec = browser.get('https://httpbin.org/spec.json').json()
print(spec['info']['description'])
# A simple HTTP Request & Response Service.<br/> <br/> <b>Run locally: </b> <code>$ docker run -p 80:80 kennethreitz/httpbin</code>
headers = browser.navigate(
    'https://httpbin.org/headers',
    headers={'Accept': 'mime/type'}
).json()
print(headers['headers']['Accept'])
# mime/type
```

## Browsers
`spoofbot` allows for useragents to be generate using information like the platform and browser version.
Currently, only Firefox and Chrome are supported, but through inheritance one can add more browsers.
The browser classes are derived from the `requests.Session` class and extend it by additional features.

Firefox indicates that brotli encoding (`br`) is acceptable, but that might lead to issues when parsing the responses.
It is possible to change that default header:

```py
ff = Firefox()
ff._accept_encoding = ['deflate', 'gzip']  # brotli (br) is cumbersome
``` 

The browsers have an automatic request delay built in which can be controlled with the `request_timeout` and `honor_timeout`.
After requests have been made, `did_wait` and `waiting_period` provide further information.

## File Cache
Using `FileCacheAdapter`, one can store responses (without metadata such as headers or cookies) in the filesystem.
It supports deleting the last request or a specific file from the cache.
The cache indicates whether the last made request got a cache hit.
If there is a request that should be cached that cannot be adequately stored with only hostname and path, one can specify and alternative url to use instead of the request's prior to the request using the adapter's `next_request_cache_url` property.
This is also supported when deleting the last request from the cache.
By setting the `backup_and_miss_next_request` property to `True`, the cache will backup the next cached request's result and update it with a new result.
If it is later determined that the backup should be restored, the `restore_backup()` method can be used.

 ## Har Cache
 Using `HarAdapter`, one is able to load `.har` files to use as cache.
 This cache does not make actual http requests to the net, but fails if no matching request could be found.
 It can be specified whether matching a request should be strict (must match all headers) or not.
 To clean, partly anonymize and standardize `.har` files, the `spoofbot.util.har` module provides `clean_har` and `clean_all_in` methods.
 When matching for requests, one can toggle rules to use (such as matching headers, header order or post data) when looking for a match using the adapter's properties.

## Example usage
Please take a look at the [tests](./tests).
Take note that the loggers provide helpful data when testing fro matches in the cache on the `DEBUG` level.

### Tips
Turn off logging of other libraries:
```py
logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
logging.getLogger('chardet.charsetprober').setLevel(logging.INFO)
logging.getLogger('chardet.universaldetector').setLevel(logging.INFO)
```