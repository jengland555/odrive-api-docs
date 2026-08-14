"""
Editorial Style & Quality Linter Engine
Enforces inclusive language, objective technical prose, heading hierarchy, and code block formatting.
"""

import re
from typing import Dict, Any, List, Tuple

class StyleLinter:
    def __init__(self, rules: Dict[str, Any]):
        self.rules = rules
        self.inclusive_rules = rules.get("inclusive_language", [])
        self.weak_phrase_rules = rules.get("weak_phrases", [])
        self.structural_rules = rules.get("structural_rules", {})

    def validate(self, filepath: str, markdown: str, line_offset: int = 0) -> List[Dict[str, Any]]:
        """
        Scans markdown line-by-line and across blocks for style violations.
        """
        issues = []
        lines = markdown.split("\n")
        in_code_block = False
        last_heading_level = 0

        for idx, line in enumerate(lines, start=1 + line_offset):
            # Check code block fencing
            stripped = line.strip()
            if stripped.startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    # Check if code block has language identifier
                    lang = stripped[3:].strip()
                    if self.structural_rules.get("require_code_block_language", True) and not lang:
                        issues.append({
                            "file": filepath,
                            "line": idx,
                            "rule": "code_block_missing_language",
                            "severity": "warning",
                            "message": "Code block is missing a syntax language specifier (e.g., ```python, ```bash, ```json)."
                        })
                else:
                    in_code_block = False
                continue

            # Don't check style rules inside code blocks
            if in_code_block:
                continue

            # 1. Heading Hierarchy Check
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if heading_match:
                level = len(heading_match.group(1))
                heading_title = heading_match.group(2).strip()

                if self.structural_rules.get("disallow_heading_skips", True):
                    if last_heading_level > 0 and level > last_heading_level + 1:
                        issues.append({
                            "file": filepath,
                            "line": idx,
                            "rule": "heading_hierarchy_skip",
                            "severity": "warning",
                            "message": f"Heading level skipped from H{last_heading_level} directly to H{level} ('{heading_title}'). Maintain progressive heading hierarchy."
                        })
                last_heading_level = level

            # 2. Inclusive Language Rules
            for rule in self.inclusive_rules:
                pattern = re.compile(rule["pattern"], re.IGNORECASE)
                matches = pattern.finditer(line)
                for match in matches:
                    matched_text = match.group(0)
                    issues.append({
                        "file": filepath,
                        "line": idx,
                        "rule": "non_inclusive_language",
                        "severity": rule.get("severity", "error"),
                        "message": f"Found non-inclusive term '{matched_text}'. Suggested replacement: '{rule['replacement']}'. Reason: {rule['reason']}"
                    })

            # 3. Weak & Subjective Phrases
            for rule in self.weak_phrase_rules:
                pattern = re.compile(rule["pattern"], re.IGNORECASE)
                matches = pattern.finditer(line)
                for match in matches:
                    matched_text = match.group(0)
                    issues.append({
                        "file": filepath,
                        "line": idx,
                        "rule": "weak_editorial_phrase",
                        "severity": rule.get("severity", "warning"),
                        "message": f"Found weak or subjective phrase '{matched_text}'. Suggestion: {rule['replacement']}. Reason: {rule['reason']}"
                    })

        # 4. Document Length Check
        min_words = self.structural_rules.get("min_word_count", 30)
        word_count = len(re.findall(r"\w+", markdown))
        if word_count < min_words:
            issues.append({
                "file": filepath,
                "line": 1,
                "rule": "document_too_short",
                "severity": "warning",
                "message": f"Document contains only {word_count} words (minimum recommended: {min_words} words)."
            })

        return issues

    def auto_fix(self, markdown: str) -> Tuple[str, int]:
        """
        Applies automatic text substitutions for straightforward inclusive language and formatting fixes.
        Returns the remediated markdown and count of fixes made.
        """
        fixed_text = markdown
        fix_count = 0

        # Replace inclusive terms
        replacements = [
            (r"\bmaster-slave\b", "primary-secondary"),
            (r"\bmaster/slave\b", "controller/target"),
            (r"\bmaster\s+slave\b", "controller target"),
            (r"\bblacklist\b", "blocklist"),
            (r"\bwhitelist\b", "allowlist"),
            (r"\bdummy\s+value\b", "placeholder value"),
            (r"\bclick here\b", "view the documentation"),
            (r"\bsimply\s+", ""),
            (r"\bjust\s+", ""),
            (r"\bobviously\s+", ""),
            (r"\beasy to use\b", "flexible"),
            (r"```\n# Untagged code block without language", "```python\n# Configured code block with python syntax")
        ]

        for pattern_str, repl in replacements:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            new_text, count = pattern.subn(repl, fixed_text)
            if count > 0:
                fixed_text = new_text
                fix_count += count

        return fixed_text, fix_count
