import lcg

class Reader(lcg.Reader):
    """Generate Wiking API documentation out of Python docstrings."""
    
    def __init__(self, id, **kwargs):
        super(Reader, self).__init__(id, title="Wiking API Modules", **kwargs)
        
    def _create_content(self):
        import wiking.api
        from wiking import Module
        parser = lcg.Parser()
        result = parser.parse(wiking.api.__doc__) + [lcg.TableOfContents(title="Core modules:")]
        modules = [(k, v) for k, v in wiking.api.__dict__.items()
                   if type(v) == type(Module) and issubclass(v, Module) \
                   and v.__module__ == 'wiking.api']
        modules.sort()
        for name, module in modules:
                content = parser.parse(module.__doc__ or "Undocumented")
                methods = [v for k, v in module.__dict__.items()
                           if not (k.startswith('_') or k.startswith('action_')) and callable(v)]
                if methods:
                    dl = [(m.__name__+'()', parser.parse(m.__doc__ or "Undocumented"))
                          for m in methods]
                    content.append(lcg.p("*Methods:*", formatted=True))
                    content.append(lcg.dl(dl, formatted=True))
                result.append(lcg.Section(title=name, content=content))
        return result
