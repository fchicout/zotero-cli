import pytest

from zotero_cli.core.strategies import (
    BibtexImportStrategy,
    CanonicalCsvImportStrategy,
    IeeeCsvImportStrategy,
    RisImportStrategy,
    SpringerCsvImportStrategy,
)
from zotero_cli.infra.factory import GatewayFactory


@pytest.mark.parametrize(
    ("ext", "header", "expected"),
    [
        (".bib", "", BibtexImportStrategy),
        (".ris", "", RisImportStrategy),
        (".csv", "item title,authors", SpringerCsvImportStrategy),
        (".csv", "document title,authors", IeeeCsvImportStrategy),
        (".csv", "title,doi,year", CanonicalCsvImportStrategy),
    ],
)
def test_the_file_extension_and_csv_header_pick_the_strategy(ext, header, expected) -> None:
    assert isinstance(GatewayFactory.get_file_import_strategy(ext, header), expected)


@pytest.mark.parametrize(("ext", "header"), [(".txt", ""), (".csv", "name,age"), (".csv", "")])
def test_an_unrecognised_file_has_no_strategy(ext, header) -> None:
    assert GatewayFactory.get_file_import_strategy(ext, header) is None
