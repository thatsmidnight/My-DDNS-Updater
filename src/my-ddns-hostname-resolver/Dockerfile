# Use the official AWS Lambda Python base image for Python 3.12
FROM public.ecr.aws/lambda/python:3.12

# Set the root directory for the Lambda function, also the working directory
ENV LAMBDA_TASK_ROOT=/var/task
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy requirements.txt first to leverage Docker caching
COPY requirements.txt .
# Install dependencies into the LAMBDA_TASK_ROOT
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -t .

# Copy the main handler file (e.g., your FastAPI app definition)
COPY handler.py .

# Copy the 'ddns_hostname_resolver' package directory into the LAMBDA_TASK_ROOT.
COPY ./ddns_hostname_resolver ./ddns_hostname_resolver/

# Set the CMD to your handler function within handler.py
CMD [ "handler.lambda_handler" ]