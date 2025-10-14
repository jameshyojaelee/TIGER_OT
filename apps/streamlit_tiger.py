#!/usr/bin/env python3
"""Streamlit UI dedicated to the TIGER scoring stage."""

from __future__ import annotations

import copy
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
from tiger_guides.offtarget.search import OffTargetSearcher
from tiger_guides.filters.ranking import apply_filters

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
        <h1>Sanjana Lab Cas13 Guide Designer</h1>
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
            preview_label = record_preview
            if gene_lookup_meta and gene_lookup_meta.get("preview"):
                preview_label = gene_lookup_meta["preview"]

            with st.spinner("Crunching sequences with TIGER..."):
                start_time = time.perf_counter()
                start_mem = _rss_mb()
                guides_df = _predict_guides(predictor, payload, batch_size)
                runtime = time.perf_counter() - start_time
                end_mem = _rss_mb()

            if guides_df.empty:
                st.warning("TIGER returned no guides. Check that input sequences are long enough for guide generation.")
                st.session_state.pop("guides_df", None)
                st.session_state.pop("guides_meta", None)
                st.session_state.pop("guides_success_message", None)
            else:
                success_message = f"Scored {len(guides_df)} guides across {num_records} transcripts ({preview_label})."
                if gene_lookup_meta:
                    success_message += f" Source: Ensembl {gene_lookup_meta.get('species_label', species_key)}."

                meta_payload = {
                    "num_records": num_records,
                    "record_preview": preview_label,
                    "gene_lookup_meta": gene_lookup_meta,
                    "runtime": runtime,
                    "delta_mem": max(0.0, end_mem - start_mem),
                    "payload_name": payload_name,
                    "species_key": species_key,
                }

                st.session_state["guides_df"] = guides_df
                st.session_state["guides_meta"] = meta_payload
                st.session_state["guides_success_message"] = success_message
                st.session_state.pop("offtarget_results", None)
                st.session_state.pop("offtarget_meta", None)

guides_df_cached = st.session_state.get("guides_df")
guides_meta = st.session_state.get("guides_meta", {})

