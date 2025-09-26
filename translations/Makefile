# This Makefile is created according to the LCG's Makefile for translations.
# See the original for comments...

mo_dir := ../wiking/translations
mo_files := $(foreach d, wiking wiking-cms, \
              $(patsubst $(d).%.po,$(mo_dir)/%/LC_MESSAGES/$(d).mo, \
              $(wildcard $(d).*.po)))
resource_po_files := $(patsubst %.po,../resources/translations/%.po, $(wildcard *.po))

all: $(mo_files) $(resource_po_files)
extract: $(wildcard *.po) $(mo_files)

ifeq ($(MAKECMDGOALS),extract)

wiking.pot: $(shell find ../lib -name "*.py" -not -path "*/cms/*") \
	    $(shell find ../resources/scripts -name "*.js" -not -name "wiking-cms.js")
wiking-cms.pot: $(shell find ../lib/wiking/cms -name "*.py") ../resources/scripts/wiking-cms.js
$(wildcard *.pot):
	pybabel extract -F $(patsubst %.pot,%.cfg,$@) --add-comments=Translators: -s ../ -o $@

$(wildcard wiking.*.po): wiking.%.po: wiking.pot
$(wildcard wiking-cms.*.po): wiking-cms.%.po: wiking-cms.pot
$(wildcard *.po):
	msgmerge -q --backup=none --update $@ $< && touch $@

endif

$(mo_dir)/%/LC_MESSAGES:
	mkdir -p $(mo_dir)/$*/LC_MESSAGES/
$(mo_dir)/%/LC_MESSAGES/wiking.mo: wiking.%.po $(mo_dir)/%/LC_MESSAGES
	msgfmt -v $< -o $@
$(mo_dir)/%/LC_MESSAGES/wiking-cms.mo: wiking-cms.%.po $(mo_dir)/%/LC_MESSAGES
	msgfmt -v $< -o $@

../resources/translations:
	mkdir -p ../resources/translations/
../resources/translations/%.po: %.po ../resources/translations
	cp $< $@

clean:
	rm -f *.pot
	rm -rf $(mo_dir)
