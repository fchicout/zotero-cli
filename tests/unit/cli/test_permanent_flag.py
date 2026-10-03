import argparse

import pytest

from zotero_cli.cli.safety import add_permanent_flag, resolve_trash
from zotero_cli.core.exceptions import UsageError


def _args(**kw) -> argparse.Namespace:
    return argparse.Namespace(**{"trash": False, "permanent": False, **kw})


def test_neither_flag_warns_when_applying_and_stays_permanent(capsys):
    assert resolve_trash(_args(), "item delete", applying=True) is False

    err = capsys.readouterr().err
    assert "`item delete` currently deletes permanently by default" in err
    assert "--permanent" in err
    assert "4.0" in err


def test_a_preview_does_not_warn(capsys):
    assert resolve_trash(_args(), "item delete", applying=False) is False

    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("flags, expected", [({"trash": True}, True), ({"permanent": True}, False)])
def test_an_explicit_choice_is_silent(capsys, flags, expected):
    assert resolve_trash(_args(**flags), "item delete", applying=True) is expected

    assert capsys.readouterr().err == ""


def test_both_flags_are_a_usage_error():
    args = _args(trash=True, permanent=True)

    with pytest.raises(UsageError, match="contradict"):
        resolve_trash(args, "item delete", applying=True)


def test_add_permanent_flag_defines_a_boolean_flag():
    parser = argparse.ArgumentParser()
    add_permanent_flag(parser, "the item")

    assert parser.parse_args([]).permanent is False
    assert parser.parse_args(["--permanent"]).permanent is True
