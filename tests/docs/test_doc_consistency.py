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
    # Find project root relative to this file (tests/docs/test_doc_consistency.py)
    project_root = Path(__file__).parent.parent.parent
    docs_dir = project_root / "docs/commands"

    assert docs_dir.exists(), f"Documentation directory '{docs_dir}' is missing!"

    registry = get_registered_commands()
    for noun in registry:
        if noun == "maint":
            continue  # Skip deprecated
        doc_file = docs_dir / f"{noun}.md"
        assert doc_file.exists(), f"Missing documentation file for noun '{noun}': {doc_file}"


@pytest.mark.docs
def test_verb_coverage():
    """Ensures every verb for a noun is documented in its markdown file."""
    project_root = Path(__file__).parent.parent.parent
    docs_dir = project_root / "docs/commands"
    registry = get_registered_commands()

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
    project_root = Path(__file__).parent.parent.parent
    readme_path = project_root / "README.md"
    registry = get_registered_commands()
    readme_content = get_markdown_content(readme_path)

    for noun in registry:
        if noun == "maint":
            continue
        # Flexible check for the link, allowing for styling like **[`noun`](...)**
        pattern = re.compile(rf"\[`?{noun}`?\]\(docs/commands/{noun}.md\)")
        assert pattern.search(readme_content), (
            f"Noun '{noun}' is missing from the README.md command index"
        )


def find_parser_paths(parser, current_path=[]):
    """Recursively walks subparsers and yields the path and the subparser."""
    subparsers_found = False
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparsers_found = True
            for choice, sub_parser in action.choices.items():
                yield from find_parser_paths(sub_parser, current_path + [choice])
    if not subparsers_found:
        yield current_path, parser


def get_all_cli_command_paths():
    """Returns a dict mapping command paths to their subparser."""
    command_paths = {}
    for cmd in CommandRegistry.get_commands():
        if cmd.name == "maint":
            continue
        parser = argparse.ArgumentParser(prog=cmd.name)
        cmd.register_args(parser)

        has_subparsers = any(isinstance(a, argparse._SubParsersAction) for a in parser._actions)
        if not has_subparsers:
            command_paths[(cmd.name,)] = parser
        else:
            for path, sub_parser in find_parser_paths(parser, [cmd.name]):
                command_paths[tuple(path)] = sub_parser
    return command_paths


def get_expected_doc_filename(path: tuple[str, ...]) -> str:
    """Maps command path tuple to documentation filename."""
    return "_".join(path[:2]) + ".md"


def extract_md_parameters(content: str) -> set[str]:
    """Parses parameter names from markdown table in Section 5, ignoring layout keywords."""
    lines = content.splitlines()
    in_section = False
    table_lines = []
    for line in lines:
        if line.startswith("## 5. Parameter Matrix"):
            in_section = True
            continue
        elif in_section and line.startswith("## "):
            break
        if in_section:
            table_lines.append(line)

    params = set()
    ignored = {"flag", "type", "description", "ergonomic", "note", "string", "choice", "path", "integer", "boolean", "command", "float", "none"}

    for line in table_lines:
        if "|" not in line or "---" in line:
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if not cells:
            continue
        # Check if this is the header row
        if any(c.lower() in {"flag", "command"} for c in cells):
            continue

        for cell in cells[:2]:
            clean_cell = cell.replace("`", "")
            # Find flags (like --doi, -d)
            flags = re.findall(r"--?[a-zA-Z0-9_-]+", clean_cell)
            for f in flags:
                if f.lower() not in ignored:
                    params.add(f)
            # If the cell is a single word, it is likely a positional argument (like query or key)
            words = clean_cell.split()
            if len(words) == 1 and not words[0].startswith("-"):
                w = re.sub(r"[^a-zA-Z0-9_-]", "", words[0])
                if w and w.lower() not in ignored:
                    params.add(w)
    return params


@pytest.mark.docs
def test_help_specs_presence():
    """Ensures every registered CLI command endpoint has a help spec file."""
    project_root = Path(__file__).parent.parent.parent
    specs_dir = project_root / "docs/help_specs"

    cli_paths = get_all_cli_command_paths()
    missing = []

    for path in cli_paths:
        doc_name = get_expected_doc_filename(path)
        if not (specs_dir / doc_name).exists():
            missing.append(f"Command '{' '.join(path)}' expects '{doc_name}'")

    # Group and uniq missing to prevent duplicates for multi-level commands sharing a doc
    missing = sorted(list(set(missing)))
    assert not missing, "Absent documentation files:\n" + "\n".join(missing)


