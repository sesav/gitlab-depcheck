import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from gitlab_depcheck.cli import GitLabClient


class TestGitLabClient:
    """Test the GitLabClient class"""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """
        Test GitLab client initialization

        """
        client = GitLabClient(gitlab_url="https://gitlab.example.com", token="test-token", timeout=30)
        assert client.gitlab_url == "https://gitlab.example.com"
        assert client.api_url == "https://gitlab.example.com/api/v4"
        await client.close()

    @pytest.mark.asyncio
    async def test_client_url_normalization(self):
        """
        Test URL normalization (trailing slash removal)

        """
        client = GitLabClient(gitlab_url="https://gitlab.example.com/", token="test-token")
        assert client.gitlab_url == "https://gitlab.example.com"
        await client.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """
        Test using client as async context manager

        """
        async with GitLabClient("https://gitlab.example.com", "token") as client:
            assert client.gitlab_url == "https://gitlab.example.com"

    @pytest.mark.asyncio
    async def test_get_projects_success(self, mock_gitlab_projects):
        """
        Test successful project fetching

        """
        mock_response = MagicMock()
        mock_response.json.return_value = mock_gitlab_projects
        mock_response.headers = {}

        client = GitLabClient("https://gitlab.example.com", "token")

        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            projects = await client.get_projects()
            assert len(projects) == 2
            assert projects[0]["path_with_namespace"] == "test/project1"

        await client.close()

    @pytest.mark.asyncio
    async def test_get_projects_with_group(self, mock_gitlab_projects):
        """
        Test fetching projects from a specific group

        """
        mock_response = MagicMock()
        mock_response.json.return_value = mock_gitlab_projects
        mock_response.headers = {}

        client = GitLabClient("https://gitlab.example.com", "token")

        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)) as mock_get:
            projects = await client.get_projects(group="test/group")
            assert len(projects) == 2

            # Verify the correct endpoint was called
            call_args = mock_get.call_args
            assert "groups/test%2Fgroup/projects" in call_args[0][0]

        await client.close()

    @pytest.mark.asyncio
    async def test_get_projects_with_search(self):
        """
        Test fetching projects with search filter

        """
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1, "name": "test-api"}]
        mock_response.headers = {}

        client = GitLabClient("https://gitlab.example.com", "token")

        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)) as mock_get:
            projects = await client.get_projects(search="api")
            assert len(projects) == 1

            # Verify search parameter was passed
            call_args = mock_get.call_args
            assert call_args[1]["params"]["search"] == "api"

        await client.close()

    @pytest.mark.asyncio
    async def test_get_projects_pagination(self):
        """
        Test handling of paginated results

        """
        # First page response
        mock_response_page1 = MagicMock()
        mock_response_page1.json.return_value = [{"id": 1}, {"id": 2}]
        mock_response_page1.headers = {"x-next-page": "2"}

        # Second page response
        mock_response_page2 = MagicMock()
        mock_response_page2.json.return_value = [{"id": 3}]
        mock_response_page2.headers = {}

        client = GitLabClient("https://gitlab.example.com", "token")

        with patch.object(client.client, "get", new=AsyncMock(side_effect=[mock_response_page1, mock_response_page2])):
            projects = await client.get_projects()
            assert len(projects) == 3

        await client.close()

    @pytest.mark.asyncio
    async def test_get_projects_http_error(self):
        """
        Test handling of HTTP errors during project fetching

        """
        client = GitLabClient("https://gitlab.example.com", "token")

        with patch.object(client.client, "get", new=AsyncMock(side_effect=httpx.HTTPError("Connection failed"))):
            projects = await client.get_projects()
            assert projects == []

        await client.close()

    @pytest.mark.asyncio
    async def test_get_file_content_success(self):
        """
        Test successful file content retrieval

        """
        import base64

        content = "requests==2.28.0\npandas>=1.5.0"
        encoded_content = base64.b64encode(content.encode()).decode()

        mock_response = MagicMock()
        mock_response.json.return_value = {"content": encoded_content}

        client = GitLabClient("https://gitlab.example.com", "token")

        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await client.get_file_content(project_id=1, file_path="requirements.txt", ref="main")
            assert result == content

        await client.close()

    @pytest.mark.asyncio
    async def test_get_file_content_fallback_branches(self):
        """
        Test fallback to master/develop when main doesn't exist

        """
        import base64

        content = "requests==2.28.0"
        encoded_content = base64.b64encode(content.encode()).decode()

        # First call (main) fails, second call (master) succeeds
        mock_response_fail = MagicMock()
        mock_response_fail.raise_for_status.side_effect = httpx.HTTPError("Not found")

        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {"content": encoded_content}

        client = GitLabClient("https://gitlab.example.com", "token")

        with patch.object(client.client, "get", new=AsyncMock(side_effect=[mock_response_fail, mock_response_success])):
            result = await client.get_file_content(project_id=1, file_path="requirements.txt", ref="main")
            assert result == content

        await client.close()

    @pytest.mark.asyncio
    async def test_get_file_content_not_found(self):
        """
        Test file not found in any branch

        """
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPError("Not found")

        client = GitLabClient("https://gitlab.example.com", "token")

        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await client.get_file_content(project_id=1, file_path="nonexistent.txt", ref="main")
            assert result is None

        await client.close()

    @pytest.mark.asyncio
    async def test_get_file_content_url_encoding(self):
        """
        Test proper URL encoding of file paths

        """
        import base64

        content = "test"
        encoded_content = base64.b64encode(content.encode()).decode()

        mock_response = MagicMock()
        mock_response.json.return_value = {"content": encoded_content}

        client = GitLabClient("https://gitlab.example.com", "token")

        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)) as mock_get:
            await client.get_file_content(project_id=1, file_path="path/to/file with spaces.txt", ref="main")

            # Check that the URL was properly encoded
            call_args = mock_get.call_args
            url = call_args[0][0]
            assert "path%2Fto%2Ffile%20with%20spaces.txt" in url

        await client.close()
