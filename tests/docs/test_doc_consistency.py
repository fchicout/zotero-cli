import argparse
import re
from pathlib import Path

import pytest

from zotero_cli.cli.base import CommandRegistry


def get_registered_commands():
    """Extracts all registered command names and their subcommands via argparse introspection."""
    commands_map = {}
    for cmd in CommandRegistry.get_commands():
        # Create a dummy parser to extract sub-actions
        parser = argparse.ArgumentParser()
        cmd.register_args(parser)

        verbs: list[str] = []
        # Look for subparsers in the parser
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                verbs.extend(action.choices.keys())

        commands_map[cmd.name] = {"instance": cmd, "verbs": verbs}
    return commands_map


def get_markdown_content(filepath):
    """Reads content from a markdown file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


@pytest.mark.docs
def test_documentation_structure():
    """Ensures every registered noun has a corresponding file in docs/commands/."""
    registry = get_registered_commands()
    docs_dir = Path("docs/commands")

    assert docs_dir.exists(), "Documentation directory 'docs/commands/' is missing!"

    for noun in registry:
        if noun == "maint":
            continue  # Skip deprecated
        doc_file = docs_dir / f"{noun}.md"
        assert doc_file.exists(), f"Missing documentation file for noun '{noun}': {doc_file}"


@pytest.mark.docs
def test_verb_coverage():
    """Ensures every verb for a noun is documented in its markdown file."""
    registry = get_registered_commands()
    docs_dir = Path("docs/commands")

    for noun, info in registry.items():
        if noun == "maint":
            continue
        doc_file = docs_dir / f"{noun}.md"
        content = get_markdown_content(doc_file)

        for verb in info["verbs"]:
            # Look for headers or code blocks mentioning the verb
            # Example: ### `verb` or **`verb`** or zotero-cli noun verb
            pattern = re.compile(
                rf"(###\s+`{verb}`|`{noun}\s+{verb}`|\*\s+`{verb}`)", re.IGNORECASE
            )
            assert pattern.search(content), (
                f"Verb '{verb}' for noun '{noun}' is not documented in {doc_file.name}"
            )


@pytest.mark.docs
def test_readme_index_coverage():
    """Ensures the README.md index contains all registered nouns."""
    registry = get_registered_commands()
    readme_content = get_markdown_content("README.md")

    for noun in registry:
        if noun == "maint":
            continue
        # Flexible check for the link, allowing for styling like **[`noun`](...)**
        pattern = re.compile(rf"\[`?{noun}`?\]\(docs/commands/{noun}.md\)")
        assert pattern.search(readme_content), (
            f"Noun '{noun}' is missing from the README.md command index"
        )
