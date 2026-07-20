from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.sandbox_service import SandboxService


@pytest.fixture
def mock_collection_repo():
    return MagicMock()


@pytest.fixture
def mock_item_repo():
    repo = MagicMock()
    repo.get_item_template.return_value = {}
    return repo


@pytest.fixture
def mock_note_repo():
    return MagicMock()


@pytest.fixture
def service(mock_collection_repo, mock_item_repo, mock_note_repo):
    return SandboxService(mock_collection_repo, mock_item_repo, mock_note_repo)


def test_create_sandbox_creates_collection_and_items(
    service, mock_collection_repo, mock_item_repo
):
    mock_collection_repo.create_collection.return_value = "COL123"
    mock_item_repo.create_generic_item.side_effect = [f"KEY{i}" for i in range(20)]

    name, created = service.create_sandbox("My Sandbox")

    mock_collection_repo.create_collection.assert_called_once_with("My Sandbox")
    assert name == "My Sandbox"
    assert created > 0
    assert mock_item_repo.create_generic_item.call_count == created

    # Every created item should be attached to the new collection.
    for call in mock_item_repo.create_generic_item.call_args_list:
        item_data = call[0][0]
        assert item_data["collections"] == ["COL123"]
        assert item_data["title"]


def test_create_sandbox_seeds_at_least_one_sdb_note(service, mock_collection_repo, mock_item_repo):
    mock_collection_repo.create_collection.return_value = "COL123"
    mock_item_repo.create_generic_item.side_effect = [f"KEY{i}" for i in range(20)]

    service.create_sandbox()

    mock_note_repo = service.note_repo
    assert mock_note_repo.create_note.call_count >= 1
    note_content = mock_note_repo.create_note.call_args_list[0][0][1]
    assert "screening_decision" in note_content
    assert "audit_version" in note_content


def test_create_sandbox_failure_raises(service, mock_collection_repo):
    mock_collection_repo.create_collection.return_value = None

    with pytest.raises(RuntimeError):
        service.create_sandbox("Bad Sandbox")


def test_create_sandbox_skips_items_that_fail_to_create(
    service, mock_collection_repo, mock_item_repo
):
    mock_collection_repo.create_collection.return_value = "COL123"
    mock_item_repo.create_generic_item.return_value = None

    name, created = service.create_sandbox()

    assert created == 0


def test_clean_sandbox_deletes_existing(service, mock_collection_repo):
    mock_collection_repo.get_collection_id_by_name.return_value = "COL123"
    mock_collection_repo.get_collection.return_value = {"key": "COL123", "version": 5}
    mock_collection_repo.delete_collection.return_value = True

    result = service.clean_sandbox("Zotero-CLI Sandbox")

    assert result is True
    mock_collection_repo.delete_collection.assert_called_once_with("COL123", 5)


def test_clean_sandbox_not_found(service, mock_collection_repo):
    mock_collection_repo.get_collection_id_by_name.return_value = None

    result = service.clean_sandbox("Nonexistent")

    assert result is False
    mock_collection_repo.delete_collection.assert_not_called()


def test_split_creator_two_words():
    result = SandboxService._split_creator("Ada Researcher")
    assert result == {"creatorType": "author", "firstName": "Ada", "lastName": "Researcher"}


def test_split_creator_single_word():
    result = SandboxService._split_creator("Cher")
    assert result == {"creatorType": "author", "firstName": "", "lastName": "Cher"}
