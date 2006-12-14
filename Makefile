SHARE = /usr/local/share
LIB = /usr/local/lib/python2.4/site-packages
CFGFILE = /etc/wiking/config.py
APACHECFG = /etc/apache2/conf.d/wiking

.PHONY: translations doc

doc: doc-en #doc-cs
doc-%:
	lcgmake --language=$* --stylesheet=default.css doc/src doc/html

translations:
	make -C translations

install: translations $(APACHECFG) $(CFGFILE) $(SHARE)/wiking check_deps
	cp -ruv doc resources sql translations $(SHARE)/wiking
	cp -ruv lib/wiking $(LIB)

uninstall:
	rm -rf $(SHARE)/wiking
	rm -rf $(LIB)/wiking
	rm -f $(APACHECFG)

purge: uninstall
	rm -f $(CFGFILE)

config_dir := $(shell dirname $(CFGFILE))

$(CFGFILE): $(config_dir)
	@echo "Writing $(CFGFILE)"
	@echo "import wiking,sys; wiking.cfg.dump_config_template(sys.stdout)"\
	      | python >$(CFGFILE)

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
lcg_version := $(shell echo 'import lcg; print lcg.__version__' | python)
lcg_version_cmp := $(shell echo 'import wiking; print \
	wiking.cmp_versions("$(lcg_version)", $(MIN_LCG_VERSION))' | python)

MIN_PYTIS_VERSION = "0.1.1"
pytis_version := $(shell echo 'import pytis; print pytis.__version__' | python)
pytis_version_cmp := $(shell echo 'import wiking; print \
	wiking.cmp_versions("$(pytis_version)",$(MIN_PYTIS_VERSION))' | python)

check_deps:
	@if [ $(lcg_version_cmp) == -1 ]; then \
	   echo "LCG $(MIN_LCG_VERSION) required," \
		"but $(lcg_version) installed."; fi
	@if [ $(pytis_version_cmp) == -1 ]; then \
	   echo "Pytis $(MIN_PYTIS_VERSION) required," \
		"but $(pytis_version) installed."; fi


version := $(shell echo 'import wiking; print wiking.__version__' | python)
dir := wiking-$(version)
file := wiking-$(version).tar.gz

compile:
	python -c "import compileall; compileall.compile_dir('lib')"
#python -OO -c "import compileall; compileall.compile_dir('lib')"

release: doc compile translations
	@ln -s .. releases/$(dir)
	@if [ -f releases/$(file) ]; then \
	   echo "Removing old file $(file)"; rm releases/$(file); fi
	@echo "Generating $(file)..."
	@(cd releases; tar --exclude "CVS" --exclude "*~" --exclude "#*" \
	     --exclude ".*" --exclude releases --exclude site \
	     --exclude "config.py" --exclude "*.pyo" \
	     -czhf $(file) $(dir))
	@rm releases/$(dir)