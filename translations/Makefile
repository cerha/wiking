domains := wiking wiking-cms
mo_files := $(shell ls *.po | sed 's/\(.*\)\.\(.*\)\.po/\2\/LC_MESSAGES\/\1.mo/')
src_files := python -m lcg/i18n ../lib

all: $(mo_files)

include $(domains:%=%.d)

%.d: $(shell $(src_files))
	@echo "Updating rules for domain $*."
	@echo -n "$*.pot: " > $@ && $(src_files) $* >> $@
	@echo "$(wildcard $*.*.po): $*.%.po: $*.pot" >> $@
	@echo "$(filter %/$*.mo,$(mo_files)): %/LC_MESSAGES/$*.mo: $*.%.po %/LC_MESSAGES" >> $@

%/LC_MESSAGES:
	mkdir -p $*/LC_MESSAGES/

%.mo:
	msgfmt -v $< -o $@

%.po:
	msgmerge -q --update $@ $< && touch $@

%.pot:
	xgettext $^ --from-code=utf-8 -o $@

clean:
	rm -f *.d *.pot

.PHONY: all clean
