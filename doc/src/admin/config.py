import lcg

class Reader(lcg.Reader):
    """Generate documentation for Wiking Configuration."""

    def _title(self):
        return "Wiking Configuration Options"

    def _content(self):
        import wiking, wiking.cms
        def descr(option):
            content = []
            doc = option.documentation()
            if doc:
                content.append(lcg.p(doc))
            content.append(lcg.p("*Default value:*", formatted=True))
            content.append(lcg.PreformattedText(option.default_string()))
            return content
        import lcg
        # Construct sections according to module and subsections with the config options
        return lcg.Parser().parse(lcg.unindent_docstring(wiking.cfg.__doc__)) + \
            [lcg.TableOfContents(title="Available options in Wiking", depth=2)] + \
            [lcg.Section(title=title,
                         content=[lcg.Section(title="Option '%s': %s" % (o.name(),o.description()),
                                              anchor=o.name(),
                                              content=descr(o))
                                  for o in cfg.options(sort=True) if o.visible()])
             for title, cfg in [("Wiking", wiking.cfg), ("Wiking CMS", wiking.cms.cfg)]]
