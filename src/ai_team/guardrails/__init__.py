"""
AI Team Guardrails Module

Comprehensive guardrails for behavioral, security, and quality validation.
These guardrails ensure agents stay on-task, produce safe outputs, and maintain quality.
"""

from typing import Tuple, Any, List, Dict, Optional, Callable
import re
import json
import os


# =============================================================================
# BEHAVIORAL GUARDRAILS
# =============================================================================

class BehavioralGuardrails:
    """Guardrails ensuring agents stay on-task and follow protocols."""
    
    ROLE_RESTRICTIONS = {
        "qa_engineer": {
            "forbidden_patterns": [
                r"def\s+(?!test_)\w+\(",
                r"class\s+(?!Test)\w+\(",
            ],
            "message": "QA Engineer should only write test code, not production code."
        },
        "product_owner": {
            "forbidden_patterns": [
                r"def\s+\w+\(",
                r"class\s+\w+\(",
                r"import\s+\w+",
            ],
            "message": "Product Owner should focus on requirements, not implementation."
        },
        "architect": {
            "forbidden_patterns": [
                r"INSERT\s+INTO",
                r"DELETE\s+FROM",
                r"UPDATE\s+\w+\s+SET",
            ],
            "message": "Architect should design systems, not implement data operations."
        }
    }
    
    @classmethod
    def validate_role_adherence(cls, content: str, agent_role: str) -> Tuple[bool, str]:
        """Ensure agent output aligns with their designated role."""
        role_lower = agent_role.lower().replace(" ", "_")
        
        if role_lower in cls.ROLE_RESTRICTIONS:
            restrictions = cls.ROLE_RESTRICTIONS[role_lower]
            for pattern in restrictions["forbidden_patterns"]:
                if re.search(pattern, content, re.IGNORECASE):
                    return (False, f"Role violation: {restrictions['message']}")
        
        return (True, content)
    
    @staticmethod
    def validate_scope_control(content: str, task_description: str, max_expansion: float = 0.3) -> Tuple[bool, str]:
        """Prevent agents from expanding scope beyond the original task."""
        task_keywords = set(re.findall(r'\b\w{4,}\b', task_description.lower()))
        output_keywords = set(re.findall(r'\b\w{4,}\b', content.lower()))
        
        if not task_keywords:
            return (True, content)
        
        overlap = len(task_keywords & output_keywords) / len(task_keywords)
        
        if overlap < (1 - max_expansion):
            return (False, f"Output deviates from task scope (relevance: {overlap:.0%})")
        
        return (True, content)
    
    @staticmethod
    def validate_reasoning_included(content: str) -> Tuple[bool, str]:
        """Ensure agent included reasoning in their response."""
        reflection_indicators = [
            "because", "therefore", "considering", "given that",
            "the reason", "this approach", "alternatively", "trade-off",
            "rationale", "decision", "chose", "selected"
        ]
        
        has_reflection = any(ind in content.lower() for ind in reflection_indicators)
        
        if not has_reflection and len(content) > 200:
            return (False, "Please include reasoning for your decisions.")
        
        return (True, content)


# =============================================================================
# SECURITY GUARDRAILS
# =============================================================================

