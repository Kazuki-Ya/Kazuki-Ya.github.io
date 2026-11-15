.PHONY: update publish

update:
	python3 scripts/update_homepage.py

publish:
	python3 scripts/update_homepage.py --push
