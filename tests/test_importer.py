"""Tests for the Zenmoney importer."""

import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from beancount.core.amount import Amount
from beancount.core.data import Transaction

from beancount_zenmoney.importer import DualCategoryMapValue, ZenMoneyImporter


class TestZenMoneyImporterIdentify:
    """Tests for the identify method."""

    def test_identify_valid_csv(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        assert importer.identify(sample_csv_path) is True

    def test_identify_wrong_extension(self, tmp_path: Path, account_map: dict[str, str]) -> None:
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("some content")
        importer = ZenMoneyImporter(account_map=account_map)
        assert importer.identify(str(txt_file)) is False

    def test_identify_wrong_csv_format(self, tmp_path: Path, account_map: dict[str, str]) -> None:
        csv_file = tmp_path / "other.csv"
        csv_file.write_text("col1;col2;col3\nval1;val2;val3\n")
        importer = ZenMoneyImporter(account_map=account_map)
        assert importer.identify(str(csv_file)) is False

    def test_identify_zenmoney_headers(self, tmp_path: Path, account_map: dict[str, str]) -> None:
        csv_file = tmp_path / "zen.csv"
        csv_file.write_text(
            "date;categoryName;payee;comment;outcomeAccountName;outcome;"
            "outcomeCurrencyShortTitle;incomeAccountName;income;"
            "incomeCurrencyShortTitle;createdDate;changedDate;qrCode\n"
        )
        importer = ZenMoneyImporter(account_map=account_map)
        assert importer.identify(str(csv_file)) is True


class TestZenMoneyImporterAccount:
    """Tests for the account method."""

    def test_account_returns_base_account(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map, base_account="Assets:Import:ZenMoney")
        assert importer.account(sample_csv_path) == "Assets:Import:ZenMoney"

    def test_account_default(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        assert importer.account(sample_csv_path) == "Assets:ZenMoney"


class TestZenMoneyImporterExtract:
    """Tests for the extract method."""

    def test_extract_returns_list(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(sample_csv_path, existing=[])
        assert isinstance(entries, list)
        assert len(entries) > 0

    def test_extract_transaction_count(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(sample_csv_path, existing=[])
        # Test CSV has 20 rows of data
        transactions = [e for e in entries if isinstance(e, Transaction)]
        assert len(transactions) == 21

    def test_extract_simple_expense(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # Find the groceries transaction (125.50 PLN on 2025-12-14)
        grocery_txn = next(
            (
                t
                for t in transactions
                if t.date == date(2025, 12, 14)
                and any(p.units == Amount(Decimal("-125.50"), "PLN") for p in t.postings if p.units)
            ),
            None,
        )
        assert grocery_txn is not None
        assert grocery_txn.payee == "SuperMarket XYZ"
        assert len(grocery_txn.postings) == 2

    def test_extract_income_transaction(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # Find the salary transaction (15000 PLN on 2025-12-15)
        salary_txn = next(
            (
                t
                for t in transactions
                if t.date == date(2025, 12, 15)
                and any(p.units == Amount(Decimal("15000"), "PLN") for p in t.postings if p.units)
            ),
            None,
        )
        assert salary_txn is not None
        assert salary_txn.payee == "ACME CORP SP ZOO"
        assert "DECEMBER SALARY" in (salary_txn.narration or "")

    def test_extract_internal_transfer(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # Find the internal transfer (2000 PLN on 2025-12-11)
        transfer_txn = next(
            (
                t
                for t in transactions
                if t.date == date(2025, 12, 11)
                and any(p.units == Amount(Decimal("2000"), "PLN") for p in t.postings if p.units)
            ),
            None,
        )
        assert transfer_txn is not None
        # Internal transfers should have postings to both accounts
        accounts = {p.account for p in transfer_txn.postings}
        assert "Assets:Bank:MainBank:PLN" in accounts
        assert "Assets:Bank:DigitalWallet:PLN" in accounts
        assert len(transfer_txn.postings) == 2

    def test_extract_currency_exchange(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # Find the currency exchange (4250 PLN -> 1000 EUR on 2025-12-12)
        fx_txn = next(
            (
                t
                for t in transactions
                if t.date == date(2025, 12, 12)
                and any(p.units == Amount(Decimal("1000"), "EUR") for p in t.postings if p.units)
            ),
            None,
        )
        assert fx_txn is not None
        # Should have PLN outflow and EUR inflow
        currencies = {p.units.currency for p in fx_txn.postings if p.units}
        assert "PLN" in currencies
        assert "EUR" in currencies

    def test_extract_refund_transaction(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # Find the refund (35.50 PLN on 2025-12-01)
        refund_txn = next(
            (
                t
                for t in transactions
                if t.date == date(2025, 12, 1)
                and any(p.units == Amount(Decimal("35.50"), "PLN") for p in t.postings if p.units)
            ),
            None,
        )
        assert refund_txn is not None
        assert refund_txn.payee == "Refund Store"

    def test_extract_eur_transaction(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # Find EUR subscription (9.99 EUR on 2025-12-13)
        eur_txn = next(
            (
                t
                for t in transactions
                if t.date == date(2025, 12, 13)
                and any(p.units == Amount(Decimal("-9.99"), "EUR") for p in t.postings if p.units)
            ),
            None,
        )
        assert eur_txn is not None
        assert eur_txn.payee == "CloudService Monthly"

    def test_extract_with_category_mapping(
        self,
        sample_csv_path: str,
        account_map: dict[str, str],
        category_map: dict[str, str | DualCategoryMapValue],
    ) -> None:
        importer = ZenMoneyImporter(account_map=account_map, category_map=category_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # Find the rent transaction
        rent_txn = next((t for t in transactions if t.date == date(2025, 12, 9)), None)
        assert rent_txn is not None
        expense_accounts = {p.account for p in rent_txn.postings if p.account.startswith("Expenses:")}
        assert "Expenses:Housing:Rent" in expense_accounts

    def test_extract_unknown_category_uses_default(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(
            account_map=account_map,
            category_map={},  # Empty map - all categories unknown
            default_expense="Expenses:Uncategorized",
        )
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # All expense transactions should use default account
        for txn in transactions:
            for posting in txn.postings:
                if posting.account.startswith("Expenses:"):
                    assert posting.account == "Expenses:Uncategorized"

    def test_extract_preserves_transaction_date(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        dates = {t.date for t in transactions}
        assert date(2025, 12, 15) in dates  # Salary
        assert date(2025, 11, 29) in dates  # Games purchase

    def test_extract_with_typeddict_category_mapping_expense(
        self, tmp_path: Path, account_map: dict[str, str], category_map: dict[str, str | DualCategoryMapValue]
    ) -> None:
        """Test extraction of expense with a TypedDict category mapping."""
        csv_file = tmp_path / "zen_typeddict_expense.csv"
        csv_file.write_text(
            "date;categoryName;payee;comment;outcomeAccountName;outcome;"
            "outcomeCurrencyShortTitle;incomeAccountName;income;"
            "incomeCurrencyShortTitle;createdDate;changedDate;qrCode\n"
            '2025-12-01;"DualCategory";"Shop A";;"MainBank - PLN";"100";PLN;'
            '"MainBank - PLN";"0";PLN;"2025-12-01 00:00:00";"2025-12-01 00:00:00";\n',
            encoding="utf-8",
        )
        importer = ZenMoneyImporter(account_map=account_map, category_map=category_map)
        entries = importer.extract(str(csv_file), existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        assert len(transactions) == 1
        expense_posting = next((p for p in transactions[0].postings if p.account.startswith("Expenses:")), None)
        assert expense_posting is not None
        assert expense_posting.account == "Expenses:Dual"

    def test_extract_with_typeddict_category_mapping_income(
        self, tmp_path: Path, account_map: dict[str, str], category_map: dict[str, str | DualCategoryMapValue]
    ) -> None:
        """Test extraction of income with a TypedDict category mapping."""
        csv_file = tmp_path / "zen_typeddict_income.csv"
        csv_file.write_text(
            "date;categoryName;payee;comment;outcomeAccountName;outcome;"
            "outcomeCurrencyShortTitle;incomeAccountName;income;"
            "incomeCurrencyShortTitle;createdDate;changedDate;qrCode\n"
            '2025-12-02;"DualCategory";"Client B";;"MainBank - PLN";"0";PLN;'
            '"MainBank - PLN";"200";PLN;"2025-12-02 00:00:00";"2025-12-02 00:00:00";\n',
            encoding="utf-8",
        )
        importer = ZenMoneyImporter(account_map=account_map, category_map=category_map)
        entries = importer.extract(str(csv_file), existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        assert len(transactions) == 1
        income_posting = next((p for p in transactions[0].postings if p.account.startswith("Income:")), None)
        assert income_posting is not None
        assert income_posting.account == "Income:Dual"


class TestZenMoneyImporterEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_payee_uses_comment(self, tmp_path: Path, account_map: dict[str, str]) -> None:
        csv_file = tmp_path / "zen.csv"
        csv_file.write_text(
            "date;categoryName;payee;comment;outcomeAccountName;outcome;"
            "outcomeCurrencyShortTitle;incomeAccountName;income;"
            "incomeCurrencyShortTitle;createdDate;changedDate;qrCode\n"
            '2025-12-01;"Bank Fees";;"ACCOUNT FEE";"MainBank - PLN";"10";PLN;'
            '"MainBank - PLN";"0";PLN;"2025-12-01 00:00:00";"2025-12-01 00:00:00";\n',
            encoding="utf-8",
        )
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(str(csv_file), existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        assert len(transactions) == 1
        assert "ACCOUNT FEE" in (transactions[0].narration or transactions[0].payee or "")

    def test_handles_utf8_bom(self, tmp_path: Path, account_map: dict[str, str]) -> None:
        csv_file = tmp_path / "zen.csv"
        content = (
            "\ufeffdate;categoryName;payee;comment;outcomeAccountName;outcome;"
            "outcomeCurrencyShortTitle;incomeAccountName;income;"
            "incomeCurrencyShortTitle;createdDate;changedDate;qrCode\n"
            '2025-12-01;"Food";"Test Store";;"MainBank - PLN";"50";PLN;'
            '"MainBank - PLN";"0";PLN;"2025-12-01 00:00:00";"2025-12-01 00:00:00";\n'
        )
        csv_file.write_text(content, encoding="utf-8")
        importer = ZenMoneyImporter(account_map=account_map)

        assert importer.identify(str(csv_file)) is True
        entries = importer.extract(str(csv_file), existing=[])
        assert len(entries) == 1

    def test_unknown_account_raises_or_uses_default(self, tmp_path: Path, account_map: dict[str, str]) -> None:
        csv_file = tmp_path / "zen.csv"
        csv_file.write_text(
            "date;categoryName;payee;comment;outcomeAccountName;outcome;"
            "outcomeCurrencyShortTitle;incomeAccountName;income;"
            "incomeCurrencyShortTitle;createdDate;changedDate;qrCode\n"
            '2025-12-01;"Food";"Store";;"UnknownBank - USD";"50";USD;'
            '"UnknownBank - USD";"0";USD;"2025-12-01 00:00:00";"2025-12-01 00:00:00";\n',
            encoding="utf-8",
        )
        importer = ZenMoneyImporter(account_map=account_map, default_account="Assets:Unknown")
        entries = importer.extract(str(csv_file), existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        assert len(transactions) == 1
        accounts = {p.account for p in transactions[0].postings}
        assert "Assets:Unknown" in accounts

    def test_unknown_account_falls_back_to_assets_unknown(
        self, tmp_path: Path, account_map: dict[str, str], caplog: pytest.LogCaptureFixture
    ) -> None:
        csv_file = tmp_path / "zen.csv"
        csv_file.write_text(
            "date;categoryName;payee;comment;outcomeAccountName;outcome;"
            "outcomeCurrencyShortTitle;incomeAccountName;income;"
            "incomeCurrencyShortTitle;createdDate;changedDate;qrCode\n"
            '2025-12-01;;;;"mBank - PLN";"100";PLN;'
            '"MainBank - PLN";"100";PLN;"2025-12-01 00:00:00";"2025-12-01 00:00:00";\n'
            '2025-12-02;;;;"mBank - PLN";"50";PLN;'
            '"MainBank - PLN";"50";PLN;"2025-12-02 00:00:00";"2025-12-02 00:00:00";\n',
            encoding="utf-8",
        )
        importer = ZenMoneyImporter(account_map=account_map)
        with caplog.at_level(logging.WARNING):
            entries = importer.extract(str(csv_file), existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        assert len(transactions) == 2
        assert {p.account for p in transactions[0].postings} == {"Assets:Unknown", "Assets:Bank:MainBank:PLN"}
        assert sum("mBank - PLN" in r.getMessage() for r in caplog.records) == 1

    def test_amounts_padded_to_two_decimals(self, tmp_path: Path, account_map: dict[str, str]) -> None:
        csv_file = tmp_path / "zen.csv"
        csv_file.write_text(
            "date;categoryName;payee;comment;outcomeAccountName;outcome;"
            "outcomeCurrencyShortTitle;incomeAccountName;income;"
            "incomeCurrencyShortTitle;createdDate;changedDate;qrCode\n"
            '2025-12-01;;;;"Bank - USD";"100";USD;'
            '"Bank - BYN";"197";BYN;"2025-12-01 00:00:00";"2025-12-01 00:00:00";\n'
            '2025-12-02;"Food";"Store";;"Bank - USD";"102.8698";USD;'
            '"Bank - USD";"0";USD;"2025-12-02 00:00:00";"2025-12-02 00:00:00";\n',
            encoding="utf-8",
        )
        accounts = account_map | {"Bank - USD": "Assets:Bank:USD", "Bank - BYN": "Assets:Bank:BYN"}
        importer = ZenMoneyImporter(account_map=accounts)
        entries = importer.extract(str(csv_file), existing=[])
        exchange, expense = sorted((e for e in entries if isinstance(e, Transaction)), key=lambda t: t.date)

        outcome, income = exchange.postings
        assert outcome.units.number.as_tuple() == Decimal("-100.00").as_tuple()
        assert income.units.number.as_tuple() == Decimal("197.00").as_tuple()
        assert income.price == Amount(Decimal("100") / Decimal("197"), "USD")
        assert expense.postings[0].units.number.as_tuple() == Decimal("-102.8698").as_tuple()

    def test_transfer_with_fee_books_difference_to_default_expense(
        self, tmp_path: Path, account_map: dict[str, str]
    ) -> None:
        csv_file = tmp_path / "zen.csv"
        csv_file.write_text(
            "date;categoryName;payee;comment;outcomeAccountName;outcome;"
            "outcomeCurrencyShortTitle;incomeAccountName;income;"
            "incomeCurrencyShortTitle;createdDate;changedDate;qrCode\n"
            '2025-12-01;;;;"MainBank - PLN";"51.2";PLN;'
            '"DigitalWallet - PLN";"50";PLN;"2025-12-01 00:00:00";"2025-12-01 00:00:00";\n',
            encoding="utf-8",
        )
        importer = ZenMoneyImporter(account_map=account_map)
        (txn,) = [e for e in importer.extract(str(csv_file), existing=[]) if isinstance(e, Transaction)]

        assert len(txn.postings) == 3
        assert txn.postings[2].account == "Expenses:Unknown"
        assert txn.postings[2].units == Amount(Decimal("1.20"), "PLN")

    def _write_row(self, tmp_path: Path, date: str, outcome: str) -> Path:
        csv_file = tmp_path / "zen.csv"
        csv_file.write_text(
            "date;categoryName;payee;comment;outcomeAccountName;outcome;"
            "outcomeCurrencyShortTitle;incomeAccountName;income;"
            "incomeCurrencyShortTitle;createdDate;changedDate;qrCode\n"
            f'{date};"Food";"Store";;"MainBank - PLN";"{outcome}";PLN;'
            '"MainBank - PLN";"0";PLN;"2025-12-01 00:00:00";"2025-12-01 00:00:00";\n',
            encoding="utf-8",
        )
        return csv_file

    def test_unparseable_amount_raises_with_line(self, tmp_path: Path, account_map: dict[str, str]) -> None:
        csv_file = self._write_row(tmp_path, "2025-12-01", "1 000")
        importer = ZenMoneyImporter(account_map=account_map)

        with pytest.raises(ValueError, match=r":2: invalid amount outcome='1 000'"):
            importer.extract(str(csv_file), existing=[])

    def test_unparseable_date_raises_with_line(self, tmp_path: Path, account_map: dict[str, str]) -> None:
        csv_file = self._write_row(tmp_path, "2025-13-45", "50")
        importer = ZenMoneyImporter(account_map=account_map)

        with pytest.raises(ValueError, match=r":2: invalid date '2025-13-45'"):
            importer.extract(str(csv_file), existing=[])


class TestCurrencyExchange:
    """Tests for currency exchange handling."""

    def test_currency_exchange_has_price_annotation(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # Find the currency exchange (4250 PLN -> 1000 EUR on 2025-12-12)
        fx_txn = next(
            (t for t in transactions if t.date == date(2025, 12, 12)),
            None,
        )
        assert fx_txn is not None

        # Find the EUR posting - it should have a price
        eur_posting = next(
            (p for p in fx_txn.postings if p.units and p.units.currency == "EUR"),
            None,
        )
        assert eur_posting is not None
        assert eur_posting.price is not None
        assert eur_posting.price.currency == "PLN"
        # 4250 PLN / 1000 EUR = 4.25 PLN per EUR
        assert eur_posting.price.number == Decimal("4.25")


class TestDateMethod:
    """Tests for the date() method."""

    def test_date_returns_latest_transaction_date(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        file_date = importer.date(sample_csv_path)
        # The test CSV has transactions from 2025-11-29 to 2025-12-15
        assert file_date == date(2025, 12, 15)

    def test_date_returns_none_for_empty_file(self, tmp_path: Path, account_map: dict[str, str]) -> None:
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text(
            "date;categoryName;payee;comment;outcomeAccountName;outcome;"
            "outcomeCurrencyShortTitle;incomeAccountName;income;"
            "incomeCurrencyShortTitle;createdDate;changedDate;qrCode\n"
        )
        importer = ZenMoneyImporter(account_map=account_map)
        assert importer.date(str(csv_file)) is None


class TestFilenameMethod:
    """Tests for the filename() method."""

    def test_filename_returns_clean_name(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        filename = importer.filename(sample_csv_path)
        assert filename is not None
        assert filename.endswith(".csv")
        assert "zenmoney" in filename.lower()

    def test_filename_includes_date_range(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        filename = importer.filename(sample_csv_path)
        assert filename is not None
        # Should contain dates in some form
        assert "2025" in filename


class TestMetadata:
    """Tests for transaction metadata."""

    def test_line_numbers_in_metadata(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # Line numbers should be sequential starting from 2 (after header)
        line_numbers = [t.meta.get("lineno") for t in transactions]
        assert all(ln is not None and ln >= 2 for ln in line_numbers)
        # First transaction should be on line 2
        assert 2 in line_numbers

    def test_timestamps_in_metadata(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # Check first transaction has timestamp metadata
        first_txn = transactions[0]
        assert "zenmoney_created" in first_txn.meta
        assert "zenmoney_changed" in first_txn.meta

    def test_category_in_metadata(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # Find a transaction with a category
        categorized_txn = next(
            (t for t in transactions if t.meta.get("zenmoney_category")),
            None,
        )
        assert categorized_txn is not None


class TestFlagConfiguration:
    """Tests for transaction flag configuration."""

    def test_default_flag_is_cleared(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        assert all(t.flag == "*" for t in transactions)

    def test_custom_flag(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map, flag="!")
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        assert all(t.flag == "!" for t in transactions)


class TestAutoTagging:
    """Tests for auto-tagging based on category."""

    def test_no_tags_without_tag_map(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        importer = ZenMoneyImporter(account_map=account_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        assert all(len(t.tags) == 0 for t in transactions)

    def test_single_tag_from_category(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        tag_map = {"Food / Groceries": "groceries"}
        importer = ZenMoneyImporter(account_map=account_map, tag_map=tag_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # Find the groceries transaction (SuperMarket XYZ on 2025-12-14)
        grocery_txn = next(
            (t for t in transactions if t.date == date(2025, 12, 14) and t.payee == "SuperMarket XYZ"),
            None,
        )
        assert grocery_txn is not None
        assert "groceries" in grocery_txn.tags

    def test_multiple_tags_from_category(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        tag_map = {"Food / Groceries": {"groceries", "food", "essentials"}}
        importer = ZenMoneyImporter(account_map=account_map, tag_map=tag_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # Find the groceries transaction
        grocery_txn = next(
            (t for t in transactions if t.date == date(2025, 12, 14) and t.payee == "SuperMarket XYZ"),
            None,
        )
        assert grocery_txn is not None
        assert "groceries" in grocery_txn.tags
        assert "food" in grocery_txn.tags
        assert "essentials" in grocery_txn.tags

    def test_no_tag_for_unmapped_category(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        tag_map = {"Food / Groceries": "groceries"}  # Only groceries mapped
        importer = ZenMoneyImporter(account_map=account_map, tag_map=tag_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # Find a restaurant transaction (not in tag_map)
        restaurant_txn = next(
            (t for t in transactions if t.meta.get("zenmoney_category") == "Food / Restaurant"),
            None,
        )
        assert restaurant_txn is not None
        assert len(restaurant_txn.tags) == 0

    def test_multiple_categories_with_tags(self, sample_csv_path: str, account_map: dict[str, str]) -> None:
        tag_map = {
            "Food / Groceries": "groceries",
            "Food / Restaurant": "dining",
            "Salary": "income",
        }
        importer = ZenMoneyImporter(account_map=account_map, tag_map=tag_map)
        entries = importer.extract(sample_csv_path, existing=[])
        transactions = [e for e in entries if isinstance(e, Transaction)]

        # Check groceries
        grocery_txn = next(
            (t for t in transactions if t.meta.get("zenmoney_category") == "Food / Groceries"),
            None,
        )
        assert grocery_txn is not None
        assert "groceries" in grocery_txn.tags

        # Check restaurant
        restaurant_txn = next(
            (t for t in transactions if t.meta.get("zenmoney_category") == "Food / Restaurant"),
            None,
        )
        assert restaurant_txn is not None
        assert "dining" in restaurant_txn.tags

        # Check salary
        salary_txn = next(
            (t for t in transactions if t.meta.get("zenmoney_category") == "Salary"),
            None,
        )
        assert salary_txn is not None
        assert "income" in salary_txn.tags
