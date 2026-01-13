from typing import Dict, Type
from .commands.base import BaseCommand

class CommandRegistry:
    _commands: Dict[str, Type[BaseCommand]] = {}

    @classmethod
    def register(cls, command_cls: Type[BaseCommand]):
        command = command_cls() # Instantiate to get properties
        cls._commands[command.name] = command_cls
        return command_cls

    @classmethod
    def get_commands(cls):
        return cls._commands.items()
