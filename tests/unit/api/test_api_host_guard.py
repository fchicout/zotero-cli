"""The API rejects requests whose Host header isn't an allowed (by default,
loopback) name - the defence against DNS rebinding, where a web page's own
hostname is re-pointed at 127.0.0.1 - and, in remote mode, requests without
the bearer token."""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from zotero_cli.api.main import (
    ENV_ALLOWED_HOSTS,
    ENV_TOKEN,
    _host_without_port,
    create_app,
    is_loopback_host,
)


@pytest.fixture(autouse=True)
def clean_env():
    # patch.dict restores os.environ afterwards, including keys that
    # `serve` sets itself.
    with patch.dict(os.environ):
        os.environ.pop(ENV_ALLOWED_HOSTS, None)
        os.environ.pop(ENV_TOKEN, None)
        yield


@pytest.mark.parametrize(
    "host", ["localhost", "localhost:1969", "127.0.0.1:1969", "[::1]:1969", "LOCALHOST"]
)
def test_loopback_host_headers_are_accepted(host):
    client = TestClient(create_app())
    assert client.get("/health", headers={"host": host}).status_code == 200


@pytest.mark.parametrize(
    "host", ["attacker.example:1969", "attacker.example", "192.168.1.5:1969", "", "testserver"]
)
def test_other_host_headers_are_rejected(host):
    client = TestClient(create_app())
    response = client.get("/health", headers={"host": host})
    assert response.status_code == 400


def test_rebinding_style_request_to_library_route_is_rejected():
    client = TestClient(create_app())
    response = client.get(
        "/items", headers={"host": "attacker.example:1969", "origin": "http://attacker.example"}
    )
    assert response.status_code == 400


def test_extra_allowed_host_from_environment(monkeypatch):
    monkeypatch.setenv(ENV_ALLOWED_HOSTS, "127.0.0.1,localhost,::1,zotero.lan")
    client = TestClient(create_app())
    assert client.get("/health", headers={"host": "zotero.lan:1969"}).status_code == 200
    assert client.get("/health", headers={"host": "other.lan"}).status_code == 400


def test_token_is_required_when_set():
    client = TestClient(create_app(allowed_hosts=["*"], token="t0ken-value"))
    assert client.get("/health", headers={"host": "192.168.1.5"}).status_code == 401
    wrong = {"host": "192.168.1.5", "authorization": "Bearer nope"}
    assert client.get("/health", headers=wrong).status_code == 401
    right = {"host": "192.168.1.5", "authorization": "Bearer t0ken-value"}
    assert client.get("/health", headers=right).status_code == 200


def test_token_read_from_environment(monkeypatch):
    monkeypatch.setenv(ENV_ALLOWED_HOSTS, "*")
    monkeypatch.setenv(ENV_TOKEN, "env-token")
    client = TestClient(create_app())
    assert client.get("/health", headers={"host": "x"}).status_code == 401
    ok = {"host": "x", "authorization": "Bearer env-token"}
    assert client.get("/health", headers=ok).status_code == 200


@pytest.mark.parametrize(
    "header,expected",
    [
        ("localhost:1969", "localhost"),
        ("[::1]:1969", "::1"),
        ("[::1]", "::1"),
        ("127.0.0.1", "127.0.0.1"),
        ("Example.COM:80", "example.com"),
    ],
)
def test_host_without_port(header, expected):
    assert _host_without_port(header) == expected


@pytest.mark.parametrize(
    "host,loopback",
    [
        ("127.0.0.1", True),
        ("127.0.0.2", True),
        ("localhost", True),
        ("::1", True),
        ("[::1]", True),
        ("0.0.0.0", False),
        ("192.168.1.5", False),
        ("example.com", False),
    ],
)
def test_is_loopback_host(host, loopback):
    assert is_loopback_host(host) is loopback
