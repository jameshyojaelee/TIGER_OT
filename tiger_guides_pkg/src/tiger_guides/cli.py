"""Command line interface for the tiger_guides package."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import click

from .config import load_config, SpeciesOption
from .logging import setup_logger
from .workflow.runner import WorkflowRunner
from .download.references import ensure_reference
from .download.models import ensure_model
from .constants import SMOKE_DIR


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """Tiger Guides command line interface."""


@main.command()
@click.argument("targets", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--species", type=click.Choice(["mouse", "human"]), required=True,
              help="Organism selector (mouse = mus_musculus, human = homo_sapiens).")
@click.option("--config", "config_path", type=click.Path(dir_okay=False, path_type=Path),
              help="Override configuration YAML.")
@click.option("--output-dir", default="runs/latest", show_default=True,
              type=click.Path(file_okay=False, path_type=Path),
              help="Directory where workflow outputs (logs, CSVs) will be placed.")
@click.option("--top-n", type=int, help="Override guides per gene.")
@click.option("--skip-download", is_flag=True, help="Reuse existing FASTA download if present.")
@click.option("--skip-validation", is_flag=True, help="Skip TIGER output validation for faster runs.")
@click.option("--resume-from", type=click.Choice(["download", "tiger", "offtarget", "filter"]),
              help="Resume the workflow from a specific checkpoint.")
@click.option("--threads", type=int, help="Override thread count during execution.")
@click.option("--verbose", is_flag=True, help="Enable verbose logging output.")
def run(targets: Path,
        species: str,
        config_path: Optional[Path],
        output_dir: Path,
        top_n: Optional[int],
        skip_download: bool,
        skip_validation: bool,
        resume_from: Optional[str],
        threads: Optional[int],
        verbose: bool) -> None:
    """Execute the full TIGER workflow."""
    species_option = SpeciesOption(species)
    config = load_config(config_path, species_option)

    if top_n is not None:
        config["top_n_guides"] = top_n
    if threads is not None:
        config.setdefault("compute", {})["threads"] = threads

    config["output_dir"] = str(output_dir)

    reference_dir = Path(config["offtarget"].get("reference_dir", "references"))
    reference_path = ensure_reference(species_option, cache_dir=reference_dir)
    config["offtarget"]["reference_transcriptome"] = str(reference_path)

    logger = setup_logger(verbose=verbose, log_file=Path(output_dir) / "workflow.log")
    runner = WorkflowRunner(
        targets_file=targets,
        config=config,
        logger=logger,
    )

    success = runner.run(
        skip_download=skip_download,
        skip_validation=skip_validation,
        resume_from=resume_from,
    )

    raise SystemExit(0 if success else 1)


@main.command()
@click.option("--species", type=click.Choice(["mouse", "human"]), required=True,
              help="Organism to prepare (downloads reference transcriptome if needed).")
@click.option("--destination", type=click.Path(file_okay=False, path_type=Path),
              default=Path("references"), show_default=True,
              help="Directory where downloaded references are cached.")
def fetch_reference(species: str, destination: Path) -> None:
    """Download and cache the transcriptome bundle for an organism."""
    species_option = SpeciesOption(species)
    ensure_reference(species_option, cache_dir=destination)


@main.command()
@click.option("--model", type=click.Choice(["tiger"]), default="tiger", show_default=True,
              help="Model bundle to fetch.")
@click.option("--destination", type=click.Path(file_okay=False, path_type=Path),
              default=Path("."), show_default=True,
              help="Directory where model assets are cached.")
def fetch_model(model: str, destination: Path) -> None:
    """Download and cache TIGER model assets."""
    path = ensure_model(model, cache_root=destination)
    click.echo(f"Model '{model}' ready at {path}")


@main.command()
@click.option("--verbose", is_flag=True, help="Show verbose output while the smoke test runs.")
def smoke(verbose: bool) -> None:
    """Run the bundled smoke-test dataset end-to-end."""
    targets = SMOKE_DIR / "targets.txt"
    config_path = SMOKE_DIR / "config.yaml"
    output_dir = Path("runs/smoke")

    species_option = SpeciesOption("mouse")
    config = load_config(config_path, species_option)
    config["output_dir"] = str(output_dir)
    config["offtarget"]["reference_transcriptome"] = str(SMOKE_DIR / "gencode.vM37.transcripts.uc.joined")

    logger = setup_logger(verbose=verbose, log_file=output_dir / "workflow.log")
    runner = WorkflowRunner(targets, config, logger=logger)
    success = runner.run(skip_download=False, skip_validation=True)
    raise SystemExit(0 if success else 1)


@main.command()
def version() -> None:
    """Print package version."""
    from . import __version__
    click.echo(__version__)
