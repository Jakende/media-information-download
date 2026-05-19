.PHONY: setup run setup-transcribe transcribe tui

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

run: setup
	. .venv/bin/activate && python3 youtube_download.py $(if $(URL),--url "$(URL)",)

setup-transcribe:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r requirements-transcribe.txt

transcribe: setup-transcribe
	. .venv/bin/activate && python3 youtube_download_transcribe.py --url "$(URL)"

tui: setup-transcribe
	. .venv/bin/activate && python3 media_tui.py
