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

"""Definition of core Wiking modules."""

from wiking import *

import mx.DateTime
from pytis.presentation import Computer, CbComputer
from mx.DateTime import today, TimeDelta
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
MB = 1024**2

_ = lcg.TranslatableTextFactory('wiking')

_STRUCTURED_TEXT_DESCR = \
    _("The content should be formatted as LCG structured text. See the %(manual)s.",
      manual=('<a target="_new" href="/_doc/lcg/data-formats/structured-text">' + \
              _("formatting manual") + "</a>"))

def _modtitle(m):
    """Return a localizable module title by module name."""
    if m is None:
        return ''
    try:
        cls = get_module(m)
    except:
        return concat(m,' (',_("unknown"),')')
    else:
        return cls.title()

def _modules(cls=None):
    if cls is None:
        cls = Module
    return [m for m in import_modules().__dict__.values()
            if type(m) == type(Module) and issubclass(m, Module) and issubclass(m, cls)]

class Mappable(object):
    """Mix-in class for modules which may be mapped through the Mapping module.

    All modules able to handle requests should be available in module selection for a mapping item.
    Note that not all 'RequestHandler' subclasses may be mapped, since they may be only designed to
    handle requests in WMI.

    """

class WikingManagementInterface(Module):
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
    
    def _wmi_modules(self, section):
        return [m for m in _modules() if hasattr(m, 'WMI_SECTION') and 
                getattr(m, 'WMI_SECTION') == section]
    
    def _wmi_order(self, module):
        if hasattr(module, 'WMI_ORDER'):
            return getattr(module, 'WMI_ORDER')
        else:
            return None
    
    def handle(self, req):
        Roles.check(req, (Roles.ADMIN,))
        req.wmi = True # Switch to WMI only after successful authorization.
        if len(req.path) == 1:
            req.path += ('Mapping',)
        try:
            module = self._module(req.path[1])
        except AttributeError:
            for section, title, descr in self._SECTIONS:
                if req.path[1] == section:
                    modules = self._wmi_modules(section)
                    if modules:
                        modules.sort(lambda a, b: cmp(self._wmi_order(a), self._wmi_order(b)))
                        return req.redirect('/'+req.path[0]+'/'+modules[0].name())
            raise NotFound(req)
        else:
            return module.handle(req)

    def menu(self, req):
        if not req.wmi:
            return super(WikingManagementInterface, self).menu(req)
        return [MenuItem(req.path[0] + '/' + section, title, descr=descr,
                         submenu=[MenuItem(req.path[0] + '/' + m.name(), m.title(),
                                           descr=m.descr(), order=self._wmi_order(m))
                                  for m in self._wmi_modules(section)])
                for section, title, descr in self._SECTIONS]

    def panels(self, req, lang):
        if req.wmi:
            return []
        else:
            return super(WikingManagementInterface, self).panels(req, lang)

class DocumentHandler(Module, RequestHandler):
    _BASE_DIR = None
    
    def _document(self, req, basedir, path):
        if not os.path.exists(basedir):
            raise Exception("Directory %s does not exist" % basedir)
        import glob, codecs
        # TODO: the documentation should be processed by LCG first into some
        # reasonable output format.  Now we just search the file in all the
        # source directories and format it.  No global navigation is used.
        for subdir in ('', 'user', 'admin'):
            basename = os.path.join(basedir, subdir, *path)
            variants = [f[-6:-4] for f in glob.glob(basename+'.*.txt')]
            if variants:
                break
        else:
            raise NotFound()
        lang = req.prefered_language(variants)
        filename = '.'.join((basename, lang, 'txt'))
        f = codecs.open(filename, encoding='utf-8')
        text = "".join(f.readlines())
        f.close()
        content = lcg.Parser().parse(text)
        if len(content) == 1 and isinstance(content[0], lcg.Section):
            title = content[0].title()
            content = lcg.SectionContainer(content[0].content(), toc_depth=0)
        else:
            title = ' :: '.join(path)
        return Document(title, content, lang=lang, variants=variants)
        
    def handle(self, req):
        return self._document(req, self._BASE_DIR, req.path)
        

class Documentation(DocumentHandler):
    """Serve the on-line documentation.

    This module is not bound to a data object.  It only serves the on-line documentation from files
    on the disk.

    """
    def handle(self, req):
        path = req.path[1:]
        if path and path[0] == 'lcg':
            path = path[1:]
            basedir = lcg.config.doc_dir
        else:
            basedir = os.path.join(cfg.wiking_dir, 'doc', 'src')
        return self._document(req, basedir, req.path[1:])

    def menu(self, req):
        return ()

    def panels(self, req, lang):
        return []


class MappingParents(WikingModule):
    """An auxiliary module for the codebook of mapping parent nodes."""
    class Spec(Specification):
        table = 'mapping'
        fields = (
            Field('mapping_id'),
            Field('identifier'),
            Field('tree_order'),
            )
        sorting = (('tree_order', ASC), ('identifier', ASC))
        cb = pp.CodebookSpec(display='identifier')


