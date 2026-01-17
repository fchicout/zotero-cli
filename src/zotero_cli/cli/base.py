import argparse
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type


class BaseCommand(ABC):
    """
    Abstract base class for all CLI commands.
    Enforces the Command Pattern.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the command (used in parser)."""
        pass

    @property
    @abstractmethod
    def help(self) -> str:
        """Help text for the command."""
        pass

    @abstractmethod
    def register_args(self, parser: argparse.ArgumentParser):
        """Register arguments for this command's subparser."""
        pass

    @abstractmethod
    def execute(self, args: argparse.Namespace):
        """Execute the command logic."""
        pass


class CommandRegistry:
    _commands: Dict[str, BaseCommand] = {}

    @classmethod
    def register(cls, command_cls: Type[BaseCommand]):
        """Decorator to register a command class."""
        command = command_cls()
        cls._commands[command.name] = command
        return command_cls

    @classmethod
    def get_commands(cls) -> List[BaseCommand]:
        """Returns all registered command instances."""
        return list(cls._commands.values())

    @classmethod
    def get_command(cls, name: str) -> Optional[BaseCommand]:
        """Returns a specific command instance by name."""
        return cls._commands.get(name)
