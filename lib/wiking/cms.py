# -*- coding: utf-8 -*-
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

"""Definition of Wiking CMS modules.

The modules defined here implement the Wiking web application interface.  The actual contents
served by these modules, as well as its structure and configuration, is stored in database and 
can be managed using a web browser through Wiking Management Interface.

"""

from wiking import *

import mx.DateTime
from pytis.presentation import Computer, CbComputer, Fields
from mx.DateTime import today, TimeDelta
from lcg import log as debug
import re, copy

CHOICE = pp.SelectionType.CHOICE
ALPHANUMERIC = pp.TextFilter.ALPHANUMERIC
LOWER = pp.PostProcess.LOWER
ONCE = pp.Editable.ONCE
NEVER = pp.Editable.NEVER
ALWAYS = pp.Editable.ALWAYS
ASC = pd.ASCENDENT
DESC = pd.DESCENDANT
now = lambda: mx.DateTime.now().gmtime()

_ = lcg.TranslatableTextFactory('wiking-cms')

_STRUCTURED_TEXT_DESCR = \
    _("The content should be formatted as LCG structured text. See the %(manual)s.",
      manual=('<a target="help" href="/_doc/lcg/data-formats/structured-text">' + \
              _("formatting manual") + "</a>"))

try:
    from mod_python.apache import import_module
except ImportError:
    # Make it work also for a standalone application.
    try:
        import wikingmodules
    except ImportError:
        def _module_dict():
            return globals()
    else:
        def _module_dict():
            return wikingmodules.__dict__
else:
    # Modules will be always reloaded in runtime when we are running a web application.
    def _module_dict():
        try:
            return import_module('wikingmodules').__dict__
        except ImportError:
            return import_module('wiking.cms').__dict__

def _modtitle(m, default=None):
    """Return a localizable module title by module name."""
    if m is None:
        return ''
    try:
        cls = _module_dict()[m]
    except:
        return default or concat(m,' (',_("unknown"),')')
    else:
        return cls.title()

def _modules(cls=None):
    if cls is None:
        cls = Module
    return [m for m in _module_dict().values()
            if type(m) == type(Module) and issubclass(m, Module) and issubclass(m, cls)]


class Roles(Roles):
    """CMS specific user roles."""
    
    CONTRIBUTOR = 'CONTRIBUTOR'
    """A user hwo has contribution privilegs for certain types of content."""
    AUTHOR = 'AUTHOR'
    """Any user who has the authoring privileges."""


class Application(CookieAuthentication, Application):
    
    _MAPPING = {'_doc': 'Documentation',
                '_wmi': 'WikingManagementInterface',
                '_css': 'Stylesheets'}

    _RIGHTS = {'Documentation': (Roles.ANYONE,),
               'SiteMap': (Roles.ANYONE,),
               'WikingManagementInterface': (Roles.AUTHOR, )}

    def resolve(self, req):
        try:
            return self._MAPPING[req.path[0]]
        except KeyError:
            return self._module('Mapping').resolve(req)
    
    def module_uri(self, modname):
        return self._module('Mapping').module_uri(modname) \
               or super(Application, self).module_uri(modname)
        
    def menu(self, req):
        module = req.wmi and 'WikingManagementInterface' or 'Menu'
        return self._module(module).menu(req)
    
    def panels(self, req, lang):
        if req.wmi:
            return ()
        else:
            return super(Application, self).panels(req, lang) + \
                   self._module('Panels').panels(req, lang)
        
    def configure(self, req):
        # TODO: This should be here as soon as req.wmi doesn't appear anywhere outside CMS.
        # req.wmi = False # Will be set to True by `WikingManagementInterface'.
        return self._module('Config').configure(req)
        
    def languages(self):
        return self._module('Languages').languages()
        
    def stylesheets(self):
        return [lcg.Stylesheet(name, uri='/_css/'+name)
                for name in self._module('Stylesheets').stylesheets()]

    def _auth_user(self, login):
        return self._module('Users').user(login)

    def _auth_check_password(self, user, password):
        return password == user.data()['password'].value()

    def authorize(self, req, module, action=None, record=None, **kwargs):
        if action and hasattr(module, 'RIGHTS_'+action):
            roles = getattr(module, 'RIGHTS_'+action)
        else:
            roles = self._RIGHTS.get(module.name(), ())
        if Roles.check(req, roles):
            return True
        elif Roles.OWNER in roles and isinstance(module, PytisModule) and record and req.user():
            return module.check_owner(req.user(), record)
        else:
            return False
    
    def _maybe_install(self, req, errstr):
        """Check a DB error string and try to set it up if it is the problem."""
        def _button(label, action='/', **params):
            return ('<form action="%s">' % action +
                    ''.join(['<input type="hidden" name="%s" value="%s">' % x
                             for x in params.items()]) +
                    '<input type="submit" value="%s">' % label +
                    '</form>')
        options = req.options()
        dboptions = dict([(k, options[k]) for k in
                          ('user', 'password', 'host', 'port') if options.has_key(k)])
        dboptions['database'] = dbname = options.get('database', req.server_hostname())
        if errstr == 'FATAL:  database "%s" does not exist\n' % dbname:
            if not req.param('createdb'):
                return 'Database "%s" does not exist.\n' % dbname + \
                       _button("Create", createdb=1)
            else:
                create = "CREATE DATABASE \"%s\" WITH ENCODING 'UTF8'" % dbname
                err = self._try_query(dboptions, create, autocommit=True, database='postgres')
                if err == 'FATAL:  database "postgres" does not exist\n':
                    err = self._try_query(dboptions, create, database='template1')
                if err is None:
                    return 'Database "%s" created.' % dbname + \
                           _button("Initialize", initdb=1)
                elif err == 'permission denied to create database\n':
                    return ('The database user does not have permission to create databases. '
                            'You need to create the database "%s" manually. ' % dbname +
                            'Login to the server as the database superuser (most often postgres) '
                            'and run the following command:'
                            '<pre>createdb %s -E UTF8</pre>' % dbname +
                            _button("Continue", initdb=1))
                else:
                    return 'Unable to create database: %s' % err
        elif errstr == 'Nen\xed mo\xbeno zjistit typ sloupce':
            if not req.param('initdb'):
                err = self._try_query(dboptions, "select * from mapping")
                if err:
                    return 'Database "%s" not initialized!' % dbname + \
                           _button("Initialize", initdb=1)
            else:
                script = ''
                for f in ('wiking.sql', 'init.sql'):
                    path = os.path.join(cfg.wiking_dir, 'sql', f)
                    if os.path.exists(path):
                        script += "".join(file(path).readlines())
                    else:
                        return ("File %s not found! " % path +
                                "Was Wiking installed properly? "
                                "Try setting-up wiking_dir in %s" %
                                cfg.config_file)
                err = self._try_query(dboptions, script)
                if not err:
                    return ("<p>Database initialized. " +
                            _button("Enter Wiking Management Interface", '/_wmi') + "</p>\n"
                            "<p>Please use the default login 'admin' with password 'wiking'.</p>"
                            "<p><em>Do not forget to change your password!</em></p>")
                else:
                    return "Unable to initialize the database: " + err
                
    def _try_query(self, dboptions, query, autocommit=False, database=None):
        import psycopg2 as dbapi
        try:
            if database is not None:
                dboptions['database'] = database
            conn = dbapi.connect(**dboptions)
            try:
                if autocommit:
                    from psycopg2 import extensions
                    conn.set_isolation_level(extensions.ISOLATION_LEVEL_AUTOCOMMIT)
                conn.cursor().execute(query)
                conn.commit()
            finally:
                conn.close()
        except dbapi.ProgrammingError, e:
            return e.args[0]

    def handle_exception(self, req, exception):
        if isinstance(exception, pd.DBException):
            try:
                if exception.exception() and exception.exception().args:
                    errstr = exception.exception().args[0]
                else:
                    errstr = exception.message()
                result = self._maybe_install(req, errstr)
                if result is not None:
                    return req.result(result)
            except:
                pass
        return super(Application, self).handle_exception(req, exception)