class Mapping(WikingModule, Publishable, Mappable):
    """Map available URIs to the modules which handle them.

    The Wiking Handler always queries this module to resolve the request URI and return the name of
    the module which is responsible for handling the request.  Futher processing of the request is
    then postponed to this module.  Only a part of the request uri may be used to determine the
    module and another part may be used by the module to determine the sub-contents.

    This implementation uses static mapping as well as database based mapping, which may be
    modified through the Wiking Management Interface.

    """
    class Spec(Specification):
        title = _("Mapping")
        help = _("Manage available URIs and Wiking modules which handle them. "
                 "Also manage the main menu.")
        def _level(self, row):
            return len(row['tree_order'].value().split('.')) - 2
        def fields(self): return (
            Field('mapping_id', width=5, editable=NEVER),
            Field('parent', _("Parent item"), codebook='MappingParents', not_null=False,
                  ), #(validity_condition=pd.NE('name', pd.Value(pd.String(), ))),
            Field('identifier', _("Identifier"), width=20, filter=ALPHANUMERIC, fixed=True,
                  type=pd.RegexString(maxlen=32, not_null=True, regex='^[a-zA-Z][0-9a-zA-Z_-]*$'),
                  descr=_("The identifier may be used to refer to this page from outside and also "
                          "from other pages. A valid identifier can only contain letters, digits, "
                          "dashes and underscores.  It must start with a letter.")),
            Field('modname', _("Module"), display=_modtitle, selection_type=CHOICE, 
                  enumerator=pd.FixedEnumerator([_m.name() for _m in _modules(Mappable)]),
                  descr=_("Select the module which handles requests for given identifier. "
                          "This is the way to make the module available from outside.")),
            Field('published', _("Published"),
                  descr=_("This flag allows you to make the item unavailable without actually "
                          "removing it.")),
            Field('private', _("Private"), default=False,
                  descr=_("Make the item available only to logged-in users.")),
            Field('ord', _("Menu order"), width=6,
                  descr=_("Enter a number denoting the item order in the menu or leave the field "
                          "blank if you don't want this item to appear in the menu.")),
            Field('tree_order'),
            Field('level', _("Identifier"), virtual=True,
                  computer=Computer(self._level, depends=('tree_order',))),
            )
        sorting = (('tree_order', ASC), ('identifier', ASC))
        bindings = {'Pages': pp.BindingSpec(_("Pages"), 'mapping_id')}
        columns = ('identifier', 'modname', 'published', 'private', 'ord')
        layout = ('identifier', 'parent', 'modname', 'published', 'private', 'ord')
        cb = pp.CodebookSpec(display='identifier')
    _REFERER = 'identifier'
    _TREE_LEVEL_COLUMN = 'level'
    _EXCEPTION_MATCHERS = (
        ('duplicate key violates unique constraint "_mapping_unique_tree_(?P<id>ord)er"',
         _("Duplicate menu order on the this tree level.")),) + \
         WikingModule._EXCEPTION_MATCHERS

    _STATIC_MAPPING = {'_doc': 'Documentation',
                       '_wmi': 'WikingManagementInterface'}
    _REVERSE_STATIC_MAPPING = dict([(v,k) for k,v in _STATIC_MAPPING.items()])
    WMI_SECTION = WikingManagementInterface.SECTION_CONTENT
    WMI_ORDER = 10
    _mapping_cache = {}

    def _link_provider(self, req, row, cid, **kwargs):
        if req.wmi and cid == 'modtitle':
            return '/_wmi/' + row['modname'].value()
        return super(Mapping, self)._link_provider(req, row, cid, **kwargs)

    def action_list(self, req, **kwargs):
        if not req.wmi:
            return self._document(req, SiteMap(depth=99))
        else:
            return super(Mapping, self).action_list(req, **kwargs)
    
    def resolve(self, req):
        "Return the name of the module responsible for handling the request."
        identifier = req.path[0]
        try:
            modname = self._STATIC_MAPPING[identifier]
        except KeyError:
            # TODO: Caching here may prevent changes in `private' flag to take
            # effect...
            try:
                modname, private = self._mapping_cache[identifier]
            except KeyError:
                row = self._data.get_row(identifier=identifier)
                if row is None:
                    raise NotFound()
                if not row['published'].value():
                    raise Forbidden()
                self._mapping_cache[identifier] = modname, private = \
                                                  row['modname'].value(), row['private'].value()
            if private and not (modname == 'Users' and \
                                req.param('action') in ('add', 'insert')):
                # We want to allow new user registration even if the user listing is private.
                # Unfortunately there seems to be no better solution than the terrible hack
                # above...  May be we should ask the module?
                Roles.check(req, (Roles.USER,))
        return modname
    
    def get_identifier(self, modname):
        """Return the current identifier for given module name.

        None will be returned when there is no mapping item for the module, or when there is more
        than one item for the same module (which is also legal).
        
        """
        rows = self._data.get_rows(modname=modname, published=True)
        if len(rows) == 1:
            return rows[0]['identifier'].value()
        return self._REVERSE_STATIC_MAPPING.get(modname)
    
    def menu(self, req):
        """Return the menu hierarchy.

        Arguments:
        
          req -- the current request object.
        
        Returns a sequence of 'MenuItem' instances.
        
        """
        children = {None: []}
        titles = self._module('Titles')
        def mkitem(row):
            mapping_id = row['mapping_id'].value()
            identifier = str(row['identifier'].value())
            return MenuItem(identifier, titles.menu_title(mapping_id, identifier),
                            hidden=row['ord'].value() is None,
                            submenu=[mkitem(r) for r in children.get(mapping_id, ())])
        for row in self._data.get_rows(sorting=self._sorting, published=True):
            parent = row['parent'].value()
            try:
                target = children[parent]
            except KeyError:
                target = children[parent] = []
            target.append(row)
        return [mkitem(row) for row in children[None]]
                
    def modtitle(self, modname):
        """Return localizable module title for given module name."""
        row = self._data.get_row(modname=modname)
        if row:
            return self._module('Titles').menu_title(row['mapping_id'].value(),
                                                     _modtitle(modname))
        else:
            return _modtitle(modname)


