domains := wiking wiking-help
mo_files := $(shell ls *.po | sed 's/\(.*\)\.\(.*\)\.po/\2\/LC_MESSAGES\/\1.mo/')
mkrules := python ../../lcg/lib/lcg/i18n.py ../lib

all: $(mo_files)

include $(domains:%=%.d)

%.d: $(shell $(mkrules))
	@echo "Updating rules for domain $*."
	@echo -n "$*.pot: " > $@ && $(mkrules) $* >> $@
	@echo "$(wildcard $*.*.po): $*.%.po: $*.pot" >> $@
	@echo "$(filter %/$*.mo,$(mo_files)): %/LC_MESSAGES/$*.mo: $*.%.po %/LC_MESSAGES" >> $@

%/LC_MESSAGES:
	mkdir -p $*/LC_MESSAGES/

%.mo:
	msgfmt -v $< -o $@

%.po:
	msgmerge -q --update $@ $< && touch $@

%.pot:
	xgettext $^ -o $@
