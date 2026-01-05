import asyncio
import base64
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import click
import httpx
from rich.console import Console
from rich.markup import escape
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from gitlab_depcheck import __version__


try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback for older versions


@dataclass
class DependencyMatch:
    project_name: str
    project_url: str
    file_path: str
    file_url: str
    version: str
    line_number: int | None = None


class GitLabClient:
    def __init__(self, gitlab_url: str, token: str, timeout: int = 30):
        self.gitlab_url = gitlab_url.rstrip("/")
        self.api_url = f"{self.gitlab_url}/api/v4"
        self.client = httpx.AsyncClient(
            headers={
                "PRIVATE-TOKEN": token,
                "Content-Type": "application/json",
            },
            timeout=timeout,
            follow_redirects=True,
        )

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def get_projects(
        self, group: str | None = None, search: str | None = None, archived: bool = False
    ) -> list[dict]:
        projects = []
        page = 1

        if group:
            endpoint = f"{self.api_url}/groups/{quote(group, safe='')}/projects"
        else:
            endpoint = f"{self.api_url}/projects"

        params = {
            "per_page": 100,
            "archived": archived,
            "simple": True,
            "membership": True,
        }

        if search:
            params["search"] = search

        while True:
            params["page"] = page

            try:
                response = await self.client.get(endpoint, params=params)
                response.raise_for_status()

                page_projects = response.json()
                if not page_projects:
                    break

                projects.extend(page_projects)

                # Check for next page
                if "x-next-page" not in response.headers:
                    break

                page += 1

            except httpx.HTTPError as e:
                print(f"Error fetching projects: {e}", file=sys.stderr)
                break

        return projects

    async def get_file_content(self, project_id: int, file_path: str, ref: str = "main") -> str | None:
        endpoint = f"{self.api_url}/projects/{project_id}/repository/files/{quote(file_path, safe='')}"
        refs_to_try = [ref, "master", "develop"] if ref == "main" else [ref]

        for try_ref in refs_to_try:
            try:
                response = await self.client.get(endpoint, params={"ref": try_ref})
                response.raise_for_status()

                data = response.json()
                content = base64.b64decode(data["content"]).decode("utf-8")
                return content

            except httpx.HTTPError:
                continue

        return None


