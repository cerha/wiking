SHARE = /usr/local/share
LIB = /usr/local/lib/python2.4/site-packages
CFGFILE = /etc/wiking/config.py
APACHECFG = /etc/apache2/conf.d/wiking

SHARE = /tmp/pokus/share
LIB = /tmp/pokus/lib
APACHECFG = /tmp/pokus/etc/apache2/conf.d/wiking
CFGFILE = /tmp/pokus/etc/wiking/config.py

.PHONY: translations

translations:
	make -C translations

install: check_deps translations $(APACHECFG) $(CFGFILE) $(SHARE)/wiking
	cp -ruv doc resources sql translations $(SHARE)/wiking
	cp -ruv lib/wiking $(LIB)

uninstall:
	rm -rf $(SHARE)/wiking
	rm -rf $(LIB)/wiking
	rm -f $(APACHECFG)

purge: uninstall
	rm -f $(CFGFILE)

MIN_LCG_VERSION = "0.3.4"
lcg_version := $(shell echo 'import lcg; print lcg.__version__' | python)
lcg_version_cmp := $(shell echo 'import wiking; print \
	wiking.cmp_versions("$(lcg_version)", $(MIN_LCG_VERSION))' | python)

check_deps:
	@if [ $(lcg_version_cmp) == -1 ]; then \
	   echo "LCG $(MIN_LCG_VERSION) required," \
		"but $(lcg_version) installed."; exit 1; fi

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


version := $(shell echo 'import wiking; print wiking.__version__' | python)
dir := wiking-$(version)
file := wiking-$(version).tar.gz

release: translations
	@ln -s .. releases/$(dir)
	@if [ -e releases/$(file) ]; then \
	   echo "Removing old file $(file)"; rm releases/$(file); fi
	@echo "Generating $(file)..."
	@(cd releases; tar --exclude "CVS" --exclude "*~" --exclude "#*" \
	     --exclude "*.pyc" --exclude "*.pyo" \
	     --exclude "config.py" --exclude releases --exclude site \
	     -czhf $(file) $(dir))
	@rm releases/$(dir)