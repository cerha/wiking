# Copyright (C) 2006, 2007 Brailcom, o.p.s.
# Author: Tomas Cerha.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from wiking import *

import time, re, os

DBG = pytis.util.DEBUG
EVT = pytis.util.EVENT
OPR = pytis.util.OPERATIONAL
log = pytis.util.StreamLogger(sys.stderr).log

_ = lcg.TranslatableTextFactory('wiking')

from lcg import _html
concat = lcg.concat

def timeit(func, *args, **kwargs):
    """Measure the function execution time.

    Invokes the function 'func' with given arguments and returns the triple
    (function result, processor time, wall time), both times in microseconds.

    """
    t1, t2 = time.clock(), time.time()
    result = func(*args, **kwargs)
    return result,  time.clock() - t1, time.time() - t2

def get_module(name):
    """Get the module class by name.
    
    This function replaces Pytis resolver in the web environment and is also
    used by the Pytis resolver in the stand-alone pytis application
    environment.
    
    """
    try:
        from mod_python.apache import import_module
        modules = import_module('wiking.modules', log=True)
    except ImportError:
        import wiking.modules as modules
    return getattr(modules, name)

def rss(title, url, items, descr, lang=None, webmaster=None):
    import wiking
    result = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>%s</title>
    <link>%s</link>
    <description>%s</description>''' % (title, url, descr or '') + \
    (lang and '''
    <language>%s</language>''' % lang or '') + (webmaster and '''
    <webMaster>%s</webMaster>''' % webmaster or '') + '''
    <generator>Wiking %s</generator>''' % wiking.__version__ + '''
    <ttl>60</ttl>
    %s
  </channel>
