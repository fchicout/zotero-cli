"""`zotero-cli schema`: the command line as JSON (Issue #556)."""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

import pytest

from zotero_cli import __version__
from zotero_cli.cli.commands.schema_cmd import SchemaCommand
from zotero_cli.cli.main import build_parser
from zotero_cli.cli.schema import COMMAND_EFFECTS, build_schema, find_command, leaf_paths
from zotero_cli.core.exceptions import EXIT_CODES, UsageError

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def schema() -> Dict[str, Any]:
    return build_schema(build_parser())


def _leaves(schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []

    def walk(node: Dict[str, Any]) -> None:
        if "commands" in node:
            for child in node["commands"]:
                walk(child)
        else:
            found.append(node)

    for node in schema["commands"]:
        walk(node)
    return found


def _command(schema: Dict[str, Any], *path: str) -> Dict[str, Any]:
    node = find_command(schema, path)
    assert node is not None, path
    return node


def _argument(command: Dict[str, Any], name: str) -> Dict[str, Any]:
    return next(a for a in command["arguments"] if a["name"] == name)


def test_the_document_names_the_program_version_and_layout(schema: Dict[str, Any]) -> None:
    assert (schema["program"], schema["version"], schema["schema_version"]) == (
        "zotero-cli",
        __version__,
        1,
    )
    assert {"exit_codes", "effects", "global_options", "commands"} <= set(schema)


def test_every_runnable_command_is_classified_and_nothing_stale_is() -> None:
    """A new command must be given an effect (read / local / write)."""
    assert set(leaf_paths(build_parser())) == set(COMMAND_EFFECTS)


def test_effects_are_one_of_the_documented_three(schema: Dict[str, Any]) -> None:
    assert set(COMMAND_EFFECTS.values()) == set(schema["effects"]) == {"read", "local", "write"}
    assert all(leaf["effect"] in schema["effects"] for leaf in _leaves(schema))


@pytest.mark.parametrize(
    ("path", "effect", "preview"),
    [
        (("search",), "read", False),
        (("item", "list"), "read", False),
        (("item", "inspect"), "read", False),
        (("system", "selftest"), "read", False),
        (("schema",), "read", False),
        (("collection", "backup"), "local", False),
        (("item", "export"), "local", False),
        (("item", "add"), "write", False),
        (("item", "trash"), "write", True),
        (("item", "delete"), "write", True),
        (("slr", "dedupe"), "write", True),
        (("system", "restore"), "write", True),
        (("collection", "delete"), "write", True),
    ],
)
def test_effects_of_known_commands(
    schema: Dict[str, Any], path: tuple, effect: str, preview: bool
) -> None:
    command = _command(schema, *path)
    assert (command["effect"], command["preview_by_default"]) == (effect, preview)


def test_a_write_command_is_preview_by_default_exactly_when_it_takes_execute(
    schema: Dict[str, Any],
) -> None:
    for leaf in _leaves(schema):
        takes_execute = any("--execute" in a["flags"] for a in leaf["arguments"])
        assert leaf["preview_by_default"] == (leaf["effect"] == "write" and takes_execute)


def test_exit_codes_are_the_single_table(schema: Dict[str, Any]) -> None:
    assert schema["exit_codes"] == {str(code): meaning for code, meaning in EXIT_CODES.items()}


def test_the_exit_code_document_lists_the_same_codes() -> None:
    document = (REPO / "docs" / "EXIT_CODES.md").read_text(encoding="utf-8")
    documented = {int(code) for code in re.findall(r"^\| `(\d+)` \|", document, re.M)}
    assert documented == set(EXIT_CODES)


def test_the_help_epilog_is_built_from_the_same_table() -> None:
    epilog = build_parser().epilog or ""
    assert all(f"{code} {meaning}" in epilog for code, meaning in EXIT_CODES.items())


def test_global_options_are_described_without_the_help_flag(schema: Dict[str, Any]) -> None:
    flags = {flag for option in schema["global_options"] for flag in option["flags"]}
    assert {"--user", "--offline", "--config", "--verbose"} <= flags
    assert "--help" not in flags
    assert "--version" not in flags


def test_arguments_carry_type_default_choices_and_repeatability(schema: Dict[str, Any]) -> None:
    search = _command(schema, "search")
    limit = _argument(search, "limit")
    assert (limit["type"], limit["default"], limit["required"]) == ("integer", 50, False)
    tag = _argument(search, "tag")
    assert (tag["type"], tag["repeatable"], tag["flags"]) == ("string", True, ["--tag"])
    assert _argument(search, "format")["choices"] == ["table", "json", "csv", "ndjson"]
    query = _argument(search, "query")
    assert (query["kind"], query["required"]) == ("positional", False)
    assert _argument(_command(schema, "item", "list"), "trash")["type"] == "boolean"


def test_a_required_option_is_marked_required(schema: Dict[str, Any]) -> None:
    export = _command(schema, "item", "export")
    assert _argument(export, "key")["required"] is True


def test_deprecated_aliases_hidden_from_help_are_not_listed(schema: Dict[str, Any]) -> None:
    flags = {f for a in _command(schema, "collection", "export")["arguments"] for f in a["flags"]}
    assert "--collection" in flags
    assert "--name" not in flags  # the hidden deprecated spelling


def test_the_schema_is_plain_deterministic_json() -> None:
    first = json.dumps(build_schema(build_parser()), sort_keys=False)
    assert first == json.dumps(build_schema(build_parser()), sort_keys=False)
    assert json.loads(first)["program"] == "zotero-cli"


def test_find_command_walks_groups_and_returns_none_for_unknown(schema: Dict[str, Any]) -> None:
    group = _command(schema, "slr", "list")
    assert {c["name"] for c in group["commands"]} >= {"pending", "included", "excluded"}
    assert find_command(schema, ["slr", "nonsense"]) is None
    assert find_command(schema, ["nonsense"]) is None


def _run(*words: str, capsys: pytest.CaptureFixture[str]) -> Dict[str, Any]:
    SchemaCommand().execute(argparse.Namespace(command_path=list(words)))
    document: Dict[str, Any] = json.loads(capsys.readouterr().out)
    return document


def test_the_command_prints_the_whole_document(capsys: pytest.CaptureFixture[str]) -> None:
    document = _run(capsys=capsys)
    assert document["program"] == "zotero-cli"
    assert len(_leaves(document)) == len(COMMAND_EFFECTS)


def test_the_command_can_print_one_command(capsys: pytest.CaptureFixture[str]) -> None:
    document = _run("item", "list", capsys=capsys)
    assert document["command"]["path"] == ["item", "list"]
    assert "commands" not in document


def test_an_unknown_command_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    command = SchemaCommand()
    args = argparse.Namespace(command_path=["item", "nonsense"])
    with pytest.raises(UsageError, match="Unknown command 'item nonsense'"):
        command.execute(args)


def test_schema_is_reachable_through_the_real_parser() -> None:
    args = build_parser().parse_args(["schema", "item", "list"])
    assert args.command_path == ["item", "list"]
    assert build_parser().parse_args(["schema"]).command_path == []
