from unittest.mock import Mock
import pytest
from zotero_cli.core.services.slr_service import (
    ScreeningPhase, SnowballingPhase, ExtractionPhase, SynthesisPhase
)

@pytest.fixture
def mock_screening_service():
    return Mock()

def test_screening_phase_execute_success(mock_screening_service):
    phase = ScreeningPhase(mock_screening_service)
    mock_screening_service.record_decision.return_value = True
    
    result = phase.execute(
        item_key="K1",
        decision="INCLUDE",
        code="C1",
        reason="Good",
        agent="test-agent",
        persona="test-persona",
        phase="full_text"
    )
    
    assert result is True
    mock_screening_service.record_decision.assert_called_once()

def test_screening_phase_execute_missing_args(mock_screening_service):
    phase = ScreeningPhase(mock_screening_service)
    with pytest.raises(ValueError, match="item_key, decision, and code are required"):
        phase.execute(item_key="K1")

def test_screening_phase_validate(mock_screening_service):
    phase = ScreeningPhase(mock_screening_service)
    assert phase.validate() is True

def test_placeholder_phases():
    # Execute and validate on placeholders to cover empty methods
    for phase_cls in [SnowballingPhase, ExtractionPhase, SynthesisPhase]:
        p = phase_cls()
        p.execute()
        assert p.validate() is True