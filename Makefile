.PHONY: all update resources sync-resources javascript translations extract doc test build install clean coverage lint lint-flake8 lint-eslint

js_src := $(wildcard javascript/*.js)
js_out := $(js_src:javascript/%.js=wiking/resources/scripts/%.js)

all: doc update

update: translations resources

resources: sync-resources javascript

sync-resources:
	git ls-files resources | rsync -a --info=name --delete --files-from=- ./ wiking/

javascript: $(js_out)

wiking/resources/scripts/%.js: javascript/%.js
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

install:
	# Only for development installs.  Use pip for production/user installs.
	flit install --symlink

clean:
	rm -rf dist wiking/resources
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
