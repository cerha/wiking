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

import time, re, os, copy

DBG = pytis.util.DEBUG
EVT = pytis.util.EVENT
OPR = pytis.util.OPERATIONAL
log = pytis.util.StreamLogger(sys.stderr).log

_ = lcg.TranslatableTextFactory('wiking')


class RequestError(Exception):
    """Base class for exceptions indicating an invalid request.

    Exceptions of this class will be handled by displaying an error message
    within the content part of the page.  The overall page layout, including
    navigation and other static page content is displayed as on any other page.
    These errors are not logged neither emailed, since they are caused by an
    invalid request.

    """
    _TITLE = None
    
    def title(self):
        """Return the error name as a string.""" 
        return self._TITLE
    
    def message(self, req):
        """Return the error message as an 'lcg.Content' element structure.""" 
        return None


class AuthenticationError(RequestError):
    """Error indicating that authentication is required for the resource."""
    
    _TITLE = _("Authentication required")

    def message(self, req):
        content = LoginDialog(req)
        if self.args:
            content = (ErrorMessage(self.args[0]), content)
        return content
    

class AuthorizationError(RequestError):
    """Error indicating that the user doesn't have privilegs for the action."""
    
    _TITLE = _("Not Authorized")

    def message(self, req):
        return lcg.p(_("You don't have sufficient privilegs for this action."))
    
    
class HttpError(RequestError):
    """Exception representing en HTTP error.

    This exception should be handled by returning the appropriate HTTP error
    code to the client.  This code is available as the public constant
    'ERROR_CODE' of the class.

    This class is abstract.  The error code and error message must be defined
    by a derived class.  The error message may also require certain constructor
    arguments passed when raising the error.
    
    """
    ERROR_CODE = None
    
    def title(self):
        name = " ".join(pp.split_camel_case(self.__class__.__name__))
        return _("Error %(code)d: %(name)s", code=self.ERROR_CODE, name=name)


class NotFound(HttpError):
    """Error indicating invalid request target."""
    ERROR_CODE = 404
    
    def message(self, req):
        msg = (_("The item '%s' does not exist on this server or cannot be "
                 "served.", req.uri),
               _("If you are sure the web address is correct, "
                 "but are encountering this error, please send "
                 "an e-mail to the webmaster."),
               _("Thank you"))
        return lcg.coerce([lcg.p(p) for p in msg])

    
class Forbidden(HttpError):
    """Error indicating unavailable request target."""
    ERROR_CODE = 403
    
    def message(self, req):
        msg = (_("The item '%s' is not available.", req.uri),
               _("The item exists on the server, but it is not published."))
        return lcg.coerce([lcg.p(p) for p in msg])

    
class NotAcceptable(HttpError):
    """Error indicating unavailability of the resource in requested language."""
    ERROR_CODE = 406
    
    def message(self, req):
        msg = (_("The resource '%s' is not available in either of "
                 "the requested languages.", req.uri),
               (_("Your browser is configured to accept only the "
                  "following languages:"), ' ',
                lcg.concat([lcg.language_name(l) for l in
                            req.prefered_languages()], separator=', ')))
        if self.args:
            msg += ((_("The available variants are:"), ' ',
                     lcg.join([lcg.link("%s?setlang=%s" % (req.uri, l),
                                        label=lcg.language_name(l),)
                               for l in self.args[0]], separator=', ')),
                    _("If you want to accept other languages permanently, "
                      "setup the language preferences in your browser "
                      "or contact your system administrator."))
        return lcg.coerce([lcg.p(p) for p in msg])


# ============================================================================

class Roles(object):
    """Static definition of available user roles."""
    ANYONE = 'ANYONE'
    """Anyone, even a user who is not logged-in."""
    USER = 'USER'
    """Any logged-in user who is at least enabled."""
    CONTRIBUTOR = 'CONTRIBUTOR'
    """A user hwo has contribution privilegs for certain types of content."""
    AUTHOR = 'AUTHOR'
    """Any user who has the authoring privileges."""
    ADMIN = 'ADMIN'
    """A user who has the admin privileges."""
    OWNER = 'OWNER'
    """The owner of the item being operated."""
    def check(cls, req, roles, owner_uid=None, raise_error=True):
        def check(req, role, owner_uid=None):
            if role == cls.ANYONE:
                return True
            # We don't want to perform authentication until here!
            user = req.user(raise_error=raise_error)
            if user is None:
                return False
            if role == cls.OWNER:
                if owner_uid:
                    return owner_uid == user.uid()
                else:
                    return False
            else:
                return role in user.roles()
        for role in roles:
            if check(req, role, owner_uid=owner_uid):
                return True
        if raise_error:
            raise AuthorizationError()
        else:
            return False
    check = classmethod(check)


