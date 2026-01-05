# GitLab Dependency Checker - Just commands
# https://github.com/casey/just

# Default recipe to display help information
default:
    @just --list

# Install dependencies
install:
    @echo "Development environment ready!"
    uv sync --all-extras --dev
    uv tool install pre-commit
    uv tool run pre-commit install
    uv tool run pre-commit install-hooks

# Format code with ruff
format:
    uvx ruff format gitlab_depcheck/

# Lint code with ruff
lint:
    uvx ruff check gitlab_depcheck/

# Lint and fix code with ruff
lint-fix:
    uvx ruff check --fix gitlab_depcheck/

# Run all checks (format + lint)
check:
    uvx ruff format --check gitlab_depcheck/
    uvx ruff check gitlab_depcheck/

# Run pre-commit on all files
pre-commit:
    pre-commit run --all-files

# Run tests with coverage report
test:
    PYTHONWARNINGS=ignore uv run pytest --cov=gitlab_depcheck \
      --cov-report=term-missing --cov-report=html --cov-fail-under=88

# Run specific test file
test-file FILE:
    PYTHONWARNINGS=ignore uv run pytest {{FILE}} -v

# Clean build artifacts
clean:
    rm -rf build/
    rm -rf dist/
    rm -rf *.egg-info
    rm -rf .pytest_cache/
    rm -rf .ruff_cache/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Build the package
build: clean
    uv build

# Update dependencies
update:
    uv lock --upgrade

# Sync dependencies from lock file
sync:
    uv sync --all-extras

# Full CI check
ci: check pre-commit
    @echo "All CI checks passed!"

# Create a new release (update version and build)
release VERSION:
    @echo "Updating version to {{VERSION}}"
    sed -i '' 's/version = "[0-9.]*"/version = "{{VERSION}}"/' pyproject.toml
    sed -i '' 's/__version__ = "[0-9.]*"/__version__ = "{{VERSION}}"/' gitlab_depcheck/__init__.py
    sed -i '' "s/version='[0-9.]*'/version='{{VERSION}}'/" gitlab_depcheck/cli.py
    just build
    @echo "Release {{VERSION}} built successfully"
