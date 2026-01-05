# GitLab Dependency Checker

![Total](https://img.shields.io/github/downloads/sesav/gitlab-depcheck/total)
![Python Version](https://img.shields.io/badge/python-3.10+-blue)
![](https://img.shields.io/github/repo-size/sesav/gitlab-depcheck)
![](https://img.shields.io/github/last-commit/sesav/gitlab-depcheck)
[![codecov](https://codecov.io/github/sesav/gitlab-depcheck/graph/badge.svg?token=GSHBWZGXAH)](https://codecov.io/github/sesav/gitlab-depcheck)
![License](https://img.shields.io/github/license/sesav/gitlab-depcheck)

A small utility that lets you quickly check whether packages are present in a specific GitLab
repository or group. Nothing super special — it’s just a tool I occasionally need myself.

If you find it useful too, feel free to use it.

## Getting Started

The easiest way to install is with `uv`:

```bash
uv tool install gitlab-depcheck
```

This puts the `gitlab-depcheck` command in your path (usually `~/.local/bin/`). If you don't have
`uv`, you can also use regular pip or pipx:

```bash
pip install gitlab-depcheck
# or
pipx install gitlab-depcheck
```

If you want to hack on the code yourself, clone the repo and install it in development mode:

```bash
git clone https://github.com/yourusername/gitlab-dep-checker.git
cd gitlab-dep-checker
uv venv
source .venv/bin/activate  # Windows folks use: .venv\Scripts\activate
uv pip install -e .
```

You can check everything's working by running:
```bash
gitlab-depcheck --version
```

## How to Use It

The simplest case - just search for a package across all your accessible projects:

```bash
gitlab-depcheck pandas
```

You can narrow things down by searching within a specific group:

```bash
gitlab-depcheck requests --group mycompany/backend
```

Or filter by project name:

```bash
gitlab-depcheck fastapi --search core-service
```

By default, archived projects are ignored, but you can include them:

```bash
gitlab-depcheck django --archived
```

Want the output in a different format? No problem:

```bash
gitlab-depcheck numpy --output json
gitlab-depcheck numpy --output csv
```

## Authentication

You'll need a GitLab personal access token with `read_api` scope. There are a few ways to provide it:

Pass it directly on the command line (not recommended for security reasons, but useful for quick tests):
```bash
gitlab-depcheck pandas --token your-token-here
```

Use an environment variable (better):
```bash
export GITLAB_TOKEN=your-token-here
gitlab-depcheck pandas
```

Or put it in a config file (best option - see below).

## Configuration

You can create a config file to avoid typing the same options over and over. Just create
`.gitlab_depcheck.toml` in your project directory or `~/.gitlab_depcheck.toml` in your home
directory:

```toml
[gitlab]
url = "https://gitlab.com"  # or your self-hosted GitLab URL
token = "your-personal-access-token"

[search]
group = "mycompany"         # default group to search in
max_concurrent = 20         # parallel API requests (default: 10)
```

The tool looks for config in this order: command line options first, then environment variables,
then a project-level `.gitlab_depcheck.toml`, and finally `~/.gitlab_depcheck.toml` in your home
directory.

This is pretty handy if you're working on a team - you can check in a project-level config with the
group and URL set, while each person keeps their token in their personal `~/.gitlab_depcheck.toml`
file.

There's a `.gitlab_depcheck.toml.example` file in the repo you can copy to get started:

```bash
# For project-specific settings
cp .gitlab_depcheck.toml.example .gitlab_depcheck.toml

# For your personal settings
cp .gitlab_depcheck.toml.example ~/.gitlab_depcheck.toml
```

(Don't worry, `.gitlab_depcheck.toml` is already in `.gitignore` so you won't accidentally commit your token.)

## Requirements

- Python 3.10+
- uv package manager
- wget or curl (for installation)

## License

This project is licensed under the [MIT License](LICENSE).
