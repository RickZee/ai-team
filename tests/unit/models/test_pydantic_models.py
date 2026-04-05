"""Pydantic model validation tests for architecture, development, requirements, QA (T2.3)."""

from __future__ import annotations

import pytest
from ai_team.models.architecture import (
    ArchitectureDecisionRecord,
    ArchitectureDocument,
    Component,
    InterfaceContract,
    TechnologyChoice,
)
from ai_team.models.development import CodeFile, CodeFileList, DeploymentConfig
from ai_team.models.qa_models import (
    BugReport,
    CoverageReport,
)
from ai_team.models.qa_models import (
    TestExecutionResult as QaTestExecutionResult,
)
from ai_team.models.qa_models import (
    TestResult as QaTestResult,
)
from ai_team.models.requirements import (
    AcceptanceCriterion,
    MoSCoW,
    NonFunctionalRequirement,
    RequirementsDocument,
    UserStory,
)
from pydantic import ValidationError


class TestArchitectureModels:
    def test_architecture_document_minimal(self) -> None:
        doc = ArchitectureDocument(
            system_overview="SVC",
            components=[Component(name="api", responsibilities="HTTP")],
            technology_stack=[
                TechnologyChoice(
                    name="FastAPI",
                    category="backend",
                    justification="async",
                )
            ],
            interface_contracts=[
                InterfaceContract(
                    provider="api",
                    consumer="web",
                    contract_type="REST",
                    description="JSON",
                )
            ],
        )
        assert doc.system_overview == "SVC"
        d = doc.model_dump()
        assert d["components"][0]["name"] == "api"

    def test_adr_requires_fields(self) -> None:
        adr = ArchitectureDecisionRecord(
            title="Use Postgres",
            context="Need SQL",
            decision="Postgres",
            consequences="Ops",
        )
        assert adr.status == "Accepted"


class TestDevelopmentModels:
    def test_code_file(self) -> None:
        cf = CodeFile(
            path="src/a.py",
            content="x=1",
            language="python",
            description="mod",
        )
        assert cf.has_tests is False

    def test_code_file_list_root(self) -> None:
        lst = CodeFileList(
            root=[
                CodeFile(
                    path="b.py",
                    content="",
                    language="python",
                    description="b",
                )
            ]
        )
        assert len(lst.root) == 1

    def test_deployment_config_optional_strings(self) -> None:
        dc = DeploymentConfig()
        assert dc.dockerfile is None
        dc2 = DeploymentConfig(dockerfile="FROM scratch", environment_variables={"A": "1"})
        assert dc2.environment_variables["A"] == "1"


class TestRequirementsModels:
    def test_user_story_and_requirements_document(self) -> None:
        us = UserStory(
            as_a="user",
            i_want="login",
            so_that="access",
            priority=MoSCoW.MUST,
            acceptance_criteria=[
                AcceptanceCriterion(description="Given valid creds, When login, Then session")
            ],
        )
        rd = RequirementsDocument(
            project_name="P",
            user_stories=[us],
        )
        assert rd.user_stories[0].priority == MoSCoW.MUST

    def test_nfr(self) -> None:
        nfr = NonFunctionalRequirement(category="security", description="TLS everywhere")
        assert nfr.measurable is True


class TestQaModels:
    def test_test_result_defaults(self) -> None:
        tr = QaTestResult()
        assert tr.quality_gate_passed is False
        assert tr.execution_results.total == 0

    def test_coverage_report_bounds(self) -> None:
        with pytest.raises(ValidationError):
            CoverageReport(line_coverage=1.5)

    def test_bug_report(self) -> None:
        br = BugReport(
            title="Leak",
            severity="high",
            reproduction_steps="1. Open 2. Crash",
        )
        assert br.line_number == 0

    def test_execution_results(self) -> None:
        er = QaTestExecutionResult(passed=3, failed=1, errors=0, skipped=0, total=4)
        assert er.passed + er.failed == 4
