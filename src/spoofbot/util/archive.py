"""Module to clean and anonymize HAR logs"""
import json
import os
from io import BytesIO
from typing import Union, Optional, MutableMapping

from loguru import logger
from mitmproxy.http import HTTPFlow
from mitmproxy.io import read_flows_from_paths
from requests import Request, PreparedRequest, Response, Session
from requests.structures import CaseInsensitiveDict
from urllib3 import HTTPResponse
from urllib3.util import Url, parse_url

from spoofbot.util.common import dict_list_to_dict, dict_list_to_tuple_list
from spoofbot.util.file import MockHTTPResponse


def load_har(path: Union[str, os.PathLike], session: Session = None) \
        -> dict[Url, list[tuple[PreparedRequest, Response]]]:
    if session is None:
        session = Session()
        session.headers.clear()
    har: dict
    with open(path, 'r') as fp:
        har = json.load(fp)
    data = {}
    for entry in har.get('log', {}).get('entries', []):
        request: PreparedRequest = session.prepare_request(request_from_har_entry(entry))
        response: HTTPResponse = response_from_har_entry(entry)
        url = parse_url(request.url)
        requests = data.get(url, [])
        requests.append((request, response))
        data[url] = requests
    return data


def request_from_har_entry(entry: dict) -> Request:
    request_entry = entry['request']
    data = {}
    if 'postData' in request_entry:
        post_data = dict_list_to_tuple_list(request_entry['postData']['params'], case_insensitive=False)
        data = '&'.join(map('='.join, post_data))
    return Request(
        method=request_entry['method'].upper(),
        url=request_entry['url'],
        headers=CaseInsensitiveDict(dict_list_to_dict(request_entry['headers'], case_insensitive=True)),
        data=data,
        cookies=dict_list_to_dict(request_entry['cookies']),
    )


def response_from_har_entry(entry: dict) -> Optional[HTTPResponse]:
    resp = entry['response']
    if resp is None:
        return None
    headers = dict_list_to_tuple_list(resp['headers'])
    resp = HTTPResponse(
        body=BytesIO(resp['content'].get('text', '').encode('utf8')),
        headers=CaseInsensitiveDict(headers),
        status=resp['status'],
        preload_content=False,
        original_response=MockHTTPResponse(headers)
    )
    resp.CONTENT_DECODERS = []  # Hack to prevent already decoded contents to be decoded again
    return resp


def load_flows(path: Union[str, os.PathLike], session: Session = None) \
        -> dict[Url, list[tuple[PreparedRequest, Response]]]:
    if session is None:
        session = Session()
        session.headers.clear()
    data = {}
    for flow in read_flows_from_paths([path]):
        request: PreparedRequest = session.prepare_request(request_from_flow(flow))
        response: HTTPResponse = response_from_flow(flow)
        url = parse_url(request.url)
        requests = data.get(url, [])
        requests.append((request, response))
        data[url] = requests
    return data


def request_from_flow(flow: HTTPFlow) -> Request:
    req = flow.request
    headers = CaseInsensitiveDict()
    for header, value in req.headers.items():
        headers[header] = value
    cookies = {}
    for cookie, value in req.cookies.items():
        cookies[cookie] = value
    return Request(
        method=req.method.upper(),
        url=req.url,
        headers=headers,
        data=req.content,
        cookies=cookies,
    )


def response_from_flow(flow: HTTPFlow) -> Optional[HTTPResponse]:
    resp = flow.response
    if resp is None:
        return None
    headers = CaseInsensitiveDict()
    for header, value in resp.headers.items():
        headers[header] = value

    resp = HTTPResponse(
        body=BytesIO(resp.content),
        headers=headers,
        status=resp.status_code,
        preload_content=False,
        original_response=MockHTTPResponse(headers.items())
    )
    resp.CONTENT_DECODERS = []  # Hack to prevent already decoded contents to be decoded again
    return resp


def print_diff(name: str, expected: str, actual: str, indent_level: int):
    indent = ' ' * indent_level
    logger.debug(f"{indent}Request {name} does not match:")
    logger.debug(f"{indent}  {actual}")
    logger.debug(f"{indent}  does not equal expected:")
    logger.debug(f"{indent}  {expected}")


def do_keys_match(
        request_headers: CaseInsensitiveDict,
        cached_headers: CaseInsensitiveDict,
        indent_level: int
) -> bool:
    if list(map(str.lower, dict(request_headers).keys())) != list(map(str.lower, dict(cached_headers).keys())):
        print_diff(
            'data',
            f"({len(cached_headers)}) {', '.join(list(dict(cached_headers).keys()))}",
            f"({len(request_headers)}) {', '.join(list(dict(request_headers).keys()))}",
            indent_level
        )
        return False
    return True


def are_dicts_same(
        request_dict: MutableMapping,
        cached_dict: MutableMapping,
        indent_level: int,
        name: str
) -> bool:
    indent = ' ' * indent_level
    missing_keys = []
    mismatching_keys = []
    redundant_keys = []
    verdict = True
    for key in cached_dict.keys():
        if key not in request_dict:
            missing_keys.append(key)
        else:
            if request_dict[key] != cached_dict[key] and key.lower() != 'cookie':
                mismatching_keys.append(key)
    for key in request_dict.keys():
        if key not in cached_dict:
            redundant_keys.append(key)
    if len(missing_keys) > 0:
        logger.debug(f"{indent}Request {name} are missing the following entries:")
        for key in missing_keys:
            logger.debug(f"{indent}  - '{key}': '{cached_dict[key]}'")
        verdict = False
    if len(redundant_keys) > 0:
        logger.debug(f"{indent}Request {name} have the following redundant entries:")
        for key in redundant_keys:
            logger.debug(f"{indent}  + '{key}': '{request_dict[key]}'")
        verdict = False
    if len(mismatching_keys) > 0:
        logger.debug(f"{indent}Request {name} have the following mismatching entries:")
        for key in mismatching_keys:
            logger.debug(f"{indent}  · '{key}': '{request_dict[key]}'")
            logger.debug(f"{indent}    {' ' * (len(key) + 2)}  does not equal expected {name[:-1]}:")
            logger.debug(f"{indent}    {' ' * (len(key) + 2)}  '{cached_dict[key]}'")
        verdict = False
    return verdict
