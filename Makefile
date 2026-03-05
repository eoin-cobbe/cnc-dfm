SHELL := /bin/bash

.PHONY: run docs-cli
run:
	@if [[ -z "$(STEP)" ]]; then \
		echo "Usage: make run STEP=/path/to/file.step ARGS='--min-radius 1.0'"; \
		exit 1; \
	fi
	@./scripts/run.sh "$(STEP)" $(ARGS)

docs-cli:
	@./scripts/generate_cli_docs.sh
