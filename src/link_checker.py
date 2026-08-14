"""
Link & Anchor Integrity Checker
Validates internal markdown anchors, relative file links, and remote HTTP/HTTPS endpoints.
"""

import os
import re
import urllib.parse
from typing import Dict, Any, List, Set, Tuple
import requests

class LinkChecker:
    def __init__(self, offline: bool = False, timeout: int = 5):
        self.offline = offline
        self.timeout = timeout
        self.url_cache: Dict[str, Tuple[bool, str]] = {}

    @staticmethod
    def slugify(text: str) -> str:
        """
        Converts heading text to GitHub-standard anchor slug.
        """
        clean = re.sub(r"[^\w\s-]", "", text.lower()).strip()
        slug = re.sub(r"\s+", "-", clean)
        return slug

    def extract_headings_slugs(self, markdown: str) -> Set[str]:
        """
        Extracts all heading slugs present in the markdown document.
        """
        slugs = set()
        for line in markdown.split("\n"):
            match = re.match(r"^#{1,6}\s+(.*)$", line.strip())
            if match:
                heading_text = match.group(1).strip()
                slugs.add(self.slugify(heading_text))
        return slugs

    def check_remote_url(self, url: str) -> Tuple[bool, str]:
        """
        Pings remote URL to verify HTTP reachability with caching.
        """
        if self.offline:
            return True, "Offline mode - skipped"

        if url in self.url_cache:
            return self.url_cache[url]

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ContentOps-DocChecker/1.0"
        }
        try:
            # Try HEAD first for performance, fall back to GET
            response = requests.head(url, headers=headers, timeout=self.timeout, allow_redirects=True)
            if response.status_code == 405 or response.status_code >= 400:
                response = requests.get(url, headers=headers, timeout=self.timeout, stream=True)

            if response.status_code < 400:
                self.url_cache[url] = (True, f"HTTP {response.status_code}")
                return True, f"HTTP {response.status_code}"
            else:
                self.url_cache[url] = (False, f"HTTP Error {response.status_code}")
                return False, f"HTTP Error {response.status_code}"
        except Exception as exc:
            err_msg = str(exc)
            if "ConnectionRefused" in err_msg or "Failed to establish a new connection" in err_msg:
                msg = "Connection refused (Endpoint unreachable)"
            elif "timed out" in err_msg:
                msg = "Request timed out"
            else:
                msg = f"Network error: {err_msg[:40]}"
            self.url_cache[url] = (False, msg)
            return False, msg

    def validate(self, filepath: str, markdown: str, line_offset: int = 0) -> List[Dict[str, Any]]:
        """
        Extracts all links from markdown and validates anchors, relative files, and HTTP URLs.
        """
        issues = []
        headings_slugs = self.extract_headings_slugs(markdown)
        base_dir = os.path.dirname(os.path.abspath(filepath))

        # Matches standard [text](url) markdown links
        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

        lines = markdown.split("\n")
        for idx, line in enumerate(lines, start=1 + line_offset):
            # Skip code block fences or commented lines
            if line.strip().startswith("```"):
                continue

            for match in link_pattern.finditer(line):
                link_text = match.group(1).strip()
                link_target = match.group(2).strip()

                # Clean target (strip title quotes if any, e.g. [text](url "title"))
                if " " in link_target:
                    link_target = link_target.split(" ")[0].strip()

                # 1. Internal Anchor within same file
                if link_target.startswith("#"):
                    anchor = link_target[1:].lower()
                    if anchor not in headings_slugs:
                        issues.append({
                            "file": filepath,
                            "line": idx,
                            "rule": "broken_internal_anchor",
                            "severity": "error",
                            "message": f"Broken local anchor '{link_target}'. Heading matching slug '#{anchor}' was not found in document."
                        })

                # 2. Remote HTTP / HTTPS URL
                elif link_target.startswith("http://") or link_target.startswith("https://"):
                    is_valid, msg = self.check_remote_url(link_target)
                    if not is_valid:
                        issues.append({
                            "file": filepath,
                            "line": idx,
                            "rule": "broken_remote_link",
                            "severity": "error",
                            "message": f"Broken external URL '{link_target}' ({msg})."
                        })

                # 3. Relative Local File link
                elif not link_target.startswith("mailto:") and not link_target.startswith("javascript:"):
                    # Check for file + anchor combination (e.g. ./other.md#section)
                    target_file = link_target
                    target_anchor = None
                    if "#" in link_target:
                        target_file, target_anchor = link_target.split("#", 1)

                    target_path = os.path.normpath(os.path.join(base_dir, target_file))
                    if not os.path.exists(target_path):
                        issues.append({
                            "file": filepath,
                            "line": idx,
                            "rule": "broken_relative_file",
                            "severity": "error",
                            "message": f"Target file '{link_target}' does not exist on disk relative to document."
                        })
                    elif target_anchor and os.path.isfile(target_path) and target_path.endswith(".md"):
                        # Check anchor in target file
                        try:
                            with open(target_path, "r", encoding="utf-8") as f:
                                target_content = f.read()
                            target_slugs = self.extract_headings_slugs(target_content)
                            if self.slugify(target_anchor) not in target_slugs:
                                issues.append({
                                    "file": filepath,
                                    "line": idx,
                                    "rule": "broken_relative_anchor",
                                    "severity": "error",
                                    "message": f"Anchor '#{target_anchor}' not found in target file '{target_file}'."
                                })
                        except Exception:
                            pass

        return issues
