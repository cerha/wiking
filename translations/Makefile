# This Makefile is created according to the LCG's Makefile for translations.
# See the original for comments...

domains := wiking wiking-cms
mo_dir := ../wiking/assets/translations
json_dir := ../wiking/assets/resources/translations
mo_files := $(foreach d, $(domains), $(patsubst $(d).%.po,\
                                       $(mo_dir)/%/LC_MESSAGES/$(d).mo,\
                                       $(wildcard $(d).*.po)))
json_files := $(foreach d, $(domains), $(patsubst $(d).%.po,\
                                       $(json_dir)/$(d).%.po.json,\
                                       $(wildcard $(d).*.po)))
pot_files := $(patsubst %,%.pot,$(domains))

all: $(mo_files) $(json_files)
extract: $(wildcard *.po) $(pot_files) $(mo_files) $(json_files)

ifeq ($(MAKECMDGOALS),extract)

# Get a list of matching source files for given domain (to be used as dependencies).
# This allows avoiding duplication of the filename patterns defined in *.cfg.
define sources
$(shell pybabel extract -F $1.cfg -s .. -o /dev/null 2>&1
  | grep '^extracting messages from '
  | sed 's/^extracting messages from //')
endef

wiking.pot: $(call sources, wiking)
wiking-cms.pot: $(call sources, wiking-cms)
%.pot: %.cfg
	pybabel extract -F $< --add-comments=Translators: -s .. -o $@

$(wildcard wiking.*.po): wiking.%.po: wiking.pot
$(wildcard wiking-cms.*.po): wiking-cms.%.po: wiking-cms.pot
$(wildcard *.po):
	msgmerge -q --backup=none --update $@ $< && touch $@

endif

$(mo_dir)/%/LC_MESSAGES/wiking.mo: wiking.%.po
	@mkdir -p $(dir $@)
	msgfmt -v $< -o $@
$(mo_dir)/%/LC_MESSAGES/wiking-cms.mo: wiking-cms.%.po
	@mkdir -p $(dir $@)
	msgfmt -v $< -o $@

$(json_dir)/%.po.json: %.po
	@mkdir -p $(dir $@)
	pojson $< > $@

clean:
	rm -rf *.pot $(mo_dir)

.PHONY: all extract clean
