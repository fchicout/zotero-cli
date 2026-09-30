import argparse

import pytest

from zotero_cli.cli.main import build_parser


def parse(*argv):
    return build_parser().parse_args(list(argv))


@pytest.mark.parametrize(
    "argv, dest, value",
    [
        (["collection", "backup", "--collection", "C", "--output", "o.zaf"], "collection", "C"),
        (["collection", "export", "--collection", "C", "--as", "bibtex", "--output", "o"], "collection", "C"),
        (["collection", "purge", "--collection", "C", "--files"], "collection", "C"),
        (["slr", "sdb", "reset", "--collection", "C", "--phase", "p"], "collection", "C"),
        (["slr", "source", "add", "--collection", "acm", "--file", "f.ris"], "collection", "acm"),
        (["item", "move", "--key", "K", "--target", "T"], "key", "K"),
        (["tag", "add", "--key", "K", "--tags", "a"], "key", "K"),
    ],
)
def test_standard_spelling(argv, dest, value, capsys):
    assert getattr(parse(*argv), dest) == value
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "argv, old, new, dest, value",
    [
        (["collection", "backup", "--name", "C", "--output", "o.zaf"], "--name", "--collection", "collection", "C"),
        (["collection", "export", "--name", "C", "--as", "bibtex", "--output", "o"], "--name", "--collection", "collection", "C"),
        (["collection", "purge", "--name", "C", "--files"], "--name", "--collection", "collection", "C"),
        (["slr", "sdb", "reset", "--name", "C", "--phase", "p"], "--name", "--collection", "collection", "C"),
        (["slr", "source", "add", "--name", "acm", "--file", "f.ris"], "--name", "--collection", "collection", "acm"),
        (["item", "move", "--item-id", "K", "--target", "T"], "--item-id", "--key", "key", "K"),
        (["tag", "add", "--item", "K", "--tags", "a"], "--item", "--key", "key", "K"),
    ],
)
def test_old_spelling_still_works_and_warns(argv, old, new, dest, value, capsys):
    assert getattr(parse(*argv), dest) == value
    err = capsys.readouterr().err
    assert f"`{old}` is deprecated; use `{new}`" in err


def test_required_flag_is_still_required(capsys):
    with pytest.raises(SystemExit):
        parse("collection", "backup", "--output", "o.zaf")
    assert "one of the arguments --collection is required" in capsys.readouterr().err


def test_both_spellings_together_are_refused():
    with pytest.raises(SystemExit):
        parse("collection", "purge", "--collection", "A", "--name", "B", "--files")


def test_item_inspect_takes_a_positional_key():
    from zotero_cli.cli.flags import resolve_key

    args = parse("item", "inspect", "ABCD1234")
    resolve_key(args)
    assert args.key == "ABCD1234"
    args = parse("item", "inspect", "--key", "ABCD1234")
    resolve_key(args)
    assert args.key == "ABCD1234"


def test_sdb_inspect_takes_either_form():
    from zotero_cli.cli.flags import resolve_key

    for argv in (["slr", "sdb", "inspect", "K1"], ["slr", "sdb", "inspect", "--key", "K1"]):
        args = parse(*argv)
        resolve_key(args)
        assert args.key == "K1"


def test_conflicting_keys_are_refused():
    from zotero_cli.cli.flags import resolve_key
    from zotero_cli.core.exceptions import UsageError

    args = parse("slr", "sdb", "inspect", "K1", "--key", "K2")
    with pytest.raises(UsageError):
        resolve_key(args)


def test_sdb_key_is_required():
    from zotero_cli.cli.flags import resolve_key
    from zotero_cli.core.exceptions import UsageError

    args = parse("slr", "sdb", "inspect")
    with pytest.raises(UsageError):
        resolve_key(args)


def test_stray_argument_reports_the_leaf_usage_line(capsys):
    with pytest.raises(SystemExit):
        parse("item", "inspect", "K", "--bogus")
    err = capsys.readouterr().err
    assert "item inspect" in err
    assert "--file FILE" in err.replace("\n", " ")  # the leaf's options, not the top-level choices
    assert "{collection," not in err
    assert "unrecognized arguments: --bogus" in err


def test_plain_parsers_are_untouched():
    assert argparse.ArgumentParser().parse_args([]) is not None
