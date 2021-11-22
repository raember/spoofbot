import os
from datetime import datetime, timedelta
from typing import Optional, Union

from loguru import logger
from requests import Response, PreparedRequest, Session

from spoofbot.adapter.cache import CacheAdapter
from spoofbot.util import HarFile, cookie_header_to_dict, Entry, Timings, Har, Browser
from spoofbot.util.archive import do_keys_match, are_dicts_same, print_diff


class HarAdapter(CacheAdapter):
    _har_file: HarFile
    _har: Har
    _mode: str
    _match_headers: bool
    _match_header_order: bool
    _match_data: bool
    _entry_idx: int
    _started_timestamp: datetime
    _expect_new_entry: bool

    def __init__(
            self,
            cache_path: Union[str, os.PathLike],
            is_active: bool = True,
            is_offline: bool = False,
            is_passive: bool = True,
            delete_after_hit: bool = False,
            mode: str = 'r+',
            match_headers: bool = True,
            match_header_order: bool = False,
            match_data: bool = True
    ):
        super(HarAdapter, self).__init__(
            cache_path=cache_path,
            is_active=is_active,
            is_offline=is_offline,
            is_passive=is_passive,
            delete_after_hit=delete_after_hit,
        )
        self._mode = mode
        self._match_headers = match_headers
        self._match_header_order = match_header_order
        self._match_data = match_data
        self._entry_idx = -1
        self._expect_new_entry = False

    @property
    def har_file(self) -> HarFile:
        return self._har_file

    @property
    def har(self) -> Har:
        return self._har

    def __enter__(self):
        self._har_file = HarFile(self._cache_path, self, self._mode).__enter__()
        self._har = self._har_file.har
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._har_file.__exit__(exc_type, exc_val, exc_tb)

    def close(self):
        self.__exit__(None, None, None)

    def _pre_send(self, request: PreparedRequest):
        self._started_timestamp = datetime.now().astimezone()

    def _post_send(self, response: Response):
        conn = getattr(response.raw, '_connection')
        if conn is not None and not getattr(conn.sock, '_closed'):
            conn.sock.close()
            setattr(response.raw, '_connection', None)

    def prepare_session(self, session: Session):
        super(HarAdapter, self).prepare_session(session)
        from spoofbot import Browser as SBBrowser
        if isinstance(session, SBBrowser):
            self._har.log.browser = Browser(
                name=session.name,
                version=session.version,
                comment="Created with Spoofbot"
            )

        # noinspection PyUnusedLocal
        def resp_hook(response: Response, **kwargs):
            # Only update the time if it was a new entry added to the list
            if not self._expect_new_entry:
                return response
            self._expect_new_entry = False

            last_entry = self._har.log.entries[-1]
            if last_entry.response != response:
                raise Exception("Hook got called on the wrong response")
            last_entry.time = response.elapsed
            last_entry.timings.wait = response.elapsed
            return response

        # noinspection PyTypeChecker
        session.hooks['response'] = resp_hook

    def _send(self, request: PreparedRequest, stream=False, timeout=None, verify=True,
              cert=None,
              proxies=None) -> Response:
        stream = True  # to keep the socket as to be able to get peer ip and port
        return super(CacheAdapter, self).send(request, stream, timeout, verify, cert,
                                              proxies)

    def find_response(self, request: PreparedRequest) -> Optional[Response]:
        for idx, entry in enumerate(self._har.log.entries):
            if self._match_requests(request, entry.request):
                self._entry_idx = idx
                return entry.response

    def _match_requests(self, request: PreparedRequest,
                        cached_request: PreparedRequest) -> bool:
        indent_level = len(request.method)
        indent = ' ' * indent_level
        if cached_request.method == request.method and \
                cached_request.url == request.url:
            success = True
            if self._match_header_order:
                success &= do_keys_match(request.headers, cached_request.headers,
                                         indent_level)
            if self._match_headers:
                success &= are_dicts_same(request.headers, cached_request.headers,
                                          indent_level, 'headers')
                if 'Cookie' in cached_request.headers or 'Cookie' in request.headers:
                    request_cookies = cookie_header_to_dict(
                        request.headers.get('Cookie', ''))
                    cached_cookies = cookie_header_to_dict(
                        cached_request.headers.get('Cookie', ''))
                    success &= are_dicts_same(request_cookies, cached_cookies,
                                              indent_level + 2, 'cookies')
            if self._match_data and cached_request.body and \
                    cached_request.body != request.body:
                success = False
                print_diff('data', cached_request.body, request.body, indent_level)
            if not success:
                logger.debug(
                    indent + '=' * 16)  # To easily distinguish multiple tested requests
            return success
        return False

    def _raise_for_offline(self, request: PreparedRequest):
        logger.error(
            f"{self._indent}Failed to find request in cache while in offline mode")
        raise ValueError(
            f"Could not find cached request for [{request.method}] {request.url}")

    def _store_response(self, response: Response):
        ip, port = None, None
        conn = getattr(response.raw, '_connection')
        if conn is not None and not getattr(conn.sock, '_closed'):
            ip, port = conn.sock.getpeername()
            port = str(port)
            conn.sock.close()
            setattr(response.raw, '_connection', None)
        self._har.log.entries.append(Entry(
            started_datetime=self._started_timestamp,
            time=response.elapsed,
            request=response.request,
            response=response,
            cache={},
            timings=Timings(
                send=timedelta(0),
                wait=response.elapsed,
                receive=timedelta(0)
            ),
            page_ref=self._har.log.pages[
                -1].id if self._har.log.pages is not None and len(
                self._har.log.pages) > 0 else None,
            server_ip_address=ip,
            connection=port,
            comment=None
        ))
        self._expect_new_entry = True

    def _delete(self, response: Response):
        if self._entry_idx < 0:
            logger.warning(
                f"{self._indent}  Failed to delete response {response} from cache: "
                "No index set.")
        else:
            del self._har.log.entries[self._entry_idx]
            self._entry_idx = -1
