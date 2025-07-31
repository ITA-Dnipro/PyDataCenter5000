import urllib

import urlparse


def add_query_params(url, params):
    """
    Add query parameters to a URL.

    This function takes an existing URL and a dictionary of parameters,
    then adds or updates the query parameters in the URL. If parameters
    already exist in the URL, they will be updated with the new values.

    Args:
        url (str): The base URL to add parameters to
        params (dict): Dictionary of query parameters to add/update

    Returns:
        str: The URL with the query parameters added/updated

    Example:
        >>> add_query_params('http://example.com', {'key': 'value'})
        'http://example.com?key=value'
        >>> add_query_params('http://example.com?existing=1', {'new': '2'})
        'http://example.com?existing=1&new=2'
    """
    url_parts = list(urlparse.urlparse(url))
    query = dict(urlparse.parse_qsl(url_parts[4]))
    query.update(params)
    url_parts[4] = urllib.urlencode(query)
    return urlparse.urlunparse(url_parts)
