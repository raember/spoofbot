import unittest
from time import sleep

import docker

client = docker.from_env()


class HttpBinTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        port = 8888
        cls.container = client.containers.run(
            'kennethreitz/httpbin',
            ports={'80': str(port)},
            remove=True, detach=True,
        )
        cls.port = port
        sleep(1)

    def get_httbin_url(self, path: str) -> str:
        assert path.startswith('/')
        return f"http://localhost:{self.port}{path}"

    @classmethod
    def tearDownClass(cls):
        cls.container.stop()
