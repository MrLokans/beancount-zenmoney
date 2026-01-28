"""Pytest fixtures for Zenmoney importer tests."""

from pathlib import Path

import pytest

from beancount_zenmoney.importer import DualCategoryMapValue


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_csv_path(fixtures_dir: Path) -> str:
    """Return path to the sample test CSV file as a string."""
    return str(fixtures_dir / "test_transactions.csv")


@pytest.fixture
def sample_csv_content(sample_csv_path: str) -> str:
    """Return the content of the sample CSV file."""
    return Path(sample_csv_path).read_text(encoding="utf-8")


@pytest.fixture
def account_map() -> dict[str, str]:
    """Return a mapping from ZenMoney account names to Beancount accounts."""
    return {
        "MainBank - PLN": "Assets:Bank:MainBank:PLN",
        "MainBank - EUR": "Assets:Bank:MainBank:EUR",
        "DigitalWallet - PLN": "Assets:Bank:DigitalWallet:PLN",
        "DigitalWallet - EUR": "Assets:Bank:DigitalWallet:EUR",
    }


@pytest.fixture
def category_map() -> dict[str, str | DualCategoryMapValue]:
    """Return a mapping from ZenMoney categories to Beancount accounts."""
    return {
        "Salary": "Income:Salary",
        "Food / Groceries": "Expenses:Food:Groceries",
        "Food / Restaurant": "Expenses:Food:Restaurant",
        "Food / Coffee": "Expenses:Food:Coffee",
        "Food / Delivery": "Expenses:Food:Delivery",
        "Transport / Taxi": "Expenses:Transport:Taxi",
        "Subscriptions": "Expenses:Subscriptions",
        "Health & Fitness": "Expenses:Health:Fitness",
        "Housing / Rent": "Expenses:Housing:Rent",
        "Bank Fees": "Expenses:Bank:Fees",
        "Gifts": "Expenses:Gifts",
        "Travel / Accommodation": "Expenses:Travel:Accommodation",
        "Family / Support": "Expenses:Family:Support",
        "Electronics": "Expenses:Shopping:Electronics",
        "Cloud Services": "Expenses:Subscriptions:Cloud",
        "Entertainment / Games": "Expenses:Entertainment:Games",
        "DualCategory": {"income": "Income:Dual", "expense": "Expenses:Dual"},
    }
