"""One error policy for every metadata client built on BaseAPIClient._lookup."""

import logging
from typing import Any
from unittest.mock import patch

import pytest
import requests

from zotero_cli.infra.dblp_api import DBLPAPIClient
from zotero_cli.infra.eric_api import ERICAPIClient
from zotero_cli.infra.hal_api import HALAPIClient
from zotero_cli.infra.inspire_hep_api import InspireHEPAPIClient
from zotero_cli.infra.zbmath_api import ZBMathAPIClient

CLIENTS = [
    (DBLPAPIClient, "10.1000/x"),
    (ERICAPIClient, "EJ123456"),
    (HALAPIClient, "hal-0001"),
    (InspireHEPAPIClient, "10.1000/x"),
    (ZBMathAPIClient, "10.1000/x"),
]


def _http_error(status: int) -> requests.exceptions.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.exceptions.HTTPError(f"HTTP {status}", response=response)


@pytest.mark.parametrize(("client_cls", "identifier"), CLIENTS)
def test_a_404_is_quietly_no_result(
    client_cls: Any, identifier: str, caplog: pytest.LogCaptureFixture
) -> None:
    client = client_cls()
    with patch.object(client, "_get", side_effect=_http_error(404)):
        with caplog.at_level(logging.WARNING):
            assert client.get_paper_metadata(identifier) is None

    assert not caplog.records


@pytest.mark.parametrize(("client_cls", "identifier"), CLIENTS)
def test_another_http_error_is_logged_and_no_result(
    client_cls: Any, identifier: str, caplog: pytest.LogCaptureFixture
) -> None:
    client = client_cls()
    with patch.object(client, "_get", side_effect=_http_error(500)):
        with caplog.at_level(logging.ERROR):
            assert client.get_paper_metadata(identifier) is None

    assert f"{client_cls.__name__}: Error fetching metadata for {identifier}" in caplog.text


# DBLP treats a non-JSON body as a quiet "no result" (test_dblp_api.py), so it is left out.
@pytest.mark.parametrize(
    ("client_cls", "identifier"), [c for c in CLIENTS if c[0] is not DBLPAPIClient]
)
def test_an_unreadable_response_is_logged_and_no_result(
    client_cls: Any, identifier: str, caplog: pytest.LogCaptureFixture
) -> None:
    client = client_cls()
    response = requests.Response()
    response.status_code = 200
    response._content = b"<html>not json</html>"
    with patch.object(client, "_get", return_value=response):
        with caplog.at_level(logging.ERROR):
            assert client.get_paper_metadata(identifier) is None

    assert f"{client_cls.__name__}: Error parsing response for {identifier}" in caplog.text
