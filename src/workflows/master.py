"""HPC wrapper for the shared tiger_guides workflow runner."""
from pathlib import Path

from tiger_guides.workflow.runner import WorkflowRunner as CoreWorkflowRunner


class Cas13WorkflowRunner(CoreWorkflowRunner):
    """Backwards-compatible wrapper around the shared workflow runner."""

    def __init__(self, targets_file, config, main_dir, dry_run=False, logger=None):
        super().__init__(
            targets_file=Path(targets_file),
            config=config,
            logger=logger,
            main_dir=Path(main_dir),
            dry_run=dry_run,
        )
