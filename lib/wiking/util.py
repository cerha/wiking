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

class Theme(object):

    class Color(object):
        def __init__(self, id, inherit=None):
            self._id = id
            self._inherit = inherit
        def id(self):
            return self._id
        def inherit(self):
            return self._inherit
        
    COLORS = (
        Color('foreground'),
        Color('background'),
        Color('highlight-bg'),
        Color('border'),
        Color('frame-fg', inherit='foreground'),
        Color('frame-bg', inherit='background'),
        Color('frame-border', inherit='border'),
        Color('heading-fg', inherit='foreground'),
        Color('heading-bg', inherit='background'),
        Color('heading-line', inherit='border'),
        Color('link'),
        Color('link-visited', inherit='link'),
        Color('link-hover', inherit='link'),
        Color('help', inherit='foreground'),
        Color('error-fg'),
        Color('error-bg'),
        Color('error-border'),
        Color('message-fg'),
        Color('message-bg'),
        Color('message-border'),
        Color('table-cell', inherit='background'),
        Color('table-cell2', inherit='table-cell'),
        Color('button-fg', inherit='foreground'),
        Color('button', inherit='heading-bg'),
        Color('button-hover', inherit='highlight-bg'),
        Color('button-border', inherit='border'),
        Color('button-inactive-fg', inherit='button-fg'),
        Color('button-inactive', inherit='button'),
        Color('button-inactive-border', inherit='button-border'),
        Color('top-fg', inherit='foreground'),
        Color('top-bg', inherit='background'),
        Color('top-border', inherit='border'),
        Color('inactive-folder'),
        Color('meta-fg', inherit='foreground'),
        Color('meta-bg', inherit='background'),
        )

    _DEFAULTS = {'foreground': '#000',
                 'background': '#fff',
                 'border': '#bcd',
                 'heading-bg': '#d8e0f0',
                 'heading-line': '#ccc',
                 'frame-bg': '#eee',
                 'frame-border': '#ddd',
                 'link': '#03b',
                 'link-hover': '#d60',
                 'meta-fg': '#840',
                 'help': '#444',
                 'error-bg': '#fdb',
                 'error-border': '#fba',
                 'message-bg': '#cfc',
                 'message-border': '#aea',
                 'table-cell': '#f8fafb',
                 'table-cell2': '#f1f3f2',
                 'button-border': '#9af',
                 'button-inactive-fg': '#555',
                 'button-inactive': '#ccc',
                 'button-inactive-border': '#999',
                 'top-bg': '#efebe7',
                 'top-border': '#9ab',
                 'highlight-bg': '#fc8',
                 'inactive-folder': '#d2d8e0',
                 }

    def __init__(self, colors=None):
        if not colors:
            colors = self._DEFAULTS
        self._colors = dict([(c.id(), c) for c in self.COLORS])
        self._theme = {'color': dict([(key, self._color(key, colors))
                                      for key in self._colors.keys()])}
        
    def _color(self, key, colors):
        if colors.has_key(key):
            return colors[key]
        else:
            inherit = self._colors[key].inherit()
            if inherit:
                return self._color(inherit, colors)
            elif colors != self._DEFAULTS:
                return self._color(key, self._DEFAULTS)
            else:
                return 'inherit'
        
    def __getitem__(self, key):
        return self._theme[key]
    
        
class MenuItem(object):
    """Abstract menu item representation."""
    def __init__(self, id, title, descr=None, hidden=False, active=True, submenu=(), order=None,
                 variants=None):
        self._id = id
        self._title = title
        self._descr = descr
        self._hidden = hidden
        self._active = active
        submenu = list(submenu)
        submenu.sort(key=lambda i: i.order())
        self._submenu = submenu
        self._order = order
        self._variants = variants
    def id(self):
        return self._id
    def title(self):
        return self._title
    def descr(self):
        return self._descr
    def hidden(self):
        return self._hidden
    def active(self):
        return self._active
    def order(self):
        return self._order
    def submenu(self):
        return self._submenu
    def variants(self):
        return self._variants


