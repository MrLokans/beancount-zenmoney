"""Tests for the Zenmoney importer."""

from beancount_zenmoney import __version__


def test_version() -> None:
    """Test that version is defined."""
    assert __version__ == "0.1.0"


# TODO: Add importer tests
