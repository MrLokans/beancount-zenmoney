# beancount-zenmoney

A [Beancount](https://github.com/beancount/beancount) importer for [Zenmoney](https://zenmoney.ru/) CSV exports.

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

```python
from beancount_zenmoney import ZenmoneyImporter

# Configure the importer
importer = ZenmoneyImporter(
    account="Assets:Bank:Checking",
    # Add configuration options
)
```

## Exporting from Zenmoney

1. Open Zenmoney app
2. Go to Settings > Export
3. Select CSV format
4. Export your transactions

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
make format     # Format code
make typecheck  # Run type checker
make check      # Run all checks (lint, typecheck, test)
make build      # Build package
make clean      # Clean build artifacts
```

## License

MIT License - see [LICENSE](LICENSE) for details.
