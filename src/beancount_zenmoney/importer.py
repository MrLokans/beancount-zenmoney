"""Zenmoney CSV importer for Beancount.

This module provides a beangulp-based importer for Zenmoney CSV exports.
"""

import csv
import datetime
import logging
from decimal import Decimal
from pathlib import Path

from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.data import Posting, Transaction
from beangulp import Importer

logger = logging.getLogger(__name__)

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
        flag: str = "*",
    ) -> None:
        self._account_map = account_map
        self._category_map = category_map or {}
        self._base_account = base_account
        self._default_expense = default_expense
        self._default_income = default_income
        self._default_account = default_account
        self._flag = flag

    def identify(self, filepath: str) -> bool:
        path = Path(filepath)
        if path.suffix.lower() != ".csv":
            return False

        try:
            with open(filepath, encoding="utf-8-sig") as f:
                first_line = f.readline().strip()
                if not first_line:
                    return False
                headers = set(first_line.split(";"))
                return ZENMONEY_HEADERS.issubset(headers)
        except (OSError, UnicodeDecodeError):
            return False

    def account(self, filepath: str) -> data.Account:
        return self._base_account

    def date(self, filepath: str) -> datetime.date | None:
        """Return the latest transaction date from the file.

        This is used by beangulp for file archiving.
        """
        dates = self._extract_dates(filepath)
        return max(dates) if dates else None

    def filename(self, filepath: str) -> str | None:
        """Return a clean filename for archiving.

        Returns a filename in the format: zenmoney-YYYY-MM-DD-to-YYYY-MM-DD.csv
        """
        dates = self._extract_dates(filepath)
        if not dates:
            return None

        min_date = min(dates)
        max_date = max(dates)

        if min_date == max_date:
            return f"zenmoney-{min_date}.csv"
        return f"zenmoney-{min_date}-to-{max_date}.csv"

    def _extract_dates(self, filepath: str) -> list[datetime.date]:
        """Extract all transaction dates from the file."""
        dates: list[datetime.date] = []
        try:
            with open(filepath, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    date_str = row.get("date", "").strip()
                    if date_str:
                        try:
                            txn_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                            dates.append(txn_date)
                        except ValueError:
                            continue
        except (OSError, UnicodeDecodeError):
            pass
        return dates

    def extract(self, filepath: str, existing: data.Entries) -> data.Entries:
        entries: data.Entries = []

        with open(filepath, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")

            for lineno, row in enumerate(reader, start=2):  # Start at 2 (after header)
                txn = self._parse_row(row, filepath, lineno)
                if txn:
                    entries.append(txn)
                else:
                    # Log skipped rows
                    date_str = row.get("date", "")
                    payee = row.get("payee", "")
                    logger.warning("Skipped row %d: date=%r, payee=%r", lineno, date_str, payee)

        return entries

    def _parse_row(self, row: dict[str, str], filepath: str, lineno: int) -> Transaction | None:
        date_str = row.get("date", "").strip()
        if not date_str:
            return None

        try:
            txn_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None

        outcome_str = row.get("outcome", "0").strip().replace(",", ".") or "0"
        income_str = row.get("income", "0").strip().replace(",", ".") or "0"

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

        # Get timestamps
        created_date = row.get("createdDate", "").strip()
        changed_date = row.get("changedDate", "").strip()

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

        # Create transaction metadata with line number and timestamps
        meta = data.new_metadata(filepath, lineno)
        if created_date:
            meta["zenmoney_created"] = created_date
        if changed_date:
            meta["zenmoney_changed"] = changed_date
        if category:
            meta["zenmoney_category"] = category

        return Transaction(
            meta=meta,
            date=txn_date,
            flag=self._flag,
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

        outcome_account = self._map_account(outcome_account_name)
        income_account = self._map_account(income_account_name)

        has_outcome = outcome > 0
        has_income = income > 0

        if has_outcome and has_income:
            # Transfer between accounts or currency exchange
            is_currency_exchange = outcome_currency != income_currency

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
            if is_currency_exchange:
                # Add price annotation for currency exchange
                # Price = outcome / income (how much outcome currency per 1 income currency)
                price_per_unit = outcome / income
                postings.append(
                    Posting(
                        income_account,
                        Amount(income, income_currency),
                        None,
                        Amount(price_per_unit, outcome_currency),  # price
                        None,
                        None,
                    )
                )
            else:
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
        safe_name = zenmoney_account.replace(" ", "").replace("-", ":")
        return f"Assets:{safe_name}"

    def _map_category(self, category: str, is_expense: bool) -> str:
        if category in self._category_map:
            return self._category_map[category]
        return self._default_expense if is_expense else self._default_income
