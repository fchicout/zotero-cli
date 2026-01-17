import sys
from typing import Any, Optional, Type

import pytest

# Add project root to path
sys.path.append(".")

BadgeGenerator: Optional[Type[Any]] = None

try:
    from scripts.generate_badges import BadgeGenerator as ActualBadgeGenerator

    BadgeGenerator = ActualBadgeGenerator
except ImportError:
    pass


@pytest.mark.unit
def test_badge_generator_exists():
    assert BadgeGenerator is not None, (
        "BadgeGenerator class not found in scripts/generate_badges.py"
    )


@pytest.mark.unit
def test_generate_coverage_badge():
    assert BadgeGenerator is not None
    gen = BadgeGenerator()
    # Mocking coverage data
    mock_data = {"totals": {"percent_covered": 81.5}}
    badge = gen.create_coverage_badge(mock_data)
    assert "81%" in badge
    assert "green" in badge


@pytest.mark.unit
def test_generate_ruff_badge():
    assert BadgeGenerator is not None
    gen = BadgeGenerator()
    # 0 errors
    badge = gen.create_ruff_badge(0)
    assert "passing" in badge
    assert "brightgreen" in badge

    # errors
    badge = gen.create_ruff_badge(5)
    assert "5_errors" in badge
    assert "red" in badge


@pytest.mark.unit
def test_generate_mypy_badge():
    assert BadgeGenerator is not None
    gen = BadgeGenerator()
    badge = gen.create_mypy_badge(True)
    assert "passing" in badge
    assert "brightgreen" in badge

    badge = gen.create_mypy_badge(False)
    assert "failing" in badge
    assert "red" in badge
