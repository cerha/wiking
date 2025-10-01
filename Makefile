.PHONY: translations doc test resources

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
	flake8 lcg bin

lint-eslint:
	npm run eslint resources/scripts/{flash,lcg-exercises,lcg}.js

lint-csslint:
	npm run csslint resources/css
