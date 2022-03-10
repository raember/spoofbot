"""Utility module  for handy features to be used in conjunction with the core modules"""

from .common import TimelessRequestsCookieJar
from .common import dict_to_dict_list, url_to_query_dict_list
from .common import dict_to_tuple_list, dict_list_to_dict, dict_list_to_tuple_list, \
    dict_to_str, cookie_header_to_dict
from .common import encode_form_data, header_to_snake_case, coerce_content
from .file import load_response, to_filepath, to_url, get_symlink_path
from .har import HarFile, Har, Log, Entry, Creator, Browser, PageTimings, Page, Cache, \
    CacheStats, Timings, JsonObject
from .http import ReferrerPolicy
from .http import are_same_origin, are_same_origin_domain, are_schemelessly_same_site, \
    are_same_site
from .http import is_ip, is_domain
from .http import opaque_origin, origin_tuple, OriginTuple
from .http import sort_dict
from .versions import get_latest, get_firefox_versions, get_chrome_versions, get_versions_since, random_version
