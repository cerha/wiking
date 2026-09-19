# This Makefile is created according to the LCG's Makefile for translations.
# See the original for comments...

# Don't leave a truncated output file behind when a recipe fails.  The shell
# redirections used below create the target before the command which should
# produce its contents even runs, so a failure would result in an empty file
# which make would consider up to date on the next run.
.DELETE_ON_ERROR:

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

# Babel's default keywords include 'gettext', which would extract the domain
# name from JavaScript 'lcg.gettext(domain)' calls as a translatable string, so
# we define the recognized keywords explicitly.
keywords := --no-default-keywords -k _ -k N_ -k ngettext:1,2 -k pgettext:1c,2

# Get a list of matching source files for given domain (to be used as dependencies).
# This allows avoiding duplication of the filename patterns defined in *.cfg.
define sources
$(shell pybabel extract -F $1.cfg -s .. -o /dev/null 2>&1
  | grep '^extracting messages from '
  | sed -e 's/^extracting messages from //' -e 's/ (.*)$$//')
endef

wiking.pot: $(call sources, wiking)
wiking-cms.pot: $(call sources, wiking-cms)
%.pot: %.cfg
	pybabel extract -F $< --add-comments=Translators: $(keywords) -s .. -o $@

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

# The JSON catalogs are embedded in each HTML page which uses the JavaScript
# code of given domain (see LCG's HtmlExporter._head), so they only contain the
# messages which actually appear in the JavaScript sources.
$(json_dir)/%.po.json: %.po
	@mkdir -p $(dir $@)
	msggrep -N '../javascript/*' $< > $@.po
	pojson $@.po > $@ && rm $@.po

clean:
	rm -rf *.pot $(mo_dir)

.PHONY: all extract clean
