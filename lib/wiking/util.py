# Copyright (C) 2006, 2007, 2008 Brailcom, o.p.s.
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

import time, string, re, os, copy, urllib
import email.Header

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
        content = LoginDialog()
        if self.args:
            content = (ErrorMessage(self.args[0]), content)
        return content

    
class AuthenticationRedirect(AuthenticationError):
    """Has the same effect as AuthenticationError, but is just not an error."""
    
    _TITLE = _("Login")
    

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
                 "served.", req.uri()),
               _("If you are sure the web address is correct, "
                 "but are encountering this error, please send "
                 "an e-mail to the webmaster."),
               _("Thank you"))
        return lcg.coerce([lcg.p(p) for p in msg])

    
class Forbidden(HttpError):
    """Error indicating unavailable request target."""
    ERROR_CODE = 403
    
    def message(self, req):
        msg = (_("The item '%s' is not available.", req.uri()),
               _("The item exists on the server, but it is not published."))
        return lcg.coerce([lcg.p(p) for p in msg])

    
class NotAcceptable(HttpError):
    """Error indicating unavailability of the resource in requested language."""
    ERROR_CODE = 406
    
    def message(self, req):
        msg = (_("The resource '%s' is not available in either of "
                 "the requested languages.", req.uri()),
               (_("Your browser is configured to accept only the "
                  "following languages:"), ' ',
                lcg.concat([lcg.language_name(l) for l in
                            req.prefered_languages()], separator=', ')))
        if self.args:
            msg += ((_("The available variants are:"), ' ',
                     lcg.join([lcg.link("%s?setlang=%s" % (req.uri(), l),
                                        label=lcg.language_name(l),)
                               for l in self.args[0]], separator=', ')),
                    _("If you want to accept other languages permanently, "
                      "setup the language preferences in your browser "
                      "or contact your system administrator."))
        return lcg.coerce([lcg.p(p) for p in msg])


class MaintananceModeError(HttpError):
    """Error indicating an invalid action in mainenance mode.

    The maintenance mode can be turned on by the 'maintenance' option in apache configuration.  If
    this option is set to 'true', no database access will be allowed and any attempt to do so will
    raise this error.  The application should handle all these errors gracefully to support the
    mainenance mode.
    
    """
    ERROR_CODE = 503

    def title(self):
        return _("Maintenance mode")

    def message(self, req):
        return lcg.p(_("The system is temporarily down for maintenance."))
    

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


class LoginPanel(Panel):
    """Displays login/logout controls and other relevant information."""
    
    class PanelContent(lcg.Content):
        def export(self, context):
            g = context.generator()
            req = context.req()
            user = req.user()
            if user:
                username = user.name()
                uri = user.uri()
                if uri:
                    username = g.link(username, uri, title=_("Go to your profile"))
                cmd, label = ('logout', _("log out"))
            else:
                username = _("not logged")
                cmd, label = ('login', _("log in"))
            content = lcg.concat(username, ' ',
                                 g.span('[', cls="hidden"),
                                 g.link(label, '?command=%s' % cmd, cls='login-ctrl'),
                                 g.span(']',cls="hidden"))
            if not user:
                uri = req.application().registration_uri(req)
                if uri:
                    content += g.br() +'\n'+ g.link(_("New user registration"), uri)
            else:
                if user.passwd_expiration():
                    date = lcg.LocalizableDateTime(str(user.passwd_expiration()))
                    content += g.br() +'\n'+ _("Your password expires on %(date)s.", date=date)
                uri = req.application().password_change_uri(req)
                if uri:
                    content += g.br() +'\n'+ g.link(_("Change your password"), uri)
            return content
        
    def __init__(self):
        super(LoginPanel, self).__init__('login', _("Login Panel"), self.PanelContent())


