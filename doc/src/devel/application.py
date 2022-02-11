import collections
import lcg
import inspect
import re


class Reader(lcg.Reader):
    """Generate Wiking API documentation out of Python docstrings."""

    _ARG_REGEX = re.compile("^  (\w+) -- ", re.MULTILINE)

    def _title(self):
        return "Wiking Application API"

    def _variants(self):
        return ('en',)

    def _content(self, lang):
        from wiking import Application
        parser = lcg.Parser()
        # modules = [(k, v) for k, v in wiking.application.__dict__.items()
        #            if type(v) == type(Module) and issubclass(v, Module) \
        #            and v.__module__ == 'wiking.application']
        # modules.sort()
        content = parser.parse(Application.__doc__) + \
            [lcg.TableOfContents(title="Application methods:", depth=1)]
        for name, method in sorted(Application.__dict__.items()):
            if name.startswith('_') or name.startswith('action_') \
                    or not callable(method) or not method.__doc__:
                continue
            args, varargs, varkw, defaults = inspect.getargspec(method)
            title = name + inspect.formatargspec(args[1:], varargs, varkw, defaults)
            doc = self._ARG_REGEX.sub(lambda m: ":" + m.group(1) + ": ", inspect.getdoc(method))
            content.append(lcg.Section(title=title, content=parser.parse(doc), id=name))
        return dict(content=content)
