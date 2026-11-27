# triage-sql

An agentic Text-to-SQL system featuring tiered LLM orchestration, adaptive model routing, and hybrid RAG for natural-language database querying. Explores PEFT/QLoRA fine-tuning, AWQ/GPTQ quantization, and vLLM inference optimization to balance SQL accuracy, latency, and inference cost. Includes comparative benchmarking, MLflow experiment tracking, Langfuse observability, and automated CI/CD deployment.

## Development

This project uses [uv](https://docs.astral.sh/uv/) to manage Python and dependencies. The required Python version is recorded in `.python-version`, and `uv.lock` pins the dependency set.

```sh
uv sync --all-groups
uv run pytest
```

Run a project script in the managed environment with `uv run`, for example:

```sh
uv run python scripts/validate_azraq_relationships.py --help
```