class Config(WikingModule):
    """Site specific configuration provider.

    This implementation stores the configuration variables as one row in a
    Pytis data object to allow their modification through WMI.

    """
    class Spec(Specification):
        title = _("Config")
        help = _("Edit site configuration.")
        fields = (
            Field('config_id', ),
            Field('title', virtual=True,
                  computer=Computer(lambda r: _("Site Configuration"), depends=())),
            Field('site_title', _("Site title"), width=24),
            Field('site_subtitle', _("Site subtitle"), width=64),
            Field('login_panel',  _("Show login panel")),
            Field('allow_registration', _("Allow registration"), default=True),
            #Field('allow_wmi_link', _("Allow WMI link"), default=True),
            Field('force_https_login', _("Force HTTPS login"), default=False),
            Field('webmaster_addr', _("Webmaster address")),
            Field('theme', _("Theme"), codebook='Themes', selection_type=CHOICE, not_null=False),
            )
        layout = ('site_title', 'site_subtitle', 'login_panel', 'allow_registration',
                  'force_https_login', 'webmaster_addr', 'theme')
    _TITLE_COLUMN = 'title'
    WMI_SECTION = WikingManagementInterface.SECTION_SETUP
    WMI_ORDER = 100

    class Configuration(object):
        """Site-specific configuration class."""
        site_title = 'Wiking site'
        site_subtitle = None
        allow_wmi_link = True
        allow_login_ctrl = True
	allow_registration = True
        login_panel = False
        webmaster_addr = None
	force_https_login = False
        exporter = None
        resolver = None
        def __init__(self, row=None):
            if row is not None:
                for key in row.keys():
                    if hasattr(self, key):
                        setattr(self, key, row[key].value())
    
    def _action_args(self, req):
        # We always work with just one record.
        return dict(record=self._record(self._data.get_row(config_id=0)))
    
    def _default_action(self, req, **kwargs):
        return 'edit'
        
    def _redirect_after_update(self, req, record):
        return self.action_edit(req, record, msg=self._UPDATE_MSG)
    
    def config(self):
        """Return the site-specific configuration object."""
        return self.Configuration(self._data.get_row(config_id=0))

    def theme(self):
        """Return the current color theme as a dictionary.

        The returned dictionary assigns color values (strings in the '#rrggbb' format) to symbolic
        color names.  These colors will used for stlylesheet substitution.

        """
        theme_id = self._data.get_row(config_id=0)['theme'].value()
        return self._module('Themes').theme(theme_id)
    
    def action_view(self, *args, **kwargs):
        return self.action_show(*args, **kwargs)

class BasePanels(Module):
    
    def panels(self, req, lang):
        config = self._module('Config').config()
        if config.login_panel:
            user = req.user()
            content = lcg.p(LoginCtrl(user))
            if config.allow_registration and not user:
                uri = self._module('Users').registration_uri(req)
                if uri:
                    lnk = lcg.link(uri, _("New user registration"))
                    content = lcg.coerce((content, lnk))
            return [Panel('login', _("Login"), content)]
        else:
            return []
    
class Panels(WikingModule, Publishable, BasePanels):
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
                  display=(_modtitle, 'modname'), selection_type=CHOICE, 
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
        columns = ('title', 'ord', 'modtitle', 'size', 'published')
        layout = ('lang', 'ptitle', 'ord',  'mapping_id', 'size',
                  'content', 'published')
    _LIST_BY_LANGUAGE = True
    WMI_SECTION = WikingManagementInterface.SECTION_CONTENT
    WMI_ORDER = 1000

    def panels(self, req, lang):
        panels = super(Panels, self).panels(req, lang)
        parser = lcg.Parser()
        for row in self._data.get_rows(lang=lang, published=True, sorting=self._sorting):
            if row['private'].value() is True and not \
                   Roles.check(req, (Roles.USER,), raise_error=False):
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
                
                
class Languages(WikingModule):
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
        cb = pp.CodebookSpec(display=lcg.language_name)
        layout = ('lang',)
        columns = ('lang', 'name')
    _REFERER = 'lang'
    WMI_SECTION = WikingManagementInterface.SECTION_SETUP
    WMI_ORDER = 200

    def languages(self):
        return [str(r['lang'].value()) for r in self._data.get_rows()]

    
class Titles(WikingModule):
    """Provide localized titles for 'Mapping' items."""
    class Spec(Specification):
        title = _("Titles")
        help = _("Manage menu titles of available mapping items (temporary).")
        fields = (
            Field('title_id'),
            Field('mapping_id', _("Identifier"), width=5, codebook='Mapping',
                  selection_type=CHOICE, editable=ONCE),
            Field('identifier', _("Identifier"), virtual=True,
                  computer=CbComputer('mapping_id', 'identifier')),
            Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                  selection_type=CHOICE, value_column='lang'),
            Field('title', _("Title")),
            )
        columns = ('identifier', 'title')
        layout = ('mapping_id', 'lang', 'title')
        sorting = (('mapping_id', ASC), ('lang', ASC))

    _LIST_BY_LANGUAGE = True
    _EXCEPTION_MATCHERS = (
        ('duplicate key violates unique constraint "titles_mapping_id_key"',
         _("The title is already defined for this page in given language.")),)+\
         WikingModule._EXCEPTION_MATCHERS
    WMI_SECTION = WikingManagementInterface.SECTION_CONTENT
    WMI_ORDER = 10000
    
    def menu_title(self, mapping_id, default):
        """Return localizable menu item title."""
        titles = dict([(row['lang'].value(), row['title'].value())
                       for row in self._data.get_rows(mapping_id=mapping_id)])
        return lcg.SelfTranslatableText(default, translations=titles)

