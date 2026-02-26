# Makefile for TINYCUA

.PHONY: install lint test coverage clean

# Install all subproject dependencies
install:
	$(MAKE) -C src/TINYCUA_BACKEND install
	$(MAKE) -C src/TINYCUA_RUNNER install
	$(MAKE) -C src/TINYCUA_SDK install

# Run linting across all subprojects
lint:
	$(MAKE) -C src/TINYCUA_BACKEND lint
	$(MAKE) -C src/TINYCUA_RUNNER lint
	$(MAKE) -C src/TINYCUA_SDK lint

# Run tests across all subprojects
test:
	$(MAKE) -C src/TINYCUA_BACKEND test
	$(MAKE) -C src/TINYCUA_RUNNER test
	$(MAKE) -C src/TINYCUA_SDK test

# Run coverage across all subprojects
coverage:
	$(MAKE) -C src/TINYCUA_BACKEND coverage
	$(MAKE) -C src/TINYCUA_RUNNER coverage
	$(MAKE) -C src/TINYCUA_SDK coverage

# Clean all subprojects
clean:
	$(MAKE) -C src/TINYCUA_BACKEND clean
	$(MAKE) -C src/TINYCUA_RUNNER clean
	$(MAKE) -C src/TINYCUA_SDK clean
