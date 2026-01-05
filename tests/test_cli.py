import pytest
from click.testing import CliRunner
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path
from gitlab_depcheck import __version__
from gitlab_depcheck.cli import main, load_config, DependencyMatch


class TestCLI:
    """Test the CLI interface"""

    def test_cli_no_token(self):
        """
        Test CLI fails without token

        """
        runner = CliRunner()
        with patch.dict("os.environ", {}, clear=True):
            with patch("gitlab_depcheck.cli.load_config", return_value={}):
                result = runner.invoke(main, ["requests"])
                assert result.exit_code == 1
                assert "token required" in result.output.lower()

    def test_cli_with_token_env_var(self):
        """
        Test CLI with token from environment variable

        """
        runner = CliRunner()
        with patch.dict("os.environ", {"GITLAB_TOKEN": "test-token"}):
            with patch("gitlab_depcheck.cli.asyncio.run", return_value=[]):
                result = runner.invoke(main, ["requests"])
                assert result.exit_code == 0

    def test_cli_with_token_option(self):
        """
        Test CLI with --token option

        """
        runner = CliRunner()
        with patch("gitlab_depcheck.cli.asyncio.run", return_value=[]):
            result = runner.invoke(main, ["requests", "--token", "test-token"])
            assert result.exit_code == 0

    def test_cli_with_url_option(self):
        """
        Test CLI with custom GitLab URL

        """
        runner = CliRunner()
        with patch("gitlab_depcheck.cli.asyncio.run", return_value=[]) as mock_run:
            result = runner.invoke(main, ["requests", "--token", "test-token", "--url", "https://gitlab.example.com"])
            assert result.exit_code == 0

            # Verify the URL was passed correctly
            call_kwargs = mock_run.call_args[0][0]
            # asyncio.run receives a coroutine, we can't easily check the args

    def test_cli_with_group_option(self):
        """
        Test CLI with --group option

        """
        runner = CliRunner()
        with patch("gitlab_depcheck.cli.asyncio.run", return_value=[]):
            result = runner.invoke(main, ["requests", "--token", "test-token", "--group", "mycompany/backend"])
            assert result.exit_code == 0

    def test_cli_with_search_option(self):
        """
        Test CLI with --search option

        """
        runner = CliRunner()
        with patch("gitlab_depcheck.cli.asyncio.run", return_value=[]):
            result = runner.invoke(main, ["requests", "--token", "test-token", "--search", "api"])
            assert result.exit_code == 0

    def test_cli_with_archived_flag(self):
        """
        Test CLI with --archived flag

        """
        runner = CliRunner()
        with patch("gitlab_depcheck.cli.asyncio.run", return_value=[]):
            result = runner.invoke(main, ["requests", "--token", "test-token", "--archived"])
            assert result.exit_code == 0

    def test_cli_with_max_concurrent(self):
        """
        Test CLI with --max-concurrent option

        """
        runner = CliRunner()
        with patch("gitlab_depcheck.cli.asyncio.run", return_value=[]):
            result = runner.invoke(main, ["requests", "--token", "test-token", "--max-concurrent", "20"])
            assert result.exit_code == 0

    def test_cli_output_table(self):
        """
        Test CLI with table output (default)

        """
        runner = CliRunner()
        matches = [
            DependencyMatch(
                project_name="test/project",
                project_url="https://gitlab.com/test/project",
                file_path="requirements.txt",
                file_url="https://gitlab.com/test/project/-/blob/main/requirements.txt",
                version="requests==2.28.0",
                line_number=1,
            )
        ]

        with patch("gitlab_depcheck.cli.asyncio.run", return_value=matches):
            result = runner.invoke(main, ["requests", "--token", "test-token"])
            assert result.exit_code == 0
            assert "test/project" in result.output

    def test_cli_output_json(self):
        """
        Test CLI with JSON output

        """
        runner = CliRunner()
        matches = [
            DependencyMatch(
                project_name="test/project",
                project_url="https://gitlab.com/test/project",
                file_path="requirements.txt",
                file_url="https://gitlab.com/test/project/-/blob/main/requirements.txt",
                version="requests==2.28.0",
                line_number=1,
            )
        ]

        with patch("gitlab_depcheck.cli.asyncio.run", return_value=matches):
            result = runner.invoke(main, ["requests", "--token", "test-token", "--output", "json"])
            assert result.exit_code == 0
            assert '"project": "test/project"' in result.output
            assert '"version": "requests==2.28.0"' in result.output

    def test_cli_output_csv(self):
        """
        Test CLI with CSV output

        """
        runner = CliRunner()
        matches = [
            DependencyMatch(
                project_name="test/project",
                project_url="https://gitlab.com/test/project",
                file_path="requirements.txt",
                file_url="https://gitlab.com/test/project/-/blob/main/requirements.txt",
                version="requests==2.28.0",
                line_number=1,
            )
        ]

        with patch("gitlab_depcheck.cli.asyncio.run", return_value=matches):
            result = runner.invoke(main, ["requests", "--token", "test-token", "--output", "csv"])
            assert result.exit_code == 0
            assert "test/project" in result.output
            assert "requirements.txt" in result.output

    def test_cli_keyboard_interrupt(self):
        """
        Test CLI handles keyboard interrupt gracefully

        """
        runner = CliRunner()
        with patch("gitlab_depcheck.cli.asyncio.run", side_effect=KeyboardInterrupt()):
            result = runner.invoke(main, ["requests", "--token", "test-token"])
            assert result.exit_code == 130

    def test_cli_exception_handling(self):
        """
        Test CLI handles exceptions gracefully

        """
        runner = CliRunner()
        with patch("gitlab_depcheck.cli.asyncio.run", side_effect=Exception("Test error")):
            result = runner.invoke(main, ["requests", "--token", "test-token"])
            assert result.exit_code == 1
            assert "Error" in result.output

    def test_cli_version_option(self):
        """
        Test --version option

        """
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_cli_help_option(self):
        """
        Test --help option

        """
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Check Python package dependencies" in result.output


