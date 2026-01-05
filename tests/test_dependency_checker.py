import pytest
from gitlab_depcheck.cli import PythonDependencyChecker


class TestPythonDependencyChecker:
    """Test the PythonDependencyChecker class"""

    def test_normalize_package_name(self):
        """
        Test package name normalization

        """
        assert PythonDependencyChecker.normalize_package_name("Django") == "django"
        assert PythonDependencyChecker.normalize_package_name("django_rest_framework") == "django-rest-framework"
        assert PythonDependencyChecker.normalize_package_name("some.package") == "some-package"
        assert PythonDependencyChecker.normalize_package_name("my___package") == "my-package"

    def test_check_requirements_txt_exact_version(self, sample_requirements_txt):
        """
        Test finding exact version in requirements.txt

        """
        result = PythonDependencyChecker.check_requirements_txt(sample_requirements_txt, "requests")
        assert result is not None
        version, line_num, line_content = result
        assert version == "==2.28.0"
        assert line_num == 2
        assert "requests==2.28.0" in line_content

    def test_check_requirements_txt_with_extras(self, sample_requirements_txt):
        """
        Test finding package with extras in requirements.txt

        """
        result = PythonDependencyChecker.check_requirements_txt(sample_requirements_txt, "pandas")
        assert result is not None
        version, line_num, line_content = result
        assert "[excel]" in version
        assert ">=1.5.0" in version
        assert line_num == 3

    def test_check_requirements_txt_with_comment(self, sample_requirements_txt):
        """
        Test finding package with inline comment

        """
        result = PythonDependencyChecker.check_requirements_txt(sample_requirements_txt, "numpy")
        assert result is not None
        version, line_num, _ = result
        assert version == "==1.23.0"
        assert line_num == 4

    def test_check_requirements_txt_no_version(self, sample_requirements_txt):
        """
        Test finding package without version specifier

        """
        result = PythonDependencyChecker.check_requirements_txt(sample_requirements_txt, "Flask")
        assert result is not None
        version, line_num, _ = result
        assert version == "*"
        assert line_num == 5

    def test_check_requirements_txt_version_range(self, sample_requirements_txt):
        """
        Test finding package with version range

        """
        result = PythonDependencyChecker.check_requirements_txt(sample_requirements_txt, "django")
        assert result is not None
        version, line_num, _ = result
        assert version == ">=4.0.0"
        assert line_num == 6

    def test_check_requirements_txt_not_found(self, sample_requirements_txt):
        """
        Test package not found in requirements.txt

        """
        result = PythonDependencyChecker.check_requirements_txt(sample_requirements_txt, "nonexistent")
        assert result is None

    def test_check_requirements_txt_case_insensitive(self, sample_requirements_txt):
        """
        Test case insensitive package matching

        """
        result = PythonDependencyChecker.check_requirements_txt(sample_requirements_txt, "REQUESTS")
        assert result is not None
        version, _, _ = result
        assert version == "==2.28.0"

    def test_check_pyproject_toml_dependencies(self, sample_pyproject_toml):
        """
        Test finding package in pyproject.toml [project.dependencies]

        """
        result = PythonDependencyChecker.check_pyproject_toml(sample_pyproject_toml, "click")
        assert result is not None
        version, line_num, _ = result
        assert version == ">=8.0.0"
        assert line_num is not None

    def test_check_pyproject_toml_with_extras(self, sample_pyproject_toml):
        """
        Test finding package with extras in pyproject.toml

        """
        result = PythonDependencyChecker.check_pyproject_toml(sample_pyproject_toml, "rich")
        assert result is not None
        version, _, _ = result
        assert "[jupyter]" in version
        assert ">=13.0.0" in version

    def test_check_pyproject_toml_optional_deps(self, sample_pyproject_toml):
        """
        Test finding package in optional dependencies

        """
        result = PythonDependencyChecker.check_pyproject_toml(sample_pyproject_toml, "pytest")
        assert result is not None
        version, _, _ = result
        assert version == ">=8.0.0"

    def test_check_pyproject_toml_not_found(self, sample_pyproject_toml):
        """
        Test package not found in pyproject.toml

        """
        result = PythonDependencyChecker.check_pyproject_toml(sample_pyproject_toml, "nonexistent")
        assert result is None

    def test_check_poetry_dependencies(self, sample_poetry_pyproject):
        """
        Test finding package in poetry dependencies

        """
        result = PythonDependencyChecker.check_pyproject_toml(sample_poetry_pyproject, "requests")
        assert result is not None
        version, line_num, _ = result
        assert version == "^2.28.0"
        assert line_num is not None

    def test_check_poetry_with_extras(self, sample_poetry_pyproject):
        """
        Test finding poetry package with extras

        """
        result = PythonDependencyChecker.check_pyproject_toml(sample_poetry_pyproject, "pandas")
        assert result is not None
        version, _, _ = result
        assert "[excel]" in version
        assert "^1.5.0" in version

    def test_check_poetry_dev_dependencies(self, sample_poetry_pyproject):
        """
        Test finding package in poetry dev dependencies

        """
        result = PythonDependencyChecker.check_pyproject_toml(sample_poetry_pyproject, "pytest")
        assert result is not None
        version, _, _ = result
        assert version == "^7.0.0"

    def test_check_dependency_requirements_file(self, sample_requirements_txt):
        """
        Test check_dependency wrapper for requirements.txt

        """
        result = PythonDependencyChecker.check_dependency("requirements.txt", sample_requirements_txt, "requests")
        assert result is not None
        version, _, _ = result
        assert version == "==2.28.0"

    def test_check_dependency_pyproject_file(self, sample_pyproject_toml):
        """
        Test check_dependency wrapper for pyproject.toml

        """
        result = PythonDependencyChecker.check_dependency("pyproject.toml", sample_pyproject_toml, "click")
        assert result is not None
        version, _, _ = result
        assert version == ">=8.0.0"

    def test_invalid_toml(self):
        """
        Test handling of invalid TOML content

        """
        invalid_toml = "this is not valid toml [[[["
        result = PythonDependencyChecker.check_pyproject_toml(invalid_toml, "test")
        assert result is None

    def test_empty_content(self):
        """
        Test handling of empty content

        """
        result = PythonDependencyChecker.check_requirements_txt("", "test")
        assert result is None

        result = PythonDependencyChecker.check_pyproject_toml("", "test")
        assert result is None

    def test_comments_and_empty_lines(self):
        """
        Test handling of comments and empty lines

        """
        content = """
# This is a comment

requests==2.28.0
# Another comment
"""
        result = PythonDependencyChecker.check_requirements_txt(content, "requests")
        assert result is not None
        version, _, _ = result
        assert version == "==2.28.0"