class PythonDependencyChecker:
    DEPENDENCY_FILES = [
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-test.txt",
        "requirements-prod.txt",
        "pyproject.toml",
    ]

    @staticmethod
    def normalize_package_name(name: str) -> str:
        """
        Normalize package name for comparison
        PEP 503: _, -, . in package names are equivalent
        """
        return re.sub(r"[-_.]+", "-", name.lower())

    @staticmethod
    def check_requirements_txt(content: str, package_name: str) -> tuple[str, int, str] | None:
        """
        Check requirements.txt format

        Supports:
        - package==1.0.0
        - package[extra]==1.0.0
        - package[extra1,extra2]>=1.0.0
        - package [extra] ==1.0.0  (with spaces)
        """
        lines = content.split("\n")
        normalized_package = PythonDependencyChecker.normalize_package_name(package_name)

        for i, line in enumerate(lines, 1):
            original_line = line
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Remove inline comments
            line = line.split("#")[0].strip()

            # Pattern for requirements.txt:
            # package[extras]==version
            # package [extras] == version
            # ^(package-name)\s*(\[[\w,\-\.]+\])?\s*([=~<>!]+)\s*(version)
            pattern = (
                r"^"
                r"([\w\-\.]+)"  # Package name (group 1)
                r"\s*"
                r"(\[[\w,\-\.]+\])?"  # Optional extras (group 2)
                r"\s*"
                r"([=~<>!]+)"  # Version operator (group 3)
                r"\s*"
                r"([0-9][0-9a-zA-Z._\-]*)"  # Version (group 4)
            )

            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                found_package = match.group(1)
                normalized_found = PythonDependencyChecker.normalize_package_name(found_package)

                if normalized_found == normalized_package:
                    extras = match.group(2) or ""
                    operator = match.group(3)
                    version_num = match.group(4)
                    version = f"{extras}{operator}{version_num}" if extras else f"{operator}{version_num}"
                    return (version, i, original_line.strip())

            # Without version: package or package[extras]
            pattern_no_version = (
                r"^"
                r"([\w\-\.]+)"  # Package name
                r"\s*"
                r"(\[[\w,\-\.]+\])?"  # Optional extras
                r"\s*$"
            )

            match = re.match(pattern_no_version, line, re.IGNORECASE)
            if match:
                found_package = match.group(1)
                normalized_found = PythonDependencyChecker.normalize_package_name(found_package)

                if normalized_found == normalized_package:
                    extras = match.group(2) or ""
                    return (f"{extras}*" if extras else "*", i, original_line.strip())

        return None

    @staticmethod
    def check_pyproject_toml(content: str, package_name: str) -> tuple[str, int, str] | None:
        """
        Check pyproject.toml format

        Supports:
        - dependencies = ["package==1.0.0"]
        - dependencies = ["package[extra]>=1.0.0"]
        - package = "^1.0.0" (poetry)
        - package = {version = "^1.0.0", extras = ["kafka"]} (poetry)
        """
        try:
            data = tomllib.loads(content)
        except Exception:
            return None

        normalized_package = PythonDependencyChecker.normalize_package_name(package_name)

        # Check [project.dependencies]
        if "project" in data and "dependencies" in data["project"]:
            deps = data["project"]["dependencies"]
            for dep in deps:
                # Pattern: package[extras]operator version
                pattern = (
                    r"^"
                    r"([\w\-\.]+)"  # Package name
                    r"\s*"
                    r"(\[[\w,\-\.]+\])?"  # Extras
                    r"\s*"
                    r"([=~<>!]+)"  # Operator
                    r"\s*"
                    r"([0-9][0-9a-zA-Z._\-]*)"  # Version
                )

                match = re.match(pattern, dep, re.IGNORECASE)
                if match:
                    found_package = match.group(1)
                    normalized_found = PythonDependencyChecker.normalize_package_name(found_package)

                    if normalized_found == normalized_package:
                        extras = match.group(2) or ""
                        operator = match.group(3)
                        version_num = match.group(4)
                        version = f"{extras}{operator}{version_num}" if extras else f"{operator}{version_num}"

                        # Find line number - search for the line with the dependency itself
                        lines = content.split("\n")
                        for i, line in enumerate(lines, 1):
                            # Search for line containing this dependency (dep) in full or partial
                            if dep.strip() in line or (found_package in line and operator in line):
                                return (version, i, line.strip())

                        return (version, None, dep)

        # Check [project.optional-dependencies]
        if "project" in data and "optional-dependencies" in data["project"]:
            optional_deps = data["project"]["optional-dependencies"]
            for group_name, deps in optional_deps.items():
                for dep in deps:
                    pattern = (
                        r"^"
                        r"([\w\-\.]+)"
                        r"\s*"
                        r"(\[[\w,\-\.]+\])?"
                        r"\s*"
                        r"([=~<>!]+)"
                        r"\s*"
                        r"([0-9][0-9a-zA-Z._\-]*)"
                    )

                    match = re.match(pattern, dep, re.IGNORECASE)
                    if match:
                        found_package = match.group(1)
                        normalized_found = PythonDependencyChecker.normalize_package_name(found_package)

                        if normalized_found == normalized_package:
                            extras = match.group(2) or ""
                            operator = match.group(3)
                            version_num = match.group(4)
                            version = f"{extras}{operator}{version_num}" if extras else f"{operator}{version_num}"

                            lines = content.split("\n")
                            for i, line in enumerate(lines, 1):
                                # Search for line containing this dependency
                                if dep.strip() in line or (found_package in line and operator in line):
                                    return (version, i, line.strip())

                            return (version, None, f"{dep} (in {group_name})")

        # Check [tool.poetry.dependencies]
        if "tool" in data and "poetry" in data["tool"]:
            poetry = data["tool"]["poetry"]
            for dep_section in ["dependencies", "dev-dependencies", "group"]:
                if dep_section == "group":
                    # Poetry groups: [tool.poetry.group.dev.dependencies]
                    if "group" not in poetry:
                        continue
                    for group_name, group_data in poetry["group"].items():
                        if "dependencies" not in group_data:
                            continue
                        deps_dict = group_data["dependencies"]
                        result = PythonDependencyChecker._check_poetry_deps(deps_dict, normalized_package, content)
                        if result:
                            return result
                else:
                    if dep_section not in poetry:
                        continue
                    deps_dict = poetry[dep_section]
                    result = PythonDependencyChecker._check_poetry_deps(deps_dict, normalized_package, content)
                    if result:
                        return result

        # Check [tool.uv]
        if "tool" in data and "uv" in data["tool"]:
            if "dependencies" in data["tool"]["uv"]:
                deps = data["tool"]["uv"]["dependencies"]
                for dep in deps:
                    pattern = (
                        r"^"
                        r"([\w\-\.]+)"
                        r"\s*"
                        r"(\[[\w,\-\.]+\])?"
                        r"\s*"
                        r"([=~<>!]+)"
                        r"\s*"
                        r"([0-9][0-9a-zA-Z._\-]*)"
                    )

                    match = re.match(pattern, dep, re.IGNORECASE)
                    if match:
                        found_package = match.group(1)
                        normalized_found = PythonDependencyChecker.normalize_package_name(found_package)

                        if normalized_found == normalized_package:
                            extras = match.group(2) or ""
                            operator = match.group(3)
                            version_num = match.group(4)
                            version = f"{extras}{operator}{version_num}" if extras else f"{operator}{version_num}"

                            lines = content.split("\n")
                            for i, line in enumerate(lines, 1):
                                # Search for line containing this dependency
                                if dep.strip() in line or (found_package in line and operator in line):
                                    return (version, i, line.strip())

                            return (version, None, dep)

        return None

    @staticmethod
    def _check_poetry_deps(deps_dict: dict, normalized_package: str, content: str) -> tuple[str, int, str] | None:
        """Check poetry dependencies in dict format"""
        for dep_name, version_spec in deps_dict.items():
            normalized_dep = PythonDependencyChecker.normalize_package_name(dep_name)

            if normalized_dep == normalized_package:
                # Version can be string or dict
                if isinstance(version_spec, str):
                    version = version_spec
                elif isinstance(version_spec, dict):
                    if "version" in version_spec:
                        version = version_spec["version"]
                        # Add extras info if present
                        if "extras" in version_spec:
                            extras_list = version_spec["extras"]
                            extras_str = f"[{','.join(extras_list)}]"
                            version = f"{extras_str}{version}"
                    else:
                        version = str(version_spec)
                else:
                    version = str(version_spec)

                # Find line - for Poetry search for line with package name and "="
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    # Search for line with package name in format: dep_name = "version" or dep_name = {version...}
                    if dep_name in line and "=" in line and not line.strip().startswith("#"):
                        return (version, i, line.strip())

                return (version, None, f'{dep_name} = "{version}"')

        return None

    @classmethod
    def check_dependency(cls, file_path: str, content: str, package_name: str) -> tuple[str, int, str] | None:
        if "pyproject.toml" in file_path.lower():
            return cls.check_pyproject_toml(content, package_name)
        if "requirements" in file_path.lower() or file_path.endswith(".txt"):
            return cls.check_requirements_txt(content, package_name)

        return None


