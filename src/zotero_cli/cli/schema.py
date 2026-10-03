"""A machine-readable description of the command line (Issue #556).

Built from the argparse tree itself, so it can't drift from what the parser
accepts. What argparse can't say, whether a command changes your data, is in
COMMAND_EFFECTS; a test fails when a command is missing from it.
"""

import argparse
from typing import Any, Dict, List, Optional, Sequence

from zotero_cli import __version__
from zotero_cli.core.exceptions import EXIT_CODES

SCHEMA_VERSION = 1

# What running a command can change:
#   read   - nothing: it only reads (the library, local state, or files you name)
#   local  - only this machine's own files and state: exports and backups it writes,
#            the job queue, the discovery graph, the config, the vector store
#   write  - your Zotero library (or the local zotero.sqlite), including deletes
# Commands that write and take --execute are preview-by-default.
COMMAND_EFFECTS: Dict[str, str] = {
    **dict.fromkeys(
        [
            "collection list",
            "item annotations",
            "item inspect",
            "item list",
            "mcp serve",
            "rag context",
            "rag query",
            "report attachments",
            "report audit",
            "report duplicates",
            "report stats",
            "report verify-latex",
            "search",
            "serve",
            "slr list excluded",
            "slr list included",
            "slr list pending",
            "slr list qa-approved",
            "slr report consensus",
            "slr report exclusion-summary",
            "slr report graph",
            "slr report prisma",
            "slr report screening",
            "slr report shift",
            "slr report status",
            "slr sdb inspect",
            "slr snowball status",
            "slr source list",
            "system check",
            "system groups",
            "system info",
            "system jobs list",
            "system selftest",
            "system verify",
            "tag list",
        ],
        "read",
    ),
    **dict.fromkeys(
        [
            "collection backup",
            "collection export",
            "init",
            "item export",
            "item pdf fetch",
            "rag ingest",
            "rag model clean",
            "rag model set",
            "rag purge",
            "slr report snapshot",
            "slr sdb export",
            "slr snowball discovery",
            "slr snowball export",
            "slr snowball review",
            "slr snowball seed",
            "system backup",
            "system jobs retry",
            "system normalize",
            "system switch",
        ],
        "local",
    ),
    **dict.fromkeys(
        [
            "collection clean",
            "collection create",
            "collection delete",
            "collection purge",
            "collection rename",
            "import arxiv",
            "import bdtd",
            "import doi",
            "import file",
            "import manual",
            "item add",
            "item delete",
            "item hydrate",
            "item merge",
            "item move",
            "item pdf attach",
            "item pdf strip",
            "item purge",
            "item restore",
            "item transfer",
            "item trash",
            "item update",
            "slr decide",
            "slr dedupe",
            "slr extract",
            "slr load",
            "slr promote",
            "slr prune",
            "slr reconcile",
            "slr screen",
            "slr sdb edit",
            "slr sdb reset",
            "slr sdb upgrade",
            "slr snowball import",
            "slr source add",
            "slr source init",
            "storage checkout",
            "system demo-sandbox",
            "system jobs run",
            "system restore",
            "tag add",
            "tag purge",
        ],
        "write",
    ),
    # Describing the command line changes nothing.
    "schema": "read",
}

_JSON_SCALARS = (str, int, float, bool, type(None))


def _subparsers(parser: argparse.ArgumentParser) -> Optional[argparse._SubParsersAction]:  # type: ignore[type-arg]
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _is_boolean(action: argparse.Action) -> bool:
    return isinstance(
        action,
        (
            argparse._StoreTrueAction,
            argparse._StoreFalseAction,
            argparse._StoreConstAction,
            argparse.BooleanOptionalAction,
        ),
    )


def _value_type(action: argparse.Action) -> str:
    if _is_boolean(action):
        return "boolean"
    if isinstance(action, argparse._CountAction) or action.type is int:
        return "integer"
    if action.type is float:
        return "number"
    return "string"


def _default(action: argparse.Action) -> Any:
    if action.default is argparse.SUPPRESS:
        return None
    if isinstance(action.default, (list, tuple)):
        return [d if isinstance(d, _JSON_SCALARS) else str(d) for d in action.default]
    return action.default if isinstance(action.default, _JSON_SCALARS) else str(action.default)


