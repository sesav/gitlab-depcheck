import pytest
from pathlib import Path


@pytest.fixture
def sample_requirements_txt():
    return """# Sample requirements file
requests==2.28.0
pandas[excel]>=1.5.0
numpy==1.23.0  # with comment
Flask
django>=4.0.0,<5.0.0
fastapi[all]==0.100.0
"""


@pytest.fixture
def sample_pyproject_toml():
    return """[project]
name = "test-project"
version = "0.1.0"
dependencies = [
    "click>=8.0.0",
    "httpx>=0.28.0",
    "rich[jupyter]>=13.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "black==23.0.0",
]
"""


@pytest.fixture
def sample_poetry_pyproject():
    return """[tool.poetry]
name = "poetry-project"
version = "0.1.0"

[tool.poetry.dependencies]
python = "^3.10"
requests = "^2.28.0"
pandas = {version = "^1.5.0", extras = ["excel"]}

[tool.poetry.group.dev.dependencies]
pytest = "^7.0.0"
"""


@pytest.fixture
def mock_gitlab_projects():
    return [
        {
            "id": 1,
            "path_with_namespace": "test/project1",
            "web_url": "https://gitlab.com/test/project1",
            "default_branch": "main",
        },
        {
            "id": 2,
            "path_with_namespace": "test/project2",
            "web_url": "https://gitlab.com/test/project2",
            "default_branch": "master",
        },
    ]


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file"""
    config_content = """[gitlab]
url = "https://gitlab.example.com"
token = "test-token-12345"

[search]
group = "test-group"
max_concurrent = 20
"""
    config_file = tmp_path / ".gitlab_depcheck.toml"
    config_file.write_text(config_content)
    return config_file
