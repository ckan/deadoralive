import requests
import mock
import httpretty

import deadoralive


def test_get_check_and_report():
    """Basic test that get_check_and_report() calls other functions correctly.

    Tests get_check_and_report()'s contract with the other functions that it
    takes as parameters, in the "happy case" where those functions all behave
    nicely and don't raise any exceptions.

    """
    client_site_url = "http://demo.ckan.org"
    apikey = "foo"

    get_resource_ids_to_check = mock.Mock()
    get_resource_ids_to_check.return_value = ["resource_id_1", "resource_id_2",
                                              "resource_id_3"]

    def get_url_for_id_(client_site_url, apikey, resource_id):
        return dict(
            resource_id_1="url_1",
            resource_id_2="url_2",
            resource_id_3="url_3",
            )[resource_id]
    get_url_for_id = mock.Mock()
    get_url_for_id.side_effect = get_url_for_id_

    def check_url_(url):
        if url in ("url_1", "url_3"):
            return dict(alive=True, status=200, reason="OK", url=url)
        else:
            return dict(alive=False, status=500, reason="Internal Server Error",
                        url=url)
    check_url = mock.Mock()
    check_url.side_effect = check_url_

    upsert_result = mock.Mock()
    upsert_result.return_value = None

    deadoralive.get_check_and_report(client_site_url, apikey,
                                     get_resource_ids_to_check, get_url_for_id,
                                     check_url, upsert_result)

    get_resource_ids_to_check.assert_called_once_with(client_site_url, apikey)

    assert get_url_for_id.call_args_list == [
        mock.call(client_site_url, apikey, "resource_id_1"),
        mock.call(client_site_url, apikey, "resource_id_2"),
        mock.call(client_site_url, apikey, "resource_id_3")]

    assert check_url.call_args_list == [mock.call("url_1"), mock.call("url_2"),
                                        mock.call("url_3")]

    assert upsert_result.call_args_list == [
        mock.call(
            client_site_url, apikey, resource_id="resource_id_1",
            result=dict(url="url_1", alive=True, status=200, reason="OK")),
        mock.call(
            client_site_url, apikey, resource_id="resource_id_2",
            result=dict(url="url_2", alive=False, status=500,
                        reason="Internal Server Error")),
        mock.call(
            client_site_url, apikey, resource_id="resource_id_3",
            result=dict(url="url_3", alive=True, status=200, reason="OK"))]


# TODO: Test get_check_and_report() when the various functions it calls fail.
# They should all fail only by raising exceptions which get_check_and_report()
# should catch.


@httpretty.activate
def test_check_url_with_200_OK():
    """Test the check_url() function when the URL responds with a 200 OK."""

    url = "http://just.testing.com/this/is/just/a/test/"
    httpretty.register_uri(httpretty.GET, url,
                           body='[{"title": "Just Testing"}]',
                           content_type="application/json")

    result = deadoralive.check_url(url)

    assert result["alive"] is True
    assert result["status"] == 200
    assert result["reason"] == "OK"
    assert result["url"] == url


@httpretty.activate
def test_check_url_with_redirect():
    # TODO.
    pass


@httpretty.activate
def test_check_url_with_too_many_redirects():
    # TODO.
    pass


@httpretty.activate
def test_check_url_with_401():
    url = "http://just.testing.com/this/is/just/a/test/"
    httpretty.register_uri(httpretty.GET, url,
                           status=401, body="foo")

    result = deadoralive.check_url(url)

    assert result["alive"] is False
    assert result["status"] == 401
    assert result["reason"] == "Unauthorized"
    assert result["url"] == url


@httpretty.activate
def test_check_url_with_500():
    url = "http://just.testing.com/this/is/just/a/test/"
    httpretty.register_uri(httpretty.GET, url, status=500)

    result = deadoralive.check_url(url)

    assert result["alive"] is False
    assert result["status"] == 500
    assert result["reason"] == "Internal Server Error"
    assert result["url"] == url


@httpretty.activate
def test_check_url_that_does_not_respond():
    # TODO.
    pass


@mock.patch("requests.get")
def test_check_url_with_invalid_http(mock_get_function):
    url = "http://just.testing.com/this/is/just/a/test/"
    mock_get_function.side_effect = requests.exceptions.RequestException(
        "Oh no invalid HTTP!")

    result = deadoralive.check_url(url)

    assert result["alive"] is False
    assert result["status"] is None
    assert "Oh no invalid HTTP!" in result["reason"]
    assert result["url"] == url


# TODO: Tests for get_resource_ids_to_check(), get_url_for_id(),
# upsert_result(), command line parsing.
