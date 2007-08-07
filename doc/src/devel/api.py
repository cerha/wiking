import lcg

class Reader(lcg.Reader):

    def __init__(self, id, **kwargs):
        super(Reader, self).__init__(id, title="Wiking API", **kwargs)
        
    def _create_content(self):
        import wiking.api
        parser = lcg.Parser()
        return [lcg.Section(title=name, content=parser.parse(module.__doc__ or "Undocumented"))
                for name, module in wiking.api.__dict__.items()
                if type(module) == type(wiking.api.Module) \
                and issubclass(module, wiking.api.Module) \
                and module.__module__ == 'wiking.api']

    
