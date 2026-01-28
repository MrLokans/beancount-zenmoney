# beancount-zenmoney

[![PyPI version](https://img.shields.io/pypi/v/beancount-zenmoney.svg)](https://pypi.org/project/beancount-zenmoney/)
[![Python versions](https://img.shields.io/pypi/pyversions/beancount-zenmoney.svg)](https://pypi.org/project/beancount-zenmoney/)
[![License](https://img.shields.io/pypi/l/beancount-zenmoney.svg)](https://github.com/MrLokans/beancount-zenmoney/blob/main/LICENSE)
[![CI](https://github.com/MrLokans/beancount-zenmoney/actions/workflows/ci.yml/badge.svg)](https://github.com/MrLokans/beancount-zenmoney/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/MrLokans/beancount-zenmoney/graph/badge.svg)](https://codecov.io/gh/MrLokans/beancount-zenmoney)

A [Beancount](https://github.com/beancount/beancount) importer for [Zenmoney](https://zenmoney.ru/) CSV exports, built on [beangulp](https://github.com/beancount/beangulp).

## Installation

```bash
pip install beancount-zenmoney
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add beancount-zenmoney
```

## Requirements

- Python 3.10+
- Beancount 3.x
- beangulp

## Quick Start

Create an `import.py` file for beangulp (see [examples/import.py](examples/import.py) for a complete example):

```python
from beancount_zenmoney import ZenMoneyImporter

account_map = {
    "PKO - PLN": "Assets:Bank:PKO:PLN",
    "Revolut - EUR": "Assets:Bank:Revolut:EUR",
}

category_map = {
    "Salary": "Income:Salary",
    "Food / Groceries": "Expenses:Food:Groceries",
    "Gifts": {"income": "Income:Gifts", "expense": "Expenses:Gifts"},
}

importers = [
    ZenMoneyImporter(
        account_map=account_map,
        category_map=category_map,
    ),
]
```

Run with beangulp:

```bash
beangulp extract -e ledger.beancount import.py zenmoney_export.csv
```

## Configuration Options

```python
ZenMoneyImporter(
    # Required: Map Zenmoney account names to Beancount accounts
    account_map={
        "Bank - PLN": "Assets:Bank:PLN",
    },

    # Optional: Map Zenmoney categories to Beancount accounts
    category_map={
        "Food": "Expenses:Food",
    },

    # Optional: Base account for the importer (default: "Assets:ZenMoney")
    base_account="Assets:Import:ZenMoney",

    # Optional: Default expense account for unknown categories
    default_expense="Expenses:Unknown",

    # Optional: Default income account for unknown categories
    default_income="Income:Unknown",

    # Optional: Default asset account for unknown Zenmoney accounts
    default_account="Assets:Unknown",

    # Optional: Transaction flag - "*" for cleared (default), "!" for pending
    flag="!",
)
```

## Features

### Transaction Types

| Zenmoney Transaction | Beancount Result |
|---------------------|------------------|
| Expense (outcome only) | Debit from asset, credit to expense |
| Income (income only) | Credit to asset, debit from income |
| Transfer (same currency) | Debit from source, credit to destination |
| Currency exchange | Debit in one currency, credit in another with price |
| Refund | Credit to asset, debit from expense |

### Currency Exchange with Price

Currency exchanges automatically include price annotations for proper cost tracking:

```beancount
2025-12-12 * "" "FX EXCHANGE EUR/PLN 4.25"
  Assets:Bank:PKO:PLN   -4250.00 PLN
  Assets:Bank:PKO:EUR    1000.00 EUR @ 4.25 PLN
```

### Metadata Preservation

Each transaction includes metadata from ZenMoney:

```beancount
2025-12-14 * "SuperMarket" ""
  zenmoney_created: "2025-12-14 10:30:00"
  zenmoney_changed: "2025-12-14 11:00:00"
  zenmoney_category: "Food / Groceries"
  Assets:Bank:PKO:PLN       -125.50 PLN
  Expenses:Food:Groceries    125.50 PLN
```

### File Archiving Support

The importer implements `date()` and `filename()` methods for beangulp archiving:

```bash
# Archive files with automatic date-based naming
beangulp archive -e ledger.beancount import.py zenmoney_export.csv
# Creates: documents/Assets/Import/ZenMoney/2025-11-29-to-2025-12-15.zenmoney.csv
```

### Logging

Skipped rows are logged as warnings for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.WARNING)
```

## Exporting from Zenmoney

1. Open the Zenmoney app or web interface
2. Go to **Menu → Export**
3. Select **CSV** format
4. Choose the date range for export
5. Download the CSV file

The CSV file should have semicolon-separated columns including:
- `date`, `categoryName`, `payee`, `comment`
- `outcomeAccountName`, `outcome`, `outcomeCurrencyShortTitle`
- `incomeAccountName`, `income`, `incomeCurrencyShortTitle`
- `createdDate`, `changedDate`

## Example Output

Expense transaction:
```beancount
2025-12-14 * "SuperMarket" ""
  Assets:Bank:PKO:PLN       -125.50 PLN
  Expenses:Food:Groceries    125.50 PLN
```

Internal transfer:
```beancount
2025-12-11 * "" ""
  Assets:Bank:PKO:PLN       -2000.00 PLN
  Assets:Cash:PLN            2000.00 PLN
```

Income transaction:
```beancount
2025-12-15 * "ACME CORP" "DECEMBER SALARY"
  Assets:Bank:PKO:PLN    15000.00 PLN
  Income:Salary         -15000.00 PLN
```

## Development

### Setup

```bash
git clone https://github.com/MrLokans/beancount-zenmoney.git
cd beancount-zenmoney
make install
```

### Releasing

The package is automatically published to PyPI when a version tag is pushed:

```bash
make release VERSION=0.2.0
```

This script will:
- Run all checks (lint, format, typecheck, tests)
- Validate the version format and ensure the tag doesn't exist
- Update version in `pyproject.toml` and `__init__.py`
- Commit, tag, and push to remote

### Available Commands

```bash
make install              # Install dependencies
make test                 # Run tests
make lint                 # Run linter
make format               # Format code (ruff check --fix + ruff format)
make typecheck            # Run type checker
make check                # Run all checks (lint, format-check, typecheck, test)
make build                # Build package
make clean                # Clean build artifacts
make release VERSION=X.Y.Z  # Create and push a release
```

### Running Tests

```bash
make test
```

Tests use pytest with fixtures for sample CSV data. Test coverage is reported automatically.

## License

MIT License - see [LICENSE](LICENSE) for details.
