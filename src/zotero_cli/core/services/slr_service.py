from abc import ABC, abstractmethod
from typing import Any

from zotero_cli.core.services.screening_service import ScreeningService


class SLRPhase(ABC):
    """
    Abstract base class for a phase in the Systematic Literature Review lifecycle.
    """

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """
        Execute the phase logic.
        """
        pass

    @abstractmethod
    def validate(self) -> bool:
        """
        Validate if the phase is ready to execute or if outputs are consistent.
        """
        pass


class ScreeningPhase(SLRPhase):
    """
    Handles Title/Abstract and Full-text screening.
    Bridges to the existing ScreeningService.
    """

    def __init__(self, service: ScreeningService):
        self.service = service

    def execute(self, **kwargs: Any) -> Any:
        """
        Executes a screening decision.
        Required kwargs: item_key, decision, code.
        """
        raw_item_key = kwargs.get("item_key")
        raw_decision = kwargs.get("decision")
        raw_code = kwargs.get("code")

        if raw_item_key is None or raw_decision is None or raw_code is None:
            raise ValueError("item_key, decision, and code are required for screening.")

        item_key = str(raw_item_key)
        decision = str(raw_decision)
        code = str(raw_code)

        return self.service.record_decision(
            item_key=item_key,
            decision=decision,
            code=code,
            reason=str(kwargs.get("reason")) if kwargs.get("reason") is not None else None,
            source_collection=str(kwargs.get("source_collection"))
            if kwargs.get("source_collection") is not None
            else None,
            target_collection=str(kwargs.get("target_collection"))
            if kwargs.get("target_collection") is not None
            else None,
            agent=str(kwargs.get("agent", "zotero-cli")),
            persona=str(kwargs.get("persona", "unknown")),
            phase=str(kwargs.get("phase", "title_abstract")),
            evidence=str(kwargs.get("evidence")) if kwargs.get("evidence") is not None else None,
        )

    def validate(self) -> bool:
        # Placeholder for complex validation logic
        return True


class SnowballingPhase(SLRPhase):
    """
    Handles Forward and Backward snowballing (Wohlin 2014).
    """

    def execute(self, **kwargs: Any) -> Any:
        pass

    def validate(self) -> bool:
        return True


class ExtractionPhase(SLRPhase):
    """
    Handles data extraction from selected papers.
    """

    def execute(self, **kwargs: Any) -> Any:
        pass

    def validate(self) -> bool:
        return True


class SynthesisPhase(SLRPhase):
    """
    Handles data synthesis and mapping.
    """

    def execute(self, **kwargs: Any) -> Any:
        pass

    def validate(self) -> bool:
        return True
