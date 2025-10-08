import csv
import os
import subprocess
from pathlib import Path
import tempfile


def _write_file(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")


def _load_transcripts(fasta_path: Path):
    transcripts = []
    current = []
    for line in fasta_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        if line.startswith(">"):
            if current:
                transcripts.append("".join(current))
                current = []
        else:
            current.append(line.strip().upper())
    if current:
        transcripts.append("".join(current))
    return transcripts


def _brute_counts(sequence: str, transcripts) -> list[int]:
    max_mismatch = 5
    counts = [0] * (max_mismatch + 1)
    length = len(sequence)
    for ref in transcripts:
        for pos in range(0, len(ref) - length + 1):
            window = ref[pos : pos + length]
            mismatches = sum(1 for a, b in zip(sequence, window) if a != b)
            if mismatches <= max_mismatch:
                counts[mismatches] += 1
    return counts


def test_offtarget_binary_multi_thread(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    binary_path = repo_root / "bin" / "offtarget_search"

    # Ensure the binary is built
    if not binary_path.exists():
        subprocess.run(["make", "bin/offtarget_search"], cwd=repo_root, check=True)

    fasta_contents = (
        ">tx1\n"
        "ACGTACGTACGTACGTACGT\n"
        ">tx2\n"
        "ACGTACGTACGTACGAACGA\n"
        ">tx3\n"
        "TTTTTTTTTTTTTTTTTTTT\n"
    )
    fasta_path = tmp_path / "reference.fa"
    _write_file(fasta_path, fasta_contents)

    guides_csv = (
        "Gene,Sequence\n"
        "GeneA,ACGTACGTACGTACGTACGT\n"
        "GeneB,ACGTACGTACGTACGAACGA\n"
        "GeneC,TTTTTTTTTTTTTTTTTTTT\n"
        "GeneD,ACGTACGTACGTACGTACGA\n"
    )
    guides_path = tmp_path / "guides.csv"
    _write_file(guides_path, guides_csv)

    output_path = tmp_path / "results.csv"

    env = os.environ.copy()
    env["TIGER_OFFTARGET_THREADS"] = "2"

    subprocess.run(
        [
            str(binary_path),
            str(guides_path),
            str(fasta_path),
            str(output_path),
        ],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )

    transcripts = _load_transcripts(fasta_path)

    with output_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    for row in rows:
        counts = _brute_counts(row["Sequence"], transcripts)
        observed = [
            int(row["MM0"]),
            int(row["MM1"]),
            int(row["MM2"]),
            int(row["MM3"]),
            int(row["MM4"]),
            int(row["MM5"]),
        ]
        assert observed == counts, f"Mismatches for {row['Gene']} differ"