class Themes(WikingModule):
    class Spec(Specification):
        title = _("Themes")
        help = _("Manage available color themes. Go to Configuration to "
                 "change the currently used theme.")
        def fields(self): return (
            Field('theme_id'),
            Field('name', _("Name"), width=20),
            ) + tuple([Field(c.id(), c.id(), dbcolumn=c.id().replace('-','_'),
                             type=pd.Color()) for c in Themes.COLORS])
        def layout(self):
            return ('name',) + tuple([c.id() for c in Themes.COLORS])
        columns = ('name',)
        cb = pp.CodebookSpec(display='name')
    WMI_SECTION = WikingManagementInterface.SECTION_STYLE
    WMI_ORDER = 100

    class Color(object):
        def __init__(self, id, default=None, inherit=None):
            self._id = id
            self._default = default
            self._inherit = inherit
        def id(self):
            return self._id
        def value(self, colors):
            return self._default or colors[self._inherit]
        def clone(self, value):
            return self.__class__(self._id, value or self._default, inherit=self._inherit)

    class Colors(object):
        def __init__(self, colors):
            self._dict = dict([(c.id(), c) for c in colors])
            self._colors = colors
        def __getitem__(self, key):
            return self._dict[key].value(self)
    
    COLORS = (
        Color('foreground', '#000'),
        Color('background', '#fff'),
        Color('border', '#bcd'),
        Color('heading-fg', inherit='foreground'),
        Color('heading-bg', '#d8e0f0'),
        Color('heading-line', '#ccc', inherit='frame-border'),
        Color('frame-fg', inherit='foreground'),
        Color('frame-bg', '#eee', inherit='background'),
        Color('frame-border', '#ddd', inherit='border'),
        Color('link', '#03b'),
        Color('link-visited', inherit='link'),
        Color('link-hover', '#d60'),
        Color('meta-fg', '#840', inherit='foreground'),
        Color('meta-bg', inherit='background'),
        Color('help', '#444', inherit='foreground'),
        Color('error-fg', inherit='foreground'),
        Color('error-bg', '#fdb'),
        Color('error-border', '#fba', inherit='border'),
        Color('message-fg', inherit='foreground'),
        Color('message-bg', '#cfc'),
        Color('message-border', '#aea', inherit='border'),
        Color('table-cell', '#f8fafb', inherit='background'),
        Color('table-cell2', '#eaeaff', inherit='table-cell'),
        Color('button-fg', inherit='foreground'),
        Color('button', inherit='heading-bg'),
        Color('button-border', '#9af', inherit='border'),
        Color('button-inactive-fg', '#555', inherit='button-fg'),
        Color('button-inactive', '#ccc', inherit='button'),
        Color('button-inactive-border', '#999', inherit='button-border'),
        Color('top-fg', inherit='foreground'),
        Color('top-bg', '#efebe7', inherit='background'),
        Color('top-border', '#9ab', inherit='border'),
        Color('highlight-bg', '#fc8', inherit='heading-bg'), # cur. lang. bg.
        Color('inactive-folder', '#d2d8e0'),
        )

    def theme(self, theme_id):
        if theme_id is not None:
            row = self._data.get_row(theme_id=theme_id)
            colors = [c.clone(row[c.id()].value()) for c in self.COLORS]
        else:
            colors = self.COLORS
        return dict(color=self.Colors(colors))

# ==============================================================================
# The modules below are able to handle requests directly.  
# The modules above are system modules used internally by Wiking.
# ==============================================================================

