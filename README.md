# My-DDNS-Updater

This is a simple, automated service that resolves my DDNS hostname to get my public IP address and update an SSM Parameter to use with a custom whitelisting authorizer.

## Overview

This project deploys AWS resources to:

* Periodically resolve a Dynamic DNS (DDNS) hostname.
* Update an AWS Systems Manager (SSM) Parameter with the resolved public IP.
* Provide a Lambda Authorizer for AWS API Gateway that uses this SSM Parameter to whitelist access based on the source IP.

This setup ensures only your home IP address (or devices connected to your home VPN) can access your private APIs, aiming for minimal cost.

## Architecture

```text
+----------------+          +-------------------+    +-------------------+
|                | Cron(5m) |                   |    |                   |
| EventBridge    +--------->| Lambda Function   +--->| SSM Parameter     |
| (Scheduler)    |          | (update_ssm_ip)   |    | (/current-home-ip)|
|                |          |                   |    |                   |
+----------------+          +---------+---------+    +---------+---------+
     ^                                ^
     |                                |
     | (Reads allowed IP)             |
     |                                |
+-------------------------+           |
|                         |           |
|    API Gateway          +-----------+
|    (Custom Domain,      |
|     with Lambda         |
|     Authorizer)         |
|                         |
+-------------------------+
```

## Prerequisites

* An AWS Account.
* AWS CLI configured with credentials that have administrative permissions for CDK deployment.
* Node.js (required by AWS CDK).
* Python 3.12 installed.
* Poetry installed (`pip install poetry`).
* Your Netgear router's DDNS service configured and running (e.g., pointing `yourname.ddns.net` to your home IP).
* An existing AWS API Gateway (REST API or HTTP API) to which you want to attach the authorizer.
* Basic understanding of AWS CDK and AWS Lambda Authorizers.

## Setup & Deployment

  **Clone the repository:**

  ```bash
  git clone [https://github.com/your-username/my-ddns-updater.git](https://github.com/your-username/my-ddns-updater.git)
  cd my-ddns-updater
  ```

1. **Install Python dependencies using Poetry:**

    ```bash
    poetry install
    ```

2. **Bootstrap your AWS environment (if not already bootstrapped):**

    ```bash
    cdk bootstrap aws://YOUR_ACCOUNT_ID/YOUR_REGION
    ```

    Replace `YOUR_ACCOUNT_ID` and `YOUR_REGION` with your actual AWS account ID and desired region (e.g., `us-west-2` from your workflow).

3. **Synthesize and Deploy the CDK Stack:**

    ```bash
    poetry run cdk deploy --context ddns-hostname="yourname.ddns.net"
    ```

    Replace `"yourname.ddns.net"` with your actual DDNS hostname.
    You will be prompted to confirm IAM changes. Type `y` and press Enter.

    After deployment, the CDK outputs will provide the ARN of the Lambda Authorizer.

## Post-Deployment Configuration (Manual Steps)

1. **Configure API Gateway Custom Authorizer:**
    * Go to the **API Gateway** console.
    * Navigate to your specific API (REST API or HTTP API).
    * **For REST API:**
        * Go to **Authorizers** under your API.
        * Click **Create New Authorizer**.
        * **Authorizer name:** `HomeIpAuthorizer` (or similar).
        * **Authorizer type:** `Lambda`.
        * **Lambda Function:** Select the `MyDdnsResolverStack-IpAuthorizerLambda-xxxxxxxx` function by ARN or name.
        * **Lambda Invoke Role:** Keep default or select your existing API Gateway invoke role.
        * **Identity Source:** `method.request.header.X-Forwarded-For` (for REST APIs, this is usually where the true client IP is if you're behind a load balancer or CloudFront) or `method.request.header.X-Caller-Ip` (if your custom setup forwards it this way). For direct client calls, it might be derived automatically. If using HTTP API, AWS often sets `requestContext.identity.sourceIp` directly. You might need to test which header provides the correct public IP. For basic direct access `requestContext.identity.sourceIp` as used in `authorize_ip.py` is usually sufficient.
        * **Authorization Caching:** Set `Authorization Caching` to **0 seconds** (recommended for dynamic IP whitelisting) to ensure the authorizer always checks the latest IP from SSM.
        * Click **Create**.
        * **Attach to Methods:** Go to **Resources** > **Method Request** (for the method you want to protect) > **Authorization**. Select your new `HomeIpAuthorizer`.
        * **Deploy API:** Remember to deploy your API to a stage after making changes for them to take effect.

    * **For HTTP API:**
        * Go to **Authorizers** under your HTTP API.
        * Click **Create**.
        * **Authorizer type:** `Lambda`.
        * **Lambda function:** Select the `MyDdnsResolverStack-IpAuthorizerLambda-xxxxxxxx` function.
        * **Identity sources:** These define where the Lambda Authorizer gets its input. The default HTTP API payload often places the source IP at `requestContext.http.sourceIp` or `requestContext.identity.sourceIp`. Ensure your `authorize_ip.py` correctly extracts it.
        * **Authorizer caching:** Set to **0 seconds**.
        * Click **Create**.
        * **Attach to Routes:** Go to **Routes** > **Attach authorizer** for the desired route.

2. **Verify SSM Parameter Update:**
    * Go to the AWS Systems Manager console.
    * Navigate to **Parameter Store**.
    * Find the parameter `/my-ddns-updater/current-home-ip` (with your suffix).
    * Verify that its value updates periodically to your home's current public IP address.

## Cost Considerations

This solution remains within AWS's Free Tier for typical personal use:

* **AWS Lambda:** The free tier includes 1 million free requests and 400,000 GB-seconds of compute time per month.
  * **Updater Lambda:** Running every 5 minutes (8,640 invocations/month) with 128MB memory for 0.5 seconds is well within this limit.
  * **Authorizer Lambda:** This will be invoked for *every* API request. For very low traffic (e.g., a few hundred requests a month), it will remain free. If your API sees significant traffic (tens of thousands or more requests per month), you might start incurring a very small cost for this.
* **Amazon EventBridge:** The free tier includes 1 million events per month, which is far more than the 8,640 schedule events per month.
* **AWS Systems Manager Parameter Store:** The free tier includes 10,000 requests per month (for standard parameters), which is more than enough for periodic Lambda access and authorizer lookups.

**Overall, the costs for this setup should be effectively $0.00 (Zero Dollars) for typical personal use.** It is a robust and highly cost-effective way to achieve dynamic IP whitelisting for your private API Gateway.
