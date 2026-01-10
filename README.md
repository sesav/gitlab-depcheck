# GitLab Dependency Checker

![Python Version](https://img.shields.io/badge/python-3.10+-blue)
![](https://img.shields.io/github/repo-size/sesav/gitlab-depcheck)
![](https://img.shields.io/github/last-commit/sesav/gitlab-depcheck)
[![codecov](https://codecov.io/github/sesav/gitlab-depcheck/graph/badge.svg?token=GSHBWZGXAH)](https://codecov.io/github/sesav/gitlab-depcheck)

A command-line utility to check if Python packages are used in GitLab repositories or groups. It helps you track package usage across your projects.

## Installation

The easiest way to install is with `uv`:

```bash
% uv tool install gitlab-depcheck
```

Now it's available globally. You can check that the installation was
successful:

```bash
% gitlab-depcheck --version
gitlab-depcheck, version 0.5.3
```

Next, create a config file `.gitlab_depcheck.toml` in your project directory or
`~/.gitlab_depcheck.toml` in your home directory:

```toml
[gitlab]
url = "https://gitlab.com"  # or your self-hosted GitLab URL
token = "your-personal-access-token"

[search]
group = "foo"              # default group to search in
max_concurrent = 20        # parallel API requests (default: 10)
```

And just run:

```bash
% gitlab-depcheck httpx

🔍 Searching for package: httpx

✓ Found 56 projects to check
Checking projects... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00

✓ Found in 4 projects:

┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┓
┃ Project               ┃ File           ┃ Package                                ┃ Line ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━┩
│ foo/bar-service       │ pyproject.toml │ httpx==0.27.1                          │   31 │
│ foo/tor-service       │ pyproject.toml │ httpx[http2]==0.25.2                   │   18 │
│ foo/org-service       │ pyproject.toml │ httpx[brotli,zstd]==0.27.1             │   49 │
│ foo/autotests         │ pyproject.toml │ httpx>=0.25.1                          │   24 │
└───────────────────────┴────────────────┴────────────────────────────────────────┴──────┘

Version distribution:
  httpx==0.27.1: 2 project(s)
  httpx==0.25.2: 1 project(s)
  httpx>=0.25.1: 1 project(s)

```

Output can be transformed into `json` or `csv`, for example:

```bash
% gitlab-depcheck numpy --output json > foo_numpy.json
% gitlab-depcheck numpy --output csv > foo_numpy.csv
```

## More options

You can narrow the search by specifying a group:

```bash
gitlab-depcheck httpx --group mycompany/backend
```

or filter by project name:

```bash
gitlab-depcheck httpx --search foo-service
```

A full list of options is available via `--help`:

```bash
% gitlab-depcheck --help
Usage: gitlab-depcheck [OPTIONS] PACKAGE

  Check Python package dependencies across GitLab projects.

  Examples:
    # Search for pandas in all accessible projects
    gitlab-depcheck pandas

    # Search in specific group
    gitlab-depcheck httpx --group mycompany/backend

    # Search with project name filter
    gitlab-depcheck fastapi --search api

    # Include archived projects
    gitlab-depcheck django --archived

  Configuration file (searches in order):
    1. .gitlab_depcheck.toml (project directory)
    2. ~/.gitlab_depcheck.toml (home directory)

    [gitlab]
    url = "https://gitlab.com"
    token = "your-token-here"

    [search]
    group = "mycompany"
    max_concurrent = 20

Options:
  --version                  Show the version and exit.
  --url TEXT                 GitLab URL (default: https://gitlab.com or from
                             config)
  --token TEXT               GitLab personal access token (or use GITLAB_TOKEN
                             env var or config)
  --group TEXT               GitLab group path (e.g., mycompany/backend)
  --search TEXT              Filter projects by name
  --archived                 Include archived projects
  --max-concurrent INTEGER   Maximum concurrent API requests
  --output [table|json|csv]  Output format
  --help                     Show this message and exit.
  ```

## Requirements

- Python 3.10+
- uv package manager
- wget or curl (for uv installation)

## License

This project is licensed under the [MIT License](LICENSE).
