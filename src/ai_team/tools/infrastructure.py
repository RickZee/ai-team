"""
Infrastructure tools for DevOps and Cloud agents.

Generators for Dockerfile, docker-compose, CI pipelines, K8s manifests,
Terraform, CloudFormation, IAM policies, cost estimation, and network design.
All generated IaC is validated against security best practices via guardrails.
"""

from typing import Optional

from crewai.tools import tool

from ai_team.guardrails import SecurityGuardrails


def _validate_iac(content: str, iac_type: str = "auto") -> str:
    """Run IaC security validation; return content or error message."""
    valid, result = SecurityGuardrails.validate_iac_security(content, iac_type=iac_type)
    if not valid:
        return f"Validation failed: {result}\n\nGenerated content (fix and re-validate):\n{content}"
    return content


# -----------------------------------------------------------------------------
# DevOps tools
# -----------------------------------------------------------------------------


@tool("Dockerfile generator")
def dockerfile_generator(
    spec: str,
    base_image: str = "python:3.11-slim",
    port: Optional[int] = 8000,
    user_name: str = "app",
) -> str:
    """Generate a production-ready Dockerfile with multi-stage build, non-root user, and HEALTHCHECK.
    Input: short spec (e.g. 'Python FastAPI app, install from requirements.txt').
    Uses best practices: multi-stage builds, non-root USER, HEALTHCHECK, minimal layers."""
    content = f"""# Multi-stage build for: {spec}
FROM {base_image} AS builder
WORKDIR /build
RUN apt-get update -qq && apt-get install -y --no-install-recommends \\
    build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM {base_image}
RUN groupadd -r {user_name} && useradd -r -g {user_name} {user_name}
WORKDIR /app
COPY --from=builder /root/.local /home/{user_name}/.local
COPY . .
ENV PATH=/home/{user_name}/.local/bin:$PATH
USER {user_name}
EXPOSE {port or 8000}
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:{port or 8000}/health')" || exit 1
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "{port or 8000}"]
"""
    return _validate_iac(content, "dockerfile")


@tool("Docker Compose generator")
def compose_generator(
    spec: str,
    app_service_name: str = "app",
    port: int = 8000,
) -> str:
    """Generate docker-compose.yml for the given spec (e.g. 'app + redis + postgres').
    Best practices: non-root user, health checks, resource limits, named volumes."""
    content = f"""# docker-compose for: {spec}
version: "3.9"
services:
  {app_service_name}:
    build: .
    user: "1000:1000"
    ports:
      - "{port}:{port}"
    environment:
      - NODE_ENV=production
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{port}/health"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 10s
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 1G
        reservations:
          memory: 256M
  redis:
    image: redis:7-alpine
    user: "999:999"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
volumes:
  redis_data:
"""
    return _validate_iac(content, "docker_compose")


@tool("CI pipeline generator")
def ci_pipeline_generator(
    spec: str,
    on_branches: str = "main, develop",
    python_version: str = "3.11",
) -> str:
    """Generate GitHub Actions CI workflow (e.g. .github/workflows/ci.yml).
    Spec describes steps needed: lint, test, build. Uses secure practices and caching."""
    content = f"""# CI pipeline: {spec}
name: CI
on:
  push:
    branches: [{', '.join(b.strip() for b in on_branches.split(','))}]
  pull_request:
    branches: [{', '.join(b.strip() for b in on_branches.split(','))}]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "{python_version}"
          cache: "pip"
      - name: Install deps
        run: pip install ruff mypy
      - name: Ruff
        run: ruff check .
      - name: Mypy
        run: mypy . --ignore-missing-imports || true
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "{python_version}"
          cache: "pip"
      - name: Install
        run: pip install -e ".[dev]"
      - name: Pytest
        run: pytest tests/ -v --tb=short
"""
    return _validate_iac(content, "auto")


@tool("Kubernetes manifest generator")
def k8s_manifest_generator(
    spec: str,
    app_name: str = "app",
    image: str = "myapp:latest",
    port: int = 8000,
) -> str:
    """Generate K8s manifests (Deployment + Service) with resource limits and securityContext.
    Spec: short description of the app. Enforces runAsNonRoot, resource limits, liveness/readiness."""
    content = f"""# K8s manifests: {spec}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {app_name}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {app_name}
  template:
    metadata:
      labels:
        app: {app_name}
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: {app_name}
        image: {image}
        ports:
        - containerPort: {port}
        resources:
          limits:
            cpu: "1000m"
            memory: "512Mi"
          requests:
            cpu: "100m"
            memory: "128Mi"
        livenessProbe:
          httpGet:
            path: /health
            port: {port}
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: {port}
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: {app_name}
spec:
  selector:
    app: {app_name}
  ports:
  - port: {port}
    targetPort: {port}
  type: ClusterIP
"""
    return _validate_iac(content, "k8s")