class Pages(WikingModule, Publishable, Mappable):
    class Spec(Specification):
        title = _("Pages")
        help = _("Manage available pages of structured text content.")
        def _level(self, row):
            return len(row['tree_order'].value().split('.')) - 2
        def fields(self): return (
            Field('page_id'),
            Field('mapping_id'),
            Field('identifier', _("Identifier"), editable=ONCE, not_null=True,
                  descr=_("The identifier may be used to refer to this page from outside and also "
                          "from other pages. A valid identifier can only contain letters, digits, "
                          "dashes and underscores.  It must start with a letter.")),
            Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                  selection_type=CHOICE, value_column='lang'),
            Field('title', _("Title")),
            Field('title_', _("Title"), virtual=True,
                  computer=Computer(self._title, depends=('title', 'identifier'))),
            Field('_content', _("Content"), compact=True, height=20, width=80,
                  descr=_STRUCTURED_TEXT_DESCR),
            Field('content'),
            Field('published', _("Published")),
            Field('status', _("Status"), virtual=True,
                  computer=Computer(self._status, depends=('content', '_content'))),
            Field('tree_order'),
            Field('level', _("Identifier"), virtual=True,
                  computer=Computer(self._level, depends=('tree_order',))),
            )
        def _title(self, row):
            return row['title'].value() or row['identifier'].value()
        def _status(self, row):
            _c = row['_content'].value()
            if _c:
                c = row['content'].value()
                return c == _c and _("Ok") or _("Changed")
            else:
                return _("Missing")
        sorting = (('tree_order', ASC), ('lang', ASC),)
        layout = ('identifier', 'lang', 'title', '_content')
        columns = ('title_', 'identifier', 'published', 'status')
        cb = pp.CodebookSpec(display='identifier')
        bindings = {'Attachments': pp.BindingSpec(_("Attachments"), 'mapping_id')}
    
    _REFERER = 'identifier'
    _EXCEPTION_MATCHERS = (
        ('duplicate key violates unique constraint "_pages_mapping_id_key"',
         _("The page already exists in given language.")),) + \
         WikingModule._EXCEPTION_MATCHERS
    _LIST_BY_LANGUAGE = True
    _RELATED_MODULES = ('Attachments',)
    _TREE_LEVEL_COLUMN = 'level'
    
    _INSERT_MSG = _("New page was successfully created. Don't forget to publish it when you are "
                    "done. Please, visit the 'Mapping' module if you want to add the page to the "
                    "main menu.")
    _UPDATE_MSG = _("Page content was modified, however the changes remain unpublished. Don't "
                    "forget to publish the changes when you are done.")
    
    _IS_OK = pd.NE('content', pd.Value(pd.String(), None))
    _ACTIONS = (Action(_("Publish changes"), 'sync',
                       descr=_("Publish the current modified content"),
                       enabled=lambda r: r['_content'].value() != r['content'].value()),
                Action(_("Preview"), 'preview',
                       descr=_("Display the current version of the page"),
                       enabled=lambda r: r['_content'].value() is not None),
                Action(_("Translate"), 'translate',
                       descr=_("Create the content by translating another language variant"),
                       enabled=lambda r: r['_content'].value() is None),
                )
    _RIGHTS_add = _RIGHTS_insert = Roles.AUTHOR
    _RIGHTS_edit = _RIGHTS_update = Roles.AUTHOR
    WMI_SECTION = WikingManagementInterface.SECTION_CONTENT
    WMI_ORDER = 200

    def _variants(self, record):
        return [str(r['lang'].value()) for r in 
                self._data.get_rows(mapping_id=record['mapping_id'].value(), condition=self._IS_OK)]

    def handle(self, req):
        if not req.wmi and len(req.path) == 2:
            return self._module('Attachments').handle(req)
        return super(Pages, self).handle(req)

    def _resolve(self, req):
        if len(req.path) == 1:
            lang = req.param('lang')
            if lang is not None:
                row = self._data.get_row(identifier=req.path[0], lang=lang, condition=self._IS_OK)
                if row:
                    return row
            else:
                variants = self._data.get_rows(identifier=req.path[0], condition=self._IS_OK)
                if variants:
                    for lang in req.prefered_languages():
                        for row in variants:
                            if row['lang'].value() == lang:
                                return row
                    raise NotAcceptable([str(r['lang'].value()) for r in variants])
        raise NotFound()

    #def _redirect_after_insert(self, req, record):
        #if not req.wmi:
        #    return self.action_view(req, record, msg=self._INSERT_MSG)

    def action_view(self, req, record, err=None, msg=None, preview=False):
        if req.wmi and preview:
            text = record['_content'].value()
        else:
            text = record['content'].value()
        attachments = self._module('Attachments').attachments(record)
        items = [(lcg.link(a.uri(), a.title()), ' ('+ a.bytesize() +') ',
                  lcg.WikiText(a.descr() or '')) for a in attachments if a.listed()]
        attachments_section = items and lcg.Section(title=_("Attachments"), content=lcg.ul(items))
        if text:
            sections = lcg.Parser().parse(text)
            if attachments_section:
                sections += [attachments_section]
            content = lcg.SectionContainer(sections, toc_depth=0)
        else:
            content = attachments_section
        return self._document(req, content, record, resources=attachments, err=err, msg=msg)

    def action_preview(self, req, record, **kwargs):
        return self.action_view(req, record, preview=True, **kwargs)
    _RIGHTS_preview = Roles.AUTHOR

    def action_translate(self, req, record):
        lang = req.param('src_lang')
        if not lang:
            if record['_content'].value() is not None:
                e = _("Content for this page already exists!")
                return self.action_show(req, record, err=e)
            cond = pd.AND(pd.NE('_content', pd.Value(pd.String(), None)),
                          pd.NE('lang', record['lang']))
            langs = [(str(row['lang'].value()), lcg.language_name(row['lang'].value())) for row in 
                     self._data.get_rows(mapping_id=record['mapping_id'].value(), condition=cond)]
            if not langs:
                e = _("Content for this page does not exist in any language.")
                return self.action_show(req, record, err=e)
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
    _RIGHTS_translate = Roles.AUTHOR

    def action_sync(self, req, record):
        try:
            record.update(content=record['_content'].value())
        except pd.DBException, e:
            kwargs = dict(err=self._module._analyze_exception(e))
        else:
            kwargs = dict(msg=_("The changes were published."))
        return self.action_show(req, record, **kwargs)
    _RIGHTS_sync = Roles.ADMIN

    