class WikingManagementInterface(Module, RequestHandler):
    """Wiking Management Interface.

    This module handles the WMI requestes by redirecting the request to the selected module.  The
    module name is part of the request URI.

    """
    SECTION_CONTENT = 'content'
    SECTION_USERS = 'users'
    SECTION_STYLE = 'style'
    SECTION_SETUP = 'setup'
    
    _SECTIONS = ((SECTION_CONTENT, _("Content"),
                  _("Manage the content available on your website.")),
                 (SECTION_STYLE,   _("Look &amp; Feel"),
                  _("Customize the appearance of your site.")),
                 (SECTION_USERS,   _("User Management"),
                  _("Manage registered users and their privileges.")),
                 (SECTION_SETUP,   _("Setup"),
                  _("Edit global properties of your web site.")),
                 )
    
    def _wmi_modules(self, modules, section):
        return [m for m in modules if hasattr(m, 'WMI_SECTION') and 
                getattr(m, 'WMI_SECTION') == section]
    
    def _wmi_order(self, module):
        if hasattr(module, 'WMI_ORDER'):
            return getattr(module, 'WMI_ORDER')
        else:
            return None
    
    def _handle(self, req):
        req.wmi = True # Switch to WMI only after successful authorization.
        if len(req.path) == 1:
            req.path += ('Menu',)
        try:
            module = self._module(req.path[1])
        except AttributeError:
            for section, title, descr in self._SECTIONS:
                if req.path[1] == section:
                    modules = self._wmi_modules(_modules(), section)
                    if modules:
                        modules.sort(lambda a, b: cmp(self._wmi_order(a), self._wmi_order(b)))
                        return req.redirect('/'+req.path[0]+'/'+modules[0].name())
            raise NotFound(req)
        else:
            return module.handle(req)

    def menu(self, req):
        modules = _modules()
        variants = self._application.languages()
        return [MenuItem(req.path[0] + '/' + section, title, descr=descr, variants=variants,
                         submenu=[MenuItem(req.path[0] + '/' + m.name(), m.title(),
                                           descr=m.descr(), order=self._wmi_order(m),
                                           variants=variants)
                                  for m in self._wmi_modules(modules, section)])
                for section, title, descr in self._SECTIONS] + \
               [MenuItem('__site_menu__', '', hidden=True, variants=variants,
                         submenu=self._module('Menu').menu(req))]
     

class Mappable(object):
    """Mix-in class for modules which may be mapped through the Mapping module.

    All modules able to handle requests should be available in module selection for a mapping item.
    Note that not all 'RequestHandler' subclasses may be mapped, since they may be only designed to
    handle requests in WMI.

    """
    pass


class CMSModule(PytisModule, RssModule, Panelizable):
    "Base class for all CMS modules."""
    RIGHTS_view = (Roles.ANYONE,)
    RIGHTS_list = (Roles.ANYONE,)
    RIGHTS_add    = RIGHTS_insert = (Roles.ADMIN,)
    RIGHTS_edit   = RIGHTS_update = (Roles.ADMIN,)
    RIGHTS_remove = RIGHTS_delete = (Roles.ADMIN,)
    RIGHTS_publish = RIGHTS_unpublish = (Roles.ADMIN,)
    RIGHTS_rss = (Roles.ANYONE,)

    def _form(self, form, req, *args, **kwargs):
        if req.wmi and form == pw.ListView:
            form = pw.BrowseForm # Disable list layout in WMI.
        return super(CMSModule, self)._form(form, req, *args, **kwargs)

    def _resolve(self, req):
        if req.wmi:
            if len(req.path) == 2: # or req.params.has_key('module'):
                if req.has_param(self._key):
                    return self._get_row_by_key(req.param(self._key))
                else:
                    return None
            elif len(req.path) == 3:
                return self._get_referered_row(req, req.path[2])
            else:
                raise NotFound()
        else:
            return super(CMSModule, self)._resolve(req)

    def _base_uri(self, req):
        if req.wmi:
            return '/_wmi/'+ self.name()
        else:
            return super(CMSModule, self)._base_uri(req)

class Mapping(CMSModule):
    """Map available URIs to the modules which handle them."""
    class Spec(Specification):
        title = _("Mapping")
        def fields(self): return (
            Field('mapping_id', editable=NEVER),
            Field('identifier', editable=NEVER),
            Field('modname', editable=NEVER),
            Field('private', editable=NEVER),
            )
    _mapping_cache = {}

    def resolve(self, req):
        identifier = req.path[0]
        try:
            # TODO: Caching here may prevent changes in `private' flag to take effect...
            modname, private = self._mapping_cache[identifier]
        except KeyError:
            row = self._data.get_row(identifier=identifier)
            if row is None:
                raise NotFound()
            #if not row['published'].value():
            #    raise Forbidden()
            self._mapping_cache[identifier] = modname, private = \
                                              row['modname'].value(), row['private'].value()
        if private and not (modname == 'Users' and req.param('action') in ('add', 'insert')):
            # We want to allow new user registration even if the user listing is private.
            # Unfortunately there seems to be no better solution than the terrible hack
            # above...  May be we should ask the module?
            if not Roles.check(req, (Roles.USER,)):
                if req.user():
                    raise AuthorizationError()
                else:
                    raise AuthenticationError()
        return modname
    
    def module_uri(self, modname):
        rows = self._data.get_rows(modname=modname) #, published=True)
        if len(rows) == 1:
            return '/'+ rows[0]['identifier'].value()
        else:
            return None


