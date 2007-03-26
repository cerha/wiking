domains := wiking wiking-help
mo_files := $(shell ls *.po | sed 's/\(.*\)\.\(.*\)\.po/\2\/LC_MESSAGES\/\1.mo/')
src_files := python -c 'import lcg, sys; print " ".join(lcg.source_files_by_domain("../lib", domain=len(sys.argv) == 2 and sys.argv[1] or None))'

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
	xgettext $^ -o $@