class SecurityGuardrails:
    """Guardrails protecting against security vulnerabilities."""
    
    DANGEROUS_CODE_PATTERNS = [
        (r'os\.system\s*\(', 'System command execution'),
        (r'subprocess\.(run|call|Popen|check_output)', 'Subprocess execution'),
        (r'eval\s*\(', 'Dynamic code evaluation'),
        (r'exec\s*\(', 'Dynamic code execution'),
        (r'__import__\s*\(', 'Dynamic import'),
        (r'compile\s*\(.*exec', 'Code compilation'),
        (r'open\s*\([^)]*[\'\"]/etc/', 'System file access'),
        (r'chmod\s+[0-7]*7[0-7]*', 'World-writable permissions'),
        (r'rm\s+-rf\s+/', 'Root filesystem deletion'),
        (r'DROP\s+(TABLE|DATABASE|INDEX)', 'SQL destructive operation'),
        (r'TRUNCATE\s+TABLE', 'SQL truncate'),
        (r';\s*DROP', 'SQL injection pattern'),
        (r'UNION\s+SELECT', 'SQL injection pattern'),
        (r'<script[^>]*>', 'XSS script injection'),
    ]
    
    PII_PATTERNS = [
        (r'\b\d{3}-\d{2}-\d{4}\b', 'SSN'),
        (r'\b(?:\d{4}[-\s]?){3}\d{4}\b', 'CREDIT_CARD'),
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'EMAIL'),
        (r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', 'PHONE'),
    ]
    
    SECRET_PATTERNS = [
        (r'(api[_-]?key|apikey)\s*[:=]\s*[\'\"]\S+[\'\"]', 'API_KEY'),
        (r'(password|passwd|pwd)\s*[:=]\s*[\'\"]\S+[\'\"]', 'PASSWORD'),
        (r'(secret|token|auth)\s*[:=]\s*[\'\"]\S+[\'\"]', 'SECRET_TOKEN'),
        (r'(aws_access_key_id)\s*[:=]\s*[\'\"]\S+[\'\"]', 'AWS_KEY'),
        (r'Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+', 'JWT_TOKEN'),
        (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----', 'PRIVATE_KEY'),
        (r'ghp_[A-Za-z0-9]{36}', 'GITHUB_TOKEN'),
        (r'sk-[A-Za-z0-9]{48}', 'OPENAI_KEY'),
    ]
    
    INJECTION_PATTERNS = [
        r'ignore\s+(previous|all|above)\s+instructions',
        r'disregard\s+(your|the)\s+(rules|instructions)',
        r'you\s+are\s+now\s+(a|an)\s+',
        r'pretend\s+(to\s+be|you\s+are)',
        r'forget\s+(everything|your\s+training)',
        r'jailbreak',
        r'DAN\s+mode',
    ]
    
    @classmethod
    def validate_code_safety(cls, content: str) -> Tuple[bool, str]:
        """Check generated code for dangerous patterns."""
        violations = []
        
        for pattern, description in cls.DANGEROUS_CODE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(description)
        
        if violations:
            return (False, f"Security violation: {', '.join(set(violations))}")
        
        return (True, content)
    
    @classmethod
    def redact_pii(cls, content: str) -> Tuple[bool, str]:
        """Detect and redact personally identifiable information."""
        redacted = content
        pii_found = []
        
        for pattern, pii_type in cls.PII_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                pii_found.append(f"{pii_type}: {len(matches)}")
                redacted = re.sub(pattern, f'[REDACTED_{pii_type}]', redacted, flags=re.IGNORECASE)
        
        if pii_found:
            return (True, f"⚠️ PII REDACTED: {'; '.join(pii_found)}\n\n{redacted}")
        
        return (True, content)
    
    @classmethod
    def validate_no_secrets(cls, content: str) -> Tuple[bool, str]:
        """Ensure no secrets or credentials are exposed."""
        secrets_found = []
        
        for pattern, secret_type in cls.SECRET_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                secrets_found.append(secret_type)
        
        if secrets_found:
            return (False, f"Secrets detected: {', '.join(set(secrets_found))}. Use environment variables instead.")
        
        return (True, content)
    
    @classmethod
    def validate_prompt_injection(cls, input_text: str) -> Tuple[bool, str]:
        """Detect potential prompt injection attempts."""
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, input_text, re.IGNORECASE):
                return (False, "Input contains prompt injection.")
        
        return (True, input_text)
    
    @staticmethod
    def validate_file_path(path: str, allowed_dirs: List[str]) -> Tuple[bool, str]:
        """Validate file paths are within allowed directories."""
        try:
            normalized = os.path.normpath(os.path.abspath(path))
        except Exception:
            return (False, "Invalid file path format.")
        
        if ".." in path:
            return (False, "Path traversal detected.")
        
        if not any(normalized.startswith(os.path.abspath(d)) for d in allowed_dirs):
            return (False, f"Path outside allowed directories.")
        
        return (True, normalized)


# =============================================================================
# QUALITY GUARDRAILS
# =============================================================================

