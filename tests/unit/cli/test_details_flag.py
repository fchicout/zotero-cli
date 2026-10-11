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
def test_the_old_per_command_verbose_flag_is_gone(argv, capsys):
    with pytest.raises(SystemExit) as raised:
        build_parser().parse_args([*argv, "--verbose"])
    assert raised.value.code == 2
    assert "unrecognized arguments: --verbose" in capsys.readouterr().err


@pytest.mark.parametrize("argv", LEAVES)
def test_details_defaults_off_without_warning(argv, capsys):
    args = build_parser().parse_args(argv)
    assert args.details is False
    assert capsys.readouterr().err == ""
