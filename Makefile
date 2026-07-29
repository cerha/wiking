.PHONY: all update resources sync-resources sync-doc clean-obsolete javascript translations extract doc test build publish publish-test install clean coverage lint lint-flake8 lint-eslint

js_src := $(wildcard javascript/*.js)
js_out := $(js_src:javascript/%.js=wiking/assets/resources/scripts/%.js)

all: doc update

update: clean-obsolete translations resources sync-doc

# The generated data directories moved under 'assets'.  Working copies created
# before that still contain them in their former locations, where they are no
# longer ignored by git, so they break the sdist build.  This target may be
# removed once all the working copies around are rebuilt.
clean-obsolete:
	rm -rf wiking/resources wiking/translations wiking/doc

resources: sync-resources javascript

sync-resources:
	git ls-files resources | rsync -a --info=name --delete --files-from=- ./ wiking/assets/

sync-doc:
	git -C doc/src ls-files | rsync -a --info=name --delete --files-from=- doc/src/ wiking/assets/doc/

javascript: $(js_out)

wiking/assets/resources/scripts/%.js: javascript/%.js
	mkdir -p $(@D)
	python3 -m rjsmin < $< > $@

translations:
	make -C translations

extract:
	make -C translations extract

doc:
	python -m lcg.make doc/src doc/html

api-doc:
	epydoc -o doc/html/api --name Wiking --inheritance=included --graph classtree wiking

test:
	python -m pytest wiking/test.py

build: update
	flit build

publish:
	python -m twine upload --repository pypi dist/*.whl

publish-test:
	python -m twine upload --repository testpypi dist/*.whl

install:
	# Only for development installs.  Use pip for production/user installs.
	flit install --symlink

clean: clean-obsolete
	rm -rf dist wiking/assets
	make -C translations clean

coverage:
	coverage run --source=wiking -m pytest wiking/test.py
	coverage report

lint: lint-flake8 lint-eslint

lint-flake8:
	flake8 wiking bin

lint-eslint:
	npm run eslint javascript/{wiking,wiking-cms,discussion}.js

lint-csslint:
	npm run csslint resources/css