class Menu(Mapping, Publishable):
    class Spec(Mapping.Spec):
        title = _("Main menu")
        help = _("Manage main menu, available URIs and Wiking modules which handle them.")
        def fields(self): return (
            Field('menu_id'),
            Field('mapping_id'),
            Field('lang', _("Language"), editable=ONCE, codebook='Languages', value_column='lang'),
            Field('title_or_identifier', _("Title")),
            Field('title', _("Title"), not_null=True,
                  descr=_("Menu item title in the current language (switch language to supply "
                          "titles in other languages)")),
            Field('description', _("Description"), width=64,
                  descr=_("Brief description of this item.  The title is often very short, so it "
                          "might be appropriate to give additional information here.")),
            Field('published', _("Published"), default=True,
                  descr=_("Allows you to control the availability of this item in each of the "
                          "supported languages (switch language to control the availability in "
                          "other languages)")),
            Field('identifier', _("Identifier"), width=20, filter=ALPHANUMERIC, fixed=True,
                  type=pd.RegexString(maxlen=32, not_null=True, regex='^[a-zA-Z][0-9a-zA-Z_-]*$'),
                  descr=_("The identifier may be used to refer to this page from outside and also "
                          "from other pages. A valid identifier can only contain letters, digits, "
                          "dashes and underscores.  It must start with a letter.")),
            Field('parent', _("Parent item"), codebook='Mapping', not_null=False,
                  display='identifier', prefer_display=True),
            Field('modname', _("Module"), display=_modtitle, prefer_display=True,
                  selection_type=CHOICE, not_null=True,
                  enumerator=pd.FixedEnumerator([_m.name() for _m in _modules(Mappable)]),
                  descr=_("Select the module which handles requests for given identifier. "
                          "This is the way to make the module available from outside.")),
            Field('private', _("Private"), default=False,
                  descr=_("Make the item available only to logged-in users.")),
            Field('ord', _("Menu order"), width=6,
                  descr=_("Enter a number denoting the item order in the menu or leave the field "
                          "blank if you don't want this item to appear in the menu.")),
            Field('tree_order', _("Tree level"), type=pd.TreeOrder()),
            Field('owner', _("Owner"), codebook='Users', not_null=False),
            )
        layout = (FieldSet(_("Options for the current language"),
                           ('title', 'description', 'published')),
                  FieldSet(_("Global options"),
                           ('identifier', 'modname', 'parent', 'ord', 'private', 'owner')))
        columns = ('title_or_identifier', 'identifier', 'modname', 'parent', 'ord',
                   'published', 'private', 'owner')
        sorting = (('tree_order', ASC), ('identifier', ASC))
        bindings = {'Pages': pp.BindingSpec(_("Pages"), 'mapping_id')}
        cb = pp.CodebookSpec(display='identifier', prefer_display=True)
        def row_style(self, row):
            return not row['published'].value() and pp.Style(foreground='#777') or None
    _EXCEPTION_MATCHERS = (
        ('duplicate key violates unique constraint "_mapping_unique_tree_(?P<id>ord)er"',
         _("Duplicate menu order on the this tree level.")),) + \
         CMSModule._EXCEPTION_MATCHERS
    _LIST_BY_LANGUAGE = True
    _REFERER = 'identifier'

    WMI_SECTION = WikingManagementInterface.SECTION_CONTENT
    WMI_ORDER = 10

    def _link_provider(self, req, row, cid, **kwargs):
        if cid == 'parent':
            return None
        return super(Menu, self)._link_provider(req, row, cid, **kwargs)

    def menu(self, req):
        children = {None: []}
        translations = {}
        def mkitem(row):
            mapping_id, identifier = row['mapping_id'].value(), str(row['identifier'].value())
            titles, descriptions = translations[mapping_id]
            return MenuItem(identifier,
                            lcg.SelfTranslatableText(identifier, translations=titles),
                            descr=lcg.SelfTranslatableText('', translations=descriptions),
                            hidden=row['ord'].value() is None, variants=titles.keys(),
                            submenu=[mkitem(r) for r in children.get(mapping_id, ())])
        for row in self._data.get_rows(sorting=self._sorting, published=True):
            mapping_id = row['mapping_id'].value()
            if not translations.has_key(mapping_id):
                parent = row['parent'].value()
                if not children.has_key(parent):
                    children[parent] = []
                children[parent].append(row)
                translations[mapping_id] = ({}, {})
            titles, descriptions = translations[mapping_id]
            lang = str(row['lang'].value())
            titles[lang] = row['title_or_identifier'].value()
            if row['description'].value() is not None:
                descriptions[lang] = row['description'].value()
        return [mkitem(row) for row in children[None]]

class Config(CMSModule):
    """Site specific configuration provider.

    This implementation stores the configuration variables as one row in a
    Pytis data object to allow their modification through WMI.

    """
    class Spec(Specification):
        class _Field(Field):
            def __init__(self, name, **kwargs):
                o = cfg.option(name)
                Field.__init__(self, name, o.description(), descr=o.documentation(), **kwargs)
        title = _("Configuration")
        help = _("Edit site configuration.")
        fields = (
            Field('config_id', ),
            _Field('site_title', width=24),
            _Field('site_subtitle', width=64),
            _Field('webmaster_addr'),
            _Field('allow_login_panel'),
            _Field('allow_registration'),
            _Field('force_https_login'),
            #_Field('allow_wmi_link'),
            _Field('upload_limit'),
            Field('theme', _("Color theme"),
                  codebook='Themes', selection_type=CHOICE, not_null=False,
                  descr=_("Select one of the available color themes.  Use the module Themes in "
                          "the section Appearance to manage the available themes.")),
            )
        layout = ('site_title', 'site_subtitle', 'webmaster_addr', 'theme',
                  'allow_login_panel', 'allow_registration', 'force_https_login',
                  'upload_limit')
    _TITLE_TEMPLATE = _("Site Configuration")
    WMI_SECTION = WikingManagementInterface.SECTION_SETUP
    WMI_ORDER = 100
    _DEFAULT_THEME = cfg.theme

    def _resolve(self, req):
        # We always work with just one record.
        return self._data.get_row(config_id=0)
    
    def _default_action(self, req, **kwargs):
        return 'edit'
        
    def _redirect_after_update(self, req, record):
        return self.action_edit(req, record, msg=self._update_msg(record))
    
    def configure(self, req):
        cfg.allow_wmi_link = True
        row = self._data.get_row(config_id=0)
        if row is not None:
            for key in row.keys():
                if hasattr(cfg, key) and not key == 'theme':
                    setattr(cfg, key, row[key].value())
            # TODO: Don't recreate the theme if it has not changed...
            theme_id = row['theme'].value()
            if theme_id is not None:
                theme = self._module('Themes').theme(theme_id)
            else:
                theme = self._DEFAULT_THEME
            cfg.theme = theme
        if cfg.upload_limit is None:
            cfg.upload_limit = cfg.option('upload_limit').default()
    

class Panels(CMSModule, Publishable):
    class Spec(Specification):
        title = _("Panels")
        help = _(u"Manage panels – the small windows shown by the side of "
                 "every page.")
        fields = (
            Field('panel_id', width=5, editable=NEVER),
            Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                  selection_type=CHOICE, value_column='lang'),
            Field('ptitle', _("Title"), width=30,
                  descr=_(u"Panel title – you may leave the field blank to "
                          "use the menu title of the selected module.")),
            Field('mtitle'),
            Field('title', _("Title"), virtual=True, width=30,
                  computer=Computer(lambda row: row['ptitle'].value() or \
                                    row['mtitle'].value() or \
                                    _modtitle(row['modname'].value()),
                                    depends=('ptitle', 'mtitle', 'modname',))),
            Field('ord', _("Order"), width=5,
                  descr=_("Number denoting the order of the panel on the page.")),
            Field('mapping_id', _("Module"), width=5, not_null=False, codebook='Mapping',
                  display=lambda row: _modtitle(row['modname'].value()),
                  prefer_display=True, selection_type=CHOICE,
                  validity_condition=pd.NE('modname', pd.Value(pd.String(), 'Pages')),
                  descr=_("The items of the selected module will be shown by the panel. "
                          "Leave blank for a text content panel.")),
            Field('identifier', editable=NEVER),
            Field('modname'),
            Field('private'),
            Field('modtitle', _("Module"), virtual=True,
                  computer=Computer(lambda r: _modtitle(r['modname'].value()),
                                    depends=('modname',))),
            Field('size', _("Items count"), width=5,
                  descr=_("Number of items from the selected module, which "
                          "will be shown by the panel.")),
            Field('content', _("Content"), width=80, height=10,
                  descr=_("Additional text content displayed on the panel.")+\
                  ' '+_STRUCTURED_TEXT_DESCR),
            Field('published', _("Published"), default=True,
                  descr=_("Controls whether the panel is actually displayed."),
                  ),
            )
        sorting = (('ord', ASC),)
        columns = ('title', 'ord', 'modtitle', 'size', 'published', 'content')
        layout = ('ptitle', 'ord', 'mapping_id', 'size', 'content', 'published')
    _LIST_BY_LANGUAGE = True
    WMI_SECTION = WikingManagementInterface.SECTION_CONTENT
    WMI_ORDER = 1000

    def panels(self, req, lang):
        panels = []
        parser = lcg.Parser()
        for row in self._data.get_rows(lang=lang, published=True, sorting=self._sorting):
            if row['private'].value() is True and not Roles.check(req, (Roles.USER,)):
                continue
            panel_id = row['identifier'].value() or str(row['panel_id'].value())
            title = row['ptitle'].value() or row['mtitle'].value() or \
                    _modtitle(row['modname'].value())
            content = ()
            if row['modname'].value():
                mod = self._module(row['modname'].value())
                content = tuple(mod.panelize(req, lang, row['size'].value()))
            if row['content'].value():
                content += tuple(parser.parse(row['content'].value()))
            panels.append(Panel(panel_id, title, lcg.Container(content)))
        return panels
                
                