async def check_project(
    client: GitLabClient, project: dict, package_name: str, console: Console
) -> list[DependencyMatch]:
    matches = []
    project_id = project["id"]
    project_name = project["path_with_namespace"]
    project_url = project["web_url"]
    default_branch = project.get("default_branch", "main")

    # Check each dependency file
    for file_path in PythonDependencyChecker.DEPENDENCY_FILES:
        try:
            content = await client.get_file_content(project_id, file_path, default_branch)

            if content is None:
                continue

            result = PythonDependencyChecker.check_dependency(file_path, content, package_name)

            if result:
                version, line_number, line_content = result
                full_package = f"{package_name}{version}"
                file_url = f"{project_url}/-/blob/{default_branch}/{file_path}"
                if line_number:
                    file_url += f"#L{line_number}"

                matches.append(
                    DependencyMatch(
                        project_name=project_name,
                        project_url=project_url,
                        file_path=file_path,
                        file_url=file_url,
                        version=full_package,
                        line_number=line_number,
                    )
                )

                break

        except Exception as e:
            console.print(f"[yellow]Warning: {project_name}/{file_path}: {e}[/yellow]")
            continue

    return matches


async def search_dependencies(
    gitlab_url: str,
    token: str,
    package_name: str,
    group: str | None = None,
    search: str | None = None,
    archived: bool = False,
    max_concurrent: int = 10,
) -> list[DependencyMatch]:
    console = Console()
    console.print(f"[bold blue]🔍 Searching for package:[/bold blue] [yellow]{package_name}[/yellow]")

    async with GitLabClient(gitlab_url, token) as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching projects...", total=None)
            projects = await client.get_projects(group=group, search=search, archived=archived)
            progress.remove_task(task)

        console.print(f"[green]✓[/green] Found {len(projects)} projects to check")

        if not projects:
            return []

        # Check projects in parallel with limit
        all_matches = []

        with Progress(console=console) as progress:
            task = progress.add_task("[cyan]Checking projects...", total=len(projects))
            semaphore = asyncio.Semaphore(max_concurrent)

            async def check_with_semaphore(proj):
                async with semaphore:
                    matches = await check_project(client, proj, package_name, console)
                    progress.advance(task)
                    return matches

            # Run all checks
            results = await asyncio.gather(*[check_with_semaphore(proj) for proj in projects], return_exceptions=True)

            # Collect results
            for result in results:
                if isinstance(result, list):
                    all_matches.extend(result)
                elif isinstance(result, Exception):
                    console.print(f"[red]Error: {result}[/red]")

        return all_matches


