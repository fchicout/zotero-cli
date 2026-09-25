"""
Issue #386: every documented `zotero-cli ...` example must parse with the real
argument parser. 46 of 324 examples didn't (positional arguments that became
flags, verbs that were renamed or never wired), and nothing caught it.

Examples come from fenced code blocks and inline code in the Markdown docs
(docs/archive and the CHANGELOG are history, not instructions) and from every
command's `--help` epilog (its `Action:` lines and backticked commands). Only
parsing is checked, not behaviour.

A concrete example must parse. A synopsis (`[--flag VALUE]`, `<verb>`,
`a|b`, `...`) can't be parsed as-is, so for those the command path must
exist and every flag it names must belong to that command.
"""

import argparse
import contextlib
import io
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional

import pytest

from zotero_cli.cli.main import build_parser

ROOT = Path(__file__).resolve().parents[2]
# docs/specs holds design specifications (some describe commands as planned,
# not as built); docs/archive is history.
EXCLUDED_DIRS = {"archive", "specs", ".venv", "node_modules", "scratch", "data", ".git", ".claude"}
EXCLUDED_FILES = {"CHANGELOG.md"}

# Stop at shell operators: what follows isn't zotero-cli's.
SHELL_OPERATORS = {"|", "||", "&&", ";", ">", ">>", "<", "2>", "&", "2>&1", "$("}
PLACEHOLDER = re.compile(r"^<[^<>]+>$|^\{\{.*\}\}$")
INLINE_CODE = re.compile(r"`(zotero-cli [^`]+)`")


@dataclass
class Example:
    source: str
    command: str

    def __str__(self) -> str:
        return f"{self.source}: {self.command}"


def _markdown_files() -> List[Path]:
    files = []
    for path in sorted(ROOT.rglob("*.md")):
        rel = path.relative_to(ROOT)
        if set(rel.parts[:-1]) & EXCLUDED_DIRS or rel.name in EXCLUDED_FILES:
            continue
        if rel.parts[0] == "tests":
            continue
        files.append(path)
    return files


def _examples_in_markdown(path: Path) -> Iterator[Example]:
    rel = path.relative_to(ROOT)
    lines = path.read_text(encoding="utf-8").splitlines()
    in_code = False
    pending: Optional[str] = None
    pending_line = 0
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            text = stripped[2:] if stripped.startswith("$ ") else stripped
            if pending is not None:
                pending += " " + text.rstrip("\\").strip()
                if not text.endswith("\\"):
                    yield Example(f"{rel}:{pending_line}", pending)
                    pending = None
                continue
            if text.startswith("zotero-cli ") or text == "zotero-cli":
                if text.endswith("\\"):
                    pending, pending_line = text.rstrip("\\").strip(), number
                else:
                    yield Example(f"{rel}:{number}", text)
        else:
            for match in INLINE_CODE.finditer(line):
                yield Example(f"{rel}:{number}", match.group(1))


def _subparsers(parser: argparse.ArgumentParser, path: str) -> Iterator[tuple]:
    yield path, parser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                yield from _subparsers(sub, f"{path} {name}".strip())


def _examples_in_epilogs() -> Iterator[Example]:
    seen = set()
    for path, parser in _subparsers(build_parser(), ""):
        for line in (parser.epilog or "").splitlines():
            stripped = line.strip()
            commands = [m.group(1) for m in INLINE_CODE.finditer(stripped)]
            if not commands:
                for prefix in ("Action:", "$ ", ""):
                    rest = stripped[len(prefix) :].strip() if stripped.startswith(prefix) else ""
                    if rest.startswith("zotero-cli "):
                        commands = [rest]
                        break
            for command in commands:
                key = (path, command)
                if key not in seen:
                    seen.add(key)
                    yield Example(f"`{path or 'zotero-cli'} --help` epilog", command)


def all_examples() -> List[Example]:
    examples: List[Example] = []
    for path in _markdown_files():
        examples.extend(_examples_in_markdown(path))
    examples.extend(_examples_in_epilogs())
    return examples