class TestConfigLoading:
    """Test configuration file loading"""

    def test_load_config_local(self, temp_config_file):
        """
        Test loading config from local directory

        """
        with patch("gitlab_depcheck.cli.Path.cwd", return_value=temp_config_file.parent):
            config = load_config()
            assert config["gitlab"]["url"] == "https://gitlab.example.com"
            assert config["gitlab"]["token"] == "test-token-12345"
            assert config["search"]["group"] == "test-group"
            assert config["search"]["max_concurrent"] == 20

    def test_load_config_home(self, temp_config_file, tmp_path):
        """
        Test loading config from home directory

        """
        # Create a different temp directory for cwd
        cwd = tmp_path / "current"
        cwd.mkdir()

        with patch("gitlab_depcheck.cli.Path.cwd", return_value=cwd):
            with patch("gitlab_depcheck.cli.Path.home", return_value=temp_config_file.parent):
                config = load_config()
                assert config["gitlab"]["url"] == "https://gitlab.example.com"

    def test_load_config_not_found(self, tmp_path):
        """
        Test when no config file exists

        """
        with patch("gitlab_depcheck.cli.Path.cwd", return_value=tmp_path):
            with patch("gitlab_depcheck.cli.Path.home", return_value=tmp_path):
                config = load_config()
                assert config == {}

    def test_load_config_invalid_toml(self, tmp_path):
        """
        Test handling of invalid TOML in config file

        """
        invalid_config = tmp_path / ".gitlab_depcheck.toml"
        invalid_config.write_text("this is not valid toml [[[")

        with patch("gitlab_depcheck.cli.Path.cwd", return_value=tmp_path):
            with patch("gitlab_depcheck.cli.Path.home", return_value=tmp_path / "fake_home"):
                config = load_config()
                assert config == {}

    def test_cli_uses_config_values(self, temp_config_file):
        """
        Test that CLI uses values from config file

        """
        runner = CliRunner()

        with patch("gitlab_depcheck.cli.Path.cwd", return_value=temp_config_file.parent):
            with patch("gitlab_depcheck.cli.asyncio.run", return_value=[]) as mock_run:
                result = runner.invoke(main, ["requests"])
                assert result.exit_code == 0

                # The config should provide the token, so no error about missing token


class TestDisplayResults:
    """Test result display functions"""

    def test_display_no_matches(self, capsys):
        """
        Test display when no matches found

        """
        from gitlab_depcheck.cli import display_results
        from rich.console import Console

        console = Console()
        display_results([], console)
        captured = capsys.readouterr()
        # Rich console output goes to stderr by default
        # We just verify it doesn't crash

    def test_display_single_match(self):
        """
        Test display with single match

        """
        from gitlab_depcheck.cli import display_results
        from rich.console import Console

        matches = [
            DependencyMatch(
                project_name="test/project",
                project_url="https://gitlab.com/test/project",
                file_path="requirements.txt",
                file_url="https://gitlab.com/test/project/-/blob/main/requirements.txt",
                version="requests==2.28.0",
                line_number=1,
            )
        ]

        console = Console()
        display_results(matches, console)
        # Just verify it doesn't crash

    def test_display_multiple_matches_same_project(self):
        """
        Test display with multiple files in same project

        """
        from gitlab_depcheck.cli import display_results
        from rich.console import Console

        matches = [
            DependencyMatch(
                project_name="test/project",
                project_url="https://gitlab.com/test/project",
                file_path="requirements.txt",
                file_url="https://gitlab.com/test/project/-/blob/main/requirements.txt",
                version="requests==2.28.0",
                line_number=1,
            ),
            DependencyMatch(
                project_name="test/project",
                project_url="https://gitlab.com/test/project",
                file_path="requirements-dev.txt",
                file_url="https://gitlab.com/test/project/-/blob/main/requirements-dev.txt",
                version="requests==2.28.0",
                line_number=5,
            ),
        ]

        console = Console()
        display_results(matches, console)
        # Just verify it doesn't crash

    def test_display_version_distribution(self):
        """
        Test version distribution display

        """
        from gitlab_depcheck.cli import display_results
        from rich.console import Console

        matches = [
            DependencyMatch(
                project_name="test/project1",
                project_url="https://gitlab.com/test/project1",
                file_path="requirements.txt",
                file_url="https://gitlab.com/test/project1/-/blob/main/requirements.txt",
                version="requests==2.28.0",
                line_number=1,
            ),
            DependencyMatch(
                project_name="test/project2",
                project_url="https://gitlab.com/test/project2",
                file_path="requirements.txt",
                file_url="https://gitlab.com/test/project2/-/blob/main/requirements.txt",
                version="requests==2.30.0",
                line_number=1,
            ),
            DependencyMatch(
                project_name="test/project3",
                project_url="https://gitlab.com/test/project3",
                file_path="requirements.txt",
                file_url="https://gitlab.com/test/project3/-/blob/main/requirements.txt",
                version="requests==2.28.0",
                line_number=1,
            ),
        ]

        console = Console()
        display_results(matches, console)
        # Just verify it doesn't crash