if isinstance(guides_df_cached, pd.DataFrame) and not guides_df_cached.empty:
    success_message = st.session_state.get("guides_success_message")
    if success_message:
        st.success(success_message)

    gene_lookup_meta = guides_meta.get("gene_lookup_meta") or {}
    alias_map = gene_lookup_meta.get("alias_map", {})
    alias_pairs = [
        f"{orig} → {resolved}"
        for orig, resolved in alias_map.items()
        if isinstance(orig, str) and isinstance(resolved, str) and orig.lower() != resolved.lower()
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
        species_label = gene_lookup_meta.get("species_label", guides_meta.get("species_key", "?"))
        st.warning(
            f"{len(missing)} gene(s) were not found in Ensembl {species_label}: {missing_preview}"
        )

    runtime = guides_meta.get("runtime")
    delta_mem = guides_meta.get("delta_mem")
    metric_cols = st.columns(4)
    metric_cols[0].metric("Elapsed", f"{runtime:.2f} s" if runtime is not None else "—")
    metric_cols[1].metric("Peak ΔRAM", f"{delta_mem:.2f} MB" if delta_mem is not None else "—")
    metric_cols[2].metric("Top score", f"{guides_df_cached['Score'].max():.3f}")
    metric_cols[3].metric("Genes covered", f"{guides_df_cached['Gene'].nunique()}")

    with st.expander("Interactive results", expanded=True):
        genes = sorted(guides_df_cached["Gene"].unique())
        selected_genes = st.multiselect("Filter by gene", options=genes, default=genes)
        filtered = guides_df_cached[guides_df_cached["Gene"].isin(selected_genes)]
        display_height = 60 + 28 * len(filtered)
        st.dataframe(
            filtered.sort_values("Score", ascending=False),
            use_container_width=True,
            height=min(600, max(200, display_height)),
        )

    top_gene_scores = (
        guides_df_cached.groupby("Gene")["Score"].max().sort_values(ascending=False).head(10)
    )
    chart_df = top_gene_scores.reset_index()
    st.markdown("### 🔝 Top genes by max TIGER score")
    st.bar_chart(chart_df.set_index("Gene"))

    payload_name = guides_meta.get("payload_name")
    csv_bytes = guides_df_cached.sort_values("Score", ascending=False).to_csv(index=False).encode("utf-8")
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

    with st.expander("Off-target search & adaptive filtering", expanded=False):
        st.write(
            "Run the optimized C off-target search to append mismatch counts and MM0 transcript/gene annotations. "
            "You can then preview adaptive filtering results using the repository defaults."
        )

        offtarget_cfg = full_config.get("offtarget", {})
        compute_cfg = full_config.get("compute", {})
        species_for_offtarget = guides_meta.get("species_key")
        reference_entry = species_options.get(species_for_offtarget) if species_for_offtarget else None

        if reference_entry is None:
            st.info("Select a species in the configuration panel and rerun TIGER scoring to enable off-target analysis.")
        else:
            reference_path = Path(reference_entry.get("reference_transcriptome", ""))
            if not reference_path.is_absolute():
                reference_path = (PROJECT_ROOT / reference_path).resolve()

            binary_path = Path(offtarget_cfg.get("binary_path", "bin/offtarget_search"))
            if not binary_path.is_absolute():
                binary_path = (PROJECT_ROOT / binary_path).resolve()

            st.caption(f"Reference: {reference_path}")

            run_offtarget = st.button("🚀 Run off-target search", use_container_width=True, key="run_offtarget")

            if run_offtarget:
                if not reference_path.exists():
                    st.error(f"Reference transcriptome not found: {reference_path}")
                elif not binary_path.exists():
                    st.error(f"Off-target binary not found: {binary_path}")
                else:
                    try:
                        searcher = OffTargetSearcher(
                            binary_path=binary_path,
                            reference_path=reference_path,
                            logger=None,
                            threads=compute_cfg.get("threads"),
                        )
                    except FileNotFoundError as exc:
                        st.error(str(exc))
                    else:
                        with st.spinner("Running off-target search..."):
                            start = time.perf_counter()
                            results_df = searcher.search(
                                guides_df_cached,
                                chunk_size=offtarget_cfg.get("chunk_size"),
                            )
                            elapsed = time.perf_counter() - start

                        st.session_state["offtarget_results"] = results_df
                        st.session_state["offtarget_meta"] = {
                            "elapsed": elapsed,
                            "reference": str(reference_path),
                            "species_key": species_for_offtarget,
                        }

            off_results = st.session_state.get("offtarget_results")
            off_meta = st.session_state.get("offtarget_meta", {})

            if isinstance(off_results, pd.DataFrame) and not off_results.empty:
                elapsed = off_meta.get("elapsed")
                ref_label = off_meta.get("reference", str(reference_path))
                st.success(
                    f"Off-target search completed on {len(off_results):,} guides using {ref_label}."
                    + (f" Runtime: {elapsed:.2f} s." if elapsed is not None else "")
                )

                mm1_hits = int((off_results["MM1"] > 0).sum())
                mm2_hits = int((off_results["MM2"] > 0).sum())
                metric_cols = st.columns(3)
                metric_cols[0].metric("Guides analysed", f"{len(off_results):,}")
                metric_cols[1].metric("Guides with MM1>0", f"{mm1_hits:,}")
                metric_cols[2].metric("Guides with MM2>0", f"{mm2_hits:,}")

                important_cols = [
                    col for col in [
                        "Gene",
                        "Sequence",
                        "Target" if "Target" in off_results.columns else None,
                        "Score",
                        "MM0",
                        "MM1",
                        "MM2",
                        "MM0_Transcripts",
                        "MM0_Genes",
                    ]
                    if col in off_results.columns
                ]

                st.dataframe(
                    off_results[important_cols].sort_values(["Gene", "Score"], ascending=[True, False]),
                    use_container_width=True,
                    height=min(600, max(220, 28 * min(len(off_results), 15))),
                )

                filter_config = copy.deepcopy(full_config)
                if "top_n_guides" not in filter_config:
                    filter_config["top_n_guides"] = filter_config.get("filtering", {}).get("top_n_guides", 10)

                filtered_guides, filter_stats = apply_filters(off_results.copy(), filter_config, logger=None)

                st.markdown("#### ✅ Adaptive filtering summary")
                st.write(
                    f"Selected {len(filtered_guides):,} guides after applying score/MM thresholds and adaptive MM0 tolerance."
                )
                st.json(filter_stats, expanded=False)

                filtered_cols = [
                    col for col in [
                        "Gene",
                        "Sequence",
                        "Target" if "Target" in filtered_guides.columns else None,
                        "Score",
                        "MM0",
                        "MM1",
                        "MM2",
                        "MM0_Transcripts",
                        "MM0_Genes",
                    ]
                    if col in filtered_guides.columns
                ]

                st.dataframe(
                    filtered_guides[filtered_cols].sort_values(["Gene", "Score"], ascending=[True, False]),
                    use_container_width=True,
                    height=min(500, max(200, 28 * min(len(filtered_guides), 10))),
                )

                raw_csv = off_results.sort_values(["Gene", "Score"], ascending=[True, False]).to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download off-target results (CSV)",
                    data=raw_csv,
                    file_name=f"{Path(payload_name or 'tiger_guides').stem}_offtarget.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

                filtered_csv = filtered_guides.sort_values(["Gene", "Score"], ascending=[True, False]).to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download filtered guides (CSV)",
                    data=filtered_csv,
                    file_name=f"{Path(payload_name or 'tiger_guides').stem}_filtered.csv",
                    mime="text/csv",
                    use_container_width=True,
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
