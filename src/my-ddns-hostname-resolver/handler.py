# Standard Library
import os
from typing import Dict, Any

# Third Party
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from ddns_hostname_resolver.utils import (
    resolve_ddns_hostname,
    get_ssm_parameter,
    put_ssm_parameter,
)

# Set up logging
logger = Logger()


@logger.inject_lambda_context(log_event=True)
def lambda_handler(
    event: Dict[str, Any], context: LambdaContext
) -> Dict[str, Any]:
    """Lambda handler function to resolve DDNS and update SSM Parameter.

    Parameters
    ----------
    event : Dict[str, Any]
        The event data passed to the Lambda function.
    context : LambdaContext
        The context object providing runtime information to the handler.

    Returns
    -------
    Dict[str, Any]
        A dictionary containing the status code and message indicating the
        result of the operation.
    """
    logger.info("DDNS Updater Lambda started.")

    # Get environment variables
    ddns_hostname = os.environ.get("DDNS_HOSTNAME")
    home_ip_ssm_param_name = os.environ.get("HOME_IP_SSM_PARAM_NAME")

    # Validate required environment variables
    if not all([ddns_hostname, home_ip_ssm_param_name]):
        logger.error("Missing required environment variables.")
        return {"statusCode": 500, "body": "Missing configuration."}

    try:
        # 1. Resolve DDNS hostname
        current_resolved_ip = resolve_ddns_hostname(ddns_hostname)
        if not current_resolved_ip:
            logger.warning(
                "Could not resolve current public IP. Skipping update."
            )
            return {
                "statusCode": 200,
                "body": "Could not resolve current public IP.",
            }

        # 2. Get current IP from SSM Parameter
        current_ip_in_ssm = get_ssm_parameter(home_ip_ssm_param_name)

        # 3. Check if update is needed
        if current_ip_in_ssm == current_resolved_ip:
            logger.info(
                f"SSM Parameter already contains the current IP ({current_resolved_ip}). "
                "No update needed."
            )
            return {
                "statusCode": 200,
                "body": "SSM parameter already up to date.",
            }
        else:
            logger.info(
                f"IP changed from {current_ip_in_ssm} to {current_resolved_ip}. "
                "Updating SSM parameter."
            )
            put_ssm_parameter(home_ip_ssm_param_name, current_resolved_ip)
            return {
                "statusCode": 200,
                "body": "SSM parameter updated successfully.",
            }

    except Exception as e:
        logger.critical(
            f"Unhandled error in Lambda handler: {e}", exc_info=True
        )
        return {"statusCode": 500, "body": f"Unhandled error: {str(e)}"}