class Panel(object):
    """Panel representation to be passed to 'Document.build()'."""
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

    The 'Document' is Wiking's abstraction of an LCG document (represented by 'lcg.ContentNode').
    
    This allows us to initialize document data without actually creating the whole LCG node
    hierarchy and specifying all the required attributes at the same time.  Default attribute
    values sensible in the Wiking environment are substituted and the whole content node hierarchy
    is built afterwards by calling the method 'build()'.

    """
    
    def __init__(self, title, content, subtitle=None, lang=None, sec_lang='en', variants=None,
                 resources=()):
        """Initialize the instance.

        Arguments:

          title -- document title as a (translatable) string.  Can be also None, in which case the
            title will default to the title of the corresponding menu item (if found).

          content -- document content as 'lcg.Content' instance or their sequence.  If a sequence
            is passed, it is allowed to contain None values, which will be omitted.

          subtitle -- document subtitle as a (translatable) string.  If not None, it will be
            appended to the title.

          lang -- language of the content as a corresponding language code (defined by the
            'lcg.ContentNode' constructor).  Can be None if the content is not language dependent
            -- i.e. is all composed of translatable text, so that it can be exported into any
            target language (supported by the application and its translations).  Should always be
            defined for language dependent content, unless the whole application is mono-lingual.

          sec_lang -- secondary content language defined by the 'lcg.ContentNode' constructor.
            Only important when using the LCG feature of quotations. 

          variants -- available language variants as a sequence of language codes.  Should be
            defined if only a limited set of target languges for the document exist.  For example
            when the document is read form a file or a database and it is known which other
            versions of the source exist.  If None, variants default to the variants defined by the
            corresponding menu item (if found) or to application-wide set of all available
            languages.
          
          resources -- external resources available for this document as 'lcg.Resource' instances.

        """
        self._title = title
        self._subtitle = subtitle
        if isinstance(content, (list, tuple)):
            content = lcg.SectionContainer([c for c in content if c is not None], toc_depth=0)
        self._content = content
        self._lang = lang
        self._variants = variants
        self._sec_lang = sec_lang
        self._resources = tuple(resources)

    def build(self, req, modname, application):
        id = '/'.join(req.path)
        parent_id = '/'.join(req.path[:-1])
        state = WikingNode.State(modname=modname,
                                 user=req.user(),
                                 wmi=req.wmi,
                                 show_panels=req.show_panels(),
                                 server_hostname=req.server_hostname())
        lang = self._lang or req.prefered_language(raise_error=False) or 'en'
        me = []
        parent = []
        def mknode(item):
            if item.id() == id:
                heading = self._title or item.title()
                if self._subtitle:
                    heading = lcg.concat(heading, ' :: ', self._subtitle)
                content = self._content
                panels = application.panels(req, lang)
                resources = resources=self._resources + tuple(application.stylesheets())
                variants = self._variants
                if variants is None:
                    variants = item.variants()
            else:
                heading = item.title()
                content = lcg.Content()
                panels = ()
                resources = ()
                variants = item.variants()
            hidden = item.hidden()
            if variants is None:
                variants = application.languages()
            elif lang not in variants:
                hidden = True
            resource_provider = lcg.StaticResourceProvider(resources)
            node = WikingNode(item.id(), state, title=item.title(), heading=heading,
                              descr=item.descr(), content=content, hidden=hidden, language=lang,
                              secondary_language=self._sec_lang, language_variants=variants or (),
                              active=item.active(), panels=panels, 
                              children=[mknode(i) for i in item.submenu()],
                              resource_provider=resource_provider)
            if item.id() == id:
                me.append(node)
            elif item.id() == parent_id:
                parent.append(node)
            return node
        nodes = [mknode(item) for item in application.menu(req)]
        if not me:
            variants = self._variants or parent and parent[0].language_variants() or None
            node = mknode(MenuItem(id, self._title, hidden=True, variants=variants))
            if parent:
                parent[0].add_child(node)
            else:
                nodes.append(node)
        root = WikingNode('__wiking_root_node__', state, title='root', content=lcg.Content(),
                          children=nodes)
        return me[0]

    
# ============================================================================
# Classes derived from LCG components
# ============================================================================

class WikingNode(lcg.ContentNode):

    class State(object):
        def __init__(self, modname, user, wmi, show_panels, server_hostname):
            self.modname = modname
            self.user = user
            self.wmi = wmi
            self.show_panels = show_panels
            self.server_hostname = server_hostname
    
    def __init__(self, id, state, heading=None, panels=(), **kwargs):
        super(WikingNode, self).__init__(id, **kwargs)
        self._heading = heading
        self._state = state
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
    
    def state(self):
        return self._state
    
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
    
    def __init__(self, uri, actions, referer, row=None, args=None, separate=False):
        super(ActionMenu, self).__init__()
        assert isinstance(uri, str), uri
        assert isinstance(actions, (tuple, list)), actions
        assert isinstance(referer, str), referer
        assert row is None or isinstance(row, pp.PresentedRow), row
        assert args is None or isinstance(args, dict), args
        assert separate is None or isinstance(separate, bool), separate
        self._uri = uri
        self._row = row
        self._actions = actions
        self._args = args or {}
        self._referer = referer
        self._separate = separate

    def _export_item(self, action, g):
        title = action.descr()
        enabled = action.enabled()
        if callable(enabled):
            enabled = enabled(self._row)
        if enabled:
            args = self._args
            uri = self._uri
            if action.name() in ('delete', 'list'):
                key = self._row.data().key()[0].id()
                if action.name() == 'delete':
                    args = dict(args, **{key: self._row[key].export()})
                else:
                    args = dict(args, search=self._row[key].export())
            elif self._referer is not None and self._row:
                if not uri.endswith('/'):
                    uri += '/'
                uri += self._row[self._referer].export()
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
                            if isinstance(a, Action)], separator=g.span(" |\n", cls="hidden"))
        content = (_("Actions:"), items)
        cls = "actions"
        if self._separate:
            content = (g.hr(),) + content + (g.hr(),)
            cls += " separated"
        return g.div(lcg.concat(content, separator="\n"), cls=cls)

    
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

    
class Message(lcg.TextContent):
    _CLASS = "message"
    
    def export(self, exporter):
        g = exporter.generator()
        return g.p(g.escape(self._text), cls=self._CLASS) + "\n"

  
class ErrorMessage(Message):
    _CLASS = "error"
    

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
        return lcg.concat(username, ' ', g.span('[', cls="hidden"), ctrl, g.span(']',cls="hidden"))


class LoginDialog(lcg.Content):
    
    def __init__(self, req):
        super(LoginDialog, self).__init__()
        self._params = req.params
        self._uri = req.uri
        self._https = req.https()
        self._https_uri = req.abs_uri(port=443)
        credentials = req.credentials()
        if credentials:
            self._login = credentials[0]
            self._password = None
        else:
            self._login = req.param('login')
            self._password = req.param('password')

    def export(self, exporter):
        g = exporter.generator()
        x = (g.label(_("Login name")+':', id='login') + g.br(),
             g.field(name='login', value=self._login, id='login', tabindex=0,
                     size=14), g.br(), 
             g.label(_("Password")+':', id='password') + g.br(),
             g.field(name='password', value=self._password, id='password', size=14, password=True),
             g.br(),
             g.hidden(name='__log_in', value='1'), 
             ) + tuple([g.hidden(name=k, value=v) for k,v in self._params.items() 
                        if k not in ('command', 'login', 'password', '__log_in')]) + (
            g.submit(_("Log in"), cls='submit'),)
        if not self._https and cfg.force_https_login:
            uri = self._https_uri
        else:
            uri = self._uri
        return g.form(x, method='POST', action=uri, cls='login-form')

    
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

def get_module(name):
    """Get the module class by name.
    
    This function replaces Pytis resolver in the web environment and is also
    used by the Pytis resolver in the stand-alone pytis application
    environment.
    
    """
    try:
        from mod_python.apache import import_module
    except ImportError:
        try:
            import wikingmodules
        except ImportError, e:
            if str(e) == 'No module named wikingmodules':
                import wiking.cms
                return getattr(wiking.cms, name)
            else:
                raise
        else:
            try:
                return getattr(wikingmodules, name)
            except AttributeError:
                import wiking.modules
                return getattr(wiking.modules, name)
    else:
        try:
            modules = import_module('wikingmodules', log=True)
        except ImportError, e:
            if str(e) == 'No module named wikingmodules':
                modules = import_module('wiking.cms', log=True)
            else:
                raise
        else:
            try:
                return getattr(modules, name)
            except AttributeError:
                # This module is imported by Python, so importing it once more through
                # Apache would cause problems.
                import wiking.modules
                return getattr(wiking.modules, name)
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
    argstr = ';'.join(["%s=%s" % (k,v) for k,v in args if v is not None])
    if argstr:
        return base + '?' + argstr
    else:
        return base


def translator(lang):
    if lang:
        return lcg.GettextTranslator(lang, path=cfg.translation_paths, fallback=True)
    else:
        return lcg.NullTranslator()
    
