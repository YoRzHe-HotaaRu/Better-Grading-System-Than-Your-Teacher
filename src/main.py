"""
Strict Grader CLI Application.

Provides a command-line interface for grading student answers
against rubrics using LLM-based evaluation.
"""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.config import StrictnessMode, get_settings
from src.extractors import ExtractionError, extract_document
from src.grading import GradingEngine, LLMError, ScoringError
from src.models import GradingResult
from src.output import AuditTrail, ReportFormat, ReportGenerator
from src.rubric import RubricParseError, RubricParser, RubricValidationError, RubricValidator

# Create Typer app
app = typer.Typer(
    name="strict-grader",
    help="A strict, unbiased LLM-based grading system",
    add_completion=False,
)

console = Console()


@app.command()
def grade(
    rubric_file: Annotated[Path, typer.Argument(help="Path to the rubric file")],
    answer_file: Annotated[Path, typer.Argument(help="Path to the student answer file")],
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output file path for the report"),
    ] = None,
    format: Annotated[
        ReportFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = ReportFormat.JSON,
    passes: Annotated[
        Optional[int],
        typer.Option("--passes", "-p", help="Number of grading passes (1-5)"),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Use hard-fail strictness mode"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed output"),
    ] = False,
) -> None:
    """
    Grade a student answer against a rubric.

    The grading is performed using LLM-based evaluation with multi-pass
    consistency checking. Results are output in the specified format.
    """
    try:
        settings = get_settings()

        # Validate inputs
        if not rubric_file.exists():
            console.print(f"[red]Error:[/red] Rubric file not found: {rubric_file}")
            raise typer.Exit(1)

        if not answer_file.exists():
            console.print(f"[red]Error:[/red] Answer file not found: {answer_file}")
            raise typer.Exit(1)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Extract documents
            task = progress.add_task("Extracting rubric...", total=None)
            rubric_doc = extract_document(rubric_file)
            progress.update(task, description="Extracting answer...")
            answer_doc = extract_document(answer_file)

            # Parse and validate rubric
            progress.update(task, description="Parsing rubric...")
            parser = RubricParser()
            rubric = parser.parse(rubric_doc.content)

            progress.update(task, description="Validating rubric...")
            validator = RubricValidator()
            validator.validate_or_raise(rubric)

            if verbose:
                progress.stop()
                console.print(
                    Panel(
                        f"[green]Rubric loaded:[/green] {rubric.title}\n"
                        f"Criteria: {rubric.criterion_count}\n"
                        f"Total Points: {rubric.total_max_points}",
                        title="Rubric Info",
                    )
                )
                progress.start()

            # Initialize grading engine
            progress.update(task, description="Initializing grading engine...")
            engine = GradingEngine(settings)

            # Determine strictness mode
            mode = StrictnessMode.HARD_FAIL if strict else settings.strictness_mode

            # Perform grading
            num_passes = passes or settings.grading_passes
            progress.update(
                task, description=f"Grading with {num_passes} passes... (this may take a moment)"
            )

            result, audit = engine.grade(
                rubric=rubric,
                student_answer=answer_doc.content,
                strictness_mode=mode,
                passes=num_passes,
            )

            progress.update(task, description="Generating report...")

        # Display results
        _display_results(result, verbose)

        # Save report if output specified
        if output:
            generator = ReportGenerator()
            saved_path = generator.save(result, output, audit, format)
            console.print(f"\n[green]Report saved to:[/green] {saved_path}")

            # Save audit trail
            audit_trail = AuditTrail(settings.output_directory / "audits")
            audit_path = audit_trail.save(audit)
            if verbose:
                console.print(f"[dim]Audit saved to: {audit_path}[/dim]")
        else:
            # Print report to stdout
            generator = ReportGenerator()
            report = generator.generate(result, audit, format)
            console.print("\n" + report)

    except ExtractionError as e:
        console.print(f"[red]Extraction Error:[/red] {e}")
        raise typer.Exit(1)
    except RubricParseError as e:
        console.print(f"[red]Rubric Parse Error:[/red] {e}")
        raise typer.Exit(1)
    except RubricValidationError as e:
        console.print(f"[red]Rubric Validation Error:[/red] {e}")
        raise typer.Exit(1)
    except LLMError as e:
        console.print(f"[red]LLM Error:[/red] {e}")
        raise typer.Exit(1)
    except ScoringError as e:
        console.print(f"[red]Scoring Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def validate_rubric(
    rubric_file: Annotated[Path, typer.Argument(help="Path to the rubric file")],
) -> None:
    """
    Validate a rubric file without performing grading.

    Checks that the rubric is well-formed and suitable for consistent grading.
    """
    try:
        if not rubric_file.exists():
            console.print(f"[red]Error:[/red] File not found: {rubric_file}")
            raise typer.Exit(1)

        # Extract document
        rubric_doc = extract_document(rubric_file)

        # Parse
        parser = RubricParser()
        rubric = parser.parse(rubric_doc.content)

        # Validate
        validator = RubricValidator()
        is_valid, issues = validator.validate(rubric)

        # Display results
        console.print(Panel(f"[bold]{rubric.title}[/bold]", title="Rubric"))

        table = Table(title="Criteria")
        table.add_column("Name", style="cyan")
        table.add_column("Points", justify="right")
        table.add_column("Description")

        for criterion in rubric.criteria:
            table.add_row(criterion.name, str(criterion.max_points), criterion.description[:50])

        console.print(table)
        console.print(f"\n[bold]Total Points:[/bold] {rubric.total_max_points}")

        if is_valid:
            console.print("\n[green]✓ Rubric is valid[/green]")
        else:
            console.print("\n[yellow]⚠ Validation issues found:[/yellow]")
            for issue in issues:
                console.print(f"  • {issue}")

    except ExtractionError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except RubricParseError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def health() -> None:
    """
    Check if the grading system is operational.

    Verifies API connectivity and configuration.
    """
    try:
        settings = get_settings()
        console.print("[bold]Strict Grader Health Check[/bold]\n")

        # Check settings
        console.print("[dim]Checking configuration...[/dim]")
        console.print(f"  API Base URL: {settings.zenmux_base_url}")
        console.print(f"  Model: {settings.zenmux_model}")
        console.print(f"  Grading Passes: {settings.grading_passes}")
        console.print(f"  Strictness Mode: {settings.strictness_mode.value}")

        # Check API connectivity
        console.print("\n[dim]Checking API connectivity...[/dim]")
        engine = GradingEngine(settings)

        if engine.health_check():
            console.print("[green]✓ API is reachable[/green]")
        else:
            console.print("[red]✗ API is not reachable[/red]")
            raise typer.Exit(1)

        console.print("\n[green]All systems operational[/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def _display_results(result: GradingResult, verbose: bool = False) -> None:
    """Display grading results in a formatted table."""

    # Score summary
    score_color = "green" if result.percentage_score >= 70 else "yellow" if result.percentage_score >= 50 else "red"
    console.print(
        Panel(
            f"[{score_color}][bold]{result.total_awarded} / {result.total_max}[/bold] "
            f"({result.percentage_score:.1f}%)[/{score_color}]",
            title="Final Score",
        )
    )

    if result.flagged_for_review:
        console.print("[yellow]⚠ This result has been flagged for human review due to variance[/yellow]")

    if verbose:
        # Detailed breakdown
        table = Table(title="Criteria Breakdown")
        table.add_column("Criterion", style="cyan")
        table.add_column("Score", justify="right")
        table.add_column("Percentage", justify="right")
        table.add_column("Status")

        for cr in result.criteria_results:
            status = "✅" if cr.awarded_points == cr.max_points else "⚠️"
            table.add_row(
                cr.criterion_name,
                f"{cr.awarded_points}/{cr.max_points}",
                f"{cr.percentage:.1f}%",
                status,
            )

        console.print(table)

        # Feedback
        console.print(Panel(result.overall_feedback, title="Feedback"))


if __name__ == "__main__":
    app()