def display_results(matches: list[DependencyMatch], console: Console):
    if not matches:
        console.print("\n[yellow]No matches found[/yellow]")
        return

    projects = {}

    for match in matches:
        if match.project_name not in projects:
            projects[match.project_name] = []
        projects[match.project_name].append(match)

    console.print(f"\n[bold green]✓ Found in {len(projects)} projects:[/bold green]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Project", style="cyan", no_wrap=True)
    table.add_column("File", style="blue")
    table.add_column("Package", style="green", no_wrap=True, overflow="fold")
    table.add_column("Line", justify="right", style="dim")

    for project_name in sorted(projects.keys()):
        project_matches = projects[project_name]

        for i, match in enumerate(project_matches):
            if i == 0:
                table.add_row(
                    f"[link={match.project_url}]{project_name}[/link]",
                    f"[link={match.file_url}]{match.file_path}[/link]",
                    escape(match.version),
                    str(match.line_number) if match.line_number else "-",
                )
            else:
                table.add_row(
                    "",
                    f"[link={match.file_url}]{match.file_path}[/link]",
                    escape(match.version),
                    str(match.line_number) if match.line_number else "-",
                )

    console.print(table)

    # Version statistics
    console.print("\n[bold]Version distribution:[/bold]")
    version_counts = {}
    for match in matches:
        version_counts[match.version] = version_counts.get(match.version, 0) + 1

    for version, count in sorted(version_counts.items(), key=lambda x: -x[1]):
        console.print(f"  {version}: [yellow]{count}[/yellow] project(s)")


def load_config() -> dict:
    """
    Load configuration from .gitlab_depcheck.toml

    Searches in order:
    1. Current directory: .gitlab_depcheck.toml
    2. Home directory: ~/.gitlab_depcheck.toml

    """

    local_config = Path.cwd() / ".gitlab_depcheck.toml"
    if local_config.exists():
        try:
            with open(local_config, "rb") as f:
                return tomllib.load(f)
        except Exception:
            pass

    # Fallback to home directory
    home_config = Path.home() / ".gitlab_depcheck.toml"
    if home_config.exists():
        try:
            with open(home_config, "rb") as f:
                return tomllib.load(f)
        except Exception:
            pass

    return {}


@click.command()
@click.version_option(version=__version__, prog_name="gitlab-depcheck")
@click.argument("package", type=str)
@click.option(
    "--url",
    help="GitLab URL (default: https://gitlab.com or from config)",
)
@click.option(
    "--token",
    help="GitLab personal access token (or use GITLAB_TOKEN env var or config)",
)
@click.option(
    "--group",
    help="GitLab group path (e.g., mycompany/backend)",
)
@click.option(
    "--search",
    help="Filter projects by name",
)
@click.option(
    "--archived",
    is_flag=True,
    help="Include archived projects",
)
@click.option(
    "--max-concurrent",
    type=int,
    default=10,
    help="Maximum concurrent API requests",
)
@click.option(
    "--output",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    help="Output format",
)
def main(package, url, token, group, search, archived, max_concurrent, output):
    """
    Check Python package dependencies across GitLab projects.

    \b
    Examples:
      # Search for pandas in all accessible projects
      gitlab-depcheck pandas

      # Search in specific group
      gitlab-depcheck requests --group mycompany/backend

      # Search with project name filter
      gitlab-depcheck fastapi --search api

      # Include archived projects
      gitlab-depcheck django --archived

    \b
    Configuration file (searches in order):
      1. .gitlab_depcheck.toml (project directory)
      2. ~/.gitlab_depcheck.toml (home directory)

      [gitlab]
      url = "https://gitlab.com"
      token = "your-token-here"

      [search]
      group = "mycompany"
      max_concurrent = 20

    """

    config = load_config()
    gitlab_url = url or config.get("gitlab", {}).get("url") or "https://gitlab.com"
    token = token or os.getenv("GITLAB_TOKEN") or config.get("gitlab", {}).get("token")

    if not token:
        click.echo("Error: GitLab token required. Use --token, GITLAB_TOKEN env var, or config file", err=True)
        sys.exit(1)

    group = group or config.get("search", {}).get("group")
    max_concurrent = max_concurrent or config.get("search", {}).get("max_concurrent", 10)
    console = Console()

    try:
        matches = asyncio.run(
            search_dependencies(
                gitlab_url=gitlab_url,
                token=token,
                package_name=package,
                group=group,
                search=search,
                archived=archived,
                max_concurrent=max_concurrent,
            )
        )

        if output == "table":
            display_results(matches, console)
        elif output == "json":
            import json

            data = [
                {
                    "project": m.project_name,
                    "project_url": m.project_url,
                    "file": m.file_path,
                    "file_url": m.file_url,
                    "version": m.version,
                    "line": m.line_number,
                }
                for m in matches
            ]
            click.echo(json.dumps(data, indent=2))
        elif output == "csv":
            import csv

            writer = csv.writer(sys.stdout)
            writer.writerow(["Project", "File", "Version", "Line", "URL"])
            for m in matches:
                writer.writerow(
                    [
                        m.project_name,
                        m.file_path,
                        m.version,
                        m.line_number or "",
                        m.file_url,
                    ]
                )

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
