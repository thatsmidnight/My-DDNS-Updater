# Standard Library
from unittest.mock import Mock, patch

# Third Party
import pytest
import dns.resolver

# Local
from ddns_hostname_resolver.utils import (
    get_ssm_client,
    resolve_ddns_hostname,
    get_ssm_parameter,
    put_ssm_parameter,
)


class TestUtils:
    """Test suite for utils module functions."""

    def test_get_ssm_client_returns_boto3_client(self):
        """Test that get_ssm_client returns a boto3 SSM client."""
        client = get_ssm_client()
        assert client is not None
        assert hasattr(client, "get_parameter")
        assert hasattr(client, "put_parameter")

    @patch("ddns_hostname_resolver.utils.dns.resolver.Resolver")
    def test_resolve_ddns_hostname_success(self, mock_resolver_class):
        """Test successful hostname resolution."""
        # Arrange
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_answer = Mock()
        mock_answer.__str__ = Mock(return_value="192.168.1.100")
        mock_resolver.resolve.return_value = [mock_answer]
        hostname = "test.example.com"

        # Act
        result = resolve_ddns_hostname(hostname)

        # Assert
        assert result == "192.168.1.100"
        mock_resolver.resolve.assert_called_once_with(hostname, "A")

    @patch("ddns_hostname_resolver.utils.dns.resolver.Resolver")
    def test_resolve_ddns_hostname_no_answer(self, mock_resolver_class):
        """Test hostname resolution when no A record is found."""
        # Arrange
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.resolver.NoAnswer()
        hostname = "nonexistent.example.com"

        # Act
        result = resolve_ddns_hostname(hostname)

        # Assert
        assert result is None
        mock_resolver.resolve.assert_called_once_with(hostname, "A")

    @patch("ddns_hostname_resolver.utils.dns.resolver.Resolver")
    def test_resolve_ddns_hostname_nxdomain(self, mock_resolver_class):
        """Test hostname resolution when hostname does not exist."""
        # Arrange
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN()
        hostname = "invalid.domain"

        # Act
        result = resolve_ddns_hostname(hostname)

        # Assert
        assert result is None
        mock_resolver.resolve.assert_called_once_with(hostname, "A")

    @patch("ddns_hostname_resolver.utils.dns.resolver.Resolver")
    def test_resolve_ddns_hostname_general_exception(self, mock_resolver_class):
        """Test hostname resolution with general exception."""
        # Arrange
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = Exception("Network error")
        hostname = "error.example.com"

        # Act
        result = resolve_ddns_hostname(hostname)

        # Assert
        assert result is None
        mock_resolver.resolve.assert_called_once_with(hostname, "A")

    def test_get_ssm_parameter_success(self, mock_ssm):
        """Test successful retrieval of SSM parameter."""
        # Arrange
        param_name = "/test/parameter"
        param_value = "test_value"
        mock_ssm.put_parameter(
            Name=param_name,
            Value=param_value,
            Type="String"
        )

        # Act
        result = get_ssm_parameter(param_name)

        # Assert
        assert result == param_value

    def test_get_ssm_parameter_not_found(self, mock_ssm):
        """Test SSM parameter retrieval when parameter does not exist."""
        # Arrange
        param_name = "/nonexistent/parameter"

        # Act
        result = get_ssm_parameter(param_name)

        # Assert
        assert result is None

    def test_put_ssm_parameter_success(self, mock_ssm):
        """Test successful update/creation of SSM parameter."""
        # Arrange
        param_name = "/test/new_parameter"
        param_value = "new_test_value"

        # Act
        result = put_ssm_parameter(param_name, param_value)

        # Assert
        assert result is True

        # Verify the parameter was actually set
        response = mock_ssm.get_parameter(Name=param_name)
        assert response["Parameter"]["Value"] == param_value

    def test_put_ssm_parameter_overwrite_existing(self, mock_ssm):
        """Test overwriting an existing SSM parameter."""
        # Arrange
        param_name = "/test/existing_parameter"
        original_value = "original_value"
        new_value = "updated_value"

        # Create initial parameter
        mock_ssm.put_parameter(
            Name=param_name,
            Value=original_value,
            Type="String"
        )

        # Act
        result = put_ssm_parameter(param_name, new_value)

        # Assert
        assert result is True

        # Verify the parameter was updated
        response = mock_ssm.get_parameter(Name=param_name)
        assert response["Parameter"]["Value"] == new_value

    @patch("ddns_hostname_resolver.utils.get_ssm_client")
    def test_put_ssm_parameter_exception(self, mock_get_client):
        """Test SSM parameter update with exception."""
        # Arrange
        mock_client = Mock()
        mock_client.put_parameter.side_effect = Exception("Put operation failed")
        mock_get_client.return_value = mock_client
        param_name = "/error/parameter"
        param_value = "error_value"

        # Act & Assert
        with pytest.raises(Exception, match="Put operation failed"):
            put_ssm_parameter(param_name, param_value)

    @pytest.mark.parametrize("hostname,expected_calls", [
        ("single.example.com", 1),
        ("another.test.com", 1),
        ("third.domain.org", 1),
    ])
    @patch("ddns_hostname_resolver.utils.dns.resolver.Resolver")
    def test_resolve_ddns_hostname_parametrized(
        self,
        mock_resolver_class,
        hostname,
        expected_calls
    ):
        """Parametrized test for hostname resolution with different hostnames."""
        # Arrange
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_answer = Mock()
        mock_answer.__str__ = Mock(return_value="10.0.0.1")
        mock_resolver.resolve.return_value = [mock_answer]

        # Act
        result = resolve_ddns_hostname(hostname)

        # Assert
        assert result == "10.0.0.1"
        assert mock_resolver.resolve.call_count == expected_calls
        mock_resolver.resolve.assert_called_with(hostname, "A")

    def _create_test_parameter(self, mock_ssm, name: str, value: str) -> None:
        """Utility function to create a test parameter in SSM."""
        mock_ssm.put_parameter(
            Name=name,
            Value=value,
            Type="String"
        )

    def _assert_parameter_exists(
        self,
        mock_ssm,
        name: str,
        expected_value: str
    ) -> None:
        """Utility function to assert a parameter exists with expected value."""
        response = mock_ssm.get_parameter(Name=name)
        assert response["Parameter"]["Value"] == expected_value
