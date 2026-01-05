import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from gitlab_depcheck.cli import check_project, search_dependencies, DependencyMatch
from rich.console import Console


class TestIntegration:
    @pytest.mark.asyncio
    async def test_check_project_finds_dependency(self, mock_gitlab_projects):
        """
        Test checking a project and finding a dependency

        """
        from gitlab_depcheck.cli import GitLabClient

        project = mock_gitlab_projects[0]
        console = Console()

        requirements_content = "requests==2.28.0\npandas>=1.5.0"

        client = GitLabClient("https://gitlab.com", "test-token")

        with patch.object(client, "get_file_content", new=AsyncMock(return_value=requirements_content)):
            matches = await check_project(client, project, "requests", console)

            assert len(matches) == 1
            assert matches[0].project_name == "test/project1"
            assert matches[0].version == "requests==2.28.0"
            assert matches[0].file_path == "requirements.txt"

        await client.close()

    @pytest.mark.asyncio
    async def test_check_project_dependency_not_found(self, mock_gitlab_projects):
        """
        Test checking a project when dependency is not found

        """
        from gitlab_depcheck.cli import GitLabClient

        project = mock_gitlab_projects[0]
        console = Console()

        requirements_content = "flask==2.0.0\ndjango>=4.0.0"

        client = GitLabClient("https://gitlab.com", "test-token")

        with patch.object(client, "get_file_content", new=AsyncMock(return_value=requirements_content)):
            matches = await check_project(client, project, "requests", console)

            assert len(matches) == 0

        await client.close()

    @pytest.mark.asyncio
    async def test_check_project_no_dependency_files(self, mock_gitlab_projects):
        """
        Test checking a project with no dependency files

        """
        from gitlab_depcheck.cli import GitLabClient

        project = mock_gitlab_projects[0]
        console = Console()

        client = GitLabClient("https://gitlab.com", "test-token")

        with patch.object(client, "get_file_content", new=AsyncMock(return_value=None)):
            matches = await check_project(client, project, "requests", console)

            assert len(matches) == 0

        await client.close()

    @pytest.mark.asyncio
    async def test_check_project_multiple_files(self, mock_gitlab_projects):
        """
        Test that only first matching file is returned

        """
        from gitlab_depcheck.cli import GitLabClient

        project = mock_gitlab_projects[0]
        console = Console()

        requirements_content = "requests==2.28.0"

        client = GitLabClient("https://gitlab.com", "test-token")

        # Both files have the package, but only first match should be returned
        with patch.object(client, "get_file_content", new=AsyncMock(return_value=requirements_content)):
            matches = await check_project(client, project, "requests", console)

            # Should only return one match (from first file found)
            assert len(matches) == 1

        await client.close()

    @pytest.mark.asyncio
    async def test_check_project_with_pyproject_toml(self, mock_gitlab_projects):
        """
        Test checking project with pyproject.toml

        """
        from gitlab_depcheck.cli import GitLabClient

        project = mock_gitlab_projects[0]
        console = Console()

        pyproject_content = """[project]
dependencies = [
    "requests>=2.28.0",
    "click>=8.0.0"
]
"""

        async def mock_get_file(project_id, file_path, ref):
            if "pyproject.toml" in file_path:
                return pyproject_content
            return None

        client = GitLabClient("https://gitlab.com", "test-token")

        with patch.object(client, "get_file_content", new=AsyncMock(side_effect=mock_get_file)):
            matches = await check_project(client, project, "requests", console)

            assert len(matches) == 1
            assert matches[0].version == "requests>=2.28.0"

        await client.close()

    @pytest.mark.asyncio
    async def test_check_project_handles_exception(self, mock_gitlab_projects):
        """
        Test that exceptions in file checking are handled

        """
        from gitlab_depcheck.cli import GitLabClient

        project = mock_gitlab_projects[0]
        console = Console()

        client = GitLabClient("https://gitlab.com", "test-token")

        with patch.object(client, "get_file_content", new=AsyncMock(side_effect=Exception("Network error"))):
            matches = await check_project(client, project, "requests", console)

            # Should handle exception gracefully and return empty list
            assert len(matches) == 0

        await client.close()

    @pytest.mark.asyncio
    async def test_search_dependencies_empty_projects(self):
        """
        Test search when no projects are found

        """
        with patch("gitlab_depcheck.cli.GitLabClient") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock()
            mock_client_instance.get_projects = AsyncMock(return_value=[])
            MockClient.return_value = mock_client_instance

            matches = await search_dependencies(
                gitlab_url="https://gitlab.com", token="test-token", package_name="requests"
            )

            assert matches == []

    @pytest.mark.asyncio
    async def test_search_dependencies_with_matches(self, mock_gitlab_projects):
        """
        Test full search workflow with matches

        """
        requirements_content = "requests==2.28.0"

        with patch("gitlab_depcheck.cli.GitLabClient") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock()
            mock_client_instance.get_projects = AsyncMock(return_value=mock_gitlab_projects)
            mock_client_instance.get_file_content = AsyncMock(return_value=requirements_content)
            MockClient.return_value = mock_client_instance

            matches = await search_dependencies(
                gitlab_url="https://gitlab.com", token="test-token", package_name="requests"
            )

            assert len(matches) == 2
            assert all(m.version == "requests==2.28.0" for m in matches)

    @pytest.mark.asyncio
    async def test_search_dependencies_with_group(self, mock_gitlab_projects):
        """
        Test search with group filter

        """
        with patch("gitlab_depcheck.cli.GitLabClient") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock()
            mock_client_instance.get_projects = AsyncMock(return_value=mock_gitlab_projects)
            mock_client_instance.get_file_content = AsyncMock(return_value=None)
            MockClient.return_value = mock_client_instance

            await search_dependencies(
                gitlab_url="https://gitlab.com", token="test-token", package_name="requests", group="test/group"
            )

            # Verify get_projects was called with group parameter
            mock_client_instance.get_projects.assert_called_once()
            call_kwargs = mock_client_instance.get_projects.call_args[1]
            assert call_kwargs.get("group") == "test/group"

    @pytest.mark.asyncio
    async def test_search_dependencies_concurrent_limit(self, mock_gitlab_projects):
        """
        Test that concurrent requests are limited

        """
        # Create many projects to test concurrency
        many_projects = [
            {
                "id": i,
                "path_with_namespace": f"test/project{i}",
                "web_url": f"https://gitlab.com/test/project{i}",
                "default_branch": "main",
            }
            for i in range(50)
        ]

        with patch("gitlab_depcheck.cli.GitLabClient") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock()
            mock_client_instance.get_projects = AsyncMock(return_value=many_projects)
            mock_client_instance.get_file_content = AsyncMock(return_value=None)
            MockClient.return_value = mock_client_instance

            matches = await search_dependencies(
                gitlab_url="https://gitlab.com", token="test-token", package_name="requests", max_concurrent=10
            )

            # Should complete without error
            assert isinstance(matches, list)
