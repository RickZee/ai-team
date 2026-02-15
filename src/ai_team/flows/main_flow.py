"""
AI Team Main Flow Orchestration

This module implements the primary event-driven flow that orchestrates
all crews and manages the end-to-end software development process.
"""

from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import uuid4
from datetime import datetime

from crewai import Flow
from crewai.flow.flow import start, listen, router
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()


# =============================================================================
# STATE MODELS
# =============================================================================

class ProjectPhase(str, Enum):
    """Phases of the development lifecycle."""
    INTAKE = "intake"
    PLANNING = "planning"
    DEVELOPMENT = "development"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    COMPLETE = "complete"
    FAILED = "failed"
    AWAITING_HUMAN = "awaiting_human"


class RequirementsDocument(BaseModel):
    """Structured requirements output from planning."""
    project_name: str
    description: str
    user_stories: List[Dict[str, str]] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)
    technical_requirements: List[str] = Field(default_factory=list)
    out_of_scope: List[str] = Field(default_factory=list)


class ArchitectureDocument(BaseModel):
    """Structured architecture output from planning."""
    overview: str
    components: List[Dict[str, Any]] = Field(default_factory=list)
    technology_stack: Dict[str, str] = Field(default_factory=dict)
    api_design: Optional[Dict[str, Any]] = None
    database_schema: Optional[Dict[str, Any]] = None


class CodeFile(BaseModel):
    """Represents a generated code file."""
    path: str
    content: str
    language: str
    description: str
    has_tests: bool = False


class TestResult(BaseModel):
    """Results from test execution."""
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    coverage_percent: float = 0.0
    error_messages: List[str] = Field(default_factory=list)
    
    @property
    def all_passed(self) -> bool:
        return self.failed == 0 and self.errors == 0 and self.total_tests > 0


class DeploymentConfig(BaseModel):
    """Deployment configuration output."""
    dockerfile: Optional[str] = None
    docker_compose: Optional[str] = None
    ci_cd_config: Optional[str] = None
    environment_variables: Dict[str, str] = Field(default_factory=dict)


class ProjectState(BaseModel):
    """Unified state management for the development flow."""
    
    # Identification
    project_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # User input
    user_request: str = ""
    clarifications: List[str] = Field(default_factory=list)
    
    # Phase tracking
    current_phase: ProjectPhase = ProjectPhase.INTAKE
    phase_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Planning outputs
    requirements: Optional[RequirementsDocument] = None
    architecture: Optional[ArchitectureDocument] = None
    
    # Development outputs
    generated_files: List[CodeFile] = Field(default_factory=list)
    
    # Testing outputs
    test_results: Optional[TestResult] = None
    test_retry_count: int = 0
    max_test_retries: int = 3
    
    # Deployment outputs
    deployment_config: Optional[DeploymentConfig] = None
    
    # Error tracking
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    # Human interaction
    human_feedback: Optional[str] = None
    awaiting_human_input: bool = False
    
    # Metrics
    total_duration_seconds: float = 0.0
    
    def add_phase_transition(self, from_phase: ProjectPhase, to_phase: ProjectPhase, reason: str = ""):
        """Record a phase transition."""
        self.phase_history.append({
            "from": from_phase.value,
            "to": to_phase.value,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason
        })
        self.current_phase = to_phase
        self.updated_at = datetime.utcnow()
    
    def add_error(self, error_type: str, message: str, recoverable: bool = True):
        """Record an error."""
        self.errors.append({
            "type": error_type,
            "message": message,
            "recoverable": recoverable,
            "timestamp": datetime.utcnow().isoformat(),
            "phase": self.current_phase.value
        })


# =============================================================================
# MAIN FLOW
# =============================================================================

