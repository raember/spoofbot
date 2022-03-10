from typing import MutableMapping

from loguru import logger
from requests.structures import CaseInsensitiveDict


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
    if list(map(str.lower, dict(request_headers).keys())) != list(
            map(str.lower, dict(cached_headers).keys())):
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
            logger.debug(f"{indent}    {' ' * (len(key) + 2)}  does not equal expected "
                         f"{name[:-1]}:")
            logger.debug(f"{indent}    {' ' * (len(key) + 2)}  '{cached_dict[key]}'")
        verdict = False
    return verdict
