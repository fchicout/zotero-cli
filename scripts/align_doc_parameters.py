import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, "src")

# Import all commands to trigger registration
from zotero_cli.cli.base import CommandRegistry


def find_parser_paths(parser, current_path=[]):
    subparsers_found = False
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparsers_found = True
            for choice, sub_parser in action.choices.items():
                yield from find_parser_paths(sub_parser, current_path + [choice])
    if not subparsers_found:
        yield current_path, parser

def get_all_cli_command_paths():
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

def get_expected_doc_filename(path):
    return "_".join(path[:2]) + ".md"

def get_action_details(action):
    # Determine name/flag
    if action.option_strings:
        name = ", ".join(action.option_strings)
    else:
        name = action.dest

    # Determine type
    if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
        type_str = "Boolean"
    elif action.type is int:
        type_str = "Integer"
    elif action.type is float:
        type_str = "Float"
    else:
        type_str = "String"

    # Description
    desc = action.help or "N/A"

    # Ergonomic note
    if getattr(action, "required", False):
        note = "Required."
    else:
        default = action.default
        if default is not None and default != argparse.SUPPRESS:
            note = f"Optional. Default: {default}."
        else:
            note = "Optional."

    return name, type_str, desc, note

def main():
    cli_paths = get_all_cli_command_paths()
    specs_dir = Path("docs/help_specs")

    # Group actions by doc name
    doc_actions: dict[str, dict[str, tuple[str, str, str, str]]] = {}
    for path, parser in cli_paths.items():
        doc_name = get_expected_doc_filename(path)
        if doc_name not in doc_actions:
            doc_actions[doc_name] = {}

        for action in parser._actions:
            if isinstance(action, argparse._HelpAction):
                continue
            if action.dest == "verb" or action.dest in ["source_verb", "report_verb", "model_verb", "list_verb", "snowball_verb", "sdb_verb", "job_verb", "import_type", "report_type"]:
                continue

            name, type_str, desc, note = get_action_details(action)
            # Avoid duplicate flags in the same shared doc
            doc_actions[doc_name][name] = (name, type_str, desc, note)

    for doc_name, actions in doc_actions.items():
        doc_path = specs_dir / doc_name
        if not doc_path.exists():
            continue

        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Build new Markdown table
        table_lines = [
            "## 5. Parameter Matrix",
            "| Flag / Parameter | Type | Description | Ergonomic Note |",
            "| :--- | :--- | :--- | :--- |"
        ]

        for name, type_str, desc, note in sorted(actions.values()):
            table_lines.append(f"| `{name}` | {type_str} | {desc} | {note} |")

        new_table_str = "\n".join(table_lines) + "\n"

        # Replace the Parameter Matrix section in Markdown
        pattern = r"## 5\. Parameter Matrix\n(.*?)(?=\n## 6|\Z)"
        content_new, count = re.subn(pattern, new_table_str, content, flags=re.DOTALL)

        if count > 0:
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write(content_new)
            print(f"Updated parameter matrix in {doc_name}")
        else:
            print(f"Failed to find Parameter Matrix section in {doc_name}")

if __name__ == "__main__":
    main()
