
mo_files := $(patsubst wiking.%.po,%/LC_MESSAGES/wiking.mo,$(shell ls *.po)) $(patsubst wiking-cms.%.po,%/LC_MESSAGES/wiking-cms.mo,$(shell ls *.po))
resource_po_files := $(patsubst wiking.%.po,../resources/translation/wiking.%.po,$(shell ls wiking.*.po))

all: $(mo_files) $(resource_po_files)

%/LC_MESSAGES:
	mkdir -p $*/LC_MESSAGES/

%/LC_MESSAGES/wiking.mo: wiking.%.po %/LC_MESSAGES
	msgfmt -v $< -o $@

%/LC_MESSAGES/wiking-cms.mo: wiking-cms.%.po %/LC_MESSAGES
	msgfmt -v $< -o $@

../resources/translation:
	mkdir -p ../resources/translation/

../resources/translation/wiking.%.po: wiking.%.po ../resources/translation
	cp $< $@

wiking.pot:
	pybabel extract -F wiking.cfg --add-comments=Translators: -s ../ -o wiking.pot

wiking-cms.pot:
	pybabel extract -F wiking-cms.cfg --add-comments=Translators: -s ../ -o wiking-cms.pot

$(shell ls wiking.*.po): wiking.%.po: wiking.pot
	msgmerge -q --backup=none --update $@ $< && touch $@

$(shell ls wiking-cms.*.po): wiking-cms.%.po: wiking-cms.pot
	msgmerge -q --backup=none --update $@ $< && touch $@

clean:
	rm -f *.d *.pot
	rm -rf ../resources/translation/
