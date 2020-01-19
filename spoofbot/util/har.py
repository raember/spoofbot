"""Module to clean and anonymize HAR logs"""
import json
import os


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


if __name__ == '__main__':
    clean_all_in('test_data')