@pytest.mark.docs
def test_help_specs_compliance():
    """Ensures help specs strictly adhere to the 7-section layout specification."""
    project_root = Path(__file__).parent.parent.parent
    specs_dir = project_root / "docs/help_specs"

    required_sections = [
        r"^# DOC-SPEC:",
        r"^## 1\. Classification",
        r"^## 2\. Logic Flow \(Visual Synthesis\)",
        r"^## 3\. Synopsis",
        r"^## 4\. Description \(Instructional Architecture\)",
        r"^## 5\. Parameter Matrix",
        r"^## 6\. Scenario-Based Examples \(Cognitive Anchors\)",
        r"^## 7\. Cognitive Safeguards"
    ]

    non_compliant = []

    for filepath in specs_dir.glob("*.md"):
        if filepath.name == "DOC_TEMPLATE.md":
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. Structural Check
        for section in required_sections:
            if not re.search(section, content, re.MULTILINE):
                non_compliant.append(f"'{filepath.name}' is missing section matching: '{section}'")

        # 2. Classification Level Validation
        classification_section = re.search(r"## 1\. Classification\n(.*?)(?=\n##|$)", content, re.DOTALL)
        if classification_section:
            class_text = classification_section.group(1)
            valid_levels = ["🔴 DESTRUCTIVE", "🟡 MODIFICATION", "🟢 READ-ONLY"]
            if not any(level in class_text for level in valid_levels):
                non_compliant.append(f"'{filepath.name}' does not state a valid Classification Level.")

    assert not non_compliant, "Template compliance errors:\n" + "\n".join(non_compliant)


@pytest.mark.docs
def test_help_specs_drift():
    """Detects drift between Python command options and Markdown parameter matrices."""
    project_root = Path(__file__).parent.parent.parent
    specs_dir = project_root / "docs/help_specs"

    cli_paths = get_all_cli_command_paths()
    drifts = []

    # Group parsers by their expected doc filename
    doc_to_paths: dict[str, list[tuple[tuple[str, ...], argparse.ArgumentParser]]] = {}
    for path, parser in cli_paths.items():
        doc_name = get_expected_doc_filename(path)
        if doc_name not in doc_to_paths:
            doc_to_paths[doc_name] = []
        doc_to_paths[doc_name].append((path, parser))

    for doc_name, path_parsers in doc_to_paths.items():
        doc_path = specs_dir / doc_name
        if not doc_path.exists():
            continue

        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse union of all argparse registered parameters for this doc
        cli_params: set[str] = set()
        for path, parser in path_parsers:
            for action in parser._actions:
                if isinstance(action, argparse._HelpAction):
                    continue
                if action.option_strings:
                    cli_params.update(action.option_strings)
                elif action.dest and action.dest != argparse.SUPPRESS:
                    cli_params.add(action.dest)

        md_params = extract_md_parameters(content)

        # Identify missing or undocumented items
        undocumented = cli_params - md_params
        deprecated_in_doc = md_params - cli_params

        # Filter out sub-verbs/actions if they appear in MD parameter table (like 'fetch', 'strip')
        for path, parser in path_parsers:
            if hasattr(parser, '_choices') and parser._choices:
                deprecated_in_doc -= set(parser._choices.keys())

        # Filter out argument names matching other sub-namespace verbs
        deprecated_in_doc -= {"fetch", "strip", "attach", "seed", "discovery", "review", "import", "status", "export", "upgrade", "reset", "edit", "inspect", "run", "retry", "list", "add", "clean", "set"}

        # We also need to ignore generic default argparse options if they leak into dest like 'verb'
        cli_params.discard('verb')
        undocumented.discard('verb')

        # Ignore sub-command verb dests (e.g. source_verb, report_verb, model_verb, list_verb, snowball_verb, sdb_verb, job_verb)
        for v in ["source_verb", "report_verb", "model_verb", "list_verb", "snowball_verb", "sdb_verb", "job_verb", "import_type", "report_type"]:
            cli_params.discard(v)
            undocumented.discard(v)

        if undocumented:
            commands_str = ", ".join([" ".join(p) for p, _ in path_parsers])
            drifts.append(f"Commands ({commands_str}) have undocumented parameters in '{doc_name}': {sorted(list(undocumented))}")
        if deprecated_in_doc:
            # Clean up the output by ignoring simple command verb names
            real_deprecated = [d for d in deprecated_in_doc if d.startswith("-") or d in cli_params]
            if real_deprecated:
                drifts.append(f"Doc '{doc_name}' references obsolete/unused options: {sorted(real_deprecated)}")

    assert not drifts, "Documentation drift detected:\n" + "\n".join(drifts)