class Languages(CMSModule):
    """List all languages available for given site.

    This implementation stores the list of available languages in a Pytis data
    object to allow their modification through WMI.

    """
    class Spec(Specification):
        title = _("Languages")
        help = _("Manage available languages.")
        fields = (
            Field('lang_id'),
            Field('lang', _("Code"), width=2, column_width=6,
                  filter=ALPHANUMERIC, post_process=LOWER, fixed=True),
            Field('name', _("Name"), virtual=True,
                  computer=Computer(lambda r: lcg.language_name(r['lang'].value()), depends=())),
            )
        sorting = (('lang', ASC),)
        cb = pp.CodebookSpec(display=lcg.language_name, prefer_display=True)
        layout = ('lang',)
        columns = ('lang', 'name')
    _REFERER = 'lang'
    _TITLE_TEMPLATE = _('%(name)s')
    WMI_SECTION = WikingManagementInterface.SECTION_SETUP
    WMI_ORDER = 200

    def languages(self):
        return [str(r['lang'].value()) for r in self._data.get_rows()]

    
class Themes(CMSModule):
    class Spec(Specification):
        class _Field(Field):
            def __init__(self, id, label, descr=None):
                Field.__init__(self, id, label, descr=descr, type=pd.Color(),
                               dbcolumn=id.replace('-','_'))
        _FIELDS = (
            (_("Normal page colors"),
             (_Field('foreground', _("Text")),
              _Field('background', _("Background")),
              _Field('highlight-bg', _("Highlight background"),
                     descr=_("Background highlighting may be used for emphasizing the current "
                             "language, etc.")),
              _Field('link', _("Link")),
              _Field('link-visited', _("Visited link")),
              _Field('link-hover', _("Hover link"),
                     descr=_("Used for changing the link color when the user moves the mouse "
                             "pointer over it.")),
              _Field('border', _("Borders")))),
            (_("Heading colors"),
             (_Field('heading-fg', _("Text")),
              _Field('heading-bg', _("Background")),
              _Field('heading-line', _("Underline"),
                     descr=_("Heading colors are used for section headings, panel headings and "
                             "other heading-like elements.  Depending on stylesheets, some "
                             "heading types may be distinguished by a different background color "
                             "and others may be just underlined.")))),
            (_("Frames"),
             (_Field('frame-fg', _("Text")), 
              _Field('frame-bg', _("Background")),
              _Field('frame-border', _("Border"),
                     descr=_("Frames are generally used for distinguishing separate areas of the "
                             "page, such as forms, tables of contents, etc.  The usage may vary "
                             "by stylesheet.")))),
            (_("Page surrounding colors"),
             (_Field('top-fg', _("Text")),
              _Field('top-bg', _("Background")),
              _Field('top-border', _("Border"),
                     descr=_("What is 'page surrounding' depends from the stylesheet. "
                             "In general it is the part of the page, which does not include "
                             "the actual contents. Most often it is the page header and "
                             "footer which usually remain unchanged throughout the whole "
                             "website.")))),
            (_("Error messages"),
             (_Field('error-fg', _("Text")),
              _Field('error-bg', _("Background")),
              _Field('error-border', _("Border")))),
            (_("Informational messages"),
             (_Field('message-fg', _("Text")),
              _Field('message-bg', _("Background")),
              _Field('message-border', _("Border")))),
            (_("Buttons"),
             (_Field('button-fg', _("Text")),
              _Field('button', _("Background")),
              _Field('button-border', _("Border")),
              _Field('button-hover', _("Hover bg.")))),
            (_("Inactive buttons"),
             (_Field('button-inactive-fg', _("Text")),
              _Field('button-inactive', _("Background")),
              _Field('button-inactive-border', _("Border")))),
            (_("Record meta data"),
             (_Field('meta-fg', _("Text")),
              _Field('meta-bg', _("Background"),
                     descr=_("These colors are used for additional items printed listings, such "
                             "as date and author of a message in news, etc.")))),
            (_("Misc."),
             (_Field('table-cell', _("Table cell")),
              _Field('table-cell2', _("Shaded table cell")),
              _Field('help', _("Form help text")),
              _Field('inactive-folder', _("Inactive folder")))),
            )
        title = _("Color Themes")
        help = _("Manage available color themes. Go to Configuration to "
                 "change the currently used theme.")
        def fields(self):
            fields = [Field('theme_id'),
                      Field('name', _("Name"))]
            for label, group in self._FIELDS:
                fields.extend(group)
            return fields
        def layout(self):
            return ('name',) + tuple([FieldSet(label, [f.id() for f in fields])
                                      for label, fields in self._FIELDS])
        columns = ('name',)
        cb = pp.CodebookSpec(display='name', prefer_display=True)
    WMI_SECTION = WikingManagementInterface.SECTION_STYLE
    WMI_ORDER = 100

    def theme(self, theme_id):
        row = self._data.get_row(theme_id=theme_id)
        colors = [(c.id(), row[c.id()].value())
                  for c in Theme.COLORS if row[c.id()].value() is not None]
        return Theme(colors=dict(colors))


    
# ==============================================================================
# The modules below are able to handle requests directly.  
# The modules above are system modules used internally by Wiking.
# ==============================================================================