class QualityGuardrails:
    """Guardrails ensuring output quality and consistency."""
    
    @staticmethod
    def validate_word_count(content: str, min_words: int = 0, max_words: int = 10000) -> Tuple[bool, str]:
        """Validate output length is within acceptable range."""
        word_count = len(content.split())
        
        if word_count < min_words:
            return (False, f"Response too short ({word_count} words).")
        
        if word_count > max_words:
            return (False, f"Response too long ({word_count} words).")
        
        return (True, content)
    
    @staticmethod
    def validate_json_output(content: str) -> Tuple[bool, str]:
        """Ensure output is valid JSON when expected."""
        text = content.strip()
        
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            text = json_match.group(1).strip()
        
        try:
            parsed = json.loads(text)
            return (True, json.dumps(parsed, indent=2))
        except json.JSONDecodeError as e:
            return (False, f"Invalid JSON: {str(e)}")
    
    @staticmethod
    def validate_python_syntax(content: str) -> Tuple[bool, str]:
        """Validate Python code syntax without executing it."""
        code_blocks = re.findall(r'```(?:python|py)?\s*([\s\S]*?)\s*```', content)
        
        if not code_blocks:
            if re.search(r'^(import|from|def|class|if|for|while)\s', content.strip(), re.MULTILINE):
                code_blocks = [content]
            else:
                return (True, content)
        
        errors = []
        for i, code in enumerate(code_blocks):
            try:
                compile(code, f'<block_{i}>', 'exec')
            except SyntaxError as e:
                errors.append(f"Block {i+1}: {e.msg} at line {e.lineno}")
        
        if errors:
            return (False, f"Python syntax errors:\n" + "\n".join(errors))
        
        return (True, content)
    
    @staticmethod
    def validate_no_placeholders(content: str) -> Tuple[bool, str]:
        """Ensure code doesn't contain incomplete placeholders."""
        placeholder_patterns = [
            (r'#\s*TODO:?\s*\w+', 'TODO'),
            (r'#\s*FIXME:?\s*\w+', 'FIXME'),
            (r'raise\s+NotImplementedError', 'NotImplementedError'),
            (r'<\s*YOUR\s*[\w\s]*\s*>', 'YOUR placeholder'),
        ]
        
        found = []
        for pattern, description in placeholder_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                found.append(description)
        
        if found:
            return (False, f"Incomplete placeholders: {', '.join(found)}")
        
        return (True, content)


# =============================================================================
# GUARDRAIL CHAIN BUILDERS
# =============================================================================

def create_full_guardrail_chain(
    agent_role: str = "",
    task_description: str = "",
    include_pii_redaction: bool = True,
    min_words: int = 20,
    max_words: int = 10000,
    check_syntax: bool = True
) -> Callable[[str], Tuple[bool, str]]:
    """Create a comprehensive guardrail chain combining all categories."""
    
    def combined_guardrail(content: str) -> Tuple[bool, str]:
        # Security checks first
        valid, result = SecurityGuardrails.validate_code_safety(content)
        if not valid:
            return (False, result)
        
        valid, result = SecurityGuardrails.validate_no_secrets(content)
        if not valid:
            return (False, result)
        
        # PII redaction
        if include_pii_redaction:
            valid, content = SecurityGuardrails.redact_pii(content)
        
        # Quality checks
        valid, result = QualityGuardrails.validate_word_count(content, min_words, max_words)
        if not valid:
            return (False, result)
        
        if check_syntax:
            valid, result = QualityGuardrails.validate_python_syntax(content)
            if not valid:
                return (False, result)
        
        valid, result = QualityGuardrails.validate_no_placeholders(content)
        if not valid:
            return (False, result)
        
        # Behavioral checks
        if agent_role:
            valid, result = BehavioralGuardrails.validate_role_adherence(content, agent_role)
            if not valid:
                return (False, result)
        
        if task_description:
            valid, result = BehavioralGuardrails.validate_scope_control(content, task_description)
            if not valid:
                return (False, result)
        
        return (True, content)
    
    return combined_guardrail


# LLM-based guardrail prompts for CrewAI
HALLUCINATION_GUARDRAIL = """
Evaluate output for hallucinations:
1. Verify API/function claims exist
2. Verify documentation references
3. Verify statistics and numbers
4. Verify technical specifications
Reject if hallucinations detected.
"""

CODE_REVIEW_GUARDRAIL = """
Review code as senior engineer:
1. Readability and organization
2. Descriptive naming
3. Efficient logic
4. Bug and edge case handling
5. Best practices
Reject if significant issues exist.
"""
