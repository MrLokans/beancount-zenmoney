"""Zenmoney CSV importer for Beancount.

This module provides a beangulp-based importer for Zenmoney CSV exports.
"""

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.data import Posting, Transaction
from beangulp import Importer

# Expected headers in ZenMoney CSV export
ZENMONEY_HEADERS = frozenset(
    {
        "date",
        "categoryName",
        "payee",
        "comment",
        "outcomeAccountName",
        "outcome",
        "outcomeCurrencyShortTitle",
        "incomeAccountName",
        "income",
        "incomeCurrencyShortTitle",
        "createdDate",
        "changedDate",
    }
)


class ZenMoneyImporter(Importer):
    """Importer for ZenMoney CSV exports."""

    def __init__(
        self,
        account_map: dict[str, str],
        category_map: dict[str, str] | None = None,
        base_account: str = "Assets:ZenMoney",
        default_expense: str = "Expenses:Unknown",
        default_income: str = "Income:Unknown",
        default_account: str | None = None,
    ) -> None:
        self._account_map = account_map
        self._category_map = category_map or {}
        self._base_account = base_account
        self._default_expense = default_expense
        self._default_income = default_income
        self._default_account = default_account

    def identify(self, filepath: str) -> bool:
        path = Path(filepath)
        if path.suffix.lower() != ".csv":
            return False

        try:
            with open(filepath, encoding="utf-8-sig") as f:
                # Read just the header line
                first_line = f.readline().strip()
                if not first_line:
                    return False

                # Parse header
                headers = set(first_line.split(";"))
                # Check if required ZenMoney headers are present
                return ZENMONEY_HEADERS.issubset(headers)
        except (OSError, UnicodeDecodeError):
            return False

    def account(self, filepath: str) -> data.Account:
        return self._base_account

    def extract(self, filepath: str, existing: data.Entries) -> data.Entries:
        entries: data.Entries = []

        with open(filepath, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")

            for row in reader:
                txn = self._parse_row(row, filepath)
                if txn:
                    entries.append(txn)

        return entries

    def _parse_row(self, row: dict[str, str], filepath: str) -> Transaction | None:
        date_str = row.get("date", "").strip()
        if not date_str:
            return None

        try:
            txn_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None

        outcome_str = row.get("outcome", "0").strip() or "0"
        income_str = row.get("income", "0").strip() or "0"

        try:
            outcome = Decimal(outcome_str)
            income = Decimal(income_str)
        except (ValueError, TypeError):
            return None

        outcome_account_name = row.get("outcomeAccountName", "").strip()
        income_account_name = row.get("incomeAccountName", "").strip()
        outcome_currency = row.get("outcomeCurrencyShortTitle", "").strip()
        income_currency = row.get("incomeCurrencyShortTitle", "").strip()

        category = row.get("categoryName", "").strip()
        payee = row.get("payee", "").strip()
        comment = row.get("comment", "").strip()

        postings = self._create_postings(
            outcome=outcome,
            income=income,
            outcome_account_name=outcome_account_name,
            income_account_name=income_account_name,
            outcome_currency=outcome_currency,
            income_currency=income_currency,
            category=category,
        )

        if not postings:
            return None

        # Build narration from payee and comment
        narration = comment if comment else ""
        txn_payee = payee if payee else (comment if not narration else None)

        # Create transaction metadata
        meta = data.new_metadata(filepath, 0)

        return Transaction(
            meta=meta,
            date=txn_date,
            flag="*",
            payee=txn_payee,
            narration=narration,
            tags=frozenset(),
            links=frozenset(),
            postings=postings,
        )

    def _create_postings(
        self,
        outcome: Decimal,
        income: Decimal,
        outcome_account_name: str,
        income_account_name: str,
        outcome_currency: str,
        income_currency: str,
        category: str,
    ) -> list[Posting]:
        postings: list[Posting] = []

        # Map ZenMoney accounts to Beancount accounts
        outcome_account = self._map_account(outcome_account_name)
        income_account = self._map_account(income_account_name)

        # Determine transaction type
        has_outcome = outcome > 0
        has_income = income > 0

        if has_outcome and has_income:
            # Transfer between accounts (internal transfer or currency exchange)
            # Outcome posting (money leaving)
            postings.append(
                Posting(
                    outcome_account,
                    Amount(-outcome, outcome_currency),
                    None,
                    None,
                    None,
                    None,
                )
            )
            # Income posting (money arriving)
            postings.append(
                Posting(
                    income_account,
                    Amount(income, income_currency),
                    None,
                    None,
                    None,
                    None,
                )
            )
        elif has_outcome:
            # Expense transaction
            expense_account = self._map_category(category, is_expense=True)
            postings.append(
                Posting(
                    outcome_account,
                    Amount(-outcome, outcome_currency),
                    None,
                    None,
                    None,
                    None,
                )
            )
            postings.append(
                Posting(
                    expense_account,
                    Amount(outcome, outcome_currency),
                    None,
                    None,
                    None,
                    None,
                )
            )
        elif has_income:
            # Income transaction
            income_category_account = self._map_category(category, is_expense=False)
            postings.append(
                Posting(
                    income_account,
                    Amount(income, income_currency),
                    None,
                    None,
                    None,
                    None,
                )
            )
            postings.append(
                Posting(
                    income_category_account,
                    Amount(-income, income_currency),
                    None,
                    None,
                    None,
                    None,
                )
            )

        return postings

    def _map_account(self, zenmoney_account: str) -> str:
        if zenmoney_account in self._account_map:
            return self._account_map[zenmoney_account]
        if self._default_account:
            return self._default_account
        # Auto-generate account name from ZenMoney name
        safe_name = zenmoney_account.replace(" ", "").replace("-", ":")
        return f"Assets:{safe_name}"

    def _map_category(self, category: str, is_expense: bool) -> str:
        if category in self._category_map:
            return self._category_map[category]
        return self._default_expense if is_expense else self._default_income
