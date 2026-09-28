"""Issue #368: each of these used to print an error and exit 0, so scripts
and agents could not tell it had failed."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.main import main


@pytest.fixture
def gateway():
    gw = MagicMock()
    gw.get_item.return_value = None
    gw.get_collection.return_value = None
    gw.get_collection_id_by_name.return_value = None
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gw),
        patch("zotero_cli.core.config.get_config"),
    ):
        yield gw


@pytest.mark.parametrize(
    "argv, code, message",
    [
        (["item", "list"], 2, "--collection or --root required"),
        (["item", "list", "--collection", "Nope"], 3, "Collection 'Nope' not found"),
        (["search"], 2, "Provide a query"),
        (["item", "inspect", "--key", "NOPE0000"], 3, "NOPE0000"),
        (["item", "export", "--key", "K1", "--format", "bibtex"], 2, "--output required"),
        (["collection", "delete", "--key", "NOPE0000"], 3, "Collection 'NOPE0000' not found"),
    ],
)
def test_failures_exit_non_zero_with_one_stderr_line(gateway, capsys, argv, code, message):
    gateway.get_item.return_value = MagicMock() if argv[:2] == ["item", "export"] else None
    with patch.object(sys, "argv", ["zotero-cli", *argv]), pytest.raises(SystemExit) as raised:
        main()

    assert raised.value.code == code
    err = capsys.readouterr().err
    assert err.startswith("Error: ")
    assert message in err


def test_import_of_an_unparseable_file_fails(gateway, capsys, tmp_path):
    bad = tmp_path / "broken.ris"
    bad.write_bytes(b"\xff\xfe not ris")
    with (
        patch.object(sys, "argv", ["zotero-cli", "import", "file", str(bad), "--collection", "X"]),
        pytest.raises(SystemExit) as raised,
    ):
        main()
    assert raised.value.code != 0
