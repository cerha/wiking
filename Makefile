# Edit the paths below to suit your needs.
SHARE = /usr/local/share
LIB = /usr/local/lib/python%d.%d/site-packages
CFGFILE = /etc/wiking/config.py
APACHECFG = /etc/apache2/conf.d/wiking


lib := $(shell python -c 'import sys; print "$(LIB)".find("%d") != -1 and \
	                 "$(LIB)" % sys.version_info[:2] or "$(LIB)"')

.PHONY: translations doc

doc:
	lcgmake doc/src doc/html

translations:
	make -C translations

install: check-lib $(SHARE)/wiking copy-files $(APACHECFG) $(CFGFILE)

check-lib:
	@echo -e "import sys\nif '$(lib)' not in sys.path: sys.exit(1)" \
	| python || echo 'WARNING: $(lib) not in Python path!'

copy-files:
	cp -ruv doc resources sql translations $(SHARE)/wiking
	cp -ruv lib/wiking $(lib)

uninstall:
	rm -rf $(SHARE)/wiking
	rm -rf $(lib)/wiking
	rm -f $(APACHECFG)

purge: uninstall
	rm -f $(CFGFILE)

cvs-install: check-lib compile translations link-lib link-share $(APACHECFG) $(CFGFILE)

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
	| PYTHONPATH=$(lib) python >$(CFGFILE)

$(config_dir):
	mkdir $(config_dir)

$(SHARE)/wiking:
	mkdir $(SHARE)/wiking

$(APACHECFG):
	@echo "Writing $(APACHECFG)"
	@echo "<Directory $(SHARE)/wiking>" > $(APACHECFG)
	@echo "    AddHandler python-program .py" >> $(APACHECFG)
	@echo "    PythonHandler wiking.handler" >> $(APACHECFG)
	@echo "</Directory>" >> $(APACHECFG)


MIN_LCG_VERSION = "0.3.4"
lcg_version = $(shell echo 'import lcg; print lcg.__version__' | python)
lcg_version_cmp = $(shell echo 'import wiking; print \
	wiking.cmp_versions("$(lcg_version)", $(MIN_LCG_VERSION))' | python)

MIN_PYTIS_VERSION = "0.1.0"
pytis_version = $(shell echo 'import pytis; print pytis.__version__' | python)
pytis_version_cmp = $(shell echo 'import wiking; print \
	wiking.cmp_versions("$(pytis_version)",$(MIN_PYTIS_VERSION))' | python)

check_deps:
	@if [ $(lcg_version_cmp) == -1 ]; then \
	   echo "LCG $(MIN_LCG_VERSION) required," \
		"but $(lcg_version) installed."; fi
	@if [ $(pytis_version_cmp) == -1 ]; then \
	   echo "Pytis $(MIN_PYTIS_VERSION) required," \
		"but $(pytis_version) installed."; fi


version = $(shell echo 'import wiking; print wiking.__version__' | python)
dir = wiking-$(version)
file = wiking-$(version).tar.gz

compile:
	@echo "Compiling Python libraries from source..."
	@python -c "import compileall; compileall.compile_dir('lib')" >/dev/null
#python -OO -c "import compileall; compileall.compile_dir('lib')"

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