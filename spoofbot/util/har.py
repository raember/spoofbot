"""Module to clean and anonymize HAR logs"""
import json
import os
import zlib
from base64 import b64decode
from io import BytesIO

import brotli
from requests import Request
from requests.structures import CaseInsensitiveDict
from urllib3 import HTTPResponse

from .common import dict_list_to_dict, dict_list_to_tuple_list, encode_form_data
from .file import MockHTTPResponse


def clean_all_in(directory: str, backup_ext: str = '.bak'):
    for filename in os.listdir(directory):
        clean_har(os.path.join(directory, filename), backup_ext)


def clean_har(har_path: str, backup_ext: str = '.bak'):
    har_filename = os.path.basename(har_path)
    ext = os.path.splitext(har_path)[-1]
    if ext == backup_ext:
        print(f"File is a backup file: '{har_filename}'")
        return
    if ext != '.har':
        print(f"File is not a HAR file: '{har_filename}'")
        return
    backup_path = f"{har_path}{backup_ext}"
    backup_filename = os.path.basename(backup_path)
    if os.path.isfile(backup_path):
        print(f"Backup file for '{har_filename}' already exists ('{backup_filename}'). Reprocessing.")
        os.remove(har_path)
        os.rename(backup_path, har_path)

    with open(har_path, 'r', encoding='utf-8-sig') as fp:
        har = json.load(fp)
    har = anonymize_har(har)
    os.rename(har_path, backup_path)
    with open(har_path, 'w', encoding='utf-8') as fp:
        json.dump(har, fp, indent=2)
    print(f"Cleaned file: '{har_filename}' Backup: '{backup_filename}'")


def anonymize_har(har: dict) -> dict:
    log = har.get('log', {})
    return {
        'log': {
            'version': log.get('version', '1.0'),
            'creator': log.get('creator', {
                'name': 'Unnamed',
                'version': ''
            }),
            'entries': list(map(_anonymize_entry, log.get('entries', [])))
        }
    }


def _anonymize_entry(entry: dict) -> dict:
    request = entry.get('request', {})
    response = entry.get('response', {})
    data = {
        'request': {
            'method': request.get('method', ''),
            'url': request.get('url', ''),
            'httpVersion': request.get('httpVersion', ''),
            'headers': list(filter(lambda h: h is not None, map(_anonymize_header, request.get('headers', [])))),
            'queryString': request.get('queryString', []),
            'cookies': list(map(_anonymize_cookie, request.get('cookies', []))),
            'headersSize': request.get('headersSize', 0),
            'bodySize': request.get('bodySize', 0),
            'postData': request.get('postData', {}),
        },
        'response': {
            'status': response.get('status', 0),
            'statusText': response.get('statusText', ''),
            'httpVersion': response.get('httpVersion', ''),
            'headers': list(filter(lambda h: h is not None, map(_anonymize_header, response.get('headers', [])))),
            'cookies': list(map(_anonymize_cookie, response.get('cookies', []))),
            'content': response.get('content', {}),
            'redirectURL': response.get('redirectURL', ''),
            'headersSize': response.get('headersSize', 0),
            'bodySize': response.get('bodySize', 0),
        }
    }
    if 'postData' not in request:
        del data['request']['postData']
    return data


def _anonymize_header(header: dict) -> dict:
    if header['name'].startswith(':'):  # Provisional header. Thanks, Chrome
        # noinspection PyTypeChecker
        return None
    return {
        'name': header.get('name'),
        'value': header['value']
    }


def _anonymize_cookie(cookie: dict) -> dict:
    return {
        'name': cookie['name'],
        'value': cookie['value'],
        'expires': cookie.get('expires', None),
        'httpOnly': cookie.get('httpOnly', False),
        'secure': cookie.get('secure', False),
    }


def request_from_entry(entry: dict, encode: bool = False) -> Request:
    request_entry = entry['request']
    params = {}
    data = {}
    if 'postData' in request_entry:
        post_data = dict_list_to_tuple_list(request_entry['postData']['params'], case_insensitive=False)
        if encode:
            data = encode_form_data(post_data)
        else:
            data = '&'.join(map('='.join, post_data))
    return Request(
        method=request_entry['method'].upper(),
        url=request_entry['url'],
        headers=CaseInsensitiveDict(dict_list_to_dict(request_entry['headers'], case_insensitive=True)),
        files=None,
        data=data,
        json=None,
        params=params,
        auth=None,
        cookies=dict_list_to_dict(request_entry['cookies']),
        hooks=None,
    )


def response_from_entry(entry: dict) -> HTTPResponse:
    response_entry = entry['response']
    headers = dict_list_to_tuple_list(response_entry['headers'])
    headers_set = CaseInsensitiveDict(headers)
    content = response_entry['content']
    body = bytearray()
    if 'text' in content:
        data = content['text'].encode('utf8')
        if 'Content-Encoding' in headers_set:
            if headers_set['Content-Encoding'] == 'gzip':
                compressor = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
                body = compressor.compress(data) + compressor.flush()
            elif headers_set['Content-Encoding'] == 'br':
                body = brotli.compress(data)
            elif 'encoding' in content:
                raise Exception()
            else:
                body = data
        elif 'encoding' in content:
            encoding = content['encoding']
            if encoding == 'base64':
                body = b64decode(data)
            else:
                raise Exception()
        else:
            body = data

    return HTTPResponse(
        body=BytesIO(body),
        headers=headers,
        status=response_entry['status'],
        preload_content=False,
        original_response=MockHTTPResponse(headers)
    )


if __name__ == '__main__':
    clean_all_in('test_data')