class Pages(CMSModule, Mappable):
    class Spec(Specification):
        title = _("Pages")
        help = _("Manage available pages of structured text content.")
        def fields(self): return (
            Field('page_id'),
            Field('mapping_id'),
            Field('identifier', _("Identifier"), editable=ONCE, not_null=True,
                  descr=_("The identifier may be used to refer to this page from outside and also "
                          "from other pages. A valid identifier can only contain letters, digits, "
                          "dashes and underscores.  It must start with a letter.")),
            Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                  selection_type=CHOICE, value_column='lang'),
            Field('title_or_identifier', _("Title")),
            Field('title', _("Title")),
            Field('description', _("Description")),
            Field('_content', _("Content"), compact=True, height=20, width=80,
                  descr=_STRUCTURED_TEXT_DESCR),
            Field('content'),
            Field('published'),
            Field('status', _("Status"), virtual=True,
                  computer=Computer(self._status, depends=('content', '_content'))),
            Field('tree_order', _("Tree level"), type=pd.TreeOrder()),
            Field('owner'),
            )
        def _status(self, row):
            if not row['published'].value():
                return _("Not published")
            if row['_content'].value() is None and row['content'].value() is None:
                return _("Missing")
            elif row['_content'].value() == row['content'].value():
                return _("Ok")
            else:
                return _("Changed")
        sorting = (('tree_order', ASC), ('identifier', ASC),)
        layout = ('identifier', 'title', '_content')
        columns = ('title_or_identifier', 'identifier', 'status')
        cb = pp.CodebookSpec(display='title_or_identifier', prefer_display=True)
        bindings = {'Attachments': pp.BindingSpec(_("Attachments"), 'page_id')}
    
    _REFERER = 'identifier'
    _REFERER_PATH_LEVEL = 1
    _EXCEPTION_MATCHERS = (
        ('duplicate key violates unique constraint "_pages_mapping_id_key"',
         _("The page already exists in given language.")),) + \
         CMSModule._EXCEPTION_MATCHERS
    _LIST_BY_LANGUAGE = True
    _RELATED_MODULES = ('Attachments',)
    _OWNER_COLUMN = 'owner'
    _SUPPLY_OWNER = False
    
    _SUBMIT_BUTTONS = ((_("Save"), None), (_("Save and publish"), 'commit'))
    _INSERT_MSG = _("New page was successfully created. Don't forget to publish it when you are "
                    "done. Please, visit the module 'Main menu' if you want to add the page to "
                    "the menu.")
    _ACTIONS = (Action(_("Publish"), 'commit',
                       descr=_("Publish the current modified content"),
                       enabled=lambda r: r['_content'].value() != r['content'].value()),
                Action(_("Revert"), 'revert',
                       descr=_("Revert last modifications"),
                       enabled=lambda r: r['_content'].value() != r['content'].value()),
                Action(_("Preview"), 'preview',
                       descr=_("Display the current version of the page"),
                       enabled=lambda r: r['_content'].value() is not None),
                Action(_("Translate"), 'translate',
                       descr=_("Create the content by translating another language variant"),
                       enabled=lambda r: r['_content'].value() is None),
                )
    RIGHTS_add = RIGHTS_insert = (Roles.AUTHOR,)
    RIGHTS_edit = RIGHTS_update = (Roles.AUTHOR, Roles.OWNER)
    WMI_SECTION = WikingManagementInterface.SECTION_CONTENT
    WMI_ORDER = 200

    def handle(self, req):
        if not req.wmi and len(req.path) == 2:
            return self._module('Attachments').handle(req)
        return super(Pages, self).handle(req)

    def _resolve(self, req):
        if req.wmi:
            return super(Pages, self)._resolve(req)
        if len(req.path) == 1:
            if req.has_param(self._key):
                return self._get_row_by_key(req.param(self._key))
            variants = self._data.get_rows(identifier=req.path[0], published=True)
            if variants:
                for lang in req.prefered_languages():
                    for row in variants:
                        if row['lang'].value() == lang:
                            return row
                raise NotAcceptable([str(r['lang'].value()) for r in variants])
            elif self._data.get_rows(identifier=req.path[0]):
                raise Forbidden()
        raise NotFound()

    def _validate(self, req, record):
        result = super(Pages, self)._validate(req, record)
        if result is None and req.params.has_key('commit'):
            if not (Roles.check(req, (Roles.ADMIN,)) or self.check_owner(req.user(), record)):
                return _("You don't have sufficient privilegs for this action.") +' '+ \
                       _("Save the page without publishing and ask the administrator to publish "
                         "your changes.")
            record['content'] = record['_content']
            record['published'] = pytis.data.Value(pytis.data.Boolean(), True)
        return result
        
    def _update_msg(self, record):
        if record['content'].value() == record['_content'].value():
            return super(Pages, self)._update_msg(record)
        else:
            return _("Page content was modified, however the changes remain unpublished. Don't "
                     "forget to publish the changes when you are done.")
    
    #def _redirect_after_insert(self, req, record):
        #if not req.wmi:
        #    return self.action_view(req, record, msg=self._insert_msg(record))
    def _redirect_after_update(self, req, record):
        if not req.wmi:
            return self.action_preview(req, record, msg=self._update_msg(record))
        else:
            return super(Pages, self)._redirect_after_update(req, record)

    def action_view(self, req, record, err=None, msg=None, preview=False):
        if req.wmi and not preview:
            return super(Pages, self).action_view(req, record, err=err, msg=msg)
        content = []
        # Main content
        if preview:
            text = record['_content'].value()
        else:
            text = record['content'].value()
        if text:
            content.append(lcg.SectionContainer(lcg.Parser().parse(text), toc_depth=0))
        # Attachment list
        attachments = self._module('Attachments').attachments(record)
        items = [(lcg.link(a.uri(), a.title()), ' ('+ a.bytesize() +') ',
                  lcg.WikiText(a.descr() or '')) for a in attachments if a.listed()]
        if items:
            content.append(lcg.Section(title=_("Attachments"), content=lcg.ul(items)))
        # Action menu
        actions = self._DEFAULT_ACTIONS_FIRST + self._ACTIONS[:-2]
        if req.wmi:
            actions += (Action(_("Back"), 'view'), self._DEFAULT_ACTIONS_LAST[1])
        content.append(self._action_menu(req, record, actions=actions, separate=True))
        return self._document(req, content, record, resources=attachments, err=err, msg=msg)

    def action_preview(self, req, record, **kwargs):
        return self.action_view(req, record, preview=True, **kwargs)
    RIGHTS_preview = (Roles.AUTHOR, Roles.OWNER)

    def action_translate(self, req, record):
        lang = req.param('src_lang')
        if not lang:
            if record['_content'].value() is not None:
                e = _("Content for this page already exists!")
                return self.action_view(req, record, err=e)
            cond = pd.AND(pd.NE('_content', pd.Value(pd.String(), None)),
                          pd.NE('lang', record['lang']))
            langs = [(str(row['lang'].value()), lcg.language_name(row['lang'].value())) for row in 
                     self._data.get_rows(mapping_id=record['mapping_id'].value(), condition=cond)]
            if not langs:
                e = _("Content for this page does not exist in any language.")
                return self.action_view(req, record, err=e)
            d = pw.SelectionDialog('src_lang', _("Choose source language"), langs,
                                   action='translate', hidden=\
                                   [(id, record[id].value()) for id in ('mapping_id', 'lang')])
            return self._document(req, d, record, subtitle=_("translate"))
        else:
            row = self._data.get_row(mapping_id=record['mapping_id'].value(),
                                     lang=str(req.params['src_lang']))
            for k in ('_content','title'):
                req.params[k] = row[k].value()
            return self.action_edit(req, record)
    RIGHTS_translate = (Roles.AUTHOR, Roles.OWNER)

    def action_commit(self, req, record):
        try:
            record.update(content=record['_content'].value(), published=True)
        except pd.DBException, e:
            kwargs = dict(err=self._analyze_exception(e))
        else:
            kwargs = dict(msg=_("The changes were published."))
        return self.action_view(req, record, **kwargs)
    RIGHTS_commit = (Roles.ADMIN, Roles.OWNER)

    def action_revert(self, req, record):
        try:
            record.update(_content=record['content'].value())
        except pd.DBException, e:
            kwargs = dict(err=self._analyze_exception(e))
        else:
            kwargs = dict(msg=_("The page contents was reverted to its previous state."))
        return self.action_view(req, record, **kwargs)
    RIGHTS_revert = (Roles.ADMIN, Roles.OWNER)
    
    
