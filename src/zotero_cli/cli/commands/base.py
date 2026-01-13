from abc import ABC, abstractmethod
import argparse

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
