# beancount-zenmoney

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

## Usage

### Basic Setup

Create an `import.py` file for beangulp:

```python
from beancount_zenmoney import ZenMoneyImporter

# Map your Zenmoney account names to Beancount accounts
account_map = {
    "PKO - PLN": "Assets:Bank:PKO:PLN",
    "PKO - EUR": "Assets:Bank:PKO:EUR",
    "Cash - PLN": "Assets:Cash:PLN",
    "Revolut - EUR": "Assets:Bank:Revolut:EUR",
}

# Map Zenmoney categories to Beancount expense/income accounts
category_map = {
    "Salary": "Income:Salary",
    "Food": "Expenses:Food",
    "Food / Groceries": "Expenses:Food:Groceries",
    "Food / Restaurants": "Expenses:Food:Restaurants",
    "Transport": "Expenses:Transport",
    "Transport / Taxi": "Expenses:Transport:Taxi",
    "Utilities": "Expenses:Housing:Utilities",
    "Entertainment": "Expenses:Entertainment",
}

importers = [
    ZenMoneyImporter(
        account_map=account_map,
        category_map=category_map,
    ),
]
```

### Running the Importer

```bash
# Extract transactions from a Zenmoney CSV export
beangulp extract -e ledger.beancount import.py zenmoney_export.csv

# Identify which importer matches a file
beangulp identify import.py zenmoney_export.csv

# Archive imported files
beangulp archive -e ledger.beancount import.py zenmoney_export.csv
```

### Configuration Options

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
)
```

### Transaction Types

The importer handles different transaction types:

| Zenmoney Transaction | Beancount Result |
|---------------------|------------------|
| Expense (outcome only) | Debit from asset, credit to expense |
| Income (income only) | Credit to asset, debit from income |
| Transfer (same currency) | Debit from source, credit to destination |
| Currency exchange | Debit in one currency, credit in another |
| Refund | Credit to asset, debit from expense |

### Example Output

A Zenmoney expense transaction:
```
2025-12-14 * "SuperMarket" ""
  Assets:Bank:PKO:PLN  -1250.00 PLN
  Expenses:Food:Groceries   1250.00 PLN
```

A currency exchange:
```
2025-12-12 * "" "FX EXCHANGE EUR/PLN"
  Assets:Bank:PKO:PLN  -42500.00 PLN
  Assets:Bank:PKO:EUR    500.00 EUR
```

An internal transfer:
```
2025-12-11 * "" ""
  Assets:Bank:PKO:PLN  -20000.00 PLN
  Assets:Cash:PLN           20000.00 PLN
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

## Development

### Setup

```bash
git clone https://github.com/yourusername/beancount-zenmoney.git
cd beancount-zenmoney
make install
```

### Available Commands

```bash
make install    # Install dependencies
make test       # Run tests
make lint       # Run linter
make format     # Format code (ruff check --fix + ruff format)
make typecheck  # Run type checker
make check      # Run all checks (lint, format-check, typecheck, test)
make build      # Build package
make clean      # Clean build artifacts
```

### Running Tests

```bash
make test
```

Tests use pytest with fixtures for sample CSV data. Test coverage is reported automatically.

## License

MIT License - see [LICENSE](LICENSE) for details.
