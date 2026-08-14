"""
YAML Frontmatter Taxonomy & Metadata Validator
Enforces Docs-as-Code metadata completeness, schema compliance, and classification standards.
"""

import re
from typing import Dict, Any, List, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

def _fallback_yaml_parse(raw_yaml: str) -> Dict[str, Any]:
    """Simple key-value YAML parser fallback when PyYAML is not installed."""
    data = {}
    for line in raw_yaml.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            elif val.startswith("[") and val.endswith("]"):
                items = val[1:-1].split(",")
                val = [item.strip().strip('"').strip("'") for item in items if item.strip()]
            elif val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            data[key] = val
    return data

class FrontmatterValidator:
    def __init__(self, rules: Dict[str, Any]):
        self.config = rules.get("frontmatter", {})
        self.required_fields = self.config.get("required_fields", [])
        self.allowed_categories = self.config.get("allowed_categories", [])
        self.allowed_statuses = self.config.get("allowed_statuses", [])
        self.date_format = self.config.get("date_format", r"^\d{4}-\d{2}-\d{2}$")

    def parse_frontmatter(self, file_content: str) -> Tuple[Dict[str, Any], str, int]:
        """
        Extracts YAML frontmatter dictionary, the remaining markdown text, and line offset.
        """
        pattern = r"^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$"
        match = re.match(pattern, file_content)
        if not match:
            return {}, file_content, 0

        raw_yaml = match.group(1)
        markdown = match.group(2)
        end_line = raw_yaml.count("\n") + 2

        metadata = {}
        if HAS_YAML:
            try:
                metadata = yaml.safe_load(raw_yaml)
                if not isinstance(metadata, dict):
                    metadata = {}
            except Exception:
                metadata = _fallback_yaml_parse(raw_yaml)
        else:
            metadata = _fallback_yaml_parse(raw_yaml)

        return metadata, markdown, end_line

    def validate(self, filepath: str, file_content: str) -> Tuple[Dict[str, Any], str, List[Dict[str, Any]]]:
        """
        Validates frontmatter against taxonomy rules and returns issues list.
        """
        issues = []
        pattern = r"^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$"
        match = re.match(pattern, file_content)

        if not match:
            issues.append({
                "file": filepath,
                "line": 1,
                "rule": "frontmatter_missing",
                "severity": "error",
                "message": "Missing YAML frontmatter block (expected '---' metadata boundary at file start)."
            })
            return {}, file_content, issues

        raw_yaml = match.group(1)
        markdown = match.group(2)

        metadata = {}
        if HAS_YAML:
            try:
                metadata = yaml.safe_load(raw_yaml)
                if not isinstance(metadata, dict):
                    issues.append({
                        "file": filepath,
                        "line": 1,
                        "rule": "frontmatter_invalid",
                        "severity": "error",
                        "message": "Frontmatter is not a valid YAML mapping."
                    })
                    return {}, markdown, issues
            except yaml.YAMLError as exc:
                line_num = getattr(exc, 'problem_mark', None).line + 1 if hasattr(exc, 'problem_mark') and exc.problem_mark else 1
                issues.append({
                    "file": filepath,
                    "line": line_num,
                    "rule": "frontmatter_yaml_error",
                    "severity": "error",
                    "message": f"YAML syntax error in frontmatter: {str(exc)}"
                })
                return {}, markdown, issues
        else:
            metadata = _fallback_yaml_parse(raw_yaml)

        # Check required fields
        for field in self.required_fields:
            if field not in metadata or metadata[field] is None or str(metadata[field]).strip() == "":
                issues.append({
                    "file": filepath,
                    "line": 1,
                    "rule": f"frontmatter_missing_{field}",
                    "severity": "error",
                    "message": f"Required frontmatter field '{field}' is missing or empty."
                })

        # Validate category enum
        if "category" in metadata and self.allowed_categories:
            category = metadata["category"]
            if category not in self.allowed_categories:
                issues.append({
                    "file": filepath,
                    "line": 1,
                    "rule": "frontmatter_invalid_category",
                    "severity": "warning",
                    "message": f"Category '{category}' is not recognized. Allowed: {', '.join(self.allowed_categories)}"
                })

        # Validate status enum
        if "status" in metadata and self.allowed_statuses:
            status = metadata["status"]
            if status not in self.allowed_statuses:
                issues.append({
                    "file": filepath,
                    "line": 1,
                    "rule": "frontmatter_invalid_status",
                    "severity": "warning",
                    "message": f"Status '{status}' is not recognized. Allowed: {', '.join(self.allowed_statuses)}"
                })

        # Validate date format
        if "last_reviewed" in metadata:
            date_val = str(metadata["last_reviewed"])
            if not re.match(self.date_format, date_val):
                issues.append({
                    "file": filepath,
                    "line": 1,
                    "rule": "frontmatter_invalid_date",
                    "severity": "warning",
                    "message": f"Date '{date_val}' in 'last_reviewed' must match ISO format YYYY-MM-DD."
                })

        return metadata, markdown, issues
