#!/usr/bin/env python3
"""Streamlit UI dedicated to the TIGER scoring stage."""

from __future__ import annotations

import io
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import streamlit as st
import yaml
from Bio import SeqIO

try:  # pragma: no cover - platform guard
    import resource
except ImportError:  # pragma: no cover - Windows fallback
    resource = None


def _find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "configs" / "default.yaml").exists():
            return candidate
    raise FileNotFoundError("Unable to locate project root containing configs/default.yaml")


PROJECT_ROOT = _find_project_root(Path(__file__).resolve())
CONFIG_PATH = PROJECT_ROOT / "configs" / "default.yaml"
SAMPLE_FASTA = PROJECT_ROOT / "runs" / "smoke" / "sequences" / "all_targets.fasta"

# Ensure local packages resolve when running via Streamlit
PACKAGE_SRC = PROJECT_ROOT / "tiger_guides_pkg" / "src"
LEGACY_SRC = PROJECT_ROOT / "src"
for path in (PACKAGE_SRC, LEGACY_SRC):
    if path.exists() and str(path) not in sys.path:
        sys.path.insert(0, str(path))

from tiger_guides.models.loader import resolve_model_paths
from tiger_guides.tiger.predictor import TIGERPredictor
from tiger_guides.download.ensembl import EnsemblDownloader

st.set_page_config(
    page_title="Sanjana Lab Cas13 Guide Designer",
    layout="wide",
)

