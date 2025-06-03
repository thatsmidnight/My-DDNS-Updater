# Standard Library
import os
from typing import Optional, List

# Third Party
import aws_cdk as cdk
import aws_cdk.aws_events as events
import aws_cdk.aws_events_targets as targets
import aws_cdk.aws_iam as iam
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_ssm as ssm
from constructs import Construct

# Local Modules
from cdk.custom_constructs.lambda_function import CustomLambdaFromDockerImage


class MyDdnsResolverStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, stack_suffix: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get DDNS hostname from CDK context (passed via CI/CD or CLI)
        self._ddns_hostname = self.node.try_get_context.try_get_context(
            "ddns-hostname"
        )
        if not ddns_hostname:
            raise ValueError(
                "DDNS hostname must be provided via CDK context 'ddns-hostname'."
            )

        # --- Configuration Parameter (SSM) ---
        # This SSM parameter will store the most recently resolved public IP of your home.
        ip_param_name = f"/my-ddns-updater/current-home-ip{stack_suffix}"
        current_home_ip_param = ssm.StringParameter(
            self,
            "CurrentHomeIpParam",
            parameter_name=ip_param_name,
            string_value="0.0.0.0",  # Initial placeholder IP
            description="Stores the current public IP address of the home network via DDNS resolver."
        )
        cdk.CfnOutput(
            self,
            "HomeIpSsmParameterName",
            value=current_home_ip_param.parameter_name,
            description="SSM Parameter name storing the current home IP.",
        )

        # --- Lambda IAM Role for Updater ---
        updater_lambda_role = iam.Role(
            self,
            "DdnsUpdaterLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # Policy to allow updater Lambda to write to the SSM Parameter
        updater_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ssm:PutParameter",
                    "ssm:GetParameter", # Needed to check current value
                ],
                resources=[current_home_ip_param.parameter_arn],
            )
        )

        # --- Lambda Function (Updater) ---
        ddns_updater_lambda = lambda_.Function(
            self,
            "DdnsUpdaterLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="update_ssm_ip.handler",
            code=lambda_.Code.from_asset("lambda"),
            timeout=cdk.Duration.seconds(30),
            memory_size=128,
            role=updater_lambda_role,
            environment={
                "DDNS_HOSTNAME": ddns_hostname,
                "HOME_IP_SSM_PARAM_NAME": current_home_ip_param.parameter_name,
            },
        )

        # --- EventBridge (CloudWatch Events) Rule ---
        # Schedule the Lambda function to run every 5 minutes
        events.Rule(
            self,
            "DdnsUpdaterSchedule",
            schedule=events.Schedule.cron(minute="0/5"),  # Every 5 minutes
            targets=[targets.LambdaFunction(ddns_updater_lambda)],
        )

        # --- Lambda IAM Role for Authorizer ---
        authorizer_lambda_role = iam.Role(
            self,
            "AuthorizerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        
        # Policy to allow authorizer Lambda to read from the SSM Parameter
        authorizer_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[current_home_ip_param.parameter_arn],
            )
        )

        # --- Lambda Function (Authorizer) ---
        # This Lambda will be attached to your API Gateway to control access.
        # It reads the allowed IP from SSM and compares it with the caller's IP.
        ip_authorizer_lambda = lambda_.Function(
            self,
            "IpAuthorizerLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="authorize_ip.handler",
            code=lambda_.Code.from_asset("lambda"),
            timeout=cdk.Duration.seconds(5), # Authorizers should be fast
            memory_size=128,
            role=authorizer_lambda_role,
            environment={
                "HOME_IP_SSM_PARAM_NAME": current_home_ip_param.parameter_name,
            },
        )
        cdk.CfnOutput(
            self,
            "LambdaAuthorizerArn",
            value=ip_authorizer_lambda.function_arn,
            description="ARN of the Lambda Authorizer. Attach this to your API Gateway methods.",
        )
        # Grant API Gateway permission to invoke the authorizer lambda
        ip_authorizer_lambda.add_permission(
            "ApiGatewayInvokePermission",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"arn:aws:execute-api:{self.region}:{self.account}:*/*/*/*", # Broad permission for simplicity, narrow if needed
        )


    def create_lambda_function(
        self,
        construct_id: str,
        src_folder_path: str,
        environment: Optional[dict] = None,
        memory_size: Optional[int] = 128,
        timeout: Optional[Duration] = Duration.seconds(10),
        initial_policy: Optional[List[iam.PolicyStatement]] = None,
        description: Optional[str] = None,
    ) -> _lambda.Function:
        """Helper method to create a Lambda function.

        Parameters
        ----------
        construct_id : str
            The ID of the construct.
        src_folder_path : str
            The path to the source folder for the Lambda function code.
        environment : Optional[dict], optional
            Environment variables for the Lambda function, by default None
        memory_size : Optional[int], optional
            Memory size for the Lambda function, by default 128
        timeout : Optional[Duration], optional
            Timeout for the Lambda function, by default Duration.seconds(10)
        initial_policy : Optional[List[iam.PolicyStatement]], optional
            Initial IAM policies to attach to the Lambda function, by default None
        description : Optional[str], optional
            Description for the Lambda function, by default None

        Returns
        -------
        _lambda.Function
            The created Lambda function instance.
        """
        custom_lambda = CustomLambdaFromDockerImage(
            scope=self,
            id=construct_id,
            src_folder_path=src_folder_path,
            stack_suffix=self.stack_suffix,
            environment=environment,
            memory_size=memory_size,
            timeout=timeout,
            initial_policy=initial_policy or [],
            description=description,
        )
        return custom_lambda.function
