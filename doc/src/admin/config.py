import lcg

class Reader(lcg.Reader):
    """Generate documentation for Wiking Configuration."""

    def _title(self):
        return "Wiking Configuration Options"
    
    def _content(self):
        from wiking import cfg
        def descr(option):
            content = []
            doc = option.documentation()
            if doc:
                content.append(lcg.p(doc))
            content.append(lcg.p("*Default value:*", formatted=True))
            content.append(lcg.PreformattedText(option.default_string()))
            return content
        import lcg
        return lcg.Parser().parse(lcg.unindent_docstring(cfg.__doc__)) + \
               [lcg.TableOfContents(title="Available options", depth=1)] + \
               [lcg.Section(title="Option '%s': %s" % (o.name(),o.description()), content=descr(o))
                for o in cfg.options(sort=True) if o.visible()]
