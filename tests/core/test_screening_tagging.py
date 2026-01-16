import pytest
from unittest.mock import Mock, patch
from zotero_cli.core.services.screening_service import ScreeningService

def test_record_decision_applies_tags():
    # Arrange
    mock_item_repo = Mock()
    mock_col_repo = Mock()
    mock_note_repo = Mock()
    mock_col_service = Mock()
    
    # We need a tag repo mock, but the service doesn't have it yet. 
    # This test anticipates the refactor.
    mock_tag_repo = Mock() 
    
    service = ScreeningService(
        mock_item_repo, mock_col_repo, mock_note_repo, mock_tag_repo, mock_col_service
    )
    
    mock_note_repo.create_note.return_value = True
    
    # Act
    service.record_decision(
        item_key="K1",
        decision="EXCLUDE",
        code="EC5",
        reason="Short Paper"
    )
    
    # Assert
    # We expect the service to call tag_repo.add_tags(item_key, ["rsl:phase:title_abstract", "rsl:exclude:EC5"])
    mock_tag_repo.add_tags.assert_called_with("K1", ["rsl:phase:title_abstract", "rsl:exclude:EC5"])
