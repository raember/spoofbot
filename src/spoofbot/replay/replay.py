import asyncio
import re
import socket
import ssl
from asyncio.streams import StreamReader, StreamWriter
from contextlib import closing
from pathlib import Path
from typing import Tuple, Optional

from aiohttp import web
from aiohttp.web_request import Request as AIORequest
from aiohttp.web_response import Response as AIOResponse, StreamResponse
from loguru import logger
from requests import PreparedRequest, Session, Request, Response
from urllib3.util import Url, parse_url

from spoofbot.adapter import CacheAdapter, HarCache
from spoofbot.util.log import log_request, log_response

StreamPair = Tuple[StreamReader, StreamWriter]


class RawHTTPParser:
    pattern = re.compile(
        br'(?P<method>[a-zA-Z]+) (?P<uri>(\w+://)?(?P<host>[^\s\'\"<>\[\]{}|/:]+)(:(?P<port>\d+))?[^\s\'\"<>\[\]{}|]*) ')
    uri: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    method: Optional[str] = None
    is_parse_error: bool = False

    def __init__(self, raw: bytes):
        rex = self.pattern.match(raw)
        if rex:
            to_int = RawHTTPParser.to_int
            to_str = RawHTTPParser.to_str

            self.uri = to_str(rex.group('uri'))
            self.host = to_str(rex.group('host'))
            self.method = to_str(rex.group('method'))
            self.port = to_int(rex.group('port'))
        else:
            self.is_parse_error = True

    @staticmethod
    def to_str(item: Optional[bytes]) -> Optional[str]:
        if item:
            return item.decode('charmap')

    @staticmethod
    def to_int(item: Optional[bytes]) -> Optional[int]:
        if item:
            return int(item)

    def __str__(self):
        return str(
            dict(URI=self.uri, HOST=self.host, PORT=self.port, METHOD=self.method))


class ProxyServer:
    _port: int
    _sock: socket.socket
    _server_sock: socket.socket
    _buffer_size: int
    _server_port: int

    def __init__(
            self,
            port: int = 8000,
            buffer_size: int = 4096,
            server_port: int = 8001
    ):
        self._port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.setblocking(False)
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_port = server_port
        self._server_sock.connect(('127.0.0.1', self._server_port))
        self._buffer_size = buffer_size

    @property
    def port(self) -> int:
        return self._port

    @property
    def buffer_size(self) -> int:
        return self._buffer_size

    @property
    def server_port(self) -> int:
        return self._server_port

    async def main_handler(self, reader: StreamReader, writer: StreamWriter):
        async def session():
            with closing(writer):
                host, port = writer.get_extra_info('peername')
                data = await reader.readuntil(b'\r\n\r\n')
                target, http_version, headers = self._parse_connect_request(data)
                logger.info(
                    f"Client {host}:{port} requested forwarding to {target.url} "
                    f"({http_version})")
                for header in data.strip(b'\r\n').decode().splitlines()[1:]:
                    logger.debug(f"  {header}")
                request = RawHTTPParser(data)
                if request.is_parse_error:
                    logger.error('Parse Error')
                elif request.method == 'CONNECT':  # https
                    await self.https_handler(reader, writer, request)
                else:
                    logger.error(f'{request.method} method is not supported')

        asyncio.create_task(session())

    async def serve_proxy(self):
        server = await asyncio.start_server(
            self.main_handler, '127.0.0.1', self._port
        )
        logger.info(f"Starting proxy on port {self._port}")
        async with server:
            await server.serve_forever()

    async def https_handler(
            self,
            reader: StreamReader,
            writer: StreamWriter,
            request: RawHTTPParser
    ):
        remote_reader, remote_writer = await asyncio.open_connection(
            'localhost',
            self._server_port
        )
        with closing(remote_writer):
            writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            await writer.drain()
            await self.relay_stream((reader, writer), (remote_reader, remote_writer))

    async def relay_stream(self, local_stream: StreamPair, remote_stream: StreamPair):
        local_reader, local_writer = local_stream
        remote_reader, remote_writer = remote_stream
        close_event = asyncio.Event()
        await asyncio.gather(
            self.forward_stream(local_reader, remote_writer, close_event),
            self.forward_stream(remote_reader, local_writer, close_event)
        )

    async def forward_stream(self, reader: StreamReader, writer: StreamWriter,
                             event: asyncio.Event):
        while not event.is_set():
            try:
                data = await asyncio.wait_for(reader.read(self._buffer_size), 1)
            except asyncio.TimeoutError:
                continue
            if data == b'':  # when it closed
                event.set()
                break
            writer.write(data)
            await writer.drain()

    def _parse_connect_request(self, req: bytes) -> tuple[Url, str, str]:
        head, data = req.decode().strip().split('\r\n', 1)
        head_data = head.split(' ')
        assert len(head_data) == 3
        assert head_data[0] == 'CONNECT'
        return parse_url(head_data[1]), head_data[2], data


class ReplayApplication(web.Application):
    _cache: CacheAdapter

    def __init__(self, cache: CacheAdapter):
        super(ReplayApplication, self).__init__()
        cache.is_active = True
        cache.is_offline = True
        if isinstance(cache, HarCache):
            cache.match_headers = False
            cache.match_header_order = False
            cache.match_data = False
        self._cache = cache

    async def _handle(self, request: AIORequest) -> StreamResponse:
        preq = self._aiohttp_req_to_prep_req(request)
        log_request(preq)
        try:
            resp = self._cache.send(preq)
            log_response(resp)
            return self._response_to_stream_resp(resp)
        except ValueError as e:
            return AIOResponse(
                status=404,
                reason="NOT FOUND",
                text=str(e),
            )

    def _aiohttp_req_to_prep_req(self, aiohttp_req: AIORequest) -> PreparedRequest:
        return Session().prepare_request(Request(
            method=aiohttp_req.method,
            url=str(aiohttp_req.url),
            headers=aiohttp_req.headers,
            files=None,
            data=aiohttp_req.content,
            params=None,
            auth=None,
            cookies=aiohttp_req.cookies,
            hooks=None,
            json=None
        ))

    def _response_to_stream_resp(self, response: Response) -> StreamResponse:
        headers = response.headers
        if 'Content-Encoding' in headers:
            del headers['Content-Encoding']
        resp = AIOResponse(
            body=response.content,
            status=response.status_code,
            reason=response.reason,
            headers=headers,
        )
        resp._body_length = len(response.content)
        resp._chunked = response.headers.get('Transfer-Encoding', '') == 'chunked'
        return resp


def get_server_ssl_ctx() -> ssl.SSLContext:
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ssl_ctx.load_cert_chain(
        certfile=Path(__file__).with_name('cert.crt'),
        keyfile=Path(__file__).with_name('private.key'),
    )
    return ssl_ctx
