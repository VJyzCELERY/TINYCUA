# Makefile for TINYCUA

SUBPROJECTS := \
	src/tinycua-backend \
	src/tinycua-sdk \
	src/tinycua-finetune \
	src/tinycua

.PHONY: install lint test clean

install:
	@for dir in $(SUBPROJECTS); do \
		$(MAKE) -C $$dir install; \
	done

lint:
	@for dir in $(SUBPROJECTS); do \
		$(MAKE) -C $$dir lint; \
	done

test:
	@for dir in $(SUBPROJECTS); do \
		$(MAKE) -C $$dir test; \
	done

clean:
	@for dir in $(SUBPROJECTS); do \
		$(MAKE) -C $$dir clean; \
	done
