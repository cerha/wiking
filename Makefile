.PHONY: translations doc

all: compile translations

compile:
	@echo "Compiling Python libraries from source..."
	@python3 -c "import compileall; compileall.compile_dir('lib')" >/dev/null
	@python3 -O -c "import compileall; compileall.compile_dir('lib')" >/dev/null

translations:
	@make -C translations
extract:
	make -C translations extract

doc:
	lcgmake doc/src doc/html

api-doc:
	PYTHONPATH=lib epydoc -o doc/html/api --name Wiking --inheritance=included --graph classtree wiking
