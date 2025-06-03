# Standard Library
from typing import Optional, List

# Third Party
import aws_cdk as cdk
import aws_cdk.aws_events as events
import aws_cdk.aws_events_targets as targets
import aws_cdk.aws_iam as iam
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_ssm as ssm
from aws_cdk import Stack, Duration
from constructs import Construct

# Local Modules
from cdk.custom_constructs.lambda_function import CustomLambdaFromDockerImage


class MyDdnsResolverStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, stack_suffix: str, **kwargs
    ) -> None:
        """Initialize the MyDdnsResolverStack.

        This stack sets up a Lambda function that resolves a DDNS hostname
        and updates an SSM Parameter with the current public IP of the home
        network. It also creates an EventBridge rule to trigger the Lambda
        function every 5 minutes. Additionally, it creates an authorizer Lambda
        function that can read the current home IP from the SSM Parameter.

        Parameters
        ----------
        scope : Construct
            The scope in which this stack is defined.
        construct_id : str
            The ID of the construct.
        stack_suffix : str
            A suffix to append to resource names for this stack.

        Raises
        ------
        ValueError
            If the DDNS hostname is not provided in the CDK context.
        """
        super().__init__(scope, construct_id, **kwargs)

        # region Get DDNS hostname from CDK context (passed via CI/CD or CLI)
        self._ddns_hostname = self.node.try_get_context("ddns-hostname")
        if not self._ddns_hostname:
            raise ValueError(
                "DDNS hostname must be provided via CDK context 'ddns-hostname'."
            )
        # endregion

        # region Create SSM Parameter to store current home IP
        # This SSM parameter will store the most recently resolved public IP of my home.
        ip_param_name = f"/my-ddns-updater/current-home-ip{stack_suffix}"
        current_home_ip_param = ssm.StringParameter(
            self,
            "CurrentHomeIpParam",
            parameter_name=ip_param_name,
            string_value="0.0.0.0",  # Initial placeholder IP
            description=(
                "Stores the current public IP address of the home network via DDNS resolver."
            ),
        )

        # Output the SSM Parameter name for reference
        cdk.CfnOutput(
            self,
            "HomeIpSsmParameterName",
            value=current_home_ip_param.parameter_name,
            description="SSM Parameter name storing the current home IP.",
            export_name=f"home-ip-ssm-param-name{stack_suffix}",
        )
        # endregion

        # region Create the Lambda function role
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
                    "ssm:GetParameter",  # Needed to check current value
                ],
                resources=[current_home_ip_param.parameter_arn],
            )
        )
        # endregion

        # region Create the Lambda function from Docker image
        ddns_updater_lambda = self.create_lambda_function(
            construct_id="MyDdnsUpdaterLambda",
            src_folder_path="my-ddns-hostname-resolver",
            environment={
                "DDNS_HOSTNAME": self._ddns_hostname,
                "HOME_IP_SSM_PARAM_NAME": current_home_ip_param.parameter_name,
            },
            memory_size=128,
            timeout=cdk.Duration.seconds(30),
            role=updater_lambda_role,
        )
        # endregion

        # region EventBridge Rule to trigger the Lambda function
        # Schedule the Lambda function to run every 5 minutes
        events.Rule(
            self,
            "DdnsUpdaterSchedule",
            schedule=events.Schedule.cron(minute="0/5"),  # Every 5 minutes
            targets=[targets.LambdaFunction(ddns_updater_lambda)],
        )
        # endregion

        # region Authorizer Lambda Function role
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

        # Grant the authorizer Lambda role permission to invoke the updater Lambda
        ddns_updater_lambda.grant_invoke(authorizer_lambda_role)

        # Output the role ARN for the authorizer Lambda role
        cdk.CfnOutput(
            self,
            "AuthorizerLambdaRoleArn",
            value=authorizer_lambda_role.role_arn,
            description="ARN of the Lambda Authorizer role.",
            export_name=f"authorizer-lambda-role-arn{stack_suffix}",
        )
        # endregion

    def create_lambda_function(
        self,
        construct_id: str,
        src_folder_path: str,
        environment: Optional[dict] = None,
        memory_size: Optional[int] = 128,
        timeout: Optional[Duration] = Duration.seconds(10),
        initial_policy: Optional[List[iam.PolicyStatement]] = None,
        role: Optional[iam.IRole] = None,
        description: Optional[str] = None,
    ) -> lambda_.Function:
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
        role : Optional[iam.IRole], optional
            IAM role to attach to the Lambda function, by default None
        description : Optional[str], optional
            Description for the Lambda function, by default None

        Returns
        -------
        lambda_.Function
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
            role=role,
            description=description,
        )
        return custom_lambda.function
