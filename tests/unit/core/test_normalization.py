from zotero_cli.core.utils.normalization import is_valid_doi


def test_is_valid_doi_accepts_plausible_doi():
    assert is_valid_doi("10.1000/xyz123")
    assert is_valid_doi("10.1234567/abc.def-ghi_jkl")


def test_is_valid_doi_rejects_empty():
    assert not is_valid_doi("")


def test_is_valid_doi_rejects_missing_prefix():
    assert not is_valid_doi("not-a-doi")
    assert not is_valid_doi("1000/xyz")


def test_is_valid_doi_rejects_missing_suffix():
    assert not is_valid_doi("10.1000/")
    assert not is_valid_doi("10.1000")


def test_is_valid_doi_rejects_whitespace():
    """Issue #242: a DOI containing embedded whitespace is not a
    plausible DOI shape and must be rejected before URL construction."""
    assert not is_valid_doi("10.1000/ab cd")
    assert not is_valid_doi(" 10.1000/abcd")