class Document(object):
    """Independent Wiking document representation.

    The 'Document' is Wiking's abstraction of an LCG document (represented by 'lcg.ContentNode').
    
    This allows us to initialize document data without actually creating the whole LCG node
    hierarchy and specifying all the required attributes at the same time.  Default attribute
    values sensible in the Wiking environment are substituted and the whole content node hierarchy
    is built afterwards by calling the method 'build()'.

    """
    
    def __init__(self, title, content, subtitle=None, lang=None, variants=None, resources=(),
                 globals=None):
        """Initialize the instance.

        Arguments:

          title -- document title as a (translatable) string.  Can be also None, in which case the
            title will default to the title of the corresponding menu item (if found).

          content -- document content as 'lcg.Content' instance or their sequence.  If a sequence
            is passed, it is allowed to contain None values, which will be omitted.

          subtitle -- document subtitle as a (translatable) string.  If not None, it will be
            appended to the title.

          lang -- language of the content as a corresponding iso language code.  Can be None if the
            content is not language dependent -- i.e. is all composed of translatable text, so that
            it can be exported into any target language (supported by the application and its
            translations).  Should always be defined for language dependent content, unless the
            whole application is mono-lingual.

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
        self._resources = tuple(resources)
        self._globals = globals

    def build(self, req, application):
        id = '/'.join(req.path)
        lang = self._lang or req.prefered_language(raise_error=False) or 'en'
        nodes = {}
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
            node = WikingNode(str(item.id()), title=item.title(), heading=heading,
                              descr=item.descr(), lang=lang, content=content, hidden=hidden,
                              variants=variants or (), active=item.active(), panels=panels, 
                              children=[mknode(i) for i in item.submenu()],
                              resource_provider=resource_provider, globals=self._globals)
            nodes[item.id()] = node
            return node
        top_level_nodes = [mknode(item) for item in application.menu(req)]
        # Find the parent node by the identifier prefix.
        parent = None
        for i in range(len(req.path)-1):
            key = '/'.join(req.path[:len(req.path)-i-1])
            if nodes.has_key(key):
                parent = nodes[key]
                break
        if nodes.has_key(id):
            node = nodes[id]
        else: 
            # Create the current document's node if it was not created with the menu.
            variants = self._variants or parent and parent.variants() or None
            node = mknode(MenuItem(id, self._title, hidden=True, variants=variants))
            if parent:
                parent.add_child(node)
            else:
                top_level_nodes.append(node)
        root = WikingNode('__wiking_root_node__', title='root', content=lcg.Content(),
                          children=top_level_nodes)
        return node

    
# ============================================================================
# Classes derived from LCG components
# ============================================================================

class WikingNode(lcg.ContentNode):

    def __init__(self, id, heading=None, panels=(), lang=None, **kwargs):
        super(WikingNode, self).__init__(id, **kwargs)
        self._heading = heading
        self._panels = panels
        self._lang = lang
        for panel in panels:
            panel.content().set_parent(self)

    def add_child(self, node):
        if isinstance(self._children, tuple):
            self._children = list(self._children)
        node._set_parent(self)
        self._children.append(node)
        
    def lang(self):
        return self._lang

    def heading(self):
        return self._heading or self._title
    
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


class ActionCtrl(lcg.Content):
    """Context action invocation control."""
    
    def __init__(self, uri, action, referer, name, row=None, relation=None):
        super(ActionCtrl, self).__init__()
        assert isinstance(uri, (str, unicode)), uri
        assert isinstance(action, Action), action
        assert isinstance(referer, str), referer
        assert isinstance(name, str), name
        assert row is None or isinstance(row, pp.PresentedRow), row
        assert relation is None or isinstance(relation, dict), relation
        self._uri = uri
        self._action = action
        self._referer = referer
        self._name = name
        self._row = row
        self._relation = relation or {}

    def export(self, context):
        g = context.generator()
        action = self._action
        title = action.descr()
        enabled = action.enabled()
        if callable(enabled):
            enabled = enabled(self._row)
        if enabled:
            args = action.kwargs() or {}
            uri = self._uri
            if action.name() in ('delete', 'list'):
                key = self._row.data().key()[0].id()
                if action.name() == 'delete':
                    args = dict(args, **{key: self._row[key].export()})
                else:
                    args = dict(args, search=self._row[key].export(), module=self._name)
            elif action.name() == 'insert':
                args = dict(args, module=self._name, **self._relation)
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


class ActionMenu(lcg.Container):
    """A set of action controls."""
    
    def __init__(self, uri, actions, referer, name, row=None, relation=None, title=_("Actions:"),
                 help=None, cls='actions'):
        ctrls = [ActionCtrl(uri, a, referer, name, row, relation=relation)
                 for a in actions]
        if help:
            ctrls.append(lcg.link(help, _("Help")))
        super(ActionMenu, self).__init__(ctrls)
        self._title = title
        self._cls = cls

    def export(self, context):
        g = context.generator()
        # Only Wiking's actions are considered, not all `pytis.presentation.Action'.
        return g.div((self._title and self._title +"\n" or '') +
                     g.list([ctrl.export(context) for ctrl in self._content]), cls=self._cls)

    
class PanelItem(lcg.Content):

    def __init__(self, fields):
        super(PanelItem, self).__init__()
        self._fields = fields
        
    def export(self, context):
        g = context.generator()
        items = [g.span(uri and g.link(value, uri) or value,
                            cls="panel-field-"+id)
                 for id, value, uri in self._fields]
        return g.div(items, cls="item")

    
class Message(lcg.TextContent):
    _CLASS = "message"
    
    def export(self, context):
        g = context.generator()
        return g.p(g.escape(self._text), cls=self._CLASS) + "\n"

  
class ErrorMessage(Message):
    _CLASS = "error"
    

class LoginDialog(lcg.Content):
    
    def export(self, context):
        g = context.generator()
        req = context.req()
        credentials = req.credentials()
        if credentials:
            login = credentials[0]
            password = None
        else:
            login = req.param('login')
            password = req.param('password') or None
        hidden = [g.hidden(name=k, value=req.param(k)) for k in req.params() 
                  if k not in ('command', 'login', 'password', '__log_in')]
        content = (
            g.label(_("Login name")+':', id='login') + g.br(),
            g.field(name='login', value=login, id='login', tabindex=1, size=14),
            g.br(), 
            g.label(_("Password")+':', id='password') + g.br(),
            g.field(name='password', value=password, id='password', size=14,
                    tabindex=2, password=True),
            g.br(),
            g.hidden(name='__log_in', value='1'),
            ) + tuple(hidden) + (
            g.submit(_("Log in"), cls='submit'),)
        links = [g.link(label, uri) for label, uri in
                 ((_("New user registration"),
                   req.application().registration_uri(req)),
                  (_("Forgot your password?"),
                   req.application().password_reminder_uri(req))) if uri]
        if links:
            content += (g.list(links),)
        if not req.https() and cfg.force_https_login:
            uri = req.server_uri(force_https=True) + req.uri()
        else:
            uri = req.uri()
        return g.form(content, method='POST', action=uri, cls='login-form')
    

    
# ============================================================================
# Classes derived from Pytis components
# ============================================================================

Field = pytis.presentation.FieldSpec

class FieldSet(pp.GroupSpec):
    def __init__(self, label, fields, horizontal=False):
        orientation = horizontal and pp.Orientation.HORIZONTAL or pp.Orientation.VERTICAL
        super(FieldSet, self).__init__(fields, label=label, orientation=orientation)
        
class Action(pytis.presentation.Action):
    def __init__(self, title, name, handler=None, **kwargs):
        # name determines the Wiking's action method.
        if not handler:
            handler = lambda r: None
        super(Action, self).__init__(title, handler, name=name, **kwargs)
    

class Data(pd.DBDataDefault):

    _dbfunction = {} # DBFunftion* instance cache

    def __init__(self, *args, **kwargs):
        super(Data, self).__init__(*args, **kwargs)
        # We don't want to care how `connection_data' is stored in the parent class...
        # We surely pass the
        self._dbconnection = kwargs['connection_data']

    def _row_data(self, **kwargs):
        return [(k, pd.Value(self.find_column(k).type(), v)) for k, v in kwargs.items()]
    
    def get_rows(self, skip=None, limit=None, sorting=(), condition=None, **kwargs):
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


    def dbfunction(self, name, *args):
        """Call the database function 'name' and return the returned value."""
        try:
            function = self.__class__._dbfunction[name]
        except KeyError:
            function = self.__class__._dbfunction[name] = \
                       pytis.data.DBFunctionDefault(name, self._dbconnection)
        result = function.call(pytis.data.Row(args))
        return result[0][0].value()


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
    
    def __init__(self, show_time=True, exact=False, leading_zeros=True, **kwargs):
        self._exact = exact
        self._show_time = show_time
        self._leading_zeros = leading_zeros
        format = '%Y-%m-%d %H:%M'
        if exact:
            format += ':%S'
        super(DateTime, self).__init__(format=format, **kwargs)

    def locale_format(self, locale_data):
        if self._exact:
            time_format = locale_data.exact_time_format
        else:
            time_format = locale_data.time_format
        return locale_data.date_format +' '+ time_format
        
    def _export(self, value, show_weekday=False, show_time=None, **kwargs):
        result = super(DateTime, self)._export(value, **kwargs)
        if show_time is None:
            show_time = self._show_time
        return lcg.LocalizableDateTime(result, show_weekday=show_weekday,
                                       show_time=show_time, leading_zeros=self._leading_zeros)

        
# We need three types, because we need to derive from two different base classes.

class Date(pytis.data.Date):
    """Pytis Date type which exports as a 'lcg.LocalizableDateTime'."""

    def __init__(self, leading_zeros=True, **kwargs):
        self._leading_zeros = leading_zeros
        super(Date, self).__init__(format='%Y-%m-%d', **kwargs)

    def locale_format(self, locale_data):
        return locale_data.date_format
        
    def _export(self, value, show_weekday=False, **kwargs):
        result = super(Date, self)._export(value, **kwargs)
        return lcg.LocalizableDateTime(result, show_weekday=show_weekday,
                                       leading_zeros=self._leading_zeros)

class Time(pytis.data.Time):
    """Pytis Time type which exports as a 'lcg.LocalizableTime'."""

    def __init__(self, exact=False, **kwargs):
        self._exact = exact
        format = '%H:%M'
        if exact:
            format += ':%S'
        super(Time, self).__init__(format=format, **kwargs)
    
    def locale_format(self, locale_data):
        if self._exact:
            return locale_data.exact_time_format
        else:
            return locale_data.time_format
        
    def _export(self, value, **kwargs):
        return lcg.LocalizableTime(super(Time, self)._export(value, **kwargs))


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

def send_mail(sender, addr, subject, text, html=None, smtp_server=None, lang=None,
              attachment=None, attachment_stream=None, attachment_type='application/octet-stream',
              cc=()):
    """Send a MIME e-mail message.

    Arguments:

      sender -- sender address as a string
      addr -- recipient address as a string
      subject -- message subject as a string or unicode
      text -- message text as a string or unicode
      html -- HTML part of the message as string or unicode
      smtp_server -- SMTP server name to use for sending the message as a
        string; if 'None', server given in configuration is used
      lang -- ISO language code as a string
      attachment -- name of the file to attach; if it is 'None', there is no
        attachment
      attachment_stream -- if not 'None' and 'attachment' is not 'None', read
        attachment data from the given stream
      attachment_type -- attachment MIME type as a string
      cc -- sequence of other recipient string addresses
      
    """
    string_class = type('')
    assert isinstance(sender, basestring)
    assert isinstance(addr, basestring)
    assert isinstance(subject, basestring)
    assert isinstance(text, basestring)
    assert html is None or isinstance(html, basestring)
    assert smtp_server is None or isinstance(smtp_server, string_class)
    assert lang is None or isinstance(lang, string_class)
    assert attachment is None or isinstance(attachment, basestring)
    assert attachment_stream is None or isinstance(attachment_stream, file)
    assert isinstance(attachment_type, string_class)
    assert isinstance(cc, (tuple, list,))
    import MimeWriter
    import mimetools
    from cStringIO import StringIO
    out = StringIO() # output buffer for our message 
    writer = MimeWriter.MimeWriter(out)
    tr = translator(lang)
    # Set up message headers.
    writer.addheader("From", sender)
    writer.addheader("To", addr)
    if cc:
        writer.addheader("Cc", string.join(cc, ', '))
    writer.addheader("Subject", email.Header.Header (tr.translate(subject), 'utf-8').encode())
    writer.addheader("Date", time.strftime("%a, %d %b %Y %H:%M:%S %z"))
    writer.addheader("MIME-Version", "1.0")
    # Start the multipart section (multipart/alternative seems to work better
    # on some MUAs than multipart/mixed).
    if attachment is None:
        multipart_type = 'alternative'
    else:
        multipart_type = 'mixed'
    writer.startmultipartbody(multipart_type)
    writer.flushheaders()
    # The plain text section.
    if isinstance(text, unicode):
        text = tr.translate(text).encode('utf-8')
    txtin = StringIO(text)
    subpart = writer.nextpart()
    subpart.addheader("Content-Transfer-Encoding", "quoted-printable")
    pout = subpart.startbody("text/plain", [("charset", 'utf-8')])
    mimetools.encode(txtin, pout, 'quoted-printable')
    txtin.close()
    # The html section.
    if html:
        if isinstance(html, unicode):
            html = tr.translate(html).encode('utf-8')
        htmlin = StringIO(html)
        subpart = writer.nextpart()
        subpart.addheader("Content-Transfer-Encoding", "quoted-printable")
        # Returns a file-like object we can write to.
        pout = subpart.startbody("text/html", [("charset", 'utf-8')])
        mimetools.encode(htmlin, pout, 'quoted-printable')
        htmlin.close()
    # The attachment section.
    if attachment is not None:
        subpart = writer.nextpart()
        subpart.addheader('Content-Transfer-Encoding', 'base64')
        subpart.addheader('Content-Disposition', 'attachment; filename=%s' % os.path.basename(attachment))
        if attachment_stream is None:
            attin = file(attachment)
        else:
            attin = attachment_stream
        pout = subpart.startbody(attachment_type)
        mimetools.encode(attin, pout, 'base64')
        attin.close()
    # Close the writer and send the message.
    writer.lastpart()
    addr_list = [addr]
    if cc:
        addr_list += cc
    if not smtp_server:
        smtp_server = cfg.smtp_server or 'localhost'
    try:
        import smtplib
        server = smtplib.SMTP(smtp_server)
        try:
            server.sendmail(sender, addr_list, out.getvalue())
        finally:
            out.close()
            server.quit()
        return None
    except Exception, e:
        return str(e)


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
    # TODO: The string passed to urllib.quote must be already encoded, but we don't know which
    # encoding will be used in the context, where the URI is used.  We just rely on the fact, thet
    # LCG uses UTF-8.
    uri = urllib.quote(base.encode('utf-8'))
    query = ';'.join([k +"="+ urllib.quote(unicode(v).encode('utf-8'))
                      for k, v in args + tuple(kwargs.items()) if v is not None])
    if query:
        uri += '?'+ query
    return uri

def translator(lang):
    if lang:
        return lcg.GettextTranslator(str(lang), path=cfg.translation_path, fallback=True)
    else:
        return lcg.NullTranslator()
