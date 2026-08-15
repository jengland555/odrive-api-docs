#!/usr/bin/env python3
"""
ODrive Docs ContentOps CLI & Health Check Pipeline
Main entrypoint for linting, semantic chunking, community error mining, and AI tone sanitization.

Author: Jenna England (Senior Technical Writer & Content Architect)
"""

import os
import sys
import time
import json
import argparse
import warnings

# Suppress macOS LibreSSL warning from urllib3
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")

from typing import List, Dict, Any

from src.frontmatter_checker import FrontmatterValidator
from src.link_checker import LinkChecker
from src.style_linter import StyleLinter
from src.enum_validator import EnumValidator
from src.ai_sanitizer import AISanitizer
from src.chunker import SemanticChunker
from src.forum_scraper import ODriveForumScraper
from src.reporter import Reporter

def load_rules(rules_path: str) -> Dict[str, Any]:
    if not os.path.exists(rules_path):
        print(f"⚠️ Rules file not found at {rules_path}. Using built-in defaults.")
        return {}
    with open(rules_path, "r", encoding="utf-8") as f:
        return json.load(f)

def collect_markdown_files(target_path: str) -> List[str]:
    if os.path.isfile(target_path):
        return [target_path] if target_path.endswith((".md", ".mdx")) else []
    
    files = []
    for root, _, filenames in os.walk(target_path):
        for f in sorted(filenames):
            if f.endswith((".md", ".mdx")):
                files.append(os.path.join(root, f))
    return files

def main():
    parser = argparse.ArgumentParser(
        description="ODrive Docs ContentOps Quality Engine: Docs-as-Code Linter, Chunker & AI Sanitizer."
    )
    parser.add_argument(
        "--path", "-p",
        default="docs/valid",
        help="Path to a markdown file or directory to scan (default: docs/valid)"
    )
    parser.add_argument(
        "--rules", "-r",
        default="rules/style_rules.json",
        help="Path to style rules JSON configuration (default: rules/style_rules.json)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors for strict CI/CD quality gating"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Disable external network calls (skip HTTP URL pings and live forum requests)"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically remediate standard inclusive language and syntax violations in-place"
    )
    parser.add_argument(
        "--ai-review",
        action="store_true",
        help="Run AI Tone & Imperative Voice Sanitizer (Gemini / Heuristic Engine)"
    )
    parser.add_argument(
        "--chunk",
        action="store_true",
        help="Execute H2/H3 Heading-Based Semantic Chunker and save RAG index to data/rag_semantic_chunks.json"
    )
    parser.add_argument(
        "--scrape-forum",
        action="store_true",
        help="Scrape ODrive Discourse forum for error resolutions and save to data/forum_scraped_errors.json"
    )
    parser.add_argument(
        "--json-output",
        help="Export lint results to a JSON file"
    )

    args = parser.parse_args()
    reporter = Reporter()
    reporter.print_header()

    start_time = time.time()
    rules = load_rules(args.rules)

    # 1. Handle Standalone Task: Forum Scraper
    if args.scrape_forum:
        print("\n🌐 Mining ODrive Discourse Forum for Community Troubleshooting Cases...")
        scraper = ODriveForumScraper(offline=args.offline)
        result = scraper.save_knowledge_base("data/forum_scraped_errors.json")
        print(f"✅ Mined {result['total_threads_mined']} community error threads.")
        print(f"📁 Exported knowledge payload to data/forum_scraped_errors.json")
        if not args.chunk and not args.path:
            return 0

    # 2. Handle Standalone Task: H2/H3 Semantic Chunker
    if args.chunk:
        print(f"\n✂️ Executing H2/H3 Heading-Based Semantic Chunker on '{args.path}'...")
        chunker = SemanticChunker(rules)
        try:
            chunk_payload = chunker.build_chunk_index(args.path, "data/rag_semantic_chunks.json")
            print(f"✅ Created {chunk_payload['total_chunks']} semantic chunks across {chunk_payload['total_documents']} documents.")
            print(f"📊 Average token density: {chunk_payload['avg_tokens_per_chunk']} tokens/chunk.")
            print(f"📁 Exported RAG Vector Payload to data/rag_semantic_chunks.json")
        except Exception as e:
            print(f"❌ Error during chunking: {str(e)}")
        if not args.ai_review and "--path" not in sys.argv:
            return 0

    # 3. Main Linter Engine Pipeline
    files = collect_markdown_files(args.path)
    if not files:
        print(f"⚠️ No markdown files found in target path '{args.path}'.")
        return 0

    frontmatter_validator = FrontmatterValidator(rules)
    link_checker = LinkChecker(offline=args.offline)
    style_linter = StyleLinter(rules)
    enum_validator = EnumValidator()
    ai_sanitizer = AISanitizer() if args.ai_review else None

    all_issues = []
    total_fixes = 0

    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Handle auto-fix
        if args.fix:
            fixed_content, fixes = style_linter.auto_fix(content)
            if fixes > 0:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(fixed_content)
                total_fixes += fixes
                content = fixed_content

        # Step 1: Frontmatter Validation
        metadata, markdown, fm_issues = frontmatter_validator.validate(filepath, content)
        all_issues.extend(fm_issues)

        # Step 2: Link & Anchor Checking
        link_issues = link_checker.validate(filepath, markdown, line_offset=0)
        all_issues.extend(link_issues)

        # Step 3: Style & Structural Quality Linting
        style_issues = style_linter.validate(filepath, markdown, line_offset=0)
        all_issues.extend(style_issues)

        # Step 4: ODrive Firmware Enum & Bitfield Validation (vs. real ODriveArduino library)
        enum_issues = enum_validator.validate(filepath, markdown, line_offset=0)
        all_issues.extend(enum_issues)

        # Step 5: Optional AI Review
        if args.ai_review and ai_sanitizer:
            print(f"\n🤖 Running AI Tone & Voice Analysis on {os.path.basename(filepath)}...")
            ai_result = ai_sanitizer.review_document(filepath, markdown)
            if ai_result.get("mode") == "Gemini AI Live":
                print(f"--- Gemini AI Tone Report ---\n{ai_result['summary']}\n")
            else:
                for finding in ai_result.get("findings", []):
                    all_issues.append({
                        "file": filepath,
                        "line": finding["line"],
                        "rule": "ai_passive_voice",
                        "severity": "warning",
                        "message": f"{finding['critique']} (Found: '{finding['original_phrase']}')"
                    })

    elapsed = time.time() - start_time

    if args.fix and total_fixes > 0:
        print(f"\n🛠️ Auto-Fix Remediated {total_fixes} style violations in-place.")

    exit_code = reporter.render_results(
        files_scanned=len(files),
        issues=all_issues,
        elapsed_time=elapsed,
        strict=args.strict
    )

    if args.json_output:
        reporter.export_json(args.json_output, len(files), all_issues, elapsed)
        print(f"📁 Exported JSON report to {args.json_output}")

    return exit_code

if __name__ == "__main__":
    sys.exit(main())
