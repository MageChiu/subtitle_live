PYTHON ?= python3

.PHONY: build run build-windows build-macos build-linux run-windows run-macos run-linux

build:
	$(PYTHON) scripts/build.py $(ARGS)

run:
	$(PYTHON) scripts/run.py $(ARGS)

build-windows:
	$(PYTHON) scripts/build.py --platform windows

build-macos:
	$(PYTHON) scripts/build.py --platform macos

build-linux:
	$(PYTHON) scripts/build.py --platform linux

run-windows:
	$(PYTHON) scripts/run.py --platform windows

run-macos:
	$(PYTHON) scripts/run.py --platform macos

run-linux:
	$(PYTHON) scripts/run.py --platform linux
