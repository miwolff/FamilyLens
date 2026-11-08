# FamilyLens – Copilot Instructions

FamilyLens is a **local-first intelligent photo search application** that lets users search their personal photo library using natural language queries.

## Readme

The [README.md](../README.md) file provides an overview of the project, including its architecture, quick start guide, API endpoints, and user requirements. It serves as the main entry point for understanding the project and how to get started.

## User Requirements

See [docs/user_requirements.md](../docs/user_requirements.md) for detailed user requirements. If you get new requirements or new requests, always add them to that file and check if all requirements are consistent. Check for updates before starting work on any new features. 

## Project goals

- **Local-first**: all processing and data stays on the user's machine — no cloud uploads of photos or metadata
- **Natural language search**: users query their photo library in plain English (e.g., "birthday party last summer", "photos with grandma")

## Version control

- Use **Git** for version control
- Write clear and descriptive commit messages
- Create branches for new features and bug fixes
- Open pull requests for code review before merging to main
- Use tags to mark release versions

## Backend

### Code style

- Use **snake_case** for variable and function names
- Use **PascalCase** for class names
- Use **4 spaces** for indentation
- Write docstrings for all public functions and classes
- Keep lines under **88 characters** (enforced by `ruff format`)
- Use type hints for all function parameters and return types
- Follow PEP 8 style guidelines for Python code

### Testing

- Use **pytest** for testing
- Write tests for all new features and bug fixes
- Aim for high test coverage, especially for critical functionality
- Use descriptive test names that clearly indicate what is being tested
- Run tests frequently during development to catch issues early

### Tooling

This project uses [uv](https://docs.astral.sh/uv/) for Python package management of the backend. Requires **Python 3.13+**.

```bash
cd backend
uv sync                   # install dependencies
uv run <script>           # run a script
uv add <package>          # add a dependency
uv add --dev <package>    # add a dev dependency
```
