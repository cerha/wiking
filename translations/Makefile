
mo_files := $(patsubst wiking.%.po,%/LC_MESSAGES/wiking.mo,$(shell ls *.po)) $(patsubst wiking-cms.%.po,%/LC_MESSAGES/wiking-cms.mo,$(shell ls *.po))
resource_po_files := $(patsubst wiking.%.po,../resources/translations/wiking.%.po,$(shell ls wiking.*.po))

all: $(mo_files) $(resource_po_files)

%/LC_MESSAGES:
	mkdir -p $*/LC_MESSAGES/

%/LC_MESSAGES/wiking.mo: wiking.%.po %/LC_MESSAGES
	msgfmt -v $< -o $@

%/LC_MESSAGES/wiking-cms.mo: wiking-cms.%.po %/LC_MESSAGES
	msgfmt -v $< -o $@

../resources/translations:
	mkdir -p ../resources/translations/

../resources/translations/wiking.%.po: wiking.%.po ../resources/translations
	cp $< $@

wiking.pot: $(shell find ../lib -name "*.py" -not -path "*/cms/*") $(shell find ../resources/scripts -name "*.js" -not -name "wiking-cms.js")
	pybabel extract -F wiking.cfg --add-comments=Translators: -s ../ -o wiking.pot

wiking-cms.pot: $(shell find ../lib/wiking/cms -name "*.py") ../resources/scripts/wiking-cms.js
	pybabel extract -F wiking-cms.cfg --add-comments=Translators: -s ../ -o wiking-cms.pot

$(shell ls wiking.*.po): wiking.%.po: wiking.pot
	msgmerge -q --backup=none --update $@ $< && touch $@

$(shell ls wiking-cms.*.po): wiking-cms.%.po: wiking-cms.pot
	msgmerge -q --backup=none --update $@ $< && touch $@

clean:
	rm -f *.d *.pot
	rm -rf ../resources/translations/
