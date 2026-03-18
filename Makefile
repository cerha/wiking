.PHONY: translations doc test resources javascript

js_src := $(wildcard javascript/*.js)
js_out := $(js_src:javascript/%.js=wiking/resources/scripts/%.js)

all: compile translations resources

compile:
	python -m compileall -d . wiking
	python -O -m compileall -d . wiking

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

javascript: $(js_out)

wiking/resources/scripts/%.js: javascript/%.js
	mkdir -p $(@D)
	python3 -m rjsmin < $< > $@

resources:
	git ls-files resources | rsync -av --delete --files-from=- ./ wiking/

# Only for development installs.  Use pip for production/user installs.
install:
	flit install --symlink

build: translations resources
	flit build

clean:
	rm -rf dist/ wiking/resources
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