# Accent styling
st.markdown(
    """
    <style>
    .tiger-hero {
        background: linear-gradient(135deg, #1e1e6f, #5e2cd5 60%, #ff6f91);
        padding: 2.75rem;
        border-radius: 1.5rem;
        color: #ffffff;
        margin-bottom: 1.5rem;
        box-shadow: 0 30px 60px rgba(62, 42, 120, 0.45);
    }
    .tiger-hero h1 {
        font-size: 2.4rem;
        margin-bottom: 0.5rem;
    }
    .tiger-hero p {
        font-size: 1.05rem;
        opacity: 0.9;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def load_predictor(config_path: Path) -> Tuple[TIGERPredictor, dict, dict]:
    with config_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    tiger_config = dict(config.get("tiger", {}))
    if not tiger_config:
        raise KeyError("Missing 'tiger' section in configuration file")

    model_paths = resolve_model_paths(tiger_config, PROJECT_ROOT)
    tiger_config["model_path"] = str(model_paths["model_path"])

    predictor = TIGERPredictor(model_path=model_paths["model_path"], config=tiger_config)
    predictor.load_model()
    return predictor, tiger_config, config


def _read_fasta_payload(upload, pasted_text: str, use_sample: bool) -> Tuple[Optional[bytes], Optional[str]]:
    if use_sample and SAMPLE_FASTA.exists():
        return SAMPLE_FASTA.read_bytes(), SAMPLE_FASTA.name
    if upload is not None:
        return upload.getvalue(), upload.name
    if pasted_text.strip():
        return pasted_text.encode("utf-8"), "pasted_sequences.fasta"
    return None, None


def _validate_fasta(data: bytes) -> Tuple[int, str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("FASTA input must be UTF-8 encoded") from exc

    handle = io.StringIO(text)
    records = list(SeqIO.parse(handle, "fasta"))
    if not records:
        raise ValueError("No FASTA records were detected")
    preview = ", ".join(record.id for record in records[:3])
    if len(records) > 3:
        preview += ", …"
    return len(records), preview


def _predict_guides(
    predictor: TIGERPredictor,
    fasta_bytes: bytes,
    batch_size: int,
) -> pd.DataFrame:
    with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".fasta") as tmp:
        tmp.write(fasta_bytes)
        temp_path = Path(tmp.name)

    try:
        return predictor.predict_from_fasta(temp_path, output_path=None, batch_size=batch_size)
    finally:
        temp_path.unlink(missing_ok=True)


def _gene_names_to_fasta_bytes(
    gene_names: list[str],
    species_key: str,
    full_config: dict,
) -> Tuple[bytes, dict]:
    species_options = full_config.get("species_options", {})
    if species_key not in species_options:
        raise ValueError(f"Species '{species_key}' is not configured.")

    species_entry = species_options[species_key]
    ensembl_cfg = full_config.get("ensembl", {})

    downloader = EnsemblDownloader(
        species=species_entry["ensembl_name"],
        rest_url=ensembl_cfg.get("rest_url", "https://rest.ensembl.org"),
        rate_limit_delay=ensembl_cfg.get("rate_limit_delay", 0.5),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_fasta = Path(tmpdir) / "gene_targets.fasta"
        records = downloader.download_genes(
            gene_list=gene_names,
            seq_type="cds",
            output_fasta=temp_fasta,
            output_dir=None,
        )

        if not records:
            raise ValueError("No coding sequences were retrieved for the provided gene list.")

        fasta_bytes = temp_fasta.read_bytes()

    alias_map = {}
    resolved_names = []
    for record in records:
        resolved = record.id.split("_")[0]
        original = record.annotations.get("original_name", resolved)
        alias_map.setdefault(original, resolved)
        resolved_names.append(resolved)

    missing = [
        name for name in gene_names
        if all(name.lower() != resolved.lower() for resolved in resolved_names)
    ]

    preview = ", ".join(resolved_names[:3])
    if len(resolved_names) > 3:
        preview += ", …"

    return fasta_bytes, {
        "alias_map": alias_map,
        "missing": missing,
        "preview": preview,
        "species_label": species_entry["ensembl_name"],
    }


def _rss_mb() -> float:
    if resource is None:
        return 0.0
    usage_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return usage_kb / (1024 * 1024)
    return usage_kb / 1024


predictor, base_tiger_config, full_config = load_predictor(CONFIG_PATH)

species_options = full_config.get("species_options", {})
species_keys = list(species_options.keys())
default_species_index = species_keys.index("human") if "human" in species_keys else 0 if species_keys else None

st.markdown(
    """
    <div class="tiger-hero">
        <h1>Sanjana Lab TIGER Guide Designer</h1>
        <p>
            Curate FASTA sequences, trigger the TIGER scoring engine, and explore ranked Cas13 guides instantly.
            Drop in your transcripts, tweak scoring knobs, and download polished outputs without waiting on the full HPC pipeline.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([1.2, 0.8], gap="large")

with left:
    st.subheader("1. Provide coding sequences")
    tabs = st.tabs(["🔎 Gene lookup", "📤 Upload FASTA", "📝 Paste FASTA"])

    with tabs[0]:
        gene_input = st.text_area(
            "Enter gene symbols (one per line)",
            height=220,
            placeholder="Nanog\nSox2",
        )
        st.caption("Use HGNC (human) or MGI (mouse) symbols; resolve species on the right.")
    with tabs[1]:
        uploaded = st.file_uploader(
            "Upload a FASTA containing CDS sequences for one or more genes.",
            type=["fasta", "fa", "fna", "txt"],
            accept_multiple_files=False,
            help="Sequences should already be CDS (coding) and named in the FASTA headers.",
        )
    with tabs[2]:
        pasted = st.text_area(
            "Paste FASTA-formatted sequences",
            height=220,
            placeholder=">MyGene\nATGC...",
        )

    use_sample = False
    if SAMPLE_FASTA.exists():
        use_sample = st.checkbox("Use bundled smoke-test FASTA (Nanog & Sox2)", value=False)
    st.caption("FASTA uploads take precedence when multiple inputs are provided. Keep runs under ~50 CDS for snappy feedback.")

with right:
    st.subheader("2. Configure scoring & lookup")
    if species_keys:
        default_index = default_species_index if default_species_index is not None else 0
        species_key = st.selectbox(
            "Species for gene lookup",
            options=species_keys,
            index=default_index,
            help="Determines which Ensembl catalog is used when resolving gene symbols.",
        )
        species_label = species_options[species_key]["ensembl_name"]
        st.caption(f"Gene lookup will pull CDS from Ensembl species: {species_label}.")
    else:
        species_key = None
        st.warning("No species configured in configs/default.yaml; gene lookup is disabled.")

    batch_size = st.slider(
        "Batch size",
        min_value=100,
        max_value=1000,
        step=100,
        value=base_tiger_config.get("batch_size", 500),
    )
    st.caption("Guide length (23 nt) and sequence context (3 nt upstream, 0 nt downstream) follow TIGER defaults.")

    st.write(" ")
    st.write(" ")
    st.markdown(
        "💡 **Advanced tip:** combine this with the off-target filter later to promote high-confidence guides."
    )

predictor.config["batch_size"] = batch_size

gene_names = [
    line.strip()
    for line in (gene_input.splitlines() if "gene_input" in locals() else [])
    if line.strip()
]

fasta_payload, fasta_name = _read_fasta_payload(uploaded, pasted, use_sample)

run_button = st.button("⚡ Run TIGER Scoring", use_container_width=True)

if run_button:
    payload = fasta_payload
    payload_name = fasta_name
    gene_lookup_meta = None

    if payload is None and gene_names:
        if species_key is None:
            st.error("Select a species before running gene lookup.")
        else:
            with st.spinner(f"Downloading {len(gene_names)} gene CDS from Ensembl for {species_key}..."):
                try:
                    payload, gene_lookup_meta = _gene_names_to_fasta_bytes(gene_names, species_key, full_config)
                    payload_name = f"{species_key}_genes.fasta"
                except ValueError as exc:
                    st.error(f"Gene lookup failed: {exc}")
                    payload = None
    elif payload is not None and gene_names:
        st.info("Using provided FASTA input. Clear the FASTA tab to run gene lookup instead.")

    if payload is None:
        st.error("Provide a FASTA file, paste sequences, toggle the sample dataset, or enter gene symbols before running.")
    else:
        try:
            num_records, record_preview = _validate_fasta(payload)
        except ValueError as exc:
            st.error(f"FASTA validation failed: {exc}")
        else:
            if gene_lookup_meta and gene_lookup_meta.get("preview"):
                record_preview = gene_lookup_meta["preview"]

            with st.spinner("Crunching sequences with TIGER..."):
                start_time = time.perf_counter()
                start_mem = _rss_mb()
                guides_df = _predict_guides(predictor, payload, batch_size)
                runtime = time.perf_counter() - start_time
                end_mem = _rss_mb()

            if guides_df.empty:
                st.warning("TIGER returned no guides. Check that input sequences are long enough for guide generation.")
            else:
                success_message = f"Scored {len(guides_df)} guides across {num_records} transcripts ({record_preview})."
                if gene_lookup_meta:
                    success_message += f" Source: Ensembl {gene_lookup_meta.get('species_label', species_key)}."
                st.success(success_message)

                if gene_lookup_meta:
                    alias_pairs = [
                        f"{orig} → {resolved}"
                        for orig, resolved in gene_lookup_meta["alias_map"].items()
                        if orig.lower() != resolved.lower()
                    ]
                    if alias_pairs:
                        preview_alias = ", ".join(alias_pairs[:5])
                        if len(alias_pairs) > 5:
                            preview_alias += ", …"
                        st.info(f"Resolved gene symbols: {preview_alias}")

                    missing = gene_lookup_meta.get("missing", [])
                    if missing:
                        missing_preview = ", ".join(missing[:5])
                        if len(missing) > 5:
                            missing_preview += ", …"
                        st.warning(
                            f"{len(missing)} gene(s) were not found in Ensembl {gene_lookup_meta.get('species_label', species_key)}: {missing_preview}"
                        )

                delta_mem = max(0.0, end_mem - start_mem)
                metric_cols = st.columns(4)
                metric_cols[0].metric("Elapsed", f"{runtime:.2f} s")
                metric_cols[1].metric("Peak ΔRAM", f"{delta_mem:.2f} MB")
                metric_cols[2].metric("Top score", f"{guides_df['Score'].max():.3f}")
                metric_cols[3].metric("Genes covered", f"{guides_df['Gene'].nunique()}")

                with st.expander("Interactive results", expanded=True):
                    genes = sorted(guides_df["Gene"].unique())
                    selected_genes = st.multiselect("Filter by gene", options=genes, default=genes)
                    filtered = guides_df[guides_df["Gene"].isin(selected_genes)]
                    st.dataframe(
                        filtered.sort_values("Score", ascending=False),
                        use_container_width=True,
                        height=min(500, 60 + 28 * len(filtered)),
                    )

                top_gene_scores = (
                    guides_df.groupby("Gene")["Score"].max().sort_values(ascending=False).head(10)
                )
                chart_df = top_gene_scores.reset_index()
                st.markdown("### 🔝 Top genes by max TIGER score")
                st.bar_chart(chart_df.set_index("Gene"))

                csv_bytes = guides_df.sort_values("Score", ascending=False).to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download ranked guides (CSV)",
                    data=csv_bytes,
                    file_name=f"{Path(payload_name or 'tiger_guides').stem}_tiger_guides.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

                st.caption(
                    "Latency and memory figures are measured locally during inference; rerun after tweaking batch size or contexts to compare."
                )

st.markdown("""
---
**Maintainer**  
James Lee – New York Genome Center · Sanjana lab

**Cite TIGER**  
Wessels, H.-H.*, Stirn, A.*, Méndez-Mancilla, A., Kim, E. J., Hart, S. K., Knowles, D. A.#, & Sanjana, N. E.#  
Prediction of on-target and off-target activity of CRISPR–Cas13d guide RNAs using deep learning. *Nature Biotechnology* (2023).  
[https://doi.org/10.1038/s41587-023-01830-8](https://doi.org/10.1038/s41587-023-01830-8)
""")
