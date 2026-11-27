#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
cd "$repo_root"
"$script_dir/azraq_postgres.sh" start
uv run python -m scripts.azraq_init
uv run python -m scripts.azraq_runtime_smoke
