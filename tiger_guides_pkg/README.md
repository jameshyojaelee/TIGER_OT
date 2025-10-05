# tiger-guides (portable Cas13 TIGER workflow)

`tiger-guides` packages the Sanjana Lab TIGER Cas13 guide design workflow so it can run on laptops, cloud VMs, or containers without the HPC environment. It mirrors the production pipeline (download → TIGER scoring → off-target search → filtering) and exposes a friendly CLI.

## Features
- Species-aware orchestration (`--species {mouse,human}`) with on-demand reference downloads
- Bundled smoke-test data for quick validation
- Shared core with the HPC scripts to keep behaviour consistent
- Optional Docker image that compiles the C off-target binary and ships the CLI

## Quick start
```bash
pip install tiger-guides

tiger-guides run my_targets.txt --species mouse --output-dir runs/latest
```

See the project documentation for advanced options, configuration, and container usage.

### Download assets on demand

```bash
# Transcriptomes (checksum-verified, cached in the destination)
tiger-guides fetch-reference --species human --destination references

# Models (provide local archive path or URL via environment variables)
export TIGER_MODEL_ARCHIVE_URL=https://example.org/tiger_model.tar.gz
export TIGER_MODEL_ARCHIVE_MD5=<expected-md5>
tiger-guides fetch-model --model tiger --destination .

# Smoke-test the pipeline end-to-end
tiger-guides smoke
```