@tool("Monitoring config generator")
def monitoring_config_generator(spec: str, exporter_port: int = 9090) -> str:
    """Generate monitoring config (Prometheus scrape config or similar) for the given spec."""
    content = f"""# Monitoring: {spec}
# Prometheus scrape config
scrape_configs:
  - job_name: 'app'
    static_configs:
      - targets: ['localhost:{exporter_port}']
    metrics_path: /metrics
    scrape_interval: 15s
"""
    return _validate_iac(content, "auto")


# -----------------------------------------------------------------------------
# Cloud tools
# -----------------------------------------------------------------------------


@tool("Terraform generator")
def terraform_generator(
    spec: str,
    provider: str = "aws",
    region: str = "us-east-1",
) -> str:
    """Generate Terraform module snippet for the given spec. Best practices: state, module reuse, tagging."""
    content = f"""# Terraform: {spec}
terraform {{
  required_version = ">= 1.5"
  required_providers {{
    {provider} = {{
      source  = "hashicorp/{provider}"
      version = "~> 5.0"
    }}
  }}
  backend "s3" {{
    # bucket, key, region via backend config
  }}
}}

provider "{provider}" {{
  region = "{region}"
  default_tags {{
    tags = {{
      Environment = "production"
      ManagedBy   = "terraform"
    }}
  }}
}}

# Define resources per spec; use variables for sensitive values with sensitive = true
"""
    return _validate_iac(content, "terraform")


@tool("CloudFormation generator")
def cloudformation_generator(spec: str, stack_name: str = "MyStack") -> str:
    """Generate AWS CloudFormation template snippet. Best practices: parameters, conditions, tagging."""
    content = f"""# CloudFormation: {spec}
AWSTemplateFormatVersion: "2010-09-09"
Description: {spec}
Parameters:
  Environment:
    Type: String
    Default: production
    AllowedValues: [development, staging, production]
Resources:
  # Add resources per spec; use Ref and Fn::GetAtt for cross-refs
  # Enable tagging on resources
"""
    return _validate_iac(content, "cloudformation")


@tool("IAM policy generator")
def iam_policy_generator(spec: str, principle: str = "least privilege") -> str:
    """Generate IAM policy JSON for the given spec. Enforces least privilege, no wildcards where avoidable."""
    content = f"""# IAM policy: {spec} ({principle})
{{
  "Version": "2012-10-17",
  "Statement": [
    {{
      "Sid": "AllowMinimalActions",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-bucket",
        "arn:aws:s3:::my-bucket/*"
      ],
      "Condition": {{
        "StringEquals": {{ "aws:RequestedRegion": "us-east-1" }}
      }}
    }}
  ]
}}
"""
    return _validate_iac(content, "iam")


@tool("Cost estimator")
def cost_estimator(spec: str, region: str = "us-east-1") -> str:
    """Produce a rough cost estimate and optimization hints for the given infrastructure spec."""
    return f"""Cost estimate (rough) for: {spec}
Region: {region}
- Compute: size instances per spec; use Spot where appropriate
- Storage: estimate GB and tier (Standard / IA / Glacier)
- Data transfer: out to internet is billable
Recommendations: use Reserved Instances for baseline; right-size; enable cost allocation tags.
"""


@tool("Network designer")
def network_designer(
    spec: str,
    cidr: str = "10.0.0.0/16",
    num_azs: int = 2,
) -> str:
    """Design VPC and subnet layout for the given spec. Security groups and NACLs best practices."""
    return f"""Network design: {spec}
VPC CIDR: {cidr}
AZs: {num_azs}
- Public subnets: 10.0.1.0/24, 10.0.2.0/24 (for ALB/NAT)
- Private subnets: 10.0.10.0/24, 10.0.11.0/24 (for app/DB)
- Security groups: restrict by source CIDR and port; no 0.0.0.0/0 on DB ports
- NACLs: stateless; allow ephemeral return traffic
"""


# Export lists for agents
DEVOPS_TOOLS = [
    dockerfile_generator,
    compose_generator,
    ci_pipeline_generator,
    k8s_manifest_generator,
    monitoring_config_generator,
]
CLOUD_TOOLS = [
    terraform_generator,
    cloudformation_generator,
    iam_policy_generator,
    cost_estimator,
    network_designer,
]
