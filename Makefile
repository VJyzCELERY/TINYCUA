# Makefile for TINYCUA

.PHONY: install lint test coverage complexity clean
.PHONY: docker-up docker-down docker-logs docker-restart
.PHONY: run run-backend run-runner stop

# Default target
all: install

# Install all subproject dependencies
install:
	$(MAKE) -C src/tinycua-backend install
	$(MAKE) -C src/tinycua-runner install
	$(MAKE) -C src/tinycua-sdk install
	$(MAKE) -C src/tinycua-finetune install
	$(MAKE) -C src/tinycua install

# Run linting across all subprojects
lint:
	$(MAKE) -C src/tinycua-backend lint
	$(MAKE) -C src/tinycua-runner lint
	$(MAKE) -C src/tinycua-sdk lint
	$(MAKE) -C src/tinycua-finetune lint
	$(MAKE) -C src/tinycua lint

# Run tests across all subprojects
test:
	$(MAKE) -C src/tinycua-backend test
	$(MAKE) -C src/tinycua-runner test
	$(MAKE) -C src/tinycua-sdk test
	$(MAKE) -C src/tinycua-finetune test
	$(MAKE) -C src/tinycua test

# Run coverage across all subprojects
coverage:
	$(MAKE) -C src/tinycua-backend coverage
	$(MAKE) -C src/tinycua-runner coverage
	$(MAKE) -C src/tinycua-sdk coverage
	$(MAKE) -C src/tinycua-finetune coverage
	$(MAKE) -C src/tinycua coverage

# Run cognitive complexity analysis across all subprojects
complexity:
	$(MAKE) -C src/tinycua-backend complexity
	$(MAKE) -C src/tinycua-runner complexity
	$(MAKE) -C src/tinycua-sdk complexity
	$(MAKE) -C src/tinycua-finetune complexity
	$(MAKE) -C src/tinycua complexity

# Clean all subprojects
clean:
	$(MAKE) -C src/tinycua-backend clean
	$(MAKE) -C src/tinycua-runner clean
	$(MAKE) -C src/tinycua-sdk clean
	$(MAKE) -C src/tinycua-finetune clean
	$(MAKE) -C src/tinycua clean

# ============================================
# Docker Operations (for tinycua-backend)
# ============================================

# Start all Docker services (database)
docker-up:
	cd src/tinycua-backend && docker compose up -d
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 3
	@cd src/tinycua-backend && docker compose ps

# Stop all Docker services
docker-down:
	cd src/tinycua-backend && docker compose down

# View Docker logs
docker-logs:
	cd src/tinycua-backend && docker compose logs -f

# Restart Docker services
docker-restart:
	cd src/tinycua-backend && docker compose restart

# ============================================
# Run Services
# ============================================

# Start all services: docker + backend + runner
run: docker-up
	@echo ""
	@echo "Starting backend and runner in background..."
	@echo ""
	@cd src/tinycua-backend && nohup python -m tinycua_backend.main > /tmp/tinycua-backend.log 2>&1 & \
		echo "Backend PID: $$!"
	@cd src/tinycua-runner && nohup python -m tinycua_runner.main > /tmp/tinycua-runner.log 2>&1 & \
		echo "Runner PID: $$!"
	@echo ""
	@echo "Services started!"
	@echo "  Backend: http://localhost:8000 (logs: /tmp/tinycua-backend.log)"
	@echo "  Runner:  http://localhost:8003 (logs: /tmp/tinycua-runner.log)"
	@echo ""
	@echo "To stop: make stop"

# Start only backend
run-backend: docker-up
	@echo "Starting backend..."
	@cd src/tinycua-backend && nohup python -m tinycua_backend.main > /tmp/tinycua-backend.log 2>&1 & \
		echo "Backend started! PID: $$!"
	@echo "Logs: /tmp/tinycua-backend.log"

# Start only runner
run-runner:
	@echo "Starting runner..."
	@cd src/tinycua-runner && nohup python -m tinycua_runner.main > /tmp/tinycua-runner.log 2>&1 & \
		echo "Runner started! PID: $$!"
	@echo "Logs: /tmp/tinycua-runner.log"

# Stop all services
stop:
	@echo "Stopping services..."
	@pkill -f "tinycua_backend.main" && echo "Backend stopped" || true
	@pkill -f "tinycua_runner.main" && echo "Runner stopped" || true
	@echo "Done!"

# ============================================
# Development Commands
# ============================================

# Alias for run (backward compatibility)
dev-start: run

# Alias for stop (backward compatibility)
dev-stop: stop

# Run the end-to-end test (requires backend and runner running)
e2e-test:
	@echo "Make sure services are running: make run"
	@	echo "Make sure an OpenAI-compatible endpoint is running with a model loaded"
	@echo ""
	cd src/tinycua-sdk && python -m tests.e2e.test_backend_runner
