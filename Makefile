# Makefile for TINYCUA

.PHONY: install lint test coverage clean

# Install all subproject dependencies
install:
	$(MAKE) -C src/tinycua-backend install
	$(MAKE) -C src/tinycua-runner install
	$(MAKE) -C src/tinycua-sdk install

# Run linting across all subprojects
lint:
	$(MAKE) -C src/tinycua-backend lint
	$(MAKE) -C src/tinycua-runner lint
	$(MAKE) -C src/tinycua-sdk lint

# Run tests across all subprojects
test:
	$(MAKE) -C src/tinycua-backend test
	$(MAKE) -C src/tinycua-runner test
	$(MAKE) -C src/tinycua-sdk test

# Run coverage across all subprojects
coverage:
	$(MAKE) -C src/tinycua-backend coverage
	$(MAKE) -C src/tinycua-runner coverage
	$(MAKE) -C src/tinycua-sdk coverage

# Clean all subprojects
clean:
	$(MAKE) -C src/tinycua-backend clean
	$(MAKE) -C src/tinycua-runner clean
	$(MAKE) -C src/tinycua-sdk clean
