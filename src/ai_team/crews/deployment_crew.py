"""
Deployment Crew: sequential crew (Cloud Engineer → DevOps Engineer) that produces
a complete deployment package from code, architecture, and test results.

Process: infrastructure_design → deployment_packaging → documentation_generation.
Product Owner expectations for documentation are passed via context (not as crew member).
Guardrails: IaC security validation, deployment completeness check.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Optional, Union

import structlog
from crewai import Crew, Process, Task
from pydantic import BaseModel

from ai_team.agents.cloud_engineer import create_cloud_engineer
from ai_team.agents.devops_engineer import create_devops_engineer
from ai_team.config.settings import get_settings
from ai_team.guardrails import crewai_code_safety_guardrail, crewai_iac_security_guardrail
from ai_team.tasks.deployment_tasks import (
    create_deployment_packaging_task,
    create_documentation_generation_task,
    create_infrastructure_design_task,
)

logger = structlog.get_logger(__name__)


def _serialize_architecture(architecture: Union[BaseModel, str]) -> str:
    """Turn architecture input into a string for task context."""
    if isinstance(architecture, str):
        return architecture
    if hasattr(architecture, "model_dump_json"):
        return architecture.model_dump_json(indent=2)
    if hasattr(architecture, "json"):
        return architecture.json(indent=2)
    return str(architecture)


def _serialize_code_files(code_files: List[Any]) -> str:
    """Summarize code files for task context."""
    if not code_files:
        return "(No code files provided)"
    lines = []
    for i, f in enumerate(code_files[:50], 1):
        if hasattr(f, "path"):
            path = getattr(f, "path", "?")
            desc = getattr(f, "description", "") or ""
            lines.append(f"- {path}: {desc}")
        elif isinstance(f, dict):
            lines.append(f"- {f.get('path', '?')}: {f.get('description', '')}")
        else:
            lines.append(f"- Item {i}: {f}")
    if len(code_files) > 50:
        lines.append(f"... and {len(code_files) - 50} more files")
    return "\n".join(lines) if lines else "(No code files provided)"


def _serialize_test_results(test_results: Any) -> str:
    """Turn test results into a string for task context."""
    if test_results is None:
        return "(No test results provided)"
    if isinstance(test_results, str):
        return test_results
    if hasattr(test_results, "model_dump_json"):
        return test_results.model_dump_json(indent=2)
    if hasattr(test_results, "execution_results"):
        er = test_results.execution_results
        parts = [
            f"Passed: {getattr(er, 'passed', '?')}",
            f"Failed: {getattr(er, 'failed', '?')}",
            f"Total: {getattr(er, 'total', '?')}",
        ]
        if getattr(er, "output", None):
            parts.append(f"Output:\n{er.output[:2000]}")
        return "\n".join(parts)
    return str(test_results)


class DeploymentCrew:
    """
    Sequential crew: Cloud Engineer and DevOps Engineer.
    Tasks: infrastructure_design → deployment_packaging → documentation_generation.
    Input: code files, architecture doc, test results.
    Output: complete deployment package (use package_output() to write to disk).
    """

    def __init__(self, verbose: bool = False) -> None:
        self._cloud = create_cloud_engineer()
        self._devops = create_devops_engineer()
        self._verbose = verbose

    def kickoff(
        self,
        code_files: List[Any],
        architecture: Union[Any, str],
        test_results: Any,
        *,
        product_owner_doc_context: Optional[str] = None,
    ) -> Any:
        """
        Run the deployment crew with the given code files, architecture, and test results.

        Product Owner expectations for documentation can be passed via
        product_owner_doc_context (included in the documentation task, not as a crew member).

        Returns the Crew kickoff result (use package_output() to write to a directory).
        """
        arch_text = _serialize_architecture(architecture)
        code_summary = _serialize_code_files(code_files)
        test_summary = _serialize_test_results(test_results)

        input_context = (
            "## Architecture\n\n"
            f"{arch_text}\n\n"
            "## Codebase (files)\n\n"
            f"{code_summary}\n\n"
            "## Test results\n\n"
            f"{test_summary}"
        )

        infra_description = (
            "Design cloud infrastructure for the application. "
            "Produce IaC templates (Terraform/CloudFormation) aligned with the architecture and codebase.\n\n"
            f"{input_context}"
        )

        task_infra = Task(
            name="infrastructure_design",
            description=infra_description,
            agent=self._cloud,
            context=[],
            expected_output="IaC templates (Terraform/CloudFormation)",
            guardrails=[crewai_code_safety_guardrail, crewai_iac_security_guardrail],
        )

        task_packaging = create_deployment_packaging_task(
            self._devops,
            context=[task_infra],
        )

        doc_description_extra = ""
        if product_owner_doc_context:
            doc_description_extra = (
                "\n\nProduct Owner expectations for documentation:\n"
                f"{product_owner_doc_context}"
            )

        task_docs = create_documentation_generation_task(
            self._devops,
            context=[task_infra, task_packaging],
        )
        if doc_description_extra:
            task_docs = Task(
                name=task_docs.name,
                description=(task_docs.description or "") + doc_description_extra,
                agent=task_docs.agent,
                context=task_docs.context,
                expected_output=task_docs.expected_output,
                guardrails=task_docs.guardrails or [],
            )

        crew = Crew(
            agents=[self._cloud, self._devops],
            tasks=[task_infra, task_packaging, task_docs],
            process=Process.sequential,
            verbose=self._verbose,
        )

        logger.info("deployment_crew_kickoff", tasks=3)
        return crew.kickoff()

    @staticmethod
    def package_output(crew_result: Any, output_dir: Union[str, Path]) -> Path:
        """
        Create a clean output directory structure from the crew result.

        Writes task outputs into organized subdirectories and a README at root.
        output_dir must be within the configured workspace or project output_dir;
        it is created if it does not exist.

        Raises:
            ValueError: If output_dir resolves outside allowed roots.
        """
        settings = get_settings()
        base = Path(output_dir).resolve()
        if not base.is_absolute():
            base = Path.cwd() / base
        try:
            output_path = base.resolve()
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Invalid output path: {e}") from e

        allowed_roots = [
            Path(settings.project.workspace_dir).resolve(),
            Path(settings.project.output_dir).resolve(),
        ]
        under_any = False
        out_str = str(output_path)
        for root in allowed_roots:
            try:
                r = root.resolve()
                if out_str == str(r) or out_str.startswith(str(r) + os.sep):
                    under_any = True
                    break
            except (OSError, RuntimeError):
                continue
        if not under_any:
            raise ValueError(
                f"Output path must be under workspace or output dir: {out_str}"
            )

        tasks_output = getattr(crew_result, "tasks_output", [])
        if not hasattr(tasks_output, "__iter__"):
            tasks_output = []

        task_names = [
            "infrastructure_design",
            "deployment_packaging",
            "documentation_generation",
        ]
        subdirs = ["infrastructure", "deployment", "docs"]
        readme_lines = [
            "# Deployment Package",
            "",
            "This package contains infrastructure, deployment configs, and documentation.",
            "",
        ]

        output_path.mkdir(parents=True, exist_ok=True)

        for i, (name, subdir) in enumerate(zip(task_names, subdirs)):
            dir_path = output_path / subdir
            dir_path.mkdir(parents=True, exist_ok=True)
            raw = ""
            if i < len(tasks_output):
                to = tasks_output[i]
                raw = getattr(to, "raw", None) or getattr(to, "output", "") or str(to)
            out_file = dir_path / f"{name}.md"
            out_file.write_text(raw or "(No output)", encoding="utf-8")
            readme_lines.append(f"- **{subdir}**: [{name}.md]({subdir}/{name}.md)")

        readme_lines.extend(["", "---", ""])
        full_raw = getattr(crew_result, "raw", None) or ""
        if full_raw:
            readme_lines.append("## Full output")
            readme_lines.append("")
            readme_lines.append("<details>")
            readme_lines.append("<summary>Expand</summary>")
            readme_lines.append("")
            readme_lines.append("```")
            readme_lines.append(full_raw[:8000].replace("```", "` ` `"))
            readme_lines.append("```")
            readme_lines.append("")
            readme_lines.append("</details>")

        (output_path / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")
        logger.info("deployment_package_output_written", path=str(output_path))
        return output_path


__all__ = ["DeploymentCrew", "package_output"]


def package_output(crew_result: Any, output_dir: Union[str, Path]) -> Path:
    """Convenience: create deployment package directory from crew result."""
    return DeploymentCrew.package_output(crew_result, output_dir)
