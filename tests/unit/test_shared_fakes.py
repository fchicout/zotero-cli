"""The shared repository fakes reject what the real interfaces don't have (Issue #389)."""

from typing import Any

import pytest


@pytest.mark.parametrize(
    "fixture_name",
    [
        "mock_gateway",
        "mock_item_repo",
        "mock_collection_repo",
        "mock_note_repo",
        "mock_tag_repo",
        "mock_attachment_repo",
    ],
)
def test_a_method_the_interface_lacks_is_an_error(
    request: pytest.FixtureRequest, fixture_name: str
) -> None:
    fake: Any = request.getfixturevalue(fixture_name)
    with pytest.raises(AttributeError):
        fake.not_a_real_method()


def test_a_real_method_is_accepted_and_checked_for_arity(mock_item_repo: Any) -> None:
    mock_item_repo.get_item.return_value = None
    assert mock_item_repo.get_item("KEY") is None
    with pytest.raises(TypeError):
        mock_item_repo.get_item("KEY", "unexpected", "extra", "arguments")
