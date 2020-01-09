# Spoofbot
Web bot for spoofing browser behaviour when using python requests.
Supports Firefox and Chrome browser on most generic Windows, MacOS and Linux spoofing.

## Example usage
```py
browser = Chrome()
cache = CacheAdapter()
browser.session.mount('https://', cache)
browser.session.mount('http://', cache)

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
Firefox indicates that brotli encoding (`br`) is acceptable, but that might lead to issue swhen parsing the responses.
It is possible to change that default header:

```py
browser = Firefox()
browser._accept_encoding = ['deflate', 'gzip']  # brotli (br) is cumbersome
``` 

## File Cache
Using `CacheAdapter`, one can store responses (without metadata such as headers) in the filesystem.
It supports deleting the last request or a specific file from the cache.
The cache indicates whether the last made request got a cache hit.
If there is a request that should be cached that cannot be adequately stored with only hostname and path, one can specify and alternative url to use instead of the request's prior to the request.
This last case is also supported when deleting the last request.

 ## Har Cache
 Using `HarAdapter`, one is able to load `.har` files to use as cache.
 This cache does not make actual http requests to the net, but fails if no matching request could be found.
 It can be specified whether matching a request should be strict (must match all headers) or not.
 