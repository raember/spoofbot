"""Utility module  for handy features to be used in conjunction with the core modules"""

from .common import TimelessRequestsCookieJar
from .common import dict_list_to_dict, dict_to_tuple_list, dict_list_to_tuple_list, cookie_header_to_dict, dict_to_str
from .common import encode_form_data
from .har import anonymize_har, clean_all_in, clean_har, request_from_entry, response_from_entry
from .http import ReferrerPolicy
from .http import are_same_origin, are_same_origin_domain, are_schemelessly_same_site, are_same_site
from .http import is_ip, is_domain
from .http import opaque_origin, tuple_origin
from .http import sort_dict