def to_argv(command: str) -> Optional[List[str]]:
    """The arguments to parse, or None when the text isn't a concrete
    example (a synopsis with `...`, or a placeholder for the whole line)."""
    # Drop a trailing shell comment; turn <placeholders> into a value before
    # lexing (the lexer would read their angle brackets as redirections).
    command = re.sub(r"\s+#\s.*$", "", command)
    command = re.sub(r"<[^<>\s][^<>]*>", "1", command)
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="|&;<>")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None
    argv: List[str] = []
    for token in tokens[1:]:  # skip "zotero-cli"
        if token in SHELL_OPERATORS or token.startswith("$("):
            break
        if token in ("...", "…") or token.endswith("...") or token.endswith("…"):
            return None
        # Synopsis brackets: "[--verbose]" means the flag is optional.
        token = token.strip("[]")
        if not token:
            continue
        if PLACEHOLDER.match(token) or re.search(r"<[^<>]+>", token):
            token = re.sub(r"<[^<>]+>", "1", token)
        argv.append(token)
    return argv


SYNOPSIS = re.compile(r"\[|\(|\||\.\.\.|…|<verb>|<subcommand>")
FLAG = re.compile(r"(?<![\w-])(--[a-zA-Z][\w-]*|-[a-zA-Z])(?![\w-])")


def synopsis_error(command: str) -> Optional[str]:
    """For a synopsis: the command path must exist and every flag it names
    must belong to that command (or be a global option)."""
    root = build_parser()
    parser = root
    words = command.split()[1:]
    path = ["zotero-cli"]
    for word in words:
        subparsers = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
        if not subparsers or word.startswith(("-", "<", "[", "(", '"', "'")):
            break
        if word not in subparsers[0].choices:
            return f"{' '.join(path)}: no such command {word!r}"
        parser = subparsers[0].choices[word]
        path.append(word)
    rest = words[len(path) - 1 :]
    positionals = [
        a
        for a in parser._actions
        if not a.option_strings and not isinstance(a, argparse._SubParsersAction)
    ]
    if rest and not positionals and not rest[0].startswith(("-", "[", "(", "<")):
        return f"{' '.join(path)}: takes no positional argument, got {rest[0]}"
    known = {o for a in parser._actions for o in a.option_strings}
    known |= {o for a in root._actions for o in a.option_strings}
    unknown = sorted({f for f in FLAG.findall(command) if f not in known})
    if unknown:
        return f"{' '.join(path)}: unknown option(s) {', '.join(unknown)}"
    return None


def parse_error(argv: List[str]) -> Optional[str]:
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
        try:
            build_parser().parse_args(argv)
        except SystemExit as exc:
            if exc.code not in (0, None):
                lines = stderr.getvalue().strip().splitlines()
                return re.sub(r"\x1b\[[0-9;]*m", "", lines[-1]) if lines else "parse error"
    return None


def broken_examples() -> List[str]:
    broken = []
    for example in all_examples():
        if SYNOPSIS.search(example.command):
            error = synopsis_error(example.command)
        else:
            argv = to_argv(example.command)
            error = parse_error(argv) if argv is not None else None
        if error:
            broken.append(f"{example}\n      -> {error}")
    return broken


@pytest.mark.docs
def test_examples_are_found():
    """Guards the extractor itself: an empty result would pass vacuously."""
    assert len(all_examples()) > 250


@pytest.mark.docs
def test_every_documented_example_parses():
    broken = broken_examples()
    assert not broken, f"{len(broken)} documented examples don't parse:\n" + "\n".join(broken)


@pytest.mark.docs
@pytest.mark.parametrize(
    "command",
    [
        'zotero-cli item inspect "ITEMKEY"',  # positional key; it's --key
        "zotero-cli tag rename --old a --new b",  # no such verb
        'zotero-cli slr decide --key K --vote "include"',  # choices are upper-case
    ],
)
def test_checker_rejects_broken_concrete_examples(command):
    argv = to_argv(command)
    assert argv is not None and parse_error(argv)


@pytest.mark.docs
@pytest.mark.parametrize(
    "command",
    [
        "zotero-cli rag ingest --collection NAME [--all]",  # unknown flag in a synopsis
        'zotero-cli item transfer "ITEMKEY" --target-group G [--delete-source]',
        "zotero-cli slr frobnicate [options]",
    ],
)
def test_checker_rejects_broken_synopses(command):
    assert synopsis_error(command)


@pytest.mark.docs
def test_checker_accepts_valid_forms():
    assert parse_error(to_argv('zotero-cli item inspect --key "K" | jq .') or ["x"]) is None
    assert synopsis_error("zotero-cli item hydrate (--key KEY | --all) [--execute]") is None
    assert to_argv("zotero-cli system verify --file <archive.zaf>") == ["system", "verify", "--file", "1"]