class Attachments(StoredFileModule):
    class Spec(StoredFileModule.Spec):
        title = _("Attachments")
        help = _("Manage page attachments. Go to a page to create new "
                 "attachments.")
        def fields(self):
            def fcomp(ffunc):
                def func(row):
                    f = row['file'].value()
                    return f and ffunc(f) or None
                return pp.Computer(func, depends=('file',))
            return (
            Field('page_attachment_id',
                  computer=Computer(self._page_attachment_id, depends=('attachment_id', 'lang'))),
            Field('attachment_id'),
            Field('mapping_id', _("Page"), codebook='Mapping', editable=ONCE),
            Field('identifier'),
            Field('lang', _("Language"), codebook='Languages', 
                  selection_type=CHOICE, editable=ONCE, value_column='lang'),
            Field('page_id'),
            Field('file', _("File"), virtual=True, editable=ALWAYS,
                  type=pd.Binary(not_null=True, maxlen=3*MB),
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
        columns = ('filename', 'title', 'bytesize', 'mime_type', 'listed',
                   'mapping_id')
        sorting = (('identifier', ASC), ('filename', ASC))
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
    _LIST_BY_LANGUAGE = True
    _SEQUENCE_FIELDS = (('attachment_id', '_attachments_attachment_id_seq'),)
    _NON_LAYOUT_FIELDS = ('mapping_id', 'lang')
    _EXCEPTION_MATCHERS = (
        ('duplicate key violates unique constraint "_attachments_mapping_id_key"',
         _("Attachment of the same filename already exists for this page.")),)
    WMI_SECTION = WikingManagementInterface.SECTION_CONTENT
    WMI_ORDER = 220
    
    def _link_provider(self, req, row, cid, **kwargs):
        if cid == 'file':
            cid = 'filename'
            kwargs['action'] = 'view'
        return super(Attachments, self)._link_provider(req, row, cid, **kwargs)

    def _redirect_to_page(self, req, record):
        return req.redirect('/_wmi/Pages/' + record['page_id'].value())
        #m = self._module('Pages')
        #record = m.record(record['page_id'])
        #return m.action_show(req, record, msg=self._UPDATE_MSG)
    def _redirect_after_insert(self, req, record):
        return self._redirect_to_page(req, record)
    def _redirect_after_delete(self, req, record):
        return self._redirect_to_page(req, record)
    def _redirect_after_update(self, req, record):
        return self._redirect_to_page(req, record)

    def _resolve(self, req):
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
                
    def action_view(self, req, record):
        return (str(record['mime_type'].value()), record['file'].value().buffer())

    
class News(WikingModule, Mappable):
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
        layout = ('lang', 'timestamp', 'title', 'content')
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
    _RIGHTS_add = _RIGHTS_insert = Roles.CONTRIBUTOR
    _RIGHTS_edit = _RIGHTS_update = (Roles.ADMIN, Roles.OWNER)
    _RIGHTS_remove = _RIGHTS_delete = Roles.ADMIN
    _CUSTOM_VIEW = CustomViewSpec('title', meta=('timestamp', 'author'), content='content',
                                  anchor="item-%s", custom_list=True)
    WMI_SECTION = WikingManagementInterface.SECTION_CONTENT
    WMI_ORDER = 300
        
    def _link_provider(self, req, row, cid, target=None, **kwargs):
        identifier = self._identifier(req)
        if not req.wmi and cid == 'title' and identifier is not None:
            anchor = '#item-'+ row[self._referer].export()
            return make_uri('/'+ identifier, **kwargs) + anchor
        elif not issubclass(target, Panel):
            return super(News, self)._link_provider(req, row, cid, target=target, **kwargs)


class Planner(News):
    class Spec(Specification):
        title = _("Planner")
        help = _("Announce future events by date in a callendar-like listing.")
        def fields(self): return (
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
            Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                  selection_type=CHOICE, value_column='lang'),
            Field('title', _("Briefly"), column_label=_("Event"), width=32,
                  descr=_("The event summary (title of the entry).")),
            Field('content', _("Text"), height=3, width=60,
                  descr=_STRUCTURED_TEXT_DESCR + ' ' + \
                  _("It is, however, recommened to use the simplest possible formatting, since "
                    "the item may be also published through an RSS channel, which does not "
                    "support formatting.")),
            Field('author', _("Author"), codebook='Users'),
            Field('timestamp', type=DateTime(not_null=True), default=now),
            Field('date_title', virtual=True,
                  computer=Computer(self._date_title,
                                    depends=('date', 'title'))))
        sorting = (('start_date', ASC),)
        columns = ('title', 'date', 'author')
        layout = ('lang', 'start_date', 'end_date', 'title', 'content')
        def _check_date(self, date):
            if date < today():
                return _("Date in the past")
        def _date(self, row):
            d = row['start_date'].export(show_weekday=True)
            if row['end_date'].value():
                d += ' - ' + row['end_date'].export(show_weekday=True)
            return d
        def _date_title(self, row):
            return row['date'].export() +': '+ row['title'].value()
        def check(self, row):
            end = row['end_date'].value()
            if end and end <= row['start_date'].value():
                return ("end_date", _("End date precedes start date"))
    _CUSTOM_VIEW = CustomViewSpec('date_title', meta=('author', 'timestamp'), content='content',
                                  anchor="item-%s", custom_list=True)
    _RSS_TITLE_COLUMN = 'date_title'
    _RSS_LINK_COLUMN = 'title'
    _RSS_DATE_COLUMN = None
    def _condition(self):
        return pd.OR(pd.GE('start_date', pd.Value(pd.Date(), today())),
                     pd.GE('end_date', pd.Value(pd.Date(), today())))

    
class Images(StoredFileModule, Mappable):
    class Spec(StoredFileModule.Spec):
        title = _("Images")
        help = _("Publish images.")
        def fields(self):
            def fcomp(ffunc):
                def func(row):
                    f = row['file'].value()
                    return f and ffunc(f) or None
                return pp.Computer(func, depends=('file',))
            def imgcomp(imgfunc):
                return fcomp(lambda f: imgfunc(f.image()))
            return (
            Field('image_id'),
            Field('published'),
            Field('file', _("File"), virtual=True, editable=ALWAYS,
                  type=pd.Image(not_null=True, maxlen=3*MB,
                                maxsize=(3000, 3000)), thumbnail='thumbnail',
                  computer=self._file_computer('file', '_filename',
                                               origname='filename')),
            Field('image', virtual=True, editable=ALWAYS,
                  type=pd.Image(not_null=True, maxlen=3*MB, maxsize=(3000, 3000)),
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
    #WMI_SECTION = WikingManagementInterface.SECTION_CONTENT
    WMI_ORDER = 500
        
    def _link_provider(self, req, row, cid, **kwargs):
        if cid == 'file':
            cid = 'filename'
            kwargs['action'] = req.wmi and 'orig' or 'view'
        if cid == 'thumbnail':
            cid = 'filename'
            kwargs['action'] = 'thumbnail'
        return super(Images, self)._link_provider(req, row, cid, **kwargs)

    def _image(self, record, id):
        mime = "image/" + str(record['format'].value())
        data = record[id].value().buffer()
        return (mime, data)
    
    _RIGHTS_orig = _RIGHTS_image = _RIGHTS_thumbnail = Roles.ANYONE
    
    def action_orig(self, req, record):
        return self._image(record, 'file')
    
    def action_image(self, req, record):
        return self._image(record, 'image')
    
    def action_thumbnail(self, req, record):
        return self._image(record, 'thumbnail')


class DefaultStylesheets(Module, RequestHandler):

    _MATCHER = re.compile (r"\$(\w[\w-]*)(?:\.(\w[\w-]*))?")
    _THEME = {'color': Themes.Colors(Themes.COLORS)}

    def stylesheets(self):
        return [lcg.Stylesheet('default.css', uri='/css/default.css')]

    def _find_file(self, name):
        filename = os.path.join(cfg.wiking_dir, 'resources', 'css', name)
        if os.path.exists(filename):
            return "".join(file(filename).readlines())
        else:
            raise wiking.NotFound()

    def _stylesheet(self, content, theme):
        def subst(match):
            name, key = match.groups()
            value = theme[name]
            if key:
                value = value[key]
            return value
        return self._MATCHER.sub(subst, content)
    
    def handle(self, req):
        return ('text/css', self._stylesheet(self._find_file(req.path[1]), self._THEME))

    
class Stylesheets(DefaultStylesheets, WikingModule, Mappable):
    class Spec(Specification):
        title = _("Styles")
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
        # TODO: Use self._identifier() ???
        identifier = self._module('Mapping').get_identifier(self.name())
        if identifier:
            return [lcg.Stylesheet(r['identifier'].value(),
                                   uri=('/'+ identifier + '/'+ r['identifier'].value()))
                    for r in self._data.get_rows(active=True)]
        else:
            return []
            
    def action_view(self, req, record, msg=None):
        content = record['content'].value() or self._find_file(record['identifier'].value())
        theme = self._module('Config').theme()
        return ('text/css', self._stylesheet(content, theme))


class _Users(WikingModule):
    class Spec(Specification):
        title = _("Users")
        help = _('Manage registered users.  Use the module "Access Rights" '
                 'to change their privileges.')
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
                  type=pd.Password(maxlen=32, not_null=True),
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
            Field('since', _("Registered since"), type=DateTime(show_time=False), default=now),
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
        cb = pp.CodebookSpec(display='user')
    _REFERER = 'login'
    _PANEL_FIELDS = ('fullname',)
    _ALLOW_TABLE_LAYOUT_IN_FORMS = False
    _OWNER_COLUMN = 'uid'
    _SUPPLY_OWNER = False
    _RIGHTS_add = _RIGHTS_insert = Roles.ANYONE
    _RIGHTS_edit = _RIGHTS_update = (Roles.ADMIN, Roles.OWNER)
    _RIGHTS_remove = _RIGHTS_delete = Roles.ADMIN #, Roles.OWNER)

    def _actions(self, req, record):
        if not req.wmi:
            if record:
                return (Action(_("Edit your profile"), 'edit',
                               descr=_("Modify your record")),
                        #Action(_("Drop registration"), 'remove',
                        #       descr=_("Remove your record permanently")),
                        #)
                        Action(_("Remove"), 'remove',
                               descr=_("Remove the user permanently")),
                        )
            else:
                return (Action(_("Register"), 'add', context=None,
                               descr=_("New user registration")),)
        return super(_Users, self)._actions(req, record)
        
    def _redirect_after_insert(self, req, record):
        content = lcg.p(_("Registration completed successfuly. "
                          "Your account now awaits administrator's approval."))
        return self._document(req, content, subtitle=_("Registration"))
    
        
class Users(_Users, Mappable):
    
    WMI_SECTION = WikingManagementInterface.SECTION_USERS
    WMI_ORDER = 100
    
    def registration_uri(self, req):
        identifier = self._identifier(req)
        return identifier and make_uri('/'+identifier, action='add') or None


class BaseAuthentication(Module):

    def authenticate(self, req):
        return None

    
class CookieAuthentication(BaseAuthentication):
    
    _LOGIN_COOKIE = 'wiking_login'
    _SESSION_COOKIE = 'wiking_session_key'

    def _user(self, login):
        return None

    def _authenticate(self, user, password):
        return False

    def authenticate(self, req):
        session = self._module('Session')
        credentials = req.credentials()
        if credentials:
            login, password = credentials
            if not login:
                raise AuthenticationError(_("Enter your login name, please!"))
            if not password:
                raise AuthenticationError(_("Enter your password, please!"))
            user = self._user(login)
            if not user or not user.password() == password:
                raise AuthenticationError(_("Invalid login!"))
            assert isinstance(user, User)
            # Login succesfull
            session_key = session.init(user)
            req.set_cookie(self._LOGIN_COOKIE, login, expires=730*DAY)
            req.set_cookie(self._SESSION_COOKIE, session_key, expires=2*DAY)
        else:
            login, key = (req.cookie(self._LOGIN_COOKIE), 
                          req.cookie(self._SESSION_COOKIE))
            if login and key:
                user = self._user(login)
                if user and session.check(user, key):
                    assert isinstance(user, User)
                    # Cookie expiration is 2 days, but session expiration is
                    # controled within the session module independently.
                    req.set_cookie(self._SESSION_COOKIE, key, expires=2*DAY)
                else:
                    # This is not true after logout
                    session_timed_out = True
                    user = None
            else:
                user = None
        if req.param('command') == 'logout' and user:
            session.close(user)
            user = None
            req.set_cookie(self._SESSION_COOKIE, None, expires=0)
        elif req.param('command') == 'login' and not user:
            raise AuthenticationError()
        return user

    
class Authentication(_Users, CookieAuthentication):
    class Spec(_Users.Spec):
        table = 'users'
    
    def _user(self, login):
        record = self._record(self._data.get_row(login=login, enabled=True))
        roles = [role for role, fields in ((Roles.USER, ('enabled',)),
                                           (Roles.CONTRIBUTOR, ('contributor', 'author', 'admin')),
                                           (Roles.AUTHOR, ('author', 'admin')),
                                           (Roles.ADMIN, ('admin',)))
                 if record['enabled'].value() and True in [record[id].value() for id in fields]]
        return User(record['uid'].value(), record['login'].value(),
                    record['password'].value(), name=record['user'].value(),
                    roles=roles, data=record)


class Session(_Users):
    class Spec(_Users.Spec):
        table = 'users'
        
    _MAX_SESSION_KEY = 0xfffffffffffffffffffffffffffff

    def _new_session_key(self):
        return hex(random.randint(0, self._MAX_SESSION_KEY))
    
    def _expiration(self):
        return now() + TimeDelta(hours=2)

    def _expired(self, time):
        return time <= now()
    
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
        

class Rights(_Users):
    class Spec(_Users.Spec):
        title = _("Access Rights")
        help = _("Manage access rights of registered users.")
        layout = ('enabled', 'contributor', 'author', 'admin')
        columns = ('user', 'login', 'enabled', 'contributor', 'author','admin')
        table = 'users'
    _ALLOW_TABLE_LAYOUT_IN_FORMS = True
    _RIGHTS_add = _RIGHTS_insert = ()
    _RIGHTS_edit = _RIGHTS_update = Roles.ADMIN
    _RIGHTS_remove = ()
    WMI_SECTION = WikingManagementInterface.SECTION_USERS
    WMI_ORDER = 200


        
class Reload(Module):

    _UNRELOADABLE_MODULES = ('sys', '__main__', '__builtin__',)
    # NOTE: Wiking and LCG are not reloadable due to the mess in Python class
    # instances  after reload.
    _RELOADABLE_REGEXP = '.*/wikingmodules/.*'

    def __init__(self, *args, **kwargs):
        super(Reload, self).__init__(*args, **kwargs)
        self._reloadable_regexp = re.compile(self._RELOADABLE_REGEXP)

    def _module_reloadable(self, name, module, req):
        return (module is not None and
                name not in self._UNRELOADABLE_MODULES and
                hasattr(module, '__file__') and
                self._reloadable_regexp.match(module.__file__))

    def _reload_modules(self, req):
        import sys
        module_names = []
        for name, module in sys.modules.items():
            if self._module_reloadable(name, module, req):
                try:
                    reload(module)
                    module_names.append(name)
                except:
                    pass
        return module_names
    
    def handle(self, req):
        module_names = self._reload_modules(req)
        import string
        content = lcg.coerce((lcg.p(_("The following modules were successfully reloaded:")),
                              lcg.p(string.join(module_names, ", ")),))
        return Document(_("Reload"), lcg.coerce(content))
        

class Search(Module, ActionHandler):

    _SEARCH_TITLE = _("Searching")
    _RESULT_TITLE = _("Search results")
    _EMPTY_SEARCH_MESSAGE = _("Given search term doesn't contain any searchable term.")

    class SearchForm(lcg.Content):
        
        _SEARCH_FIELD_LABEL = _("Search words: ")
        _SEARCH_BUTTON_LABEL = _("Search")

        def __init__(self, req):
            lcg.Content.__init__(self)
            self._params = req.params
            self._uri = req.uri

        def _contents(self, generator):
            return (generator.label(self._SEARCH_FIELD_LABEL, id='input'),
                    generator.field(name='input', id='input', tabindex=0, size=20),
                    generator.br(),
                    generator.submit(self._SEARCH_BUTTON_LABEL, cls='submit'),)
        
        def export(self, exporter):
            generator = exporter.generator()
            contents = self._contents(generator)
            contents = contents + (generator.hidden(name='action', value='search'),)
            return generator.form(contents, method='POST', action=self._uri)

    class Result:
        def __init__ (self, uri, title, sample=None):
            self._title = title
            self._sample = sample
            self._uri = uri
        def uri(self):
            return self._uri
        def title(self):
            return self._title
        def sample(self):
            return self._sample

    def _search_form(self, req, message=None):
        content = []
        if message is not None:
            content.append(lcg.p(message))
        content = [self.SearchForm(req)]
        variants = self._module('Languages').languages()
        lang = req.prefered_language(variants)
        return Document(self._SEARCH_TITLE, lcg.Container(content), lang=lang)

    def _transform_input(self, input):
        input = re.sub('[&|!()"\'\\\\]', ' ', input)
        input = input.strip()
        input = re.sub(' +', '&', input)
        return input

    def _perform_search(self, expression, req):
        return ()

    def _result_item(self, item):
        sample = item.sample()
        link = lcg.link(item.uri(), label=item.title(), descr=sample,)
        if sample is None:
            result_item = lcg.Paragraph((link,))
        else:
            result_item = lcg.DefinitionList((lcg.Definition(link, lcg.coerce(sample)),))
        return result_item

    def _empty_result_page(self):
        return lcg.p(_("Nothing found."))

    def _result_page(self, req, result):
        if result:
            content = lcg.Container([self._result_item(item) for item in result])
        else:
            content = self._empty_result_page()
        variants = self._module('Languages').languages()
        lang = req.prefered_language(variants)
        return Document(self._RESULT_TITLE, content, lang=lang)
    
    # Actions
    
    def _default_action(self, req, **kwargs):
        return 'show'

    def action_show(self, req, **kwargs):
        return self._search_form(req)
        
    def action_search(self, req, **kwargs):
        input = req.params.get('input', '')
        expression = self._transform_input(input)
        if not expression:
            return self._search_form(req, message=self._EMPTY_SEARCH_MESSAGE)
        result = self._perform_search(expression, req)
        return self._result_page(req, result)
