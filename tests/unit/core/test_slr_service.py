from unittest.mock import Mock

from zotero_cli.core.services.slr_service import (
    ExtractionPhase,
    ScreeningPhase,
    SnowballingPhase,
    SynthesisPhase,
)


def test_slr_phases_instantiation():
    """Verifies that all SLR phases can be instantiated and have basic methods."""
    mock_service = Mock()
    phases = [
        ScreeningPhase(service=mock_service),
        SnowballingPhase(),
        ExtractionPhase(),
        SynthesisPhase(),
    ]

    for phase in phases:
        assert phase.validate() is True