</rss>''' % '\n    '.join(['''<item>
       <title>%s</title>
       <guid>%s</guid>
       <link>%s</link>''' % (title, url, url) + (descr and '''
       <description>%s</description>''' % descr or '') + (date and '''
       <pubDate>%s</pubDate>''' % date or '') + (author and '''
       <author>%s</author>''' % author or '') + '''
    </item>''' for title, url, descr, date, author in items])
    return result

def send_mail (sender, addr, subject, text, html, smtp_server='localhost'):
    """Send a mime e-mail message with text and HTML version."""
    import MimeWriter
    import mimetools
    from cStringIO import StringIO
    out = StringIO() # output buffer for our message 
    htmlin = StringIO(html)
    txtin = StringIO(text)
    writer = MimeWriter.MimeWriter(out)
    # Set up message headers.
    writer.addheader("From", sender)
    writer.addheader("To", addr)
    writer.addheader("Subject", subject)
    writer.addheader("Date", time.strftime("%a, %d %b %Y %H:%M:%S",
    writer.addheader("MIME-Version", "1.0")
    # Start the multipart section (multipart/alternative seems to work better
    # on some MUAs than multipart/mixed).
    writer.startmultipartbody("alternative")
    writer.flushheaders()
    # The plain text section.
    subpart = writer.nextpart()
    subpart.addheader("Content-Transfer-Encoding", "quoted-printable")
    pout = subpart.startbody("text/plain", [("charset", 'utf-8')])
    mimetools.encode(txtin, pout, 'quoted-printable')
    txtin.close()
    # The html section.
    subpart = writer.nextpart()
    subpart.addheader("Content-Transfer-Encoding", "quoted-printable")
    # Returns a file-like object we can write to.
    pout = subpart.startbody("text/html", [("charset", 'utf-8')])
    mimetools.encode(htmlin, pout, 'quoted-printable')
    htmlin.close()
    # Close the writer and send the message.
    writer.lastpart()
    import smtplib
    server = smtplib.SMTP(smtp_server)
    try:
        server.sendmail(sender, addr, out.getvalue())
    finally:
        out.close()
        server.quit()


def cmp_versions(v1, v2):
    """Compare version strings, such as '0.3.1' and return the result.

    The returned value is -1, 0 or 1 such as for the builtin 'cmp()' function.
    
    """
    v1a = [int(v) for v in v1.split('.')]
    v2a = [int(v) for v in v2.split('.')]
    for (n1, n2) in zip(v1a, v2a):
        c = cmp(n1, n2)
        if c != 0:
            return c
    return 0


# ============================================================================

class HttpError(Exception)
    """Exception representing en HTTP error.

    Raising this exception will be handled by returning the appropriate HTTP
    error code to the user and displaying the error message within the content
    part of the page.  The overall page layout, including navigation and other
    static page content is displayed as on any other page.  These errors are
    not logged neither emailed, since they are usually caused by an invalid
    request.

    This class is abstract.  The error code and error message must be defined
    by a derived class.  The error message may also require certain constructor
    arguments passed when raising the error.
    
    """
    
    ERROR_CODE = None
    
    def title(self):
        name = " ".join(pp.split_camel_case(self.__class__.__name__))
        return _("Error %d: %s", self.ERROR_CODE, name)
    
    def msg(self, req):
        pass


class NotFound(HttpError):
    """Error indicating invalid request target."""
    ERROR_CODE = 404
    
    def msg(self, req):
        msg = (_("The item '%s' does not exist on this server or cannot be "
                 "served.", req.uri),
               _("If you are sure the web address is correct, "
                 "but are encountering this error, please send "
                 "an e-mail to the webmaster."),
               _("Thank you"))
        return lcg.concat([lcg.concat("<p>", p, "</p>\n\n") for p in msg])

    
class NotAcceptable(HttpError):
    """Error indicating unavailability of the resource in requested language."""
    ERROR_CODE = 406
    
    def msg(self, req):
        from lcg import _html
        prefered = [lcg.language_name(l) for l in req.prefered_languages()]
        msg = (_("The resource '%s' is not available in either of "
                 "the requested languages.", req.uri),
               lcg.concat(_("Your browser is configured to accept only the "
                            "following languages:"), ' ',
                          lcg.concat(prefered, separator=', ')))
        if self.args:
            available = [_html.link(lcg.language_name(l),
                                    "%s?setlang=%s" % (req.uri, l))
                         for l in self.args[0]]
            msg += (lcg.concat(_("The available variants are:"), ' ',
                               lcg.concat(available, separator=', ')),
                    _("If you want to accept other languages permanently, "
                      "setup the language preferences in your browser "
                      "or contact your system administrator."))
        return lcg.concat([lcg.concat("<p>", p, "</p>\n\n") for p in msg])


class Unauthorized(HttpError):
    """Error indicating that authentication is required for the resource."""
    ERROR_CODE = 401

    def title(self):
        return _("Authentication required")


class FileUpload(object):
    """An abstract representation of uploaded file fields."""

    def file(self):
        """Return a file-like object from which the data may be read."""
        
    def filename(self):
        """Return the original filename as a string"""
        
    def type(self):
        """Return the mime type provided byt he UA as a string"""

# ============================================================================

class MenuItem(object):
    """Menu item representation to be passed to 'Document.mknode()'."""
    def __init__(self, id, title):
        self._id = id
        self._title = title
    def id(self):
        return self._id
    def title(self):
        return self._title


class Panel(object):
    """Panel representation to be passed to 'Document.mknode()'."""
    def __init__(self, id, title, content):
        self._id = id
        self._title = title
        self._content = content
    def id(self):
        return self._id
    def title(self):
        return self._title
    def content(self):
        return self._content


class Document(object):
    """Independent Wiking document representation.

    This allows us to initialize document data without actually creating the
    'lcg.ContentNode' instance.  The instance can be created later using the
    'mknode()' method (passing it the remaining arguments required by
    'lcg.ContentNone' constructor.

    """
    
    def __init__(self, title, content, descr=None, lang=None, variants=(),
                 sec_lang='en'):
        self._title = title
        if isinstance(content, (list, tuple)):
            content = lcg.SectionContainer([c for c in content if c],
                                           toc_depth=0)
        self._content = content
        self._descr = descr
        self._lang = lang
        self._variants = variants
        self._sec_lang = sec_lang

    def lang(self):
        return self._lang
    
    def mknode(self, id, config, menu, panels, stylesheets):
        return WikingNode(id, config, title=self._title, content=self._content,
                          lang=self._lang, variants=self._variants or (),
                          descr=self._descr, menu=menu, panels=panels,
                          stylesheets=stylesheets,
                          secondary_language=self._sec_lang)

    
# ============================================================================
# Classes derived from LCG components
# ============================================================================

class WikingNode(lcg.ContentNode):
    
    def __init__(self, id, config, menu=(), lang=None, variants=(), panels=(),
                 stylesheets=(), **kwargs):
        self._config = config
        self._menu = menu
        self._panels = panels
        self._stylesheets = stylesheets
        for panel in panels:
            panel.content().set_parent(self)
        super(WikingNode, self).__init__(None, id, language=lang,
                                         language_variants=variants, **kwargs)
        
    def config(self):
        return self._config
    
    def menu(self):
        return self._menu
    
    def panels(self):
        return self._panels
    
    def stylesheets(self):
        return self._stylesheets
               
    
class ActionMenu(lcg.Content):
    
    def __init__(self, uri, actions, data=None, row=None):
        super(ActionMenu, self).__init__()
        assert isinstance(uri, str), uri
        assert isinstance(actions, (tuple, list)), actions
        assert data is None or isinstance(data, pytis.data.Data), data
        assert row is None or isinstance(row, pp.PresentedRow), row
        self._uri = uri
        self._data = data
        self._row = row
        self._actions = actions

    def _export_item(self, action):
        if action.context() is not None:
            key = dict([(c.id(), self._row[c.id()].export())
                        for c in self._data.key()])
        else:
            key = {}
        enabled = action.enabled()
        if callable(enabled):
            enabled = enabled(self._row)
        if enabled:            
            target = _html.uri(self._uri, action=action.name(), **key)
            cls = None
        else:
            target = None
            cls = 'inactive'
        return _html.link(action.title(), target, cls=cls)
        
    def export(self, exporter):
        # Only Wiking's Actions are considered, not `pytis.presentation.Action'.
        items = concat([self._export_item(a) for a in self._actions
                        if isinstance(a, Action)],
                       separator=_html.span(" |\n", cls="hidden"))
        return _html.p(concat(_("Actions:"), items, separator="\n"),
                       cls="actions")
          
class PanelItem(lcg.Content):

    def __init__(self, fields):
        super(PanelItem, self).__init__()
        self._fields = fields
        
    def export(self, exporter):
        items = [_html.span(uri and _html.link(value, uri) or value,
                            cls="panel-field-"+id)
                 for id, value, uri in self._fields]
        return _html.div(items, cls="item")


class CustomViewSpec(object):
    def __init__(self, divs, anchor=None, labeled_fields=(),
                 formatted_fields=(), custom_list=False, cls='view-item'):
        self._divs = divs
        self._anchor = anchor
        self._labeled_fields = labeled_fields
        self._formated_fields = formatted_fields
        self._custom_list = custom_list
        self._cls = cls
    def divs(self):
        return self._divs
    def anchor(self):
        return self._anchor
    def formatted_fields(self):
        return self._formated_fields
    def labeled_fields(self):
        return self._labeled_fields
    def custom_list(self):
        return self._custom_list
    def cls(self):
        return self._cls

    
class _CustomView(object):
    """Base class for custom view classes."""
    def __init__(self, custom_spec=None):
        self._custom_spec = custom_spec
        if custom_spec:
            self._override()
        
    def _export_structured_text(self, text, exporter):
        content = lcg.Container(lcg.Parser().parse(text))
        content.set_parent(self.parent())
        return content.export(exporter)
    
    def _export_row_custom(self, exporter, row):
        spec = self._custom_spec
        parts = []
        formatted = spec.formatted_fields()
        labeled = spec.labeled_fields()
        for id in spec.divs():
            content = self._row[id].export()
            if id in formatted:
                content = self._export_structured_text(content, exporter)
            # We can't use join to preserve TranslatableText instances.
            if id in labeled:
                content = self._view.field(id).label() + ": " + content
            if not parts and spec.anchor(): # Make the first part a link target.
                name = spec.anchor() % row[self._data.key()[0].id()].export()
                content = _html.link(content, None, name=name)
                cls = 'item-heading'
            else:
                cls = 'item-body'
            parts.append(_html.div(content, cls=cls+' '+id))
        return _html.div(parts, cls=spec.cls())

    
class RecordView(pw.ShowForm, _CustomView):
    """Content element class showing one record of a module."""
    
    def _override(self):
        self.export = lambda e: self._export_row_custom(e, self._row)
        
    
class ListView(pw.BrowseForm, _CustomView):
    """Content element class showing list of records of a module."""

    def _override(self):
        if self._custom_spec.custom_list():
            self._wrap_exported_rows = self._wrap_exported_rows_custom
            self._export_row = self._export_row_custom
        
    def _wrap_exported_rows_custom(self, rows):
        return _html.div(rows, cls="list-view")

    
class Message(lcg.TextContent):
    _CLASS = "message"
    
    def export(self, exporter):
        return _html.p(_html.escape(self._text), cls=self._CLASS) + "\n"

  
class ErrorMessage(Message):
    _CLASS = "error"
    

class LoginDialog(lcg.Content):
    
    def __init__(self, req):
        super(LoginDialog, self).__init__()
        self._params = req.params
        self._uri = req.uri
        self._login = req.login_name()

    def export(self, exporter):
        #TODO: labels!!!!!!!!!!!!
        x = (_html.label(_("Login name")+':', id='login') + _html.br(),
             _html.field(name='login', value=self._login, id='login',
                         tabindex=0, size=14), _html.br(), 
             _html.label(_("Password")+':', id='password') + _html.br(),
             _html.field(name='password', id='password', size=14,
                         password=True), _html.br(),
             _html.hidden(name='__log_in', value='1'), 
             ) + tuple([_html.hidden(name=k, value=v)
                        for k,v in self._params.items()]) + (
            _html.submit(_("Log in"), cls='submit'),)
        return _html.form(x, method='POST', action=self._uri, cls='login-form')
        
        
def translator(lang):
    if lang:
        path = {
            'wiking': os.path.join(cfg.wiking_dir, 'translations'),
            'lcg':  '/usr/local/share/lcg/translations',
            'lcg-locale':  '/usr/local/share/lcg/translations',
            'pytis': '/usr/local/share/pytis/translations',
            }
        return lcg.GettextTranslator(lang, path=path, fallback=True)
    else:
        return lcg.NullTranslator()
    
# ============================================================================
# Classes derived from Pytis components
# ============================================================================

Field = pytis.presentation.FieldSpec

class Action(pytis.presentation.Action):
    def __init__(self, title, name, handler=None, **kwargs):
        # name determines the Wiking's method (and the 'action' argument.
        self._name = name
        if not handler:
            handler = lambda r: None
        super(Action, self).__init__(title, handler, **kwargs)
        
    def name(self):
        return self._name
    

class Data(pd.DBDataDefault):

    def _row_data(self, **kwargs):
        return [(k, pd.Value(self.find_column(k).type(), v))
                for k, v in kwargs.items()]
    
    def get_rows(self, skip=None, limit=None, sorting=(), condition=None,
                 **kwargs):
        if kwargs:
            conds = [pd.EQ(k,v) for k,v in self._row_data(**kwargs)]
            if condition:
                conds.append(condition)
            condition = pd.AND(*conds)
        self.select(condition=condition, sort=sorting)
        rows = []
        if skip:
            self.skip(skip)
        while True:
            row = self.fetchone()
            if row is None:
                break
            rows.append(row)
            if limit is not None and len(rows) > limit:
                break
        self.close()
        return rows

    def get_row(self, **kwargs):
        rows = self.get_rows(**kwargs)
        if len(rows) == 0:
            return None
        else:
            return rows[0]

    def make_row(self, **kwargs):
        return pd.Row(self._row_data(**kwargs))

    
class WikingResolver(pytis.util.Resolver):
    """A custom resolver of Wiking modules."""
    
    def __init__(self, assistant=None):
        assert assistant is None or isinstance(assistant, pytis.util.Resolver)
        self._assistant = assistant
    
    def get(self, name, spec_name):
        try:
            cls = get_module(name)
        except AttributeError, e:
            if self._assistant:
                return self._assistant.get(name, spec_name)
            else:
                raise pytis.util.ResolverModuleError(name, str(e))
        try:
            spec = cls.spec(self)
        except AttributeError:
            return self._assistant.get(name, spec_name)
        try:
            method = getattr(spec, spec_name)
        except AttributeError:
            raise pytis.util.ResolverSpecError(name, spec_name)
        return method()

        
class DateTime(pytis.data.DateTime):
    """Pytis DateTime type which exports as a 'lcg.LocalizableDateTime'."""
    
    def __init__(self, exact=False, **kwargs):
        self._is_exact = exact
        format = '%Y-%m-%d %H:%M'
        if exact:
            format += ':%S'
        super(DateTime, self).__init__(format=format, **kwargs)

    def is_exact(self):
        return self._is_exact
        
    def _export(self, value, show_weekday=False, show_time=True, **kwargs):
        result = super(DateTime, self)._export(value, **kwargs)
        return lcg.LocalizableDateTime(result, show_weekday=show_weekday,
                                       show_time=show_time)

        
# We need two types, because we need to derive from two different base classes.

class Date(pytis.data.Date):
    """Pytis Date type which exports as a 'lcg.LocalizableDateTime'."""#

    def __init__(self, **kwargs):
        super(Date, self).__init__(format='%Y-%m-%d', **kwargs)
        
    def _export(self, value, show_weekday=False, **kwargs):
        result = super(Date, self)._export(value, **kwargs)
        return lcg.LocalizableDateTime(result, show_weekday=show_weekday)

