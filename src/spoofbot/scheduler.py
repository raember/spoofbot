from abc import ABC
from datetime import datetime, timedelta
from time import sleep

from loguru import logger


class RequestScheduler(ABC):
    _last_request_timestamp: datetime
    _did_wait: bool

    def __init__(self):
        self._did_wait = False
        self._last_request_timestamp = datetime(1, 1, 1)

    @property
    def did_wait(self) -> bool:
        return self._did_wait

    def wait(self, **kwargs):
        raise NotImplementedError('Must be overwritten')

    def reset_timeout(self, timestamp: datetime = datetime.now()):
        self._last_request_timestamp = timestamp


class NormalRequestScheduler(RequestScheduler):
    _request_timeout: timedelta

    def __init__(self, seconds: float = 1.0):
        super().__init__()
        self._request_timeout = timedelta(seconds=seconds)

    @property
    def request_timeout(self) -> timedelta:
        return self._request_timeout

    @request_timeout.setter
    def request_timeout(self, value: timedelta):
        self._request_timeout = value

    def wait(self, **kwargs):
        if kwargs.get('ignore', False):
            logger.debug("Request will be a hit in cache. No need to wait.")
            self._did_wait = False
            return
        time_passed = datetime.now() - self._last_request_timestamp
        if time_passed >= self._request_timeout:
            logger.debug("Timeout already passed")
            self._did_wait = False
            return
        time_to_wait = self._request_timeout - time_passed
        logger.debug(f"Waiting for {time_to_wait.total_seconds()} seconds.")
        sleep(time_to_wait.total_seconds())
        self._did_wait = True
