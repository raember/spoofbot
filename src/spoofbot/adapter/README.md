# FileCache

The FileCache provides a `requests.Session`-compatible adapter that uses the filesystem as a cache for requests. It works by mapping incoming requests into appropriate file paths which will save the received response to the request, to be loaded and returned on subsequent requests.

## Modes of operation

The FileCache supports `active`, `passive` and `offline` mode. These modes are not all mutually exclusive and can be combined.

### Active mode (default: enabled)

This mode enables the adapter to search the cache for cached responses. If the cache request is a hit, it will be loaded and returned immediately without sending out an HTTP request to the remote server.

### Passive mode (default: enabled)

This mode enables the cache to save received responses from remote servers. The FileCache will override any matching cache entries for the request.

### Offline mode (default: disabled)

If enabled, this mode will prevent any outgoing HTTP requests from being sent to the remote servers and will instead raise an exception. This mode is at odds with a disabled active mode, as the latter would send the request regardless of whether the cache request would have been a hit or a miss.

---

# ArchiveCache

The ArchiveCache provides a `requests.Session`-compatible adapter that caches requests and their corresponding responses loaded from:

* `.har` (`load_har`) archives obtained from web browsers via the network tab of the dev-tools.
* or [MITMProxy](https://mitmproxy.org/) flow files (`load_flows`) from a MITMProxy session.

This allows for a relatively precise request modelling, as all the request parameters are stored. Incoming requests will be compared to the loaded ones to find the right match. The ArchiveCache main use-case is for making unittests. Hit requests will get deleted from memory alongside their response unless configured otherwise (`delete_after_matching`).

## Matching controls

The ArchiveCache allows controlling of how precise the requests must match the stored requests, which can come in handy when some conditions cannot be recreated consistently.

### Match header order (default: enabled)

The order of the headers will be taken into account when scanning for the right request. Due to some underlying mechanisms in the `requests` module, the header order will get altered post adapter processing. This is probably the most sensible condition to turn off for the aforementioned reason.

### Match headers (default: enabled)

All headers must match the stored request's headers.

### Match data (default: enabled)

The body of the requests (for `POST` requests) must match the body of the stored requests exactly.
