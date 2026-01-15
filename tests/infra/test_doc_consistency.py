import re
from pathlib import Path
from zotero_cli.cli.base import CommandRegistry
import zotero_cli.cli.commands  # Trigger registration
import pytest

def get_registered_commands():
    """Extracts all registered command names and their subcommands."""
    commands = {}
    for cmd in CommandRegistry.get_commands():
        # This is simplified; assuming commands handle their own subcommands logic internally
        # for a rigorous check we might need to instantiate them or inspect their args.
        # But for now, let's track the top-level commands.
        commands[cmd.name] = cmd
    return commands

def get_markdown_content(filepath):
    """Reads content from a markdown file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ""

def extract_commands_from_readme(content):
    """
    Heuristic: Looks for commands in code blocks or table rows.
    Specifically targets the Command Reference table in README.md
    """
    # Naive search for `zotero-cli <cmd>`
    found_commands = set()
    
    # Pattern for table rows like: | **Category** | `command` | `subcommand` | ...
    # This is specific to our README format
    table_pattern = re.compile(r"|\s*`?([a-z]+)`?\s*|\s*(`?([a-z-]+)`?)?\s*|")
    
    for line in content.split('\n'):
        match = table_pattern.search(line)
        if match:
            # Group 1 is top-level command
            # Group 3 is subcommand (optional)
            cmd = match.group(1).strip('`')
            sub = match.group(3)
            if sub:
                sub = sub.strip('`')
                found_commands.add(f"{cmd} {sub}")
            else:
                found_commands.add(cmd)
                
    return found_commands

@pytest.mark.infra
def test_readme_coverage():
    """Ensures all registered commands are mentioned in the README."""
    
    # 1. Get Code Truth
    registry_commands = CommandRegistry.get_commands()
    
    # 2. Get Doc Truth
    readme_path = Path("README.md")
    readme_content = get_markdown_content(readme_path)
    
    # We need a way to know "valid" subcommands to check rigorously.
    # For now, let's just check that the TOP LEVEL command appears in the docs.
    # To be more precise, we can manually define the expected full commands for now
    # or improve the CommandRegistry to expose subcommands meta-data.
    
    # Let's perform a simple check: Does the command name appear in the README?
    for cmd in registry_commands:
        assert cmd.name in readme_content, f"Command '{cmd.name}' is missing from README.md"

@pytest.mark.infra
def test_user_guide_coverage():
    """Ensures USER_GUIDE.md exists and mentions commands."""
    user_guide_path = Path("docs/USER_GUIDE.md")
    assert user_guide_path.exists(), "USER_GUIDE.md is missing!"
    
    content = get_markdown_content(user_guide_path)
    registry_commands = CommandRegistry.get_commands()
    
    for cmd in registry_commands:
        assert f"zotero-cli {cmd.name}" in content or f"`{cmd.name}`" in content, \
            f"Command '{cmd.name}' is not documented in USER_GUIDE.md"
