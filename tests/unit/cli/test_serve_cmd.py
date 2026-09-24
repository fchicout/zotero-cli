import argparse
import os
from unittest.mock import patch

import pytest

from zotero_cli.api.main import ENV_ALLOWED_HOSTS, ENV_TOKEN
from zotero_cli.cli.commands.serve_cmd import ServeCommand


def _args(**overrides):
    parser = argparse.ArgumentParser()
    ServeCommand().register_args(parser)
    args = parser.parse_args([])
    for k, v in overrides.items():
        setattr(args, k, v)
    return args


@pytest.fixture(autouse=True)
def clean_env():
    # patch.dict restores os.environ afterwards, including keys that
    # `serve` sets itself.
    with patch.dict(os.environ):
        os.environ.pop(ENV_ALLOWED_HOSTS, None)
        os.environ.pop(ENV_TOKEN, None)
        yield


def test_default_bind_is_loopback_without_token(monkeypatch):
    with patch("zotero_cli.cli.commands.serve_cmd.uvicorn.run") as run:
        ServeCommand().execute(_args())
    assert run.call_args.kwargs["host"] == "127.0.0.1"
    assert os.environ[ENV_ALLOWED_HOSTS] == "127.0.0.1,localhost,::1"
    assert ENV_TOKEN not in os.environ


def test_non_loopback_bind_is_refused_without_allow_remote(capsys):
    with patch("zotero_cli.cli.commands.serve_cmd.uvicorn.run") as run:
        with pytest.raises(SystemExit) as exc:
            ServeCommand().execute(_args(host="0.0.0.0"))
    assert exc.value.code == 2
    run.assert_not_called()
    assert "--allow-remote" in capsys.readouterr().err


def test_allow_remote_generates_and_prints_a_token(capsys):
    with patch("zotero_cli.cli.commands.serve_cmd.uvicorn.run") as run:
        ServeCommand().execute(_args(host="0.0.0.0", allow_remote=True))
    run.assert_called_once()
    token = os.environ[ENV_TOKEN]
    assert len(token) >= 32
    assert f"Authorization: Bearer {token}" in capsys.readouterr().out
    assert os.environ[ENV_ALLOWED_HOSTS] == "*"


def test_allowed_host_is_added_to_the_allowlist():
    with patch("zotero_cli.cli.commands.serve_cmd.uvicorn.run"):
        ServeCommand().execute(_args(allowed_host=["zotero.lan"]))
    assert os.environ[ENV_ALLOWED_HOSTS].split(",")[-1] == "zotero.lan"