class Attachments(StoredFileModule, CMSModule):
    class Spec(StoredFileModule.Spec):
        title = _("Attachments")
        help = _("Manage page attachments. Go to a page to create new "
                 "attachments.")
        def fields(self):
            def fcomp(ffunc):
                def func(row):
                    f = row['file'].value()
                    return f is not None and ffunc(f) or None
                return pp.Computer(func, depends=('file',))
            return (
            Field('page_attachment_id',
                  computer=Computer(self._page_attachment_id, depends=('attachment_id', 'lang'))),
            Field('attachment_id'),
            Field('mapping_id', codebook='Mapping', editable=ONCE,
                  computer=Computer(self._mapping_id, depends=('page_id',))),
            Field('identifier'),
            Field('lang', _("Language"), codebook='Languages',
                  computer=Computer(self._lang, depends=('page_id',)),
                  selection_type=CHOICE, editable=ONCE, value_column='lang'),
            Field('page_id', _("Page"), codebook='Pages'),
            Field('file', _("File"), virtual=True, editable=ALWAYS,
                  type=pd.Binary(not_null=True, maxlen=cfg.upload_limit),
                  computer=self._file_computer('file', '_filename', origname='filename',
                                               mime='mime_type'),
                  descr=_("Upload a file from your local system.  The file name will be used "
                          "to refer to the attachment within the page content.  Please note, "
                          "that the file will be served over the internet, so the filename should "
                          "not contain any special characters.  Letters, digits, underscores, "
                          "dashes and dots are safe.  You risk problems with most other "
                          "characters.")),
            Field('filename', _("Filename"), computer=fcomp(lambda f: f.filename()),
                  type=pd.RegexString(maxlen=64, not_null=True, regex='^[0-9a-zA-Z_\.-]*$')),
            Field('mime_type', _("Mime-type"), width=22,
                  computer=fcomp(lambda f: f.type())),
            Field('title', _("Title"), width=30, maxlen=64,
                  descr=_("The name of the attachment (e.g. the full name of the document). "
                          "If empty, the file name will be used instead.")),
            Field('description', _("Description"), width=60, height=3, maxlen=240,
                  descr=_("Optional description used for the listing of attachments (see below).")),
            Field('ext', virtual=True, computer=Computer(self._ext, ('filename',))),
            Field('bytesize', _("Byte size"),
                  computer=fcomp(lambda f: pp.format_byte_size(len(f)))),
            Field('listed', _("Listed"), default=True,
                  descr=_("Check if you want the item to appear in the listing of attachments at "
                          "the bottom of the page.")),
            #Field('timestamp', type=DateTime()), #, default=now),
            # Fields supporting file storage.
            Field('dbname'),
            Field('_filename', virtual=True,
                  computer=self._filename_computer('dbname', 'attachment_id', 'ext')),
            )
        layout = ('file', 'title', 'description', 'listed')
        columns = ('filename', 'title', 'bytesize', 'mime_type', 'listed', 'page_id')
        sorting = (('identifier', ASC), ('filename', ASC))
        def _mapping_id(self, row):
            return row['page_id'].value() and int(row['page_id'].value().split('.')[0])
        def _lang(self, row):
            return row['page_id'].value() and str(row['page_id'].value().split('.')[1])
        def _ext(self, row):
            if row['filename'].value() is None:
                return ''
            ext = os.path.splitext(row['filename'].value())[1].lower()
            return len(ext) > 1 and ext[1:] or ext
        def _page_attachment_id(self, row):
            id = row['attachment_id'].value()
            if id is None:
                return None
            return '%d.%s' % (id, row['lang'].value())
    class Attachment(lcg.Resource):
        def __init__(self, row):
            file = row['filename'].export()
            uri = '/'+ row['identifier'].export() + '/'+ file
            title = row['title'].export() or file
            descr = row['description'].value()
            self._bytesize = row['bytesize'].export()
            self._listed = row['listed'].value()
            super(Attachments.Attachment, self).__init__(file, uri=uri,
                                                         title=title,
                                                         descr=descr)
        def bytesize(self):
            return self._bytesize
        def listed(self):
            return self._listed
    class Image(Attachment, lcg.Image):
        pass
            
    _STORED_FIELDS = (('file', '_filename'),)
    _REFERER = 'filename'
    _LIST_BY_LANGUAGE = True
    _SEQUENCE_FIELDS = (('attachment_id', '_attachments_attachment_id_seq'),)
    _RELATION_FIELDS = ('page_id',)
    _EXCEPTION_MATCHERS = (
        ('duplicate key violates unique constraint "_attachments_mapping_id_key"',
         _("Attachment of the same filename already exists for this page.")),)
    WMI_SECTION = WikingManagementInterface.SECTION_CONTENT
    WMI_ORDER = 220
    RIGHTS_add = RIGHTS_insert = (Roles.AUTHOR, Roles.OWNER)
    RIGHTS_edit = RIGHTS_update = (Roles.AUTHOR, Roles.OWNER)
    RIGHTS_remove = RIGHTS_delete = (Roles.AUTHOR, Roles.OWNER)
    
    def _link_provider(self, req, row, cid, **kwargs):
        if cid == 'file':
            return make_uri(self._base_uri(req) +'/'+ row['filename'].export(), download=1)
        return super(Attachments, self)._link_provider(req, row, cid, **kwargs)

    def _redirect_to_page(self, req, record):
        return req.redirect('/_wmi/Pages/' + record['identifier'].value())
        #m = self._module('Pages')
        #record = m.record(record['page_id'])
        #return m.action_view(req, record, msg=self._update_msg(record))
    def _redirect_after_insert(self, req, record):
        return self._redirect_to_page(req, record)
    def _redirect_after_delete(self, req, record):
        return self._redirect_to_page(req, record)
    def _redirect_after_update(self, req, record):
        return self._redirect_to_page(req, record)

    def _resolve(self, req):
        if req.wmi:
            if len(req.path) == 3 and req.has_param(self._key):
                row = self._data.get_row(**{self._key: req.param(self._key)})
                if row:
                    return row
            return super(Attachments, self)._resolve(req)
        else:
            if len(req.path) == 2:
                row = self._data.get_row(identifier=req.path[0], filename=req.path[1])
                if row:
                    return row
            raise NotFound()

    def attachments(self, page):
        def resource(row):
            if row['mime_type'].value().startswith('image/'):
                return self.Image(row)
            else:
                return self.Attachment(row)
        return [resource(row) for row in
                self._data.get_rows(mapping_id=page['mapping_id'].value(),
                                    lang=page['lang'].value())]
                
    def action_view(self, req, record, **kwargs):
        if req.wmi and not req.param('download'):
            return super(Attachments, self).action_view(req, record, **kwargs)
        else:
            return (str(record['mime_type'].value()), record['file'].value().buffer())

    
class News(CMSModule, Mappable):
    class Spec(Specification):
        title = _("News")
        help = _("Publish site news.")
        def fields(self): return (
            Field('news_id', editable=NEVER),
            Field('timestamp', _("Date"), width=19,
                  type=DateTime(not_null=True), default=now),
            Field('date', _("Date"), virtual=True,
                  computer=Computer(self._date, depends=('timestamp',)),
                  descr=_("Date of the news item creation.")),
            Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                  selection_type=CHOICE, value_column='lang'),
            Field('title', _("Briefly"), column_label=_("Message"), width=32,
                  descr=_("The item summary (title of the entry).")),
            Field('content', _("Text"), height=6, width=80,
                  descr=_STRUCTURED_TEXT_DESCR + ' ' + \
                  _("It is, however, recommened to use the simplest possible formatting, since "
                    "the item may be also published through an RSS channel, which does not "
                    "support formatting.")),
            Field('author', _("Author"), codebook='Users'),
            Field('date_title', virtual=True,
                  computer=Computer(self._date_title, depends=('date', 'title'))))
        sorting = (('timestamp', DESC),)
        columns = ('title', 'date', 'author')
        layout = ('timestamp', 'title', 'content')
        list_layout = pp.ListLayout('title', meta=('timestamp', 'author'),  content='content',
                                    anchor="item-%s")
        def _date(self, row):
            return row['timestamp'].export(show_time=False)
        def _date_title(self, row):
            return row['date'].export() +': '+ row['title'].value()
        
    _LIST_BY_LANGUAGE = True
    _OWNER_COLUMN = 'author'
    _PANEL_FIELDS = ('date', 'title')
    _RSS_TITLE_COLUMN = 'title'
    _RSS_DESCR_COLUMN = 'content'
    _RSS_DATE_COLUMN = 'timestamp'
    _RSS_AUTHOR_COLUMN = 'author'
    RIGHTS_add = RIGHTS_insert = (Roles.CONTRIBUTOR,)
    RIGHTS_edit = RIGHTS_update = (Roles.ADMIN, Roles.OWNER)
    RIGHTS_remove = RIGHTS_delete = (Roles.ADMIN,)
    WMI_SECTION = WikingManagementInterface.SECTION_CONTENT
    WMI_ORDER = 300
        
    def _link_provider(self, req, row, cid, target=None):
        if cid == 'title' and target is Panel or cid is None and target is RssModule:
            uri = self._base_uri(req)
            if uri:
                return uri + '#item-'+ row[self._referer].export()
            else:
                return None
        return super(News, self)._link_provider(req, row, cid, target=target)


