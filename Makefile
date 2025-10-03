# Makefile for Cas13 TIGER Workflow

.PHONY: all clean test install help

# Default target
all: bin/offtarget_search
	@echo "✅ Build complete!"
	@echo "Run: ./run_tiger_workflow.sh targets.txt"

# Build C off-target search binary
bin/offtarget_search: lib/offtarget/search.c
	@echo "Building off-target search binary..."
	@mkdir -p bin
	@cd lib/offtarget && $(MAKE)
	@echo "✅ Binary built: bin/offtarget_search"

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	@rm -f bin/offtarget_search
	@cd lib/offtarget && $(MAKE) clean
	@echo "✅ Clean complete"

# Install Python dependencies
install:
	@echo "Installing Python dependencies..."
	pip install -r requirements.txt
	@echo "✅ Dependencies installed"

# Run tests
test:
	@echo "Running tests..."
	python3 -m pytest tests/ -v
	@echo "✅ Tests complete"

# Help
help:
	@echo "Cas13 TIGER Workflow - Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all       - Build all components (default)"
	@echo "  clean     - Remove build artifacts"
	@echo "  install   - Install Python dependencies"
	@echo "  test      - Run tests"
	@echo "  help      - Show this help message"
	@echo ""
	@echo "Usage:"
	@echo "  make              # Build everything"
	@echo "  make clean        # Clean build"
	@echo "  make install      # Install dependencies"
