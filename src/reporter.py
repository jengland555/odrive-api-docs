"""
Terminal Dashboard & Report Generator
Renders rich terminal tables, violation callouts, and JSON reports for CI/CD pipelines.
"""

import sys
import json
from typing import Dict, Any, List

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

class Reporter:
    def __init__(self):
        self.console = Console() if HAS_RICH else None

    def print_header(self, title: str = "ODrive Docs ContentOps Engine"):
        if HAS_RICH:
            self.console.print(Panel.fit(
                f"[bold cyan]{title}[/bold cyan]\n[dim]Docs-as-Code Quality Gating, Style Enforcement & AI Tone Pipeline[/dim]",
                border_style="cyan"
            ))
        else:
            print("=" * 70)
            print(f"  {title}")
            print("  Docs-as-Code Quality Gating & Editorial Linter")
            print("=" * 70)

    def render_results(self, files_scanned: int, issues: List[Dict[str, Any]], elapsed_time: float, strict: bool = False) -> int:
        """
        Renders terminal report and returns appropriate exit code (0 for pass, 1 for fail).
        """
        error_count = sum(1 for i in issues if i["severity"] == "error")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")

        # In strict mode, warnings are treated as errors
        effective_errors = error_count + (warning_count if strict else 0)
        is_pass = effective_errors == 0

        if HAS_RICH:
            self.console.print()
            if issues:
                table = Table(title="[bold yellow]🔍 Documentation Quality Findings[/bold yellow]", show_header=True, header_style="bold magenta")
                table.add_column("File", style="dim", width=28)
                table.add_column("Line", justify="right", width=6)
                table.add_column("Severity", justify="center", width=10)
                table.add_column("Rule", style="bold", width=22)
                table.add_column("Message", style="white")

                for item in issues:
                    file_short = item["file"].split("/")[-2:]
                    file_display = "/".join(file_short)
                    sev_style = "[bold red]ERROR[/bold red]" if item["severity"] == "error" else "[bold yellow]WARN[/bold yellow]"
                    table.add_row(
                        file_display,
                        str(item["line"]),
                        sev_style,
                        item["rule"],
                        item["message"]
                    )
                self.console.print(table)
                self.console.print()

            # Summary Metrics Table
            summary_table = Table(show_header=False, box=None)
            summary_table.add_row("[bold]Files Scanned:[/bold]", f"[cyan]{files_scanned}[/cyan]")
            summary_table.add_row("[bold]Errors:[/bold]", f"[red]{error_count}[/red]")
            summary_table.add_row("[bold]Warnings:[/bold]", f"[yellow]{warning_count}[/yellow]")
            summary_table.add_row("[bold]Execution Time:[/bold]", f"{elapsed_time:.2f}s")
            self.console.print(Panel(summary_table, title="[bold]📊 Summary Metrics[/bold]", border_style="blue"))

            # Final Verdict
            if is_pass:
                self.console.print(Panel("[bold green]✅ PASS: All documentation health checks passed successfully![/bold green]", border_style="green"))
            else:
                self.console.print(Panel(f"[bold red]❌ FAIL: Documentation pipeline failed with {effective_errors} blocker(s).[/bold red]", border_style="red"))
        else:
            # Fallback plain text / ANSI
            print("\n--- FINDINGS ---")
            for item in issues:
                sev = "ERROR" if item["severity"] == "error" else "WARN"
                print(f"[{sev}] {item['file']}:{item['line']} ({item['rule']}) -> {item['message']}")

            print("\n--- SUMMARY ---")
            print(f"Files Scanned: {files_scanned} | Errors: {error_count} | Warnings: {warning_count} | Time: {elapsed_time:.2f}s")
            if is_pass:
                print(">>> [PASS] All checks passed!")
            else:
                print(f">>> [FAIL] {effective_errors} blocking issue(s) detected.")

        return 0 if is_pass else 1

    def export_json(self, output_path: str, files_scanned: int, issues: List[Dict[str, Any]], elapsed_time: float):
        payload = {
            "status": "PASS" if not any(i["severity"] == "error" for i in issues) else "FAIL",
            "files_scanned": files_scanned,
            "errors": sum(1 for i in issues if i["severity"] == "error"),
            "warnings": sum(1 for i in issues if i["severity"] == "warning"),
            "elapsed_seconds": elapsed_time,
            "issues": issues
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