class Planner(News):
    class Spec(News.Spec):
        title = _("Planner")
        help = _("Announce future events by date in a callendar-like listing.")
        def fields(self): return [
            Field('planner_id', editable=NEVER),
            Field('start_date', _("Date"), width=10,
                  type=Date(not_null=True, constraints=(self._check_date,)),
                  descr=_("The date when the planned event begins. Enter the date including year. "
                          "Example: %(date)s", date=lcg.LocalizableDateTime((now()+7).date))),
            Field('end_date', _("End date"), width=10, type=Date(),
                  descr=_("The date when the event ends if it is not the same as the start date "
                          "(for events which last several days).")),
            Field('date', _("Date"), virtual=True,
                  computer=Computer(self._date, depends=('start_date', 'end_date'))),
            Field('title', _("Briefly"), column_label=_("Event"), width=32,
                  descr=_("The event summary (title of the entry).")),
            ] + [f for f in super(Planner.Spec, self).fields() if f.id() in 
                 ('lang', 'content', 'author', 'timestamp', 'date_title')]
        sorting = (('start_date', ASC),)
        columns = ('title', 'date', 'author')
        layout = ('start_date', 'end_date', 'title', 'content')
        list_layout = pp.ListLayout('date_title', meta=('author', 'timestamp'), content='content',
                                    anchor="item-%s")

        def _check_date(self, date):
            if date < today():
                return _("Date in the past")
        def _date(self, row):
            d = row['start_date'].export(show_weekday=True)
            if row['end_date'].value():
                d += ' - ' + row['end_date'].export(show_weekday=True)
            return d
        def check(self, row):
            end = row['end_date'].value()
            if end and end <= row['start_date'].value():
                return ("end_date", _("End date precedes start date"))
    _RSS_TITLE_COLUMN = 'date_title'
    _RSS_DATE_COLUMN = None
    def _condition(self, req, **kwargs):
        scondition = super(Planner, self)._condition(req, **kwargs)
        condition = pd.OR(pd.GE('start_date', pd.Value(pd.Date(), today())),
                          pd.GE('end_date', pd.Value(pd.Date(), today())))
        if scondition:
            return pd.AND(scondition, condition)
        else:
            return condition

    
class Images(StoredFileModule, CMSModule, Mappable):
    class Spec(StoredFileModule.Spec):
        title = _("Images")
        help = _("Publish images.")
        def fields(self):
            def fcomp(ffunc):
                def func(row):
                    f = row['file'].value()
                    return f is not None and ffunc(f) or None
                return pp.Computer(func, depends=('file',))
            def imgcomp(imgfunc):
                return fcomp(lambda f: imgfunc(f.image()))
            return (
            Field('image_id'),
            Field('published'),
            Field('file', _("File"), virtual=True, editable=ALWAYS,
                  type=pd.Image(not_null=True, maxlen=cfg.upload_limit, maxsize=(3000, 3000)),
                  computer=self._file_computer('file', '_filename', origname='filename')),
            Field('image', virtual=True, editable=ALWAYS,
                  type=pd.Image(not_null=True, maxlen=cfg.upload_limit, maxsize=(3000, 3000)),
                  computer=self._file_computer('image', '_image_filename',
                                               compute=lambda r: self._resize(r, (800, 800)))),
            Field('thumbnail', virtual=True, type=pd.Image(),
                  computer=self._file_computer('thumbnail', '_thumbnail_filename',
                                               compute=lambda r: self._resize(r, (130, 130)))),
            Field('filename', _("File"), computer=fcomp(lambda f: f.filename())),
            Field('title', _("Title"), width=30),
            Field('author', _("Author"), width=30),
            Field('location', _("Location"), width=50),
            Field('description', _("Description"), width=60, height=5),
            Field('taken', _("Date of creation"), type=DateTime()),
            Field('format', computer=imgcomp(lambda i: i.format.lower())),
            Field('width', _("Width"), computer=imgcomp(lambda i: i.size[0])),
            Field('height', _("Height"), computer=imgcomp(lambda i: i.size[1])),
            Field('size', _("Pixel size"), computer=imgcomp(lambda i: '%dx%d' % i.size)),
            Field('bytesize', _("Byte size"),
                  computer=fcomp(lambda f: pp.format_byte_size(len(f)))),
            Field('exif'),
            Field('timestamp', default=now),
            # Fields supporting image file storage.
            Field('dbname'),
            Field('_filename', virtual=True, computer=self._filename_computer('-orig')),
            Field('_thumbnail_filename', virtual=True,
                  computer=self._filename_computer('-thumbnail')),
            Field('_image_filename', virtual=True, computer=self._filename_computer()),
            )
        def _filename_computer(self, append=''):
            args = ('dbname', 'image_id', 'format', append)
            return super(Images.Spec, self)._filename_computer(*args)
        def _resize(self, row, size):
            # We use the lazy get to prevent running the computer.  This allows
            # us to find out, whether a new file was uploaded and prevents
            # loading the value from file.
            file = row.get('file', lazy=True).value()
            if file is not None and file.path() is None:
                # Recompute the value by resizing the original image.
                from PIL.Image import ANTIALIAS
                from cStringIO import StringIO
                img = copy.copy(file.image())
                log(OPR, "Generating a thumbnail:", (img.size, size))
                img.thumbnail(size, ANTIALIAS)
                stream = StringIO()
                img.save(stream, img.format)
                return pd.Image.Buffer(buffer(stream.getvalue()))
            else:
                # The image will be loaded from file.
                return None

        layout = ('file', 'title', 'author', 'location', 'taken', 'description')
        columns = ('filename', 'title', 'author', 'location', 'taken', 'description')
        
    _STORED_FIELDS = (('file', '_filename'),
                      ('image', '_image_filename'),
                      ('thumbnail', '_thumbnail_filename'))
    _SEQUENCE_FIELDS = (('image_id', '_images_image_id_seq'),)
    _REFERER = 'filename'
    
    #WMI_SECTION = WikingManagementInterface.SECTION_CONTENT
    WMI_ORDER = 500
        
    def _link_provider(self, req, row, cid, **kwargs):
        if cid == 'file':
            return make_uri(self._base_uri(req) +'/'+ row['filename'].export(), action='orig')
        return super(Images, self)._link_provider(req, row, cid, **kwargs)
    
    def _image_provider(self, req, row, cid, **kwargs):
        if cid == 'file':
            return make_uri(self._base_uri(req) +'/'+ row['filename'].export(), action='thumbnail')
        return super(Images, self)._link_provider(req, row, cid, **kwargs)

    def _image(self, record, id):
        mime = "image/" + str(record['format'].value())
        data = record[id].value().buffer()
        return (mime, data)
    
    RIGHTS_orig = RIGHTS_image = RIGHTS_thumbnail = (Roles.ANYONE,)
    
    def action_orig(self, req, record):
        return self._image(record, 'file')
    
    def action_image(self, req, record):
        return self._image(record, 'image')
    
    def action_thumbnail(self, req, record):
        return self._image(record, 'thumbnail')


class SiteMap(Module, RequestHandler, Mappable):

    @classmethod
    def title(cls):
        return _("Site Map")
    
    def _handle(self, req):
        return Document(self.title(), lcg.RootIndex(depth=99))

        
class Stylesheets(CMSModule, Stylesheets):
    class Spec(Specification):
        title = _("Stylesheets")
        help = _("Manage available Cascading Stylesheets.")
        fields = (
            Field('stylesheet_id'),
            Field('identifier',  _("Identifier"), width=16),
            Field('active',      _("Active")),
            Field('description', _("Description"), width=40),
            Field('content',     _("Content"), height=20, width=80),
            )
        layout = ('identifier', 'active', 'description', 'content')
        columns = ('identifier', 'active', 'description')
    _REFERER = 'identifier'
    WMI_SECTION = WikingManagementInterface.SECTION_STYLE
    WMI_ORDER = 200

    def stylesheets(self):
        return [r['identifier'].value() for r in self._data.get_rows(active=True)]
        
    def action_view(self, req, record, **kwargs):
        if req.wmi:
            return super(Stylesheets, self).action_view(req, record, **kwargs)
        else:
            content = record['content'].value() or self._find_file(record['identifier'].value())
            return ('text/css', self._substitute(content))


