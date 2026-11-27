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

## Azraq PostgreSQL snapshot

The versioned schema, relationship metadata, and snapshot manifest are in this repository. The anonymized CSV snapshot remains a local input under `data/raw/azraq/`; the initializer checks every input file against the manifest before loading it.

See the [Azraq data and evaluation tutorial](docs/tutorial-001-azraq.md) for reproducible initialization, relationship eligibility, evaluation generation, and leakage checks.

```sh
./scripts/azraq_postgres.sh start
uv run python -m scripts.azraq_init
```

The initializer creates an immutable schema named from the dataset snapshot ID. It does not add primary-key or foreign-key constraints, and it loads `users.password` as NULL. The local container uses PostgreSQL 18.7 and binds only to `127.0.0.1:55432`. Its default password is a disposable local placeholder. Set `POSTGRES_PASSWORD` before the first start and `DATABASE_URL` for the initializer to use a different local credential.

Stop the container without deleting its database volume with:

```sh
./scripts/azraq_postgres.sh stop
```