def _describe_argument(action: argparse.Action) -> Dict[str, Any]:
    positional = not action.option_strings
    repeatable = (
        isinstance(action, (argparse._AppendAction, argparse._CountAction))
        or action.nargs in ("*", "+")
        or (isinstance(action.nargs, int) and action.nargs > 1)
    )
    entry: Dict[str, Any] = {
        "name": action.metavar if positional and isinstance(action.metavar, str) else action.dest,
        "kind": "positional" if positional else "option",
        "flags": list(action.option_strings),
        "type": _value_type(action),
        "required": bool(action.required) if not positional else action.nargs not in ("?", "*"),
        "repeatable": repeatable,
        "default": _default(action),
        "choices": [c if isinstance(c, _JSON_SCALARS) else str(c) for c in action.choices]
        if action.choices is not None
        else None,
        "help": " ".join((action.help or "").split()),
    }
    return entry


def _visible_arguments(parser: argparse.ArgumentParser) -> List[argparse.Action]:
    """The arguments a user can see: not the help flag, not a subcommand selector, and
    not the deprecated aliases kept hidden with help=SUPPRESS."""
    return [
        action
        for action in parser._actions
        if not isinstance(action, (argparse._HelpAction, argparse._SubParsersAction))
        and action.help is not argparse.SUPPRESS
        and not isinstance(action, argparse._VersionAction)
    ]


def _describe_command(
    parser: argparse.ArgumentParser, path: Sequence[str], help_text: str
) -> Dict[str, Any]:
    node: Dict[str, Any] = {
        "name": path[-1],
        "path": list(path),
        "help": " ".join((help_text or "").split()),
        "description": " ".join((parser.description or "").split()) or None,
        "arguments": [_describe_argument(a) for a in _visible_arguments(parser)],
    }
    children = _subparsers(parser)
    if children is None:
        key = " ".join(path)
        effect = COMMAND_EFFECTS.get(key)
        node["effect"] = effect
        node["preview_by_default"] = effect == "write" and any(
            "--execute" in a.option_strings for a in parser._actions
        )
        return node
    helps = {a.dest: a.help or "" for a in children._choices_actions}
    node["commands"] = [
        _describe_command(sub, [*path, name], helps.get(name, ""))
        for name, sub in children.choices.items()
    ]
    return node


def leaf_paths(parser: argparse.ArgumentParser, prefix: Sequence[str] = ()) -> List[str]:
    """Every runnable command, as 'noun verb'."""
    children = _subparsers(parser)
    if children is None:
        return [" ".join(prefix)]
    paths: List[str] = []
    for name, sub in children.choices.items():
        paths.extend(leaf_paths(sub, [*prefix, name]))
    return paths


def build_schema(parser: argparse.ArgumentParser) -> Dict[str, Any]:
    children = _subparsers(parser)
    helps = {a.dest: a.help or "" for a in children._choices_actions} if children else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "program": "zotero-cli",
        "version": __version__,
        "exit_codes": {str(code): meaning for code, meaning in EXIT_CODES.items()},
        "effects": {
            "read": "changes nothing",
            "local": "changes only this machine's own files and state (exports, backups, job queue, config)",
            "write": "changes your Zotero library or the local zotero.sqlite; commands with "
            "preview_by_default only show what they would do until --execute",
        },
        "global_options": [_describe_argument(a) for a in _visible_arguments(parser)],
        "commands": [
            _describe_command(sub, [name], helps.get(name, ""))
            for name, sub in (children.choices.items() if children else [])
        ],
    }


def find_command(schema: Dict[str, Any], path: Sequence[str]) -> Optional[Dict[str, Any]]:
    """The node for `path` (e.g. ['item', 'list']) in a schema, or None."""
    nodes = schema["commands"]
    found: Optional[Dict[str, Any]] = None
    for word in path:
        found = next((n for n in nodes if n["name"] == word), None)
        if found is None:
            return None
        nodes = found.get("commands", [])
    return found
