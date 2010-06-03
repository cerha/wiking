# Edit the paths below to suit your needs.
prefix = /usr/local
sysconfdir = /etc
datadir = /var/lib
share = $(prefix)/share
confdir = $(sysconfdir)/wiking
libdir = $(prefix)/lib/python%d.%d/site-packages
cfgfile = $(confdir)/config.py
storage = $(datadir)/wiking/
webuser = www-data

lib := $(shell python -c 'import sys; print "$(libdir)".find("%d") != -1 and \
	                 "$(libdir)" % sys.version_info[:2] or "$(libdir)"')

.PHONY: translations doc

all: check compile translations

check: check-lib check-user

check-lib:
	@python -c "import sys; '$(lib)' not in sys.path and sys.exit(1)" || \
           echo 'WARNING: $(lib) not in Python path!'

check-user:
	@if [ ~$(webuser) = '~$(webuser)' ]; then \
	   echo 'Error: $(webuser) is not a valid user!' && exit 1; fi

compile:
	@echo "Compiling Python libraries from source..."
	@python -c "import compileall; compileall.compile_dir('lib')" >/dev/null
#python -O -c "import compileall; compileall.compile_dir('lib')"

translations:
	@make -C translations

doc:
	lcgmake doc/src doc/html

api-doc:
	PYTHONPATH=lib epydoc -o doc/html/api --name Wiking --inheritance=included --graph classtree wiking

install-links: link-lib link-share $(cfgfile) $(storage)

install: $(share)/wiking copy-files $(cfgfile) $(storage)

uninstall:
	rm -rf $(share)/wiking
	rm -rf $(lib)/wiking

purge: uninstall
	rm -f $(cfgfile)
	rm -rf $(storage)

copy-files:
	cp -ruv doc resources sql translations $(share)/wiking
	cp -ruv lib/wiking $(lib)

link-lib:
	@if [ -d $(lib)/wiking ]; then echo "$(lib)/wiking already exists!"; \
	else echo "Linking wiking libraries to $(lib)/wiking"; \
	ln -s $(CURDIR)/lib/wiking $(lib)/wiking; fi

link-share: link-share-doc link-share-translations link-share-resources link-share-sql

link-share-%: $(share)/wiking
	@if [ -d $(share)/wiking/$* ]; then echo "$(share)/wiking/$* already exists!"; \
	else echo "Linking wiking $* to $(share)/wiking"; \
	ln -s $(CURDIR)/$* $(share)/wiking; fi

$(cfgfile): $(confdir)
	@echo "Writing $(cfgfile)"
	@echo "import wiking,sys; wiking.cfg.dump_config_template(sys.stdout)" \
	| PYTHONPATH=$(lib):$$PYTHONPATH python >$(cfgfile)

$(confdir):
	mkdir $(confdir)

$(share)/wiking:
	mkdir $(share)/wiking

$(storage):
	mkdir $(storage)
	chgrp $(webuser) $(storage)
	chmod g+w $(storage)
