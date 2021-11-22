from loguru import logger
from requests import Response, PreparedRequest


def log_request(request: PreparedRequest):
    fg_cyan = 36
    logger.debug(f"\033[{fg_cyan}m{request.method}\033[0m {request.url}")


fg_red = 31
fg_mag = 35
rev_vd = 7
fg_grn = 32
fg_wht = 97
fg_lred = 91

STATUS_COLOR_MESSAGE = {
    500: (fg_red, 'Internal Server Error'),
    501: (fg_red, 'Not Implemented'),
    502: (fg_red, 'Bad Gateway'),
    503: (fg_red, 'Service Unavailable'),
    504: (fg_red, 'Gateway Timeout'),
    505: (fg_red, 'HTTP Version Not Supported'),
    506: (fg_mag, 'Variant Also Negotiates'),
    507: (fg_mag, 'Insufficient Storage'),  # WebDAV
    508: (fg_mag, 'Loop Detected'),  # WebDAV
    510: (fg_mag, 'Not Extended'),
    511: (fg_mag, 'Network Authentication Required'),
    400: (fg_mag, 'Bad Request'),
    401: (fg_mag, 'Unauthorized'),
    402: (fg_mag, 'Payment Required'),
    403: (fg_mag, 'Forbidden'),
    404: (fg_mag, 'Not Found'),
    405: (fg_mag, 'Method Not Allowed'),
    406: (fg_mag, 'Not Acceptable'),
    407: (fg_mag, 'Proxy Authentication Required'),
    408: (fg_mag, 'Request Timeout'),
    409: (fg_mag, 'Conflict'),
    410: (fg_mag, 'Gone'),
    411: (fg_mag, 'Length Required'),
    412: (fg_mag, 'Precondition Failed'),
    413: (fg_mag, 'Payload Too Large'),
    414: (fg_mag, 'URI Too Long'),
    415: (fg_mag, 'Unsupported Media Type'),
    416: (fg_mag, 'Range Not Satisfiable'),
    417: (fg_mag, 'Expectation Failed'),
    418: (fg_mag, "I'm a teapot"),
    421: (fg_mag, 'Misdirected Request'),
    422: (fg_mag, 'Unprocessable Entity'),  # WebDAV
    423: (fg_mag, 'Locked'),  # WebDAV
    424: (fg_mag, 'Failed Dependency'),  # WebDAV
    425: (fg_mag, 'Too Early'),
    426: (fg_mag, 'Upgrade Required'),
    428: (fg_mag, 'Precondition Required'),
    429: (fg_mag, 'Too Many Requests'),
    431: (fg_mag, 'Request Header Fields Too Large'),
    451: (fg_mag, 'Unavailable For Legal Reasons'),
    300: (rev_vd, 'Multiple Choices'),
    301: (rev_vd, 'Moved Permanently'),
    302: (rev_vd, 'Found'),
    303: (rev_vd, 'See Other'),
    304: (rev_vd, 'Not Modified'),
    305: (rev_vd, 'Use Proxy'),
    307: (rev_vd, 'Temporary Redirect'),
    308: (rev_vd, 'Permanent Redirect'),
    200: (fg_grn, 'OK'),
    201: (fg_grn, 'Created'),
    202: (fg_grn, 'Accepted'),
    203: (fg_grn, 'Non-Authoritative Information'),
    204: (fg_grn, 'No Content'),
    205: (fg_grn, 'Reset Content'),
    206: (fg_grn, 'Partial Content'),
    207: (fg_grn, 'Multi-Status'),  # WebDAV
    208: (fg_grn, 'Already Reported'),  # WebDAV
    226: (fg_grn, 'IM Used'),
    100: (fg_wht, 'Continue'),
    101: (fg_wht, 'Switching Protocols'),
    102: (fg_wht, 'Processing'),  # WebDAV
    103: (fg_wht, 'Early Hints'),
}


def log_response(response: Response):
    color, msg = STATUS_COLOR_MESSAGE.get(response.status_code, (fg_lred, 'UNKNOWN'))
    logger.debug(
        f"{' ' * len(response.request.method)} \033[{color}m← "
        f"{response.status_code} {msg}\033[0m "
        f"{response.headers.get('Content-Type', '-')}")
