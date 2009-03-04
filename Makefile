# Edit the paths below to suit your needs.
prefix = /usr/local
sysconfdir = /etc
datadir = /var/lib
SHARE = $(prefix)/share
LIB = $(prefix)/lib/python%d.%d/site-packages
CFGFILE = $(sysconfdir)/wiking/config.py
STORAGE = $(datadir)/wiking/
APACHE_USER = www-data

lib := $(shell python -c 'import sys; print "$(LIB)".find("%d") != -1 and \
	                 "$(LIB)" % sys.version_info[:2] or "$(LIB)"')

.PHONY: translations doc

all: check-lib check-user compile translations

check-lib:
	@python -c "import sys; '$(lib)' not in sys.path and sys.exit(1)" || \
           echo 'WARNING: $(lib) not in Python path!'

check-user:
	@if [ ~$(APACHE_USER) == '~$(APACHE_USER)' ]; then \
	   echo 'Error: $(APACHE_USER) is not a valid user!' && exit 1; fi

compile:
	@echo "Compiling Python libraries from source..."
	@python -c "import compileall; compileall.compile_dir('lib')" >/dev/null
#python -O -c "import compileall; compileall.compile_dir('lib')"

translations:
	@make -C translations

doc:
	lcgmake doc/src doc/html

install: $(SHARE)/wiking copy-files $(CFGFILE) $(STORAGE)

cvs-install: link-lib link-share $(CFGFILE) $(STORAGE)

uninstall:
	rm -rf $(SHARE)/wiking
	rm -rf $(lib)/wiking

purge: uninstall
	rm -f $(CFGFILE)
	rm -rf $(STORAGE)

copy-files:
	cp -ruv doc resources sql translations $(SHARE)/wiking
	cp -ruv lib/wiking $(lib)

link-lib:
	@if [ -d $(lib)/wiking ]; then echo "$(lib)/wiking already exists!"; \
	else echo "Linking wiking libraries to $(lib)/wiking"; \
	ln -s $(CURDIR)/lib/wiking $(lib)/wiking; fi

link-share: link-share-doc link-share-translations link-share-resources link-share-sql

link-share-%: $(SHARE)/wiking
	@if [ -d $(SHARE)/wiking/$* ]; then echo "$(SHARE)/wiking/$* already exists!"; \
	else echo "Linking wiking $* to $(SHARE)/wiking"; \
	ln -s $(CURDIR)/$* $(SHARE)/wiking; fi

cvs-update: do-cvs-update compile translations

do-cvs-update:
	@echo "All local modifications will be lost and owerwritten with clean repository copies!"
	@echo -n "Press Enter to continue or Ctrl-C to abort: "
	@read || exit 1
	cvs update -dPC

config_dir = $(shell dirname $(CFGFILE))

$(CFGFILE): $(config_dir)
	@echo "Writing $(CFGFILE)"
	@echo "import wiking,sys; wiking.cfg.dump_config_template(sys.stdout)" \
	| PYTHONPATH=$(lib):$$PYTHONPATH python >$(CFGFILE)

$(config_dir):
	mkdir $(config_dir)

$(SHARE)/wiking:
	mkdir $(SHARE)/wiking

$(STORAGE):
	mkdir $(STORAGE)
	chgrp $(APACHE_USER) $(STORAGE)
	chmod g+w $(STORAGE)

version = $(shell echo 'import wiking; print wiking.__version__' | python)
dir = wiking-$(version)
file = wiking-$(version).tar.gz

release: doc compile translations
	@ln -s .. releases/$(dir)
	@if [ -f releases/$(file) ]; then \
	   echo "Removing old file $(file)"; rm releases/$(file); fi
	@echo "Generating $(file)..."
	@(cd releases; tar --exclude "CVS" --exclude "*~" --exclude "#*" \
	     --exclude ".*" --exclude releases --exclude site \
	     --exclude "config.py*" --exclude "*.pyo" --exclude upload.sh \
	     -czhf $(file) $(dir))
	@rm releases/$(dir)