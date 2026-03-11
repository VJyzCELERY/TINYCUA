# Makefile for TINYCUA

.PHONY: install lint test coverage complexity clean

# Install all subproject dependencies
install:
	$(MAKE) -C src/tinycua-backend install
	$(MAKE) -C src/tinycua-runner install
	$(MAKE) -C src/tinycua-sdk install
	$(MAKE) -C src/tinycua-finetune install

# Run linting across all subprojects
lint:
	$(MAKE) -C src/tinycua-backend lint
	$(MAKE) -C src/tinycua-runner lint
	$(MAKE) -C src/tinycua-sdk lint
	$(MAKE) -C src/tinycua-finetune lint

# Run tests across all subprojects
test:
	$(MAKE) -C src/tinycua-backend test
	$(MAKE) -C src/tinycua-runner test
	$(MAKE) -C src/tinycua-sdk test
	$(MAKE) -C src/tinycua-finetune test

# Run coverage across all subprojects
coverage:
	$(MAKE) -C src/tinycua-backend coverage
	$(MAKE) -C src/tinycua-runner coverage
	$(MAKE) -C src/tinycua-sdk coverage
	$(MAKE) -C src/tinycua-finetune coverage

# Run cognitive complexity analysis across all subprojects
complexity:
	$(MAKE) -C src/tinycua-backend complexity
	$(MAKE) -C src/tinycua-runner complexity
	$(MAKE) -C src/tinycua-sdk complexity
	$(MAKE) -C src/tinycua-finetune complexity

# Clean all subprojects
clean:
	$(MAKE) -C src/tinycua-backend clean
	$(MAKE) -C src/tinycua-runner clean
	$(MAKE) -C src/tinycua-sdk clean
	$(MAKE) -C src/tinycua-finetune clean
