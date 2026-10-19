import argparse

import pytest

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.flags import user_flag


def test_user_flag_reads_the_global_option() -> None:
    assert user_flag(argparse.Namespace(user=True)) is True
    assert user_flag(argparse.Namespace(user=False)) is False
    assert user_flag(argparse.Namespace()) is False


def _command(label: str, name: str) -> type:
    class Command(BaseCommand):
        @property
        def name(self) -> str:
            return name

        @property
        def help(self) -> str:
            return label

        def register_args(self, parser: argparse.ArgumentParser) -> None:
            pass

        def execute(self, args: argparse.Namespace) -> None:
            pass

    return Command


def test_registering_two_different_commands_under_one_name_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(CommandRegistry, "_commands", {})
    CommandRegistry.register(_command("first", "dup"))

    class Other(_command("second", "dup")):  # type: ignore[misc]
        pass

    with pytest.raises(ValueError, match="already registered"):
        CommandRegistry.register(Other)
