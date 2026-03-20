from zotero_cli.cli.tui.extraction_tui import ExtractionTUI
from zotero_cli.cli.tui.screening_tui import ScreeningTUI
from zotero_cli.cli.tui.snowball_tui import SnowballReviewTUI
from zotero_cli.core.interfaces import (
    ExtractionService,
    OpenerService,
    ScreeningService,
    SnowballGraphService,
)

class TUIFactory:
    """
    Decouples CLI commands from TUI instantiation logic.
    """
    @staticmethod
    def get_screening_tui(service: ScreeningService) -> ScreeningTUI:
        return ScreeningTUI(service)

    @staticmethod
    def get_extraction_tui(service: ExtractionService, opener: OpenerService) -> ExtractionTUI:
        return ExtractionTUI(service, opener)

    @staticmethod
    def get_snowball_tui(service: SnowballGraphService) -> SnowballReviewTUI:
        return SnowballReviewTUI(service)
