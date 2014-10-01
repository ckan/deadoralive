#!/usr/bin/env python2.7
"""A script that checks client sites for dead links.

Gets lists of links to be checked from a client site, checks the links to see
if they're working or broken, and posts the results back to the client site.

The client site must implement the deadoralive API as documented in
README.markdown. For example, a CKAN site with the ckanext-deadoralive extension
installed will do.

"""
import sys
import argparse
import logging
import socket

import requests
import requests.exceptions


class CouldNotGetResourceIDsError(Exception):
    """Raised if getting the resource IDs to check fails."""
    pass


def get_resources_to_check(client_site_url, apikey):
    """Return a list of resource IDs to check for broken links.

    Calls the client site's API to get a list of resource IDs.

    :raises CouldNotGetResourceIDsError: if getting the resource IDs fails
        for any reason

    """
    url = client_site_url + "deadoralive/get_resources_to_check"
    response = requests.get(url, headers=dict(Authorization=apikey))
    if not response.ok:
        raise CouldNotGetResourceIDsError(
            "Couldn't get resource IDs to check: {code} {reason}".format(
                code=response.status_code, reason=response.reason))
    return response.json()


class CouldNotGetURLError(Exception):
    """Raised if getting the URL for a given ID from the client site fails."""
    pass


def get_url_for_id(client_site_url, apikey, resource_id):
    """Return the URL for the given resource ID.

    Contacts the client site's API to get the URL for the ID and returns it.

    :raises CouldNotGetURLError: if getting the URL fails for any reason

    """
    # TODO: Handle invalid responses from the client site.
    url = client_site_url + "deadoralive/get_url_for_resource_id"
    params = {"resource_id": resource_id}
    response = requests.get(url, headers=dict(Authorization=apikey),
                            params=params)
    if not response.ok:
        raise CouldNotGetURLError(
            "Couldn't get URL for resource {id}: {code} {reason}".format(
                id=resource_id, code=response.status_code,
                reason=response.reason))

    return response.json()


def check_url(url):
    """Check whether the given URL is dead or alive.

    Returns a dict with four keys:

        "url": The URL that was checked (string)
        "alive": Whether the URL was working, True or False
        "status": The HTTP status code of the response from the URL,
            e.g. 200, 401, 500 (int)
        "reason": The reason for the success or failure of the check,
            e.g. "OK", "Unauthorized", "Internal Server Error" (string)

    The "status" may be None if we did not get a valid HTTP response,
    e.g. in the event of a timeout, DNS failure or invalid HTTP response.

    The "reason" will always be a string, but may be a requests library
    exception string rather than an HTTP reason string if we did not get a valid
    HTTP response.

    """
    result = {"url": url}
    try:
        response = requests.get(url)
        result["status"] = response.status_code
        result["reason"] = response.reason
        response.raise_for_status()  # Raise if status_code is not OK.
        result["alive"] = True
    except requests.exceptions.RequestException as err:
        result["alive"] = False
        if "reason" not in result:
            result["reason"] = str(err)
        if "status" not in result:
            # This can happen if the response is invalid HTTP, if we get a DNS
            # failure, or a timeout, etc.
            result["status"] = None

    # We should always have these four fields in the result.
    assert "url" in result
    assert result.get("alive") in (True, False)
    assert "status" in result
    assert "reason" in result

    return result


def upsert_result(client_site_url, apikey, resource_id, result):
    """Post the given link check result to the client site."""

    # TODO: Handle exceptions and unexpected results.
    url = client_site_url + "deadoralive/upsert"
    params = result.copy()
    params["resource_id"] = resource_id
    requests.post(url, headers=dict(Authorization=apikey), params=params)


def _get_logger():
    # TODO: Add options for verbose and debug logging.
    # TODO: Add option for logging to file.
    logger = logging.getLogger("deadoralive")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - "
                                  "%(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger


def get_check_and_report(client_site_url, apikey, get_resource_ids_to_check,
                         get_url_for_id, check_url, upsert_result):
    """Get links from the client site, check them, and post the results back.

    Get resource IDs from the client site, get the URL for each resource ID from
    the client site, check each URL, and post the results back to the client
    site.

    This function can be called repeatedly to keep on getting more links from
    the client site and checking them.

    The functions that this function calls to carry out the various tasks are
    taken as parameters to this function for testing purposes - it makes it
    easy for tests to pass in mock functions. It also decouples the code nicely.

    :param client_site_url: the base URL of the client site
    :type client_site_url: string

    :param apikey: the API key to use when making requests to the client site
    :type apikey: string or None

    :param get_resource_ids_to_check: The function to call to get the list of
        resource IDs to be checked from the client site. See
        get_resource_ids_to_check() above for the interface that this function
        should implement.
    :type get_resource_ids_to_check: callable

    :param get_url_for_id: The function to call to get the URL for a given
        resource ID from the client site. See get_url_for_id() above for the
        interface that this function should implement.
    :type get_url_for_id: callable

    :param check_url: The function to call to check whether a URL is dead or
        alive. See check_url() above for the interface that this function
        should implement.
    :type check_url: callable

    :param upsert_result: The function to call to post a link check result to
        the client site. See upsert_result() above for the interface that this
        function should implement.
    :type upsert_result: callable

    """
    logger = _get_logger()
    resource_ids = get_resource_ids_to_check(client_site_url, apikey)
    for resource_id in resource_ids:
        try:
            url = get_url_for_id(client_site_url, apikey, resource_id)
        except CouldNotGetURLError:
            logger.info("This link checker was not authorized to access "
                        "resource {0}, skipping.".format(resource_id))
            continue
        result = check_url(url)
        status = result["status"]
        reason = result["reason"]
        if result["alive"]:
            logger.info("Checking URL {0} of resource {1} succeeded with "
                        "status {2}:".format(url, resource_id, status))
        else:
            logger.info("Checking URL {0} of resource {1} "
                        "failed with error {2}:".format(url, resource_id,
                                                        reason))
        upsert_result(client_site_url, apikey, resource_id=resource_id,
                      result=result)


def main(args=None):

    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--apikey")
    parser.add_argument("--port", type=int, default=4723)
    parsed_args = parser.parse_args(args)
    client_site_url = parsed_args.url
    if not client_site_url.endswith("/"):
        client_site_url = client_site_url + "/"
    apikey = parsed_args.apikey
    port = parsed_args.port

    s = socket.socket()
    try:
        s.bind(('localhost', port))
    except socket.error as err:
        if err.errno == 98:
            sys.exit(
                "Port {port} is already in use.\n"
                "Is there another instance of {process} already running?\n"
                "To run multiple instances of {process} at once use the "
                "--port <num> option.".format(port=port, process=sys.argv[0]))
        else:
            raise

    get_check_and_report(client_site_url, apikey, get_resources_to_check,
                         get_url_for_id, check_url, upsert_result)


if __name__ == "__main__":
    main()
