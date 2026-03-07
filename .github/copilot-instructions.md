# FamilyLens – Copilot Instructions

FamilyLens is a **local-first intelligent photo search application** that lets users search their personal photo library using natural language queries.

## Tooling

This project uses [uv](https://docs.astral.sh/uv/) for Python package management. Requires **Python 3.14+**.

```bash
uv sync                   # install dependencies
uv run <script>           # run a script
uv add <package>          # add a dependency
uv add --dev <package>    # add a dev dependency
```

## Project goals

- **Local-first**: all processing and data stays on the user's machine — no cloud uploads of photos or metadata
- **Natural language search**: users query their photo library in plain English (e.g., "birthday party last summer", "photos with grandma")

## Code style

- Use **snake_case** for variable and function names
- Use **PascalCase** for class names
- Use **4 spaces** for indentation
- Write docstrings for all public functions and classes
- Keep lines under **80 characters** when possible
- Use type hints for all function parameters and return types
- Follow PEP 8 style guidelines for Python code

## Testing

- Use **pytest** for testing
- Write tests for all new features and bug fixes
- Aim for high test coverage, especially for critical functionality
- Use descriptive test names that clearly indicate what is being tested
- Run tests frequently during development to catch issues early

## Version control

- Use **Git** for version control
- Write clear and descriptive commit messages
- Create branches for new features and bug fixes
- Open pull requests for code review before merging to main
- Use tags to mark release versions

