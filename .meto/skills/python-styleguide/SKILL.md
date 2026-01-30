---
name: python-styleguide
description: Comprehensive Python coding conventions and style guidelines (PEP 8, type hints, docstrings)
---

# Python Style Guide

You are an expert in Python best practices and code quality. Use this guide when writing or reviewing Python code.

## Core Principles

- **Readability first**: Python prioritizes human readability over machine efficiency
- **PEP 8 compliance**: Follow the official Python style guide
- **Type hints**: Use built-in generic types (PEP 585) for Python 3.9+
- **Docstrings**: Provide PEP 257-compliant documentation for all public functions/classes

## Type Annotations (PEP 585)

**Preferred** - built-in generic types (Python 3.9+):
```python
def process_items(items: list[str]) -> dict[str, int]:
    names: set[str] = set()
    pairs: tuple[str, int] = ("key", 42)
```

**Avoid** - legacy `typing` module equivalents:
```python
from typing import List, Dict  # Don't use these
def process_items(items: List[str]) -> Dict[str, int]:  # Old style
```

**When to use `typing` module**:
- Types without built-in equivalents: `Callable`, `Iterable`, `TypeGuard`, `TypedDict`, `Literal`, `Protocol`
- Advanced constructs: `Union`, `Optional`, `ParamSpec`, `TypeVar`

```python
from typing import Callable, Iterable, Optional

def transform(data: Iterable[str], mapper: Callable[[str], int]) -> Optional[int]:
    ...
```

## Function Design

**Signatures**:
```python
def fetch_data(url: str, timeout: int = 30, retries: int = 3) -> dict[str, Any]:
    """Fetch data from remote API.

    Args:
        url: Target endpoint URL
        timeout: Connection timeout in seconds
        retries: Number of retry attempts

    Returns:
        Parsed JSON response as dictionary

    Raises:
        TimeoutError: If request exceeds timeout
        ValueError: If response is invalid JSON
    """
    ...
```

**Requirements**:
- Descriptive names using snake_case
- Type hints on all parameters and return values
- Docstring immediately after `def` (PEP 257)
- Handle edge cases explicitly with clear error messages

## Code Style (PEP 8)

**Line length**: Max 79 characters (hard limit 99 for CI)

**Indentation**: 4 spaces per level (no tabs)

**Imports**:
```python
# 1. Standard library
import os
import sys
from pathlib import Path

# 2. Third-party
import requests
from pydantic import BaseModel

# 3. Local
from meto.agent import Agent
from meto.conf import Settings
```

**Naming conventions**:
- `snake_case` for functions, variables, modules
- `PascalCase` for classes
- `UPPER_CASE` for constants
- `_leading_underscore` for protected/internal

**Spacing**:
```python
# Good
result = func(arg1, arg2)

# Bad
result=func(arg1,arg2)
```

## Function Structure

**Break down complexity**:
```python
# Too complex - refactor
def process_large_file(path: str) -> list[dict]:
    # 50 lines of parsing, validation, transformation...

# Better - separate concerns
def read_file(path: str) -> str: ...
def parse_content(content: str) -> list[dict]: ...
def validate_data(data: list[dict]) -> list[dict]: ...

def process_large_file(path: str) -> list[dict]:
    content = read_file(path)
    parsed = parse_content(content)
    return validate_data(parsed)
```

## Docstrings (PEP 257)

**One-line docstring**:
```python
def calculate_sum(numbers: list[int]) -> int:
    """Return the sum of a list of numbers."""
    return sum(numbers)
```

**Multi-line docstring**:
```python
def connect_to_database(
    host: str,
    port: int,
    credentials: Credentials,
) -> Connection:
    """Establish a connection to the database server.

    Args:
        host: Database server hostname or IP address
        port: TCP port number for connection
        credentials: Authentication credentials

    Returns:
        Active database connection object

    Raises:
        ConnectionError: If server is unreachable
        AuthError: If credentials are invalid

    Example:
        >>> creds = Credentials(user="admin", key="secret")
        >>> conn = connect_to_database("localhost", 5432, creds)
    """
    ...
```

## Error Handling

**Be specific**:
```python
# Good
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    raise ValueError(f"Invalid JSON: {e}") from e

# Bad
try:
    data = json.loads(raw)
except Exception:  # Too broad
    pass
```

**Document edge cases**:
```python
def divide(numerator: float, denominator: float) -> float:
    """Divide two numbers.

    Raises:
        ZeroDivisionError: If denominator is zero
    """
    if denominator == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return numerator / denominator
```

## Testing

**Critical paths need tests**:
```python
def test_parse_invalid_json():
    """Test that invalid JSON raises ValueError."""
    with pytest.raises(ValueError):
        parse_content("{invalid json}")
```

**Test edge cases**:
- Empty inputs: `""`, `[]`, `None`
- Invalid types: wrong types passed to typed functions
- Boundary values: `0`, `-1`, `MAX_INT`
- Large datasets: performance considerations

## Maintainability

**Document design decisions**:
```python
# Using OrderedDict instead of dict for Python 3.6 compatibility
# despite dict being ordered since 3.7
from collections import OrderedDict
```

**Comment external dependencies**:
```python
# pydantic used for runtime validation (not just type checking)
from pydantic import BaseModel, validator
```

**Why over what**:
```python
# Pre-compile regex for performance (called in tight loop)
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
```

## Review Checklist

When reviewing Python code, verify:

**Essential**:
- [ ] PEP 8 compliant (ruff check)
- [ ] Type hints on all public functions
- [ ] Docstrings for public functions/classes
- [ ] Built-in generic types used (`list[str]` not `List[str]`)

**Important**:
- [ ] Functions under 20 lines (or refactored)
- [ ] Clear exception handling with specific error types
- [ ] Edge cases documented and tested
- [ ] External dependencies commented

**Nice to have**:
- [ ] Algorithm complexity noted for non-trivial implementations
- [ ] Example usage in docstrings
- [ ] Type coverage >80%
