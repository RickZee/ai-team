"""Unit tests for ``infrastructure`` DevOps and Cloud generators."""

from __future__ import annotations

from unittest.mock import patch

from ai_team.tools.infrastructure import (
    CLOUD_TOOLS,
    DEVOPS_TOOLS,
    ci_pipeline_generator,
    cloudformation_generator,
    compose_generator,
    cost_estimator,
    dockerfile_generator,
    iam_policy_generator,
    k8s_manifest_generator,
    monitoring_config_generator,
    network_designer,
    terraform_generator,
)


class TestDockerfileGenerator:
    def test_output_contains_multi_stage_and_healthcheck(self) -> None:
        out = dockerfile_generator.run(spec="FastAPI service", base_image="python:3.12-slim")
        assert "FROM python:3.12-slim" in out
        assert "HEALTHCHECK" in out
        assert "USER " in out
        assert "Validation failed" not in out


class TestComposeGenerator:
    def test_output_contains_services_and_redis(self) -> None:
        out = compose_generator.run(spec="app + redis", app_service_name="api", port=8080)
        assert "services:" in out
        assert "redis:" in out
        assert "8080:8080" in out


class TestCiPipelineGenerator:
    def test_output_is_github_actions_shape(self) -> None:
        out = ci_pipeline_generator.run(spec="lint and test", python_version="3.12")
        assert "name: CI" in out
        assert "actions/checkout@v4" in out
        assert "ruff check" in out


class TestK8sManifestGenerator:
    def test_output_contains_deployment_and_security(self) -> None:
        out = k8s_manifest_generator.run(spec="web app", app_name="web", port=3000)
        assert "kind: Deployment" in out
        assert "runAsNonRoot" in out
        assert "containerPort: 3000" in out


class TestMonitoringConfigGenerator:
    def test_output_contains_scrape_config(self) -> None:
        out = monitoring_config_generator.run(spec="app metrics", exporter_port=9100)
        assert "scrape_configs:" in out
        assert "9100" in out


class TestTerraformGenerator:
    def test_output_contains_provider_block(self) -> None:
        out = terraform_generator.run(spec="S3 bucket", provider="aws", region="eu-west-1")
        assert "terraform {" in out
        assert 'provider "aws"' in out
        assert "eu-west-1" in out


class TestCloudFormationGenerator:
    def test_output_contains_template_header(self) -> None:
        out = cloudformation_generator.run(spec="VPC stack", stack_name="Net")
        assert "AWSTemplateFormatVersion" in out
        assert "Parameters:" in out


class TestIamPolicyGenerator:
    def test_output_is_json_policy_shape(self) -> None:
        out = iam_policy_generator.run(spec="S3 read", principle="least privilege")
        assert "2012-10-17" in out
        assert "Statement" in out


class TestCostEstimatorAndNetworkDesigner:
    def test_cost_estimator_returns_text(self) -> None:
        out = cost_estimator.run(spec="EC2 + RDS", region="us-west-2")
        assert "Cost estimate" in out
        assert "us-west-2" in out

    def test_network_designer_returns_subnets(self) -> None:
        out = network_designer.run(spec="3-tier", cidr="172.16.0.0/16", num_azs=3)
        assert "172.16.0.0/16" in out
        assert "3" in out


class TestToolLists:
    def test_devops_tools_count(self) -> None:
        assert len(DEVOPS_TOOLS) == 5

    def test_cloud_tools_count(self) -> None:
        assert len(CLOUD_TOOLS) == 5


class TestValidateIacFailurePath:
    def test_dockerfile_returns_validation_message_when_guardrail_fails(self) -> None:
        with patch(
            "ai_team.tools.infrastructure.SecurityGuardrails.validate_iac_security",
            return_value=(False, "IaC security: hard fail"),
        ):
            out = dockerfile_generator.run(spec="x")
        assert "Validation failed" in out
        assert "hard fail" in out
