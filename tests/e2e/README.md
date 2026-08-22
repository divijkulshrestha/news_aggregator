# Playwright End-to-End Testing

This project uses Playwright with Python for end-to-end testing of the Personal News Aggregator.

## Setup

1. **Install dependencies** (already done):
   ```bash
   pip install playwright pytest-playwright pytest-asyncio
   ```

2. **Install Playwright browsers**:
   ```bash
   python -m playwright install
   ```

## Running Tests

### Run all tests:
```bash
pytest tests/e2e -v
```

### Run tests in headed mode (see the browser):
```bash
pytest tests/e2e -v --headed
```

### Run tests in a specific browser:
```bash
# Chromium (default)
pytest tests/e2e --browser chromium

# Firefox
pytest tests/e2e --browser firefox

# WebKit (Safari)
pytest tests/e2e --browser webkit
```

### Run a specific test file:
```bash
pytest tests/e2e/test_homepage.py -v
```

### Run with the convenience script:
```bash
python run_e2e_tests.py
```

> This is a Python-only Playwright suite (pytest-playwright). A parallel TypeScript
> (`@playwright/test`) suite existed briefly covering the same scenarios and was removed to
> avoid maintaining two frameworks for identical coverage.

## Test Structure

```
tests/e2e/
├── conftest.py          # Pytest configuration and fixtures
├── test_homepage.py     # Homepage UI tests
├── test_articles.py     # Article display tests
├── test_filtering.py    # Filter functionality tests
└── test_api.py          # API endpoint tests
```

## Test Coverage

### Homepage Tests
- ✅ Page loads with correct title and header
- ✅ Category filters are displayed
- ✅ Time filters are displayed
- ✅ Refresh button is visible

### Article Tests
- ✅ Articles load and display
- ✅ Article cards contain required information
- ✅ Refresh button reloads articles

### Filtering Tests
- ✅ Filter by category
- ✅ Switch between categories
- ✅ Filter by time range
- ✅ Combine category and time filters

### API Tests
- ✅ Fetch articles from API
- ✅ Filter by category via API
- ✅ Filter by time range via API
- ✅ Fetch stats from API

## Configuration

Tests are configured in `pytest.ini` with default settings. You can override these on the command line.

## Debugging

### Generate test code with Codegen:
```bash
python -m playwright codegen http://localhost:8000
```

### Run tests in debug mode:
```bash
PWDEBUG=1 pytest tests/e2e
```

### Take screenshots on failure:
```bash
pytest tests/e2e --screenshot on
```

## CI/CD Integration

Tests can be run in CI/CD pipelines. The backend server is automatically started by the test fixtures.

## Requirements

- Python 3.8+
- FastAPI backend running on port 8000
- Playwright browsers installed
