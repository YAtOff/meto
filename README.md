# Meto

![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)
![Poetry](https://img.shields.io/badge/poetry-1.8.0-black.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**Meto** is a Python-based framework designed to build, manage, and orchestrate autonomous AI agents. It provides a robust architecture for managing agent lifecycles, tool execution, and interactions with Large
Language Models (LLMs) using a modern, type-safe Python stack.

## 🚀 Features

- **Agent Orchestration:** Comprehensive engine for managing agent lifecycles, sessions, and command loops.
- **Tool System:** Flexible tool runner and schema definitions for extending agent capabilities (e.g., via OpenAI function calling).
- **Rich CLI:** A modern, intuitive command-line interface built with [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/).
- **Type Safety:** Strict type validation and settings management using [Pydantic](https://docs.pydantic.dev/) and [Basedpyright](https://github.com/DetachHead/basedpyright).
- **Developer Experience:** Pre-configured with [Ruff](https://docs.astral.sh/ruff/) (linting), [Black](https://black.readthedocs.io/) (formatting), and [Pytest](https://docs.pytest.org/).

## 🛠️ Tech Stack

- **Language:** Python 3.13
- **AI / LLM:**
  - `openai` (LLM interaction)
- **Data & Config:**
  - `pydantic`, `pydantic-settings` (Validation & Settings)
- **CLI / UI:**
  - `typer` (CLI framework)
  - `rich` (Terminal output)
  - `prompt_toolkit` (Interactive prompts)
- **Utilities:**
  - `tenacity` (Retry logic)
  - `httpx`, `requests` (HTTP clients)
- **Development:**
  - **Build:** Poetry
  - **Testing:** Pytest, Pytest-Sugar
  - **Linting:** Ruff
  - **Formatting:** Black
  - **Type Checking:** Basedpyright

## 📁 Project Structure

The project follows a standard Python layout using `src/` for code organization.

```
meto/
├── .venv/                  # Virtual Environment
├── dist/                   # Distribution files
├── src/meto/               # Application Source Code
│   ├── agent/            # Core Agent Engine
│   │   ├── agent.py       # Main Agent class definition
│   │   ├── agent_loop.py  # Execution loop logic
│   │   ├── agent_loader.py # Loading agent configurations
│   │   ├── agent_registry.py # Registry for managing agents
│   │   ├── session.py      # Session management
│   │   ├── tool_runner.py  # Tool execution logic
│   │   ├── tool_schema.py  # Tool schemas (OpenAI compatible)
│   │   ├── context.py      # Agent state/context
│   │   ├── prompt.py       # Prompt construction
│   │   └── ...
│   ├── cli.py             # Command-line interface (Typer)
│   ├── conf.py            # Application configuration
│   └── __main__.py       # Module entry point
├── tests/                  # Test Suite (Pytest)
│   ├── agent/            # Unit tests for agent logic
│   ├── test_placeholder.py
│   └── ...
├── pyproject.toml         # Poetry config, dependencies & tools
├── ruff.toml              # Ruff linter configuration
├── pyproject.toml         # Project metadata
└── README.md               # This file
```

## 📦 Installation

### Prerequisites

- Python 3.13+
- [Poetry](https://python-poetry.org/) (recommended)

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd meto
   ```

2. **Install dependencies using Poetry:**
   ```bash
   poetry install
   ```

3. **Activate the virtual environment:**
   ```bash
   poetry shell
   ```

## 🏃 Usage

### Command Line Interface

Meto exposes its functionality primarily through a CLI built with Typer.

```bash
# Run the application
python -m meto

# Or use poetry to run the command
poetry run meto

# Display help (depending on CLI structure)
poetry run meto --help
```

### Python API

You can also import Meto directly into your Python scripts:

```python
from meto.agent import Agent

# Initialize and run an agent
agent = Agent(name="my-agent")
agent.run()
```

## 🧪 Testing

Run the test suite using Pytest.

```bash
# Run all tests
pytest

# Run with sugar output (configured in pyproject.toml)
pytest
```

## 🛠️ Development

This project uses a modern Python toolchain.

- **Linting:**
  ```bash
  ruff check .
  ```

- **Formatting:**
  ```bash
  black .
  ```

- **Type Checking:**
  ```bash
  basedpyright src
  ```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
```
Here is the content for a `README.md` file based on the project structure analysis. You can copy the text below, save it as `README.md`, and place it in the root directory of your project.

```markdown
# Meto

![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)
![Poetry](https://img.shields.io/badge/poetry-1.8.0-black.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**Meto** is a Python-based framework designed to build, manage, and orchestrate autonomous AI agents. It provides a robust architecture for managing agent lifecycles, tool execution, and interactions with Large Language Models (LLMs) using a modern, type-safe Python stack.

## 🚀 Features

- **Agent Orchestration:** Comprehensive engine for managing agent lifecycles, sessions, and command loops.
- **Tool System:** Flexible tool runner and schema definitions for extending agent capabilities (e.g., via OpenAI function calling).
- **Rich CLI:** A modern, intuitive command-line interface built with [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/).
- **Type Safety:** Strict type validation and settings management using [Pydantic](https://docs.pydantic.dev/) and [Basedpyright](https://github.com/DetachHead/basedpyright).
- **Developer Experience:** Pre-configured with [Ruff](https://docs.astral.sh/ruff/) (linting), [Black](https://black.readthedocs.io/) (formatting), and [Pytest](https://docs.pytest.org/).

## 🛠️ Tech Stack

- **Language:** Python 3.13
- **AI / LLM:**
  - `openai` (LLM interaction)
- **Data & Config:**
  - `pydantic`, `pydantic-settings` (Validation & Settings)
- **CLI / UI:**
  - `typer` (CLI framework)
  - `rich` (Terminal output)
  - `prompt_toolkit` (Interactive prompts)
- **Utilities:**
  - `tenacity` (Retry logic)
  - `httpx`, `requests` (HTTP clients)
- **Development:**
  - **Build:** Poetry
  - **Testing:** Pytest, Pytest-Sugar
  - **Linting:** Ruff
  - **Formatting:** Black
  - **Type Checking:** Basedpyright

## 📁 Project Structure

The project follows a standard Python layout using `src/` for code organization.

```
meto/
├── .venv/                  # Virtual Environment
├── dist/                   # Distribution files
├── src/meto/               # Application Source Code
│   ├── agent/            # Core Agent Engine
│   │   ├── agent.py       # Main Agent class definition
│   │   ├── agent_loop.py  # Execution loop logic
│   │   ├── agent_loader.py # Loading agent configurations
│   │   ├── agent_registry.py # Registry for managing agents
│   │   ├── session.py      # Session management
│   │   ├── tool_runner.py  # Tool execution logic
│   │   ├── tool_schema.py  # Tool schemas (OpenAI compatible)
│   │   ├── context.py      # Agent state/context
│   │   ├── prompt.py       # Prompt construction
│   │   └── ...
│   ├── cli.py             # Command-line interface (Typer)
│   ├── conf.py            # Application configuration
│   └── __main__.py       # Module entry point
├── tests/                  # Test Suite (Pytest)
│   ├── agent/            # Unit tests for agent logic
│   ├── test_placeholder.py
│   └── ...
├── pyproject.toml         # Poetry config, dependencies & tools
├── ruff.toml              # Ruff linter configuration
├── pyproject.toml         # Project metadata
└── README.md               # This file
```

## 📦 Installation

### Prerequisites

- Python 3.13+
- [Poetry](https://python-poetry.org/) (recommended)

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd meto
   ```

2. **Install dependencies using Poetry:**
   ```bash
   poetry install
   ```

3. **Activate the virtual environment:**
   ```bash
   poetry shell
   ```

## 🏃 Usage

### Command Line Interface

Meto exposes its functionality primarily through a CLI built with Typer.

```bash
# Run the application
python -m meto

# Or use poetry to run the command
poetry run meto

# Display help (depending on CLI structure)
poetry run meto --help
```

### Python API

You can also import Meto directly into your Python scripts:

```python
from meto.agent import Agent

# Initialize and run an agent
agent = Agent(name="my-agent")
agent.run()
```

## 🧪 Testing

Run the test suite using Pytest.

```bash
# Run all tests
pytest

# Run with sugar output (configured in pyproject.toml)
pytest
```

## 🛠️ Development

This project uses a modern Python toolchain.

- **Linting:**
  ```bash
  ruff check .
  ```

- **Formatting:**
  ```bash
  black .
  ```

- **Type Checking:**
  ```bash
  basedpyright src
  ```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
