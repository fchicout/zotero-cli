import pytest

from zotero_cli.cli.main import build_parser

LEAVES = [
    ["import", "file", "x.bib", "--collection", "C"],
    ["item", "pdf", "fetch", "--key", "K"],
    ["collection", "clean", "--collection", "C"],
]


@pytest.mark.parametrize("argv", LEAVES)
def test_details_flag_leaves_global_verbose_alone(argv):
    """Issue #374: a subcommand's detail flag must not reset the global -v."""
    args = build_parser().parse_args(["-v", *argv, "--details"])
    assert args.verbose is True
    assert args.details is True


@pytest.mark.parametrize("argv", LEAVES)
def test_deprecated_verbose_alias_maps_to_details_and_warns(argv, capsys):
    args = build_parser().parse_args([*argv, "--verbose"])
    assert args.details is True
    assert args.verbose is False
    assert "--verbose` on this command is deprecated; use --details" in capsys.readouterr().err


@pytest.mark.parametrize("argv", LEAVES)
def test_details_defaults_off_without_warning(argv, capsys):
    args = build_parser().parse_args(argv)
    assert args.details is False
    assert capsys.readouterr().err == ""