class _Users(CMSModule):
    class Spec(Specification):
        title = _("Users")
        help = _("Manage registered users.  Use the module 'Access Rights' "
                 "to change their privileges.")
        def _fullname(self, row):
            name = row['firstname'].value()
            surname = row['surname'].value()
            if name and surname:
                return name + " " + surname
            else:
                return name or surname or row['login'].value()
        def _user(self, row):
            nickname = row['nickname'].value()
            if nickname:
                return nickname
            else:
                return row['fullname'].value()
        def fields(self): return (
            Field('uid', width=8, editable=NEVER),
            Field('login', _("Login name"), width=16,
                  type=pd.RegexString(maxlen=16, not_null=True,
                                      regex='^[a-zA-Z][0-9a-zA-Z_\.-]*$'),
                  descr=_("A valid login name can only contain letters, "
                          "digits, underscores, dashes and dots and must "
                          "start with a letter.")),
            Field('password', _("Password"), width=16,
                  type=pd.Password(minlen=4, maxlen=32, not_null=True),
                  descr=_("Please write the new password into each of the two fields.  Leave both "
                          "fields blank if you are editing an existing account and don't want to "
                          "change the password.")),
            Field('fullname', _("Full Name"), virtual=True, editable=NEVER,
                  computer=Computer(self._fullname, depends=('firstname','surname','login'))),
            Field('user', _("User"), dbcolumn='user_',
                  computer=Computer(self._user, depends=('fullname', 'nickname'))),
            Field('firstname', _("First name")),
            Field('surname', _("Surname")),
            Field('nickname', _("Nickname")),
            Field('email', _("E-mail"), width=36),
            Field('phone', _("Phone")),
            Field('address', _("Address"), height=3),
            Field('uri', _("URI"), width=36),
            Field('since', _("Registered since"), type=DateTime(show_time=False), default=now,
                  style=lambda r: not r['enabled'].value() and pp.Style(overstrike=True) or None),
            Field('enabled', _("Enabled")),
            Field('contributor', _("Contribution privileges")),
            Field('author', _("Authoring privileges")),
            Field('admin', _("Admin privileges")),
            Field('session_expire'),
            Field('session_key'),
            )
        columns = ('fullname', 'nickname', 'email', 'since')
        sorting = (('surname', ASC), ('firstname', ASC))
        layout = (FieldSet(_("Personal data"),
                           ('firstname', 'surname', 'nickname')),
                  FieldSet(_("Contact information"),
                           ('email', 'phone', 'address', 'uri')),
                  FieldSet(_("Login information"), ('login', 'password')))
        cb = pp.CodebookSpec(display='user', prefer_display=True)
    _REFERER = 'login'
    _PANEL_FIELDS = ('fullname',)
    _ALLOW_TABLE_LAYOUT_IN_FORMS = False
    _OWNER_COLUMN = 'uid'
    _SUPPLY_OWNER = False
    RIGHTS_add = RIGHTS_insert = (Roles.ANYONE,)
    RIGHTS_edit = RIGHTS_update = (Roles.ADMIN, Roles.OWNER)
    RIGHTS_remove = RIGHTS_delete = (Roles.ADMIN,) #, Roles.OWNER)

    def _actions(self, req, record):
        if not req.wmi:
            if record:
                actions = (Action(_("Edit your profile"), 'edit', descr=_("Modify your record")),
                        Action(_("Remove"), 'remove', descr=_("Remove the user permanently")))
                if not record['enabled'].value():
                    actions = (Action(_("Enable"), 'enable', descr=_("Enable this account")),) + \
                              actions
                return actions
            else:
                return (Action(_("Register"), 'add', context=None,
                               descr=_("New user registration")),)
        return super(_Users, self)._actions(req, record)
        
    def _redirect_after_insert(self, req, record):
        content = lcg.p(_("Registration completed successfuly. "
                          "Your account now awaits administrator's approval."))
        msg, err = None, None
        addr = cfg.webmaster_addr or cfg.bug_report_address
        if addr:
            text = _("New user %(fullname)s registered at %(server_hostname)s. "
                     "Please approve the account: %(uri)s",
                     fullname=record['fullname'].value(), server_hostname=req.server_hostname(),
                     uri=req.abs_uri()+'/'+record['login'].value())
            err = send_mail('wiking@' + req.server_hostname(), addr,
                            'New user registration: ' + record['fullname'].value(),
                            translator('en').translate(text),
                            smtp_server=cfg.smtp_server)
            if err:
                err = _("Failed sending e-mail notification:") +' '+ err
            else:
                msg = _("E-mail notification has been sent to server administrator.")
        return self._document(req, content, subtitle=_("Registration"), msg=msg, err=err)

    def action_enable(self, req, record):
        err, msg = None, None
        try:
            record.update(enabled=True)
        except pd.DBException, e:
            err=self._analyze_exception(e)
        else:
            # TODO: Send notification also from the Rights module...
            msg = _("The account was enabled.")
            text = _("Your account at %(uri)s has been enabled. "
                     "Please log in with username '%(login)s' and your password.",
                     uri=req.abs_uri()[:-len(req.uri)], login=record['login'].value())
            err = send_mail('wiking@' + req.server_hostname(), record['email'].value(),
                            _("Your account has been ebabled."),
                            translator('en').translate(text),
                            smtp_server=cfg.smtp_server)
            if err:
                err = _("Failed sending e-mail notification:") +' '+ err
            else:
                msg += ' '+ _("E-mail notification has been sent to %s." % record['email'].value())
        return self.action_view(req, record, msg=msg, err=err)
    RIGHTS_enable = (Roles.ADMIN,)
    
        
class Users(_Users, Mappable):
    
    WMI_SECTION = WikingManagementInterface.SECTION_USERS
    WMI_ORDER = 100
    
    def registration_uri(self, req):
        uri = self._base_uri(req)
        return uri and make_uri(uri, action='add') or None

    def user(self, login):
        record = self._record(self._data.get_row(login=login))
        if record:
            roles = [role for role, keys in ((Roles.USER, ('enabled',)),
                                             (Roles.CONTRIBUTOR, ('contributor','author','admin')),
                                             (Roles.AUTHOR, ('author','admin')),
                                             (Roles.ADMIN, ('admin',)))
                     if record['enabled'].value() and True in [record[k].value() for k in keys]]
            return User(login, name=record['user'].value(), uid=record['uid'].value(),
                        roles=roles, data=record)
        else:
            return None


class Rights(_Users):
    class Spec(_Users.Spec):
        title = _("Access Rights")
        help = _("Manage access rights of registered users.")
        layout = ('enabled', 'contributor', 'author', 'admin')
        columns = ('user', 'login', 'enabled', 'contributor', 'author','admin')
        table = 'users'
    _ALLOW_TABLE_LAYOUT_IN_FORMS = True
    RIGHTS_add = RIGHTS_insert = ()
    RIGHTS_edit = RIGHTS_update = (Roles.ADMIN,)
    RIGHTS_remove = ()
    WMI_SECTION = WikingManagementInterface.SECTION_USERS
    WMI_ORDER = 200

    
class Session(_Users, Session):
    class Spec(_Users.Spec):
        table = 'users'

    def init(self, user):
        session_key = self._new_session_key()
        user.data().update(session_expire=self._expiration(), session_key=session_key)
        return session_key
        
    def check(self, user, session_key):
        record = user.data()
        if not self._expired(record['session_expire'].value()):
            record.update(session_expire=self._expiration())
            return True
        else:
            return False

    def close(self, user):
        user.data().update(session_expire=None, session_key=None)
        
