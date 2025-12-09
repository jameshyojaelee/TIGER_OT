"""Workflow runner mirroring the TIGER HPC pipeline."""
from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd
from Bio import SeqIO

from ..download.ensembl import EnsemblDownloader
from ..filters.ranking import apply_filters
from ..models.loader import resolve_model_paths
from ..offtarget.search import OffTargetSearcher
from ..tiger.predictor import TIGERPredictor
from ..tiger.validator import validate_tiger_output
from ..logging import setup_logger
from ..config import dump_yaml


class WorkflowRunner:
    def __init__(
        self,
        targets_file: Path,
        config: Dict,
        logger=None,
        main_dir: Optional[Path] = None,
        dry_run: bool = False,
    ) -> None:
        self.targets_file = Path(targets_file)
        if not self.targets_file.exists():
            raise FileNotFoundError(f"Targets file not found: {self.targets_file}")

        self.config = config
        self.logger = logger or setup_logger()
        self.root = Path(main_dir) if main_dir else Path.cwd()
        self.dry_run = dry_run

        self.output_dir = Path(self.config.get("output_dir", "runs/latest"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.original_targets = self._load_targets()
        self.targets = list(self.original_targets)
        self.gene_aliases = {}

        self.downloader: Optional[EnsemblDownloader] = None
        self.tiger: Optional[TIGERPredictor] = None
        self.offtarget: Optional[OffTargetSearcher] = None

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _load_targets(self) -> Iterable[str]:
        with self.targets_file.open("r", encoding="utf-8") as fh:
            targets = [line.strip() for line in fh if line.strip()]
        self.logger.info(f"Loaded {len(targets)} target genes from {self.targets_file}")
        return targets

    def _register_resolved_targets(self, records: Iterable[pd.Series]) -> None:
        resolved_names = []
        alias_map = {}
        for record in records:
            resolved = record.id.split("_")[0]
            original = record.annotations.get("original_name", resolved)
            resolved_names.append(resolved)
            alias_map.setdefault(resolved, original)

        if resolved_names:
            renamed = [
                f"{alias_map[name]} → {name}"
                for name in resolved_names
                if alias_map[name].lower() != name.lower()
            ]
            if renamed:
                preview = ", ".join(renamed[:5])
                more = "..." if len(renamed) > 5 else ""
                self.logger.info(f"Gene symbols normalised: {preview}{more}")

            missing = [
                original for original in self.original_targets
                if all(original.lower() != resolved.lower() for resolved in resolved_names)
            ]
            if missing:
                preview = ", ".join(missing[:5])
                more = "..." if len(missing) > 5 else ""
                self.logger.warning(
                    f"⚠️  {len(missing)} input gene(s) could not be resolved via Ensembl: {preview}{more}"
                )

            self.targets = resolved_names
            self.gene_aliases = alias_map

    # ------------------------------------------------------------------
    # Workflow orchestration
    # ------------------------------------------------------------------
    def run(self, *, skip_download: bool = False, skip_validation: bool = False,
            resume_from: Optional[str] = None) -> bool:
        self._persist_config()

        if self.dry_run:
            self._print_workflow_plan()
            return True

        try:
            if not resume_from or resume_from == "download":
                fasta_file = self._step_download(skip_download)
                if fasta_file is None:
                    return False
            else:
                fasta_file = self.output_dir / "sequences" / "all_targets.fasta"

            if not resume_from or resume_from in {"download", "tiger"}:
                tiger_output = self._step_tiger(fasta_file, skip_validation)
                if tiger_output is None:
                    return False
            else:
                tiger_output = self.output_dir / "tiger" / "guides.csv"

            if not resume_from or resume_from in {"download", "tiger", "offtarget"}:
                offtarget_output = self._step_offtarget(tiger_output)
                if offtarget_output is None:
                    return False
            else:
                offtarget_output = self.output_dir / "offtarget" / "results.csv"

            if not resume_from or resume_from in {"download", "tiger", "offtarget", "filter"}:
                final_output = self._step_filter(offtarget_output)
                if final_output is None:
                    return False
            else:
                final_output = self.output_dir / "final_guides.csv"

            self.logger.info("=" * 60)
            self.logger.info("✅ Workflow completed successfully!")
            self.logger.info(f"📄 Final results: {final_output}")
            self.logger.info("=" * 60)
            return True
        except Exception as exc:  # pragma: no cover - top-level guard
            self.logger.error(f"Workflow failed: {exc}", exc_info=True)
            return False

    # ------------------------------------------------------------------
    def _persist_config(self) -> None:
        config_path = self.output_dir / "config.yaml"
        dump_yaml(self.config, config_path)

    def _step_download(self, skip_download: bool) -> Optional[Path]:
        seq_dir = self.output_dir / "sequences"
        seq_dir.mkdir(parents=True, exist_ok=True)
        fasta_file = seq_dir / "all_targets.fasta"

        if skip_download and fasta_file.exists():
            self.logger.info(f"⏭️  Skipping download; using existing {fasta_file}")
            try:
                records = list(SeqIO.parse(fasta_file, "fasta"))
                if records:
                    self._register_resolved_targets(records)
            except Exception:  # pragma: no cover - best effort
                self.logger.warning("Could not inspect existing FASTA for gene aliases")
            return fasta_file

        self.downloader = EnsemblDownloader(
            species=self.config["species"],
            rest_url=self.config["ensembl"]["rest_url"],
            rate_limit_delay=self.config["ensembl"].get("rate_limit_delay", 0.5),
            logger=self.logger,
        )

        records = self.downloader.download_genes(
            gene_list=self.targets,
            seq_type="cds",
            output_fasta=fasta_file,
            output_dir=seq_dir / "individual",
        )

        if not records:
            self.logger.error("Failed to download any sequences; aborting")
            return None

        self._register_resolved_targets(records)
        return fasta_file

    def _step_tiger(self, fasta_file: Path, skip_validation: bool) -> Optional[Path]:
        tiger_dir = self.output_dir / "tiger"
        tiger_dir.mkdir(exist_ok=True)
        guides_csv = tiger_dir / "guides.csv"

        tiger_config = self.config["tiger"]
        model_paths = resolve_model_paths(tiger_config, self.root)

        self.tiger = TIGERPredictor(
            model_path=model_paths["model_path"],
            config=tiger_config,
            logger=self.logger,
        )

        guides_df = self.tiger.predict_from_fasta(
            fasta_path=fasta_file,
            output_path=guides_csv,
            batch_size=tiger_config.get("batch_size", 500)
        )

        if not skip_validation and not validate_tiger_output(guides_csv, logger=self.logger):
            return None

        return guides_csv

    def _step_offtarget(self, tiger_output: Path) -> Optional[Path]:
        offtarget_dir = self.output_dir / "offtarget"
        offtarget_dir.mkdir(exist_ok=True)
        results_csv = offtarget_dir / "results.csv"

        guides_df = pd.read_csv(tiger_output)

        offtarget_cfg = self.config.get("offtarget", {})
        min_score = offtarget_cfg.get("min_score_for_offtarget", 0.0)

        if "Score" in guides_df.columns and min_score > 0.0:
            before = len(guides_df)
            guides_df = guides_df[guides_df["Score"] >= min_score].copy()
            self.logger.info(
                f"Prefiltering guides for off-target search: "
                f"{len(guides_df):,} / {before:,} with Score >= {min_score}"
            )

        if guides_df.empty:
            self.logger.warning(
                "No guides passed the off-target prefilter; skipping off-target search."
            )
            # Create an empty results file with the same columns to keep downstream steps happy
            guides_df.to_csv(results_csv, index=False)
            return results_csv

        offtarget_cfg = self.config["offtarget"]
        binary_cfg = Path(offtarget_cfg.get("binary_path", "bin/offtarget_search"))
        candidate_paths = []

        if binary_cfg.is_absolute():
            candidate_paths.append(binary_cfg)
        else:
            candidate_paths.append((self.root / binary_cfg).resolve())
            candidate_paths.append(binary_cfg)

        # Package resource fallbacks
        try:
            pkg_root = resources.files("tiger_guides")
            resource_candidates = [
                pkg_root / binary_cfg.name,
                pkg_root / "resources" / binary_cfg.name,
                pkg_root / "resources" / "bin" / binary_cfg.name,
                pkg_root / "bin" / binary_cfg.name,
            ]
            for res in resource_candidates:
                try:
                    if res.exists():
                        candidate_paths.append(Path(str(res)))
                except FileNotFoundError:
                    continue
        except ModuleNotFoundError:
            pass

        which_path = shutil.which(binary_cfg.name)
        if which_path:
            candidate_paths.append(Path(which_path))

        binary_path = next((path for path in candidate_paths if path.exists()), None)
        if binary_path is None:
            raise FileNotFoundError(f"Off-target binary not found: {binary_cfg}")

        reference_path = Path(offtarget_cfg["reference_transcriptome"])
        if not reference_path.is_absolute():
            candidate = (self.root / reference_path).resolve()
            if candidate.exists():
                reference_path = candidate
            else:
                reference_dir = Path(offtarget_cfg.get("reference_dir", "references"))
                if not reference_dir.is_absolute():
                    reference_dir = (self.root / reference_dir).resolve()
                reference_path = (reference_dir / reference_path.name).resolve()
        else:
            reference_path = reference_path.resolve()

        self.offtarget = OffTargetSearcher(
            binary_path=binary_path,
            reference_path=reference_path,
            logger=self.logger,
            threads=self.config.get("compute", {}).get("threads"),
        )

        results_df = self.offtarget.search(
            guides_df=guides_df,
            output_path=results_csv,
            chunk_size=offtarget_cfg.get("chunk_size"),
        )

        return results_csv

    def _step_filter(self, offtarget_output: Path) -> Optional[Path]:
        df = pd.read_csv(offtarget_output)

        ranked, stats = apply_filters(df, self.config, logger=self.logger)
        final_csv = self.output_dir / "final_guides.csv"
        ranked.to_csv(final_csv, index=False)

        summary_path = self.output_dir / "filtering_stats.json"
        summary_path.write_text(pd.Series(stats).to_json(indent=2))

        return final_csv

    def _print_workflow_plan(self) -> None:
        self.logger.info("\n" + "=" * 60)
        self.logger.info("WORKFLOW EXECUTION PLAN (DRY RUN)")
        self.logger.info("=" * 60)

        self.logger.info("\n1. Download FASTA sequences")
        self.logger.info(f"   - Species: {self.config.get('species')}")
        self.logger.info(f"   - Genes: {len(self.targets)}")
        self.logger.info(f"   - Output: {self.output_dir}/sequences/")

        self.logger.info("\n2. Run TIGER prediction")
        tiger_cfg = self.config.get("tiger", {})
        self.logger.info(f"   - Model: {tiger_cfg.get('model_path')}")
        self.logger.info(f"   - Guide length: {tiger_cfg.get('guide_length')}")
        self.logger.info(f"   - Output: {self.output_dir}/tiger/")

        offtarget_cfg = self.config.get("offtarget", {})
        self.logger.info("\n3. Off-target analysis")
        self.logger.info(f"   - Reference: {offtarget_cfg.get('reference_transcriptome')}")
        self.logger.info(f"   - Max mismatches: {offtarget_cfg.get('max_mismatches')}")
        self.logger.info(f"   - Output: {self.output_dir}/offtarget/")

        filtering_cfg = self.config.get("filtering", {})
        top_n = self.config.get("top_n_guides", filtering_cfg.get("top_n_guides", 10))
        self.logger.info("\n4. Filter and rank guides")
        self.logger.info(f"   - Top N per gene: {top_n}")
        self.logger.info(f"   - MM1 threshold: {filtering_cfg.get('mm1_threshold')}")
        self.logger.info(f"   - MM2 threshold: {filtering_cfg.get('mm2_threshold')}")
        self.logger.info(f"   - Output: {self.output_dir}/final_guides.csv")
