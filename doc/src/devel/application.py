import lcg

class Reader(lcg.Reader):
    """Generate Wiking API documentation out of Python docstrings."""
    
    _DEFAULTS = {'title': "Wiking Application API"}
        
    def _create_content(self):
        from wiking import Application
        parser = lcg.Parser()
        #modules = [(k, v) for k, v in wiking.application.__dict__.items()
        #           if type(v) == type(Module) and issubclass(v, Module) \
        #           and v.__module__ == 'wiking.application']
        #modules.sort()
        content = parser.parse(Application.__doc__) + \
                  [lcg.TableOfContents(title="Application methods:")] + \
                  [lcg.Section(title=name+'()', content=parser.parse(attr.__doc__))
                   for name, attr in Application.__dict__.items()
                   if not name.startswith('_') and not name.startswith('action_') \
                   and callable(attr) and attr.__doc__]
        return content
