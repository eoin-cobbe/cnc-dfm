SHELL := /bin/bash

.PHONY: run
run:
	@if [[ -z "$(STEP)" ]]; then \
		echo "Usage: make run STEP=/path/to/file.step ARGS='--min-radius 1.0'"; \
		exit 1; \
	fi
	@./scripts/run.sh "$(STEP)" $(ARGS)
