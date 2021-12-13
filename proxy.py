import asyncio

from spoofbot.replay.replay import ProxyServer

asyncio.run(ProxyServer(server_port=8080).serve_proxy())
# asyncio.run(ProxyServer(server_port=8080).forward())