class User(object):
    def __init__(self, uid, login, password, name=None, roles=(), data=None):
        self._uid = uid
        self._login = login
        self._password = password
        self._name = name or login
        self._roles = tuple(roles)
        self._data = data
    def uid(self):
        return self._uid
    def login(self):
        return self._login
    def password(self):
        return self._password
    def name(self):
        return self._name
    def roles(self):
        return self._roles
    def data(self):
        return self._data
    
        
class FileUpload(object):
    """An abstract representation of uploaded file fields."""

    def file(self):
        """Return a file-like object from which the data may be read."""
        
    def filename(self):
        """Return the original filename as a string"""
        
    def type(self):
        """Return the mime type provided byt he UA as a string"""


class MenuItem(object):
    """Abstract menu item representation."""
    def __init__(self, id, title, descr=None, hidden=False, submenu=(), order=None):
        self._id = id
        self._title = title
        self._descr = descr
        self._hidden = hidden
        submenu = list(submenu)
        submenu.sort(key=lambda i: i.order())
        self._submenu = submenu
        self._order = order
    def id(self):
        return self._id
    def title(self):
        return self._title
    def descr(self):
        return self._descr
    def hidden(self):
        return self._hidden
    def order(self):
        return self._order
    def submenu(self):
        return self._submenu


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
    'lcg.ContentNode' instance (more precisely 'WikingNode' in our case).  The
    instance can be created later using the 'mknode()' method (passing it the
    remaining arguments required by node's constructor).

    """
    
    def __init__(self, title, content, subtitle=None, lang=None, variants=(),
                 sec_lang='en', resources=()):
        self._title = title
        self._subtitle = subtitle
        if isinstance(content, (list, tuple)):
            content = lcg.SectionContainer([c for c in content if c], toc_depth=0)
        self._content = content
        self._lang = lang
        self._variants = variants
        self._sec_lang = sec_lang
        self._resources = tuple(resources)

    def lang(self):
        return self._lang
    
    def mknode(self, id, config, menu, panels, stylesheets):
        kwargs = dict(language=self._lang, language_variants=self._variants or (),
                      secondary_language=self._sec_lang)
        parent_id = '/'.join(id.split('/')[:-1])
        me = []
        parent = []
        def _mknode(item):
            if item.id() == id:
                heading = self._title or item.title()
                if self._subtitle:
                    heading = lcg.concat(heading, ' :: ', self._subtitle)
                content = self._content
                resources = resources=self._resources + tuple(stylesheets)
                panels_ = panels
            else:
                heading = item.title()
                content = lcg.Content()
                resources = ()
                panels_ = ()
            resource_provider = lcg.StaticResourceProvider(resources)
            node = WikingNode(item.id(), config, title=item.title(), heading=heading,
                              descr=item.descr(), content=content,  hidden=item.hidden(),
                              children=[_mknode(i) for i in item.submenu()],
                              panels=panels_, resource_provider=resource_provider, **kwargs)
            if item.id() == id:
                me.append(node)
            if item.id() == parent_id:
                parent.append(node)
            return node
        nodes = [_mknode(item) for item in menu]
        if not me:
            node = _mknode(MenuItem(id, self._title, hidden=True))
            if parent:
                parent[0].add_child(node)
            else:
                nodes.append(node)
        root = WikingNode('__wiking_root_node__', config, title='root', content=lcg.Content(),
                          children=nodes)
        return me[0]

    
# ============================================================================
# Classes derived from LCG components
# ============================================================================

class WikingNode(lcg.ContentNode):
    
    def __init__(self, id, config, heading=None, panels=(), **kwargs):
        super(WikingNode, self).__init__(id, **kwargs)
        self._heading = heading
        self._config = config
        self._panels = panels
        for panel in panels:
            panel.content().set_parent(self)

    def add_child(self, node):
        if isinstance(self._children, tuple):
            self._children = list(self._children)
        node._set_parent(self)
        self._children.append(node)
        
    def heading(self):
        return self._heading or self._title
    
    def config(self):
        return self._config
    
    def top(self):
        parent = self._parent
        if parent is None:
            return None
        elif parent.parent() is None:
            return self
        else:
            return parent.top()
    
    def panels(self):
        return self._panels


class ActionMenu(lcg.Content):
    """A menu of actions related to one record or the whole module."""
    
    def __init__(self, actions, row=None, args=None, uri=None):
        super(ActionMenu, self).__init__()
        assert isinstance(actions, (tuple, list)), actions
        assert uri is None or isinstance(uri, str), uri
        assert row is None or isinstance(row, pp.PresentedRow), row
        assert args is None or isinstance(args, dict), args
        self._uri = uri
        self._row = row
        self._actions = actions
        self._args = args or {}

    def _export_item(self, action, g):
        title = action.descr()
        enabled = action.enabled()
        if callable(enabled):
            enabled = enabled(self._row)
        if enabled:
            args = self._args
            if self._uri is not None:
                uri = self._uri
            elif action.context() is None and self._row is not None:
                if action.name() == 'delete':
                    args = copy.copy(args)
                    key = self._row.data().key()[0].id()
                    args[key] = self._row[key].export()
                uri = '.'
            else:
                uri = ''
            target = g.uri(uri, action=action.name(), **args)
            cls = None
        else:
            target = None
            cls = 'inactive'
            title += " (" + _("not available") + ")"
        return g.link(action.title(), target, title=title, cls=cls)
        
    def export(self, exporter):
        g = exporter.generator()
        # Only Wiking's Actions are considered, not `pytis.presentation.Action'.
        items = lcg.concat([self._export_item(a, g) for a in self._actions
                        if isinstance(a, Action)],
                       separator=g.span(" |\n", cls="hidden"))
        return g.p(lcg.concat(_("Actions:"), items, separator="\n"),
                   cls="actions")

class LoginCtrl(lcg.Content):
    """Displays the logged in user and a login/logout control."""
    
    def __init__(self, user):
        super(LoginCtrl, self).__init__()
        assert user is None or isinstance(user, User), user
        self._user = user

    def export(self, exporter):
        g = exporter.generator()
        if self._user:
            username = self._user.name()
            cmd, label = ('logout', _("log out"))
        else:
            username = _("not logged")
            cmd, label = ('login', _("log in"))
        ctrl = g.link(label, '?command=%s' % cmd, cls='login-ctrl')
        return lcg.concat(username, ' ', g.span('[', cls="hidden"), ctrl,
                          g.span(']', cls="hidden"))
    
    
class PanelItem(lcg.Content):

    def __init__(self, fields):
        super(PanelItem, self).__init__()
        self._fields = fields
        
    def export(self, exporter):
        g = exporter.generator()
        items = [g.span(uri and g.link(value, uri) or value,
                            cls="panel-field-"+id)
                 for id, value, uri in self._fields]
        return g.div(items, cls="item")


class CustomViewSpec(object):
    def __init__(self, title, meta=(), content=None, anchor=None,
                 labeled_fields=(), custom_list=False, cls='view-item'):
        self._title = title
        self._meta = meta
        self._content = content
        self._anchor = anchor
        self._labeled_fields = labeled_fields
        self._custom_list = custom_list
        self._cls = cls
    def title(self):
        return self._title
    def meta(self):
        return self._meta
    def content(self):
        return self._content
    def anchor(self):
        return self._anchor
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
        g = exporter.generator()
        spec = self._custom_spec
        labeled = spec.labeled_fields()
        title = self._row[spec.title()].export()
        if spec.anchor():
            name = spec.anchor() % row[self._data.key()[0].id()].export()
            title = g.link(title, None, name=name)
        parts = [g.h(title, level=3)]
        if spec.meta():
            meta = ''
            for id in spec.meta():
                f = self._view.field(id)
                content = self._export_value(exporter, row, f)
                if id in labeled:
                    label = f.label()
                    content = g.span(label, cls='label') + ": " + content
                if meta:
                    meta += ', '
                meta += g.span(content, cls=id)
            parts.append(g.div(meta, cls='meta'))
        if spec.content():
            src = self._row[spec.content()].export()
            content = self._export_structured_text(src, exporter)
            parts.append(g.div(content, cls='content'))
        return g.div(parts, cls=spec.cls())

    
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
        
    def _wrap_exported_rows_custom(self, exporter, rows):
        return exporter.generator().div(rows, cls="list-view")

    
class Message(lcg.TextContent):
    _CLASS = "message"
    
    def export(self, exporter):
        g = exporter.generator()
        return g.p(g.escape(self._text), cls=self._CLASS) + "\n"

  
class ErrorMessage(Message):
    _CLASS = "error"
    

class LoginDialog(lcg.Content):
    
    def __init__(self, req):
        super(LoginDialog, self).__init__()
        self._params = req.params
        self._uri = req.uri
        self._https = req.https()
        self._https_uri = req.abs_uri(port=443)
        credentials = req.credentials()
        self._login = credentials and credentials[0]

    def export(self, exporter):
        g = exporter.generator()
        #TODO: labels!!!!!!!!!!!!
        x = (g.label(_("Login name")+':', id='login') + g.br(),
             g.field(name='login', value=self._login, id='login', tabindex=0,
                     size=14), g.br(), 
             g.label(_("Password")+':', id='password') + g.br(),
             g.field(name='password', id='password', size=14, password=True),
             g.br(),
             g.hidden(name='__log_in', value='1'), 
             ) + tuple([g.hidden(name=k, value=v)
                        for k,v in self._params.items() if k != 'command']) + (
            g.submit(_("Log in"), cls='submit'),)
        if not self._https and self.parent().config().force_https_login:
            uri = self._https_uri
        else:
            uri = self._uri
        return g.form(x, method='POST', action=uri, cls='login-form')

    
class SiteMap(lcg.NodeIndex):
    def _start_item(self):
        return self.parent().root()


    
def translator(lang):
    if lang:
        return lcg.GettextTranslator(lang, path=cfg.translation_paths, fallback=True)
    else:
        return lcg.NullTranslator()
    
# ============================================================================
# Classes derived from Pytis components
# ============================================================================

Field = pytis.presentation.FieldSpec

class FieldSet(pp.GroupSpec):
    def __init__(self, label, fields):
        super(FieldSet, self).__init__(fields, label=label,
                                       orientation=pp.Orientation.VERTICAL)
        
class Action(pytis.presentation.Action):
    def __init__(self, title, name, handler=None, **kwargs):
        # name determines the Wiking's action method.
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


class Specification(pp.Specification):
    _instance_cache = {}
    actions = []
    data_cls = Data
    def __new__(cls, module, resolver):
        try:
            instance = cls._instance_cache[module]
        except KeyError:
            instance = cls._instance_cache[module] = pp.Specification.__new__(cls, resolver)
        return instance

    def __init__(self, module, resolver):
        if self.table is None:
            self.table = pytis.util.camel_case_to_lower(module.name(), '_')
        actions = list(self.actions)
        for base in module.__bases__ + (module,):
            if hasattr(base, '_ACTIONS'):
                for action in base._ACTIONS:
                    if action not in actions:
                        actions.append(action)
        self.actions = tuple(actions)
        return super(Specification, self).__init__(resolver)
    
        
class WikingResolver(pytis.util.Resolver):
    """A custom resolver of Wiking modules."""
    
    def get(self, name, spec_name):
        try:
            module_cls = get_module(name)
            spec_cls = module_cls.Spec
        except AttributeError, e:
            return super(WikingResolver, self).get(name, spec_name)
        spec = spec_cls(module_cls, self)
        try:
            method = getattr(spec, spec_name)
        except AttributeError:
            raise pytis.util.ResolverSpecError(name, spec_name)
        return method()
    
class WikingFileResolver(WikingResolver, pytis.util.FileResolver):
    pass
    
        
class DateTime(pytis.data.DateTime):
    """Pytis DateTime type which exports as a 'lcg.LocalizableDateTime'."""
    
    def __init__(self, show_time=True, exact=False, **kwargs):
        self._is_exact = exact
        self._show_time = show_time
        format = '%Y-%m-%d %H:%M'
        if exact:
            format += ':%S'
        super(DateTime, self).__init__(format=format, **kwargs)

    def is_exact(self):
        return self._is_exact
        
    def _export(self, value, show_weekday=False, show_time=None, **kwargs):
        result = super(DateTime, self)._export(value, **kwargs)
        if show_time is None:
            show_time = self._show_time
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


# ============================================================================
# Misc functions
# ============================================================================



def timeit(func, *args, **kwargs):
    """Measure the function execution time.

    Invokes the function 'func' with given arguments and returns the triple
    (function result, processor time, wall time), both times in microseconds.

    """
    t1, t2 = time.clock(), time.time()
    result = func(*args, **kwargs)
    return result,  time.clock() - t1, time.time() - t2

def import_modules():
    """Import module definitions and return them as a python module.

    Wiking comes with a set of predefined modules.  They are all defined in the 'wiking.modules'
    module.  These default modules can be overridden by defining custom modules in a module named
    'wikingmodules' available in the Python path.  This allows adding extension modules to the
    Wiking CMS (on a per site basis) or a complete redefinition of the application behavior.  The
    modular wiking engine can be thus used as a universal web application development toolkit.

    """
    try:
        from mod_python.apache import import_module
        try:
            modules = import_module('wikingmodules', log=True)
        except ImportError:
            modules = import_module('wiking.modules', log=True)
    except ImportError:
        try:
            import wikingmodules as modules
        except ImportError:
            import wiking.modules as modules
    return modules


def get_module(name):
    """Get the module class by name.
    
    This function replaces Pytis resolver in the web environment and is also
    used by the Pytis resolver in the stand-alone pytis application
    environment.
    
    """
    return getattr(import_modules(), name)


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

def send_mail(sender, addr, subject, text, html, smtp_server='localhost'):
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
    writer.addheader("Date", time.strftime("%a, %d %b %Y %H:%M:%S %z"))
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
    if html:
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


def make_uri(base, *args, **kwargs):
    """Return a URI constructed from given base URI and args."""
    args += tuple(kwargs.items())
    if args:
        return base + '?' + ';'.join(["%s=%s" % item for item in args])
    else:
        return base


