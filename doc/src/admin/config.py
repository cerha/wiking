import lcg


class Reader(lcg.Reader):
    """Generate documentation for Wiking Configuration."""

    def _title(self):
        return "Wiking Configuration Options"

    def _variants(self):
        return ('en',)

    def _content(self, lang):
        import wiking
        import wiking.cms

        def descr(option):
            content = [lcg.em(option.description())]
            doc = option.documentation()
            if doc:
                content.append(lcg.p(doc))
            content.append(lcg.p("*Default value:*", formatted=True))
            content.append(lcg.PreformattedText(option.default_string()))
            return content
        import lcg
        # Initial text is taken from configuration module docstring.
        intro = lcg.Parser().parse(lcg.unindent_docstring(wiking.cfg.__doc__))
        # Construct sections according to module and subsections with the config options
        sections = [
            lcg.Section(title=title, content=[
                lcg.Section(title="Option '%s'" % o.name(),
                            id=o.name(), descr=o.description(),
                            content=descr(o))
                for o in cfg.options(sort=True) if o.visible()])
            for title, cfg in (("Wiking Configuration Options", wiking.cfg),
                               ("Wiking CMS Configuration Options", wiking.cms.cfg))
        ]
        overview = [
            lcg.Section(title=section.title() + " Overview", content=lcg.ul(
                lcg.coerce((lcg.link(s, s.id()), ": ", s.descr()))
                for s in section.sections()))
            for section in sections
        ]
        return dict(content=intro + overview + sections)
