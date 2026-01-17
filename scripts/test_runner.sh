#!/bin/bash
# Zotero-CLI Test Runner
# Categorizes and executes tests according to the Golden Path v2.1

set -e

# Defaults
CATEGORY=${1:-"all"}
COVERAGE=${2:-"false"}

# Check if we are in the right directory
if [ ! -d "tests" ]; then
    echo "Error: Must run from project root (cissa/tools/zotero-cli/)"
    exit 1
fi

run_unit() {
    echo "--- Running Unit Tests ---"
    if [ "$COVERAGE" = "true" ]; then
        pytest --cov=src/zotero_cli tests/unit
    else
        pytest tests/unit
    fi
}

run_e2e() {
    echo "--- Running E2E Tests ---"
    if [ "$COVERAGE" = "true" ]; then
        pytest --cov=src/zotero_cli --cov-append tests/e2e
    else
        pytest tests/e2e
    fi
}

run_docs() {
    echo "--- Running Documentation Tests ---"
    pytest tests/docs
}

case $CATEGORY in
    "unit")
        run_unit
        ;;
    "e2e")
        run_e2e
        ;;
    "docs")
        run_docs
        ;;
    "all")
        run_unit
        run_e2e
        run_docs
        ;;
    *)
        echo "Usage: $0 [unit|e2e|docs|all] [true|false (coverage)]"
        exit 1
        ;;
esac
