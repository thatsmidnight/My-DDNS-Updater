# Standard Library
from typing import Optional

# Third Party
import boto3
import dns.resolver
from aws_lambda_powertools import Logger

# Set up logging
logger = Logger(service="ddns_hostname_resolver_utils")


def get_ssm_client() -> boto3.client:
    """Returns a Boto3 SSM client for interacting with AWS Systems Manager
    Parameter Store.

    Returns
    -------
    boto3.client
        A Boto3 client for AWS Systems Manager.
    """
    return boto3.client("ssm")


def resolve_ddns_hostname(hostname: str) -> Optional[str]:
    """Resolves the DDNS hostname to its current public IP address.

    Parameters
    ----------
    hostname : str
        The DDNS hostname to resolve.

    Returns
    -------
    Optional[str]
        The resolved IP address as a string, or None if resolution fails.
    """
    try:
        # Create a DNS resolver and resolve the hostname
        resolver = dns.resolver.Resolver()
        # Set the resolver to use the default DNS servers
        answers = resolver.resolve(hostname, "A")
        # Extract the first answer (IP address)
        current_ip = str(answers[0])
        logger.info(f"Resolved DDNS hostname '{hostname}' to IP: {current_ip}")
        return current_ip
    except dns.resolver.NoAnswer:
        # Handle the case where no answer is returned
        logger.warning(f"No A record found for hostname: {hostname}")
    except dns.resolver.NXDOMAIN:
        # Handle the case where the hostname does not exist
        logger.warning(f"Hostname does not exist: {hostname}")
    except Exception as e:
        # Handle other exceptions (e.g., network issues)
        logger.error(f"Error resolving DDNS hostname '{hostname}': {e}")
    return None


def get_ssm_parameter(param_name: str) -> Optional[str]:
    """Retrieves a string parameter from SSM Parameter Store.

    Parameters
    ----------
    param_name : str
        The name of the SSM parameter to retrieve.

    Returns
    -------
    Optional[str]
        The value of the SSM parameter, or None if not found or an error
        occurs.

    Raises
    -------
    Exception
        If there is an error retrieving the parameter.
    """
    try:
        # Get the SSM client
        ssm_client = get_ssm_client()
        # Get the parameter value
        response = ssm_client.get_parameter(
            Name=param_name, WithDecryption=False
        )
        return response["Parameter"]["Value"]
    except ssm_client.exceptions.ParameterNotFound:
        # Handle the case where the parameter does not exist
        logger.warning(f"SSM Parameter '{param_name}' not found.")
        return None
    except Exception as e:
        # Handle other exceptions
        logger.error(f"Error getting SSM Parameter '{param_name}': {e}")
        raise


def put_ssm_parameter(param_name: str, new_value: str) -> bool:
    """Updates or creates a string parameter in SSM Parameter Store.

    Parameters
    ----------
    param_name : str
        The name of the SSM parameter to update or create.
    new_value : str
        The new value to set for the SSM parameter.

    Returns
    -------
    bool
        True if the parameter was successfully updated, False otherwise.

    Raises
    -------
    Exception
        If there is an error putting the parameter.
    """
    try:
        # Get the SSM client
        ssm_client = get_ssm_client()
        # Put the parameter with overwrite option
        ssm_client.put_parameter(
            Name=param_name, Value=new_value, Type="String", Overwrite=True
        )
        logger.info(
            f"Successfully updated SSM Parameter '{param_name}' to: {new_value}"
        )
        return True
    except Exception as e:
        # Handle exceptions during the put operation
        logger.error(
            f"Error putting SSM Parameter '{param_name}' with value '{new_value}': {e}"
        )
        raise