class AITeamFlow(Flow[ProjectState]):
    """
    Main orchestration flow for the AI development team.
    
    Coordinates all crews through the software development lifecycle:
    1. Intake & Validation
    2. Planning (Requirements + Architecture)
    3. Development (Code Generation)
    4. Testing (QA Validation)
    5. Deployment (DevOps Configuration)
    """
    
    def __init__(self):
        super().__init__()
        self.logger = structlog.get_logger().bind(flow="AITeamFlow")
    
    @start()
    def intake_request(self) -> Dict[str, Any]:
        """Entry point: Parse and validate user request."""
        self.logger.info("intake_started", request_length=len(self.state.user_request))
        
        if not self.state.user_request or len(self.state.user_request.strip()) < 10:
            self.state.add_error("validation_error", "Request too short.")
            return {"status": "invalid", "reason": "request_too_short"}
        
        # Import here to avoid circular imports
        from ai_team.guardrails import SecurityGuardrails
        
        is_safe, message = SecurityGuardrails.validate_prompt_injection(self.state.user_request)
        if not is_safe:
            self.state.add_error("security_error", message, recoverable=False)
            return {"status": "rejected", "reason": "prompt_injection"}
        
        self.state.add_phase_transition(ProjectPhase.INTAKE, ProjectPhase.PLANNING, "Input validated")
        return {"status": "success", "request": self.state.user_request}
    
    @router(intake_request)
    def route_after_intake(self, intake_result: Dict[str, Any]) -> str:
        """Route based on intake validation results."""
        status = intake_result.get("status", "unknown")
        
        if status == "success":
            return "run_planning"
        elif status == "invalid":
            return "request_clarification"
        else:
            return "handle_fatal_error"
    
    @listen("run_planning")
    def run_planning_crew(self) -> Dict[str, Any]:
        """Execute planning crew for requirements and architecture."""
        self.logger.info("planning_started")
        
        try:
            # In real implementation, import and run PlanningCrew
            # For now, create placeholder outputs
            self.state.requirements = RequirementsDocument(
                project_name=f"Project_{self.state.project_id[:8]}",
                description=self.state.user_request,
                user_stories=[],
                acceptance_criteria=[],
                technical_requirements=[]
            )
            
            self.state.architecture = ArchitectureDocument(
                overview="Architecture designed by AI Architect",
                components=[],
                technology_stack={}
            )
            
            self.state.add_phase_transition(ProjectPhase.PLANNING, ProjectPhase.DEVELOPMENT, "Planning completed")
            return {"status": "success", "needs_clarification": False}
            
        except Exception as e:
            self.logger.error("planning_failed", error=str(e))
            self.state.add_error("planning_error", str(e))
            return {"status": "error", "error": str(e)}
    
    @router(run_planning_crew)
    def route_after_planning(self, planning_result: Dict[str, Any]) -> str:
        """Route based on planning outcome."""
        if planning_result.get("status") == "success":
            if planning_result.get("needs_clarification"):
                return "request_clarification"
            return "run_development"
        return "handle_fatal_error"
    
    @listen("run_development")
    def run_development_crew(self) -> Dict[str, Any]:
        """Execute development crew for code generation."""
        self.logger.info("development_started")
        
        try:
            # Placeholder for actual development crew
            self.state.generated_files = [
                CodeFile(
                    path="src/main.py",
                    content="# Generated main file\nprint('Hello World')",
                    language="python",
                    description="Main application entry point",
                    has_tests=False
                )
            ]
            
            self.state.add_phase_transition(ProjectPhase.DEVELOPMENT, ProjectPhase.TESTING, "Code generated")
            return {"status": "success", "files": self.state.generated_files}
            
        except Exception as e:
            self.logger.error("development_failed", error=str(e))
            self.state.add_error("development_error", str(e))
            return {"status": "error", "error": str(e)}
    
    @router(run_development_crew)
    def route_after_development(self, dev_result: Dict[str, Any]) -> str:
        """Route based on development outcome."""
        if dev_result.get("status") == "success":
            return "run_testing"
        return "handle_development_error"
    
    @listen("run_testing")
    def run_testing_crew(self) -> Dict[str, Any]:
        """Execute testing crew for QA validation."""
        self.logger.info("testing_started")
        
        try:
            # Placeholder for actual testing crew
            self.state.test_results = TestResult(
                total_tests=10,
                passed=10,
                failed=0,
                errors=0,
                coverage_percent=85.0
            )
            
            if self.state.test_results.all_passed:
                self.state.add_phase_transition(ProjectPhase.TESTING, ProjectPhase.DEPLOYMENT, "Tests passed")
                return {"status": "success", "results": self.state.test_results}
            else:
                return {"status": "tests_failed", "results": self.state.test_results}
                
        except Exception as e:
            self.logger.error("testing_failed", error=str(e))
            return {"status": "error", "error": str(e)}
    
    @router(run_testing_crew)
    def route_after_testing(self, test_result: Dict[str, Any]) -> str:
        """Route based on test results."""
        status = test_result.get("status", "error")
        
        if status == "success":
            return "run_deployment"
        elif status == "tests_failed":
            if self.state.test_retry_count < self.state.max_test_retries:
                self.state.test_retry_count += 1
                return "retry_development"
            return "escalate_test_failures"
        return "handle_testing_error"
    
    @listen("run_deployment")
    def run_deployment_crew(self) -> Dict[str, Any]:
        """Execute deployment crew for DevOps configuration."""
        self.logger.info("deployment_started")
        
        try:
            self.state.deployment_config = DeploymentConfig(
                dockerfile="FROM python:3.11-slim\nWORKDIR /app\nCOPY . .\nCMD [\"python\", \"main.py\"]",
                docker_compose="version: '3.8'\nservices:\n  app:\n    build: .",
            )
            
            self.state.add_phase_transition(ProjectPhase.DEPLOYMENT, ProjectPhase.COMPLETE, "Deployment configured")
            return {"status": "success", "config": self.state.deployment_config}
            
        except Exception as e:
            self.logger.error("deployment_failed", error=str(e))
            return {"status": "error", "error": str(e)}
    
    @router(run_deployment_crew)
    def route_after_deployment(self, deploy_result: Dict[str, Any]) -> str:
        """Route based on deployment outcome."""
        if deploy_result.get("status") == "success":
            return "finalize_project"
        return "handle_deployment_error"
    
    @listen("finalize_project")
    def finalize_project(self) -> Dict[str, Any]:
        """Final step: Package all outputs and generate summary."""
        duration = (datetime.utcnow() - self.state.created_at).total_seconds()
        self.state.total_duration_seconds = duration
        
        summary = {
            "project_id": self.state.project_id,
            "status": "complete",
            "files_generated": len(self.state.generated_files),
            "tests_passed": self.state.test_results.passed if self.state.test_results else 0,
            "duration_seconds": duration,
        }
        
        self.logger.info("project_complete", **summary)
        return summary
    
    @listen("request_clarification")
    def request_human_clarification(self) -> Dict[str, Any]:
        """Request clarification from user."""
        self.state.awaiting_human_input = True
        self.state.add_phase_transition(self.state.current_phase, ProjectPhase.AWAITING_HUMAN, "Clarification needed")
        return {"status": "awaiting_input", "message": "Please provide more details."}
    
    @listen("escalate_test_failures")
    def escalate_to_human(self) -> Dict[str, Any]:
        """Escalate persistent failures to human."""
        self.state.add_phase_transition(self.state.current_phase, ProjectPhase.AWAITING_HUMAN, "Escalated")
        return {"status": "escalated", "message": f"Tests failed after {self.state.test_retry_count} retries."}
    
    @listen("handle_fatal_error")
    def handle_fatal_error(self) -> Dict[str, Any]:
        """Handle unrecoverable errors."""
        self.state.add_phase_transition(self.state.current_phase, ProjectPhase.FAILED, "Fatal error")
        return {"status": "failed", "errors": self.state.errors}
    
    @listen("retry_development")
    def retry_development(self) -> str:
        """Retry development with test feedback."""
        self.logger.info("retrying_development")
        return "run_development"
    
    @listen("handle_development_error")
    def handle_development_error(self) -> Dict[str, Any]:
        return {"status": "error", "phase": "development"}
    
    @listen("handle_testing_error")
    def handle_testing_error(self) -> Dict[str, Any]:
        return {"status": "error", "phase": "testing"}
    
    @listen("handle_deployment_error")
    def handle_deployment_error(self) -> Dict[str, Any]:
        return {"status": "error", "phase": "deployment"}


def run_ai_team(project_request: str) -> Dict[str, Any]:
    """Main entry point to run the AI Team flow."""
    flow = AITeamFlow()
    flow.state.user_request = project_request
    result = flow.kickoff()
    
    return {
        "result": result,
        "state": flow.state.model_dump()
    }


if __name__ == "__main__":
    result = run_ai_team("Create a simple REST API for managing a todo list")
    print(result)
