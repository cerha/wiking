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
MB = 1024**2
now = lambda: mx.DateTime.now().gmtime()

_ = lcg.TranslatableTextFactory('wiking')

def _modspec(m):
    """Return module specification by module name."""
    try:
        cls = get_module(m)
    except:
        return None
    else:
        return cls.Spec

def _modtitle(m):
    """Return a localizable module title by module name."""
    if m is None:
        return ''
    spec = _modspec(m)
    if spec:
        return spec.title
    else:
        return concat(m,' (',_("unknown"),')')

# This constant lists names of modules which don't handle requests directly and
# thus should not appear in the module selection for the Mapping items.
# It should be considered a temporary hack, but the list should be maintained.
_SYSMODULES = ('Languages', 'Modules', 'Config', 'Mapping','Panels', 'Titles')

_STRUCTURED_TEXT_DESCR = _("The content should be formatted as LCG "
                           "structured text. See the %(manual)s.",
                           manual=('<a target="_new" href="/_doc/lcg/'
                                   'data-formats/structured-text">' + \
                                   _("formatting manual") + "</a>"))

class Mapping(WikingModule, Publishable):
    """Mapping available URIs to the modules which handle them.

    The Wiking Handler always queries this module to resolve the request URI
    and return the name of the module which is responsible for handling the
    request.  Futher processing of the request is then postponed to this
    module.  Only a part of the request uri may be used to determine the module
    and another part may be used by the module to determine the sub-contents.

    This implementation uses static mapping as well as database based mapping,
    which may be modified through the Wiking Management Interface.

    """
    class Spec(pp.Specification):
        title = _("Mapping")
        help = _("Manage available URIs and Wiking modules which handle them. "
                 "Also manage the main menu.")
        fields = (
            Field('mapping_id', width=5, editable=NEVER),
            #Field('parent', _("Parent"), codebook='Mapping'),
            Field('identifier', _("Identifier"), width=20,
                  filter=ALPHANUMERIC, post_process=LOWER, fixed=True,
                  type=pd.RegexString(maxlen=32, not_null=True,
                                      regex='^[a-zA-Z][0-9a-zA-Z_-]*$'),
                  descr=_("The identifier may be used to refer to this page "
                          "from outside and also from other pages. "
                          "A valid identifier can only contain letters, "
                          "digits, dashes and underscores.  It must start "
                          "with a letter.")),
            Field('mod_id', _("Module"), selection_type=CHOICE,
                  codebook='Modules',
                  validity_condition=pd.AND(*[pd.NE('name',
                                                    pd.Value(pd.String(),_m))
                                              for _m in _SYSMODULES])),
            Field('modname', _("Module")),
            Field('modtitle', _("Module"), virtual=True,
                  computer=Computer(lambda r: _modtitle(r['modname'].value()),
                                    depends=('modname',)),
                  descr=_("Select the module which handles requests for "
                          "given identifier.  This is the way to make the "
                          "module available from outside.")),
            Field('published', _("Published"),
                  descr=_("This flag allows you to make the item unavailable "
                          "withoit actually removing it.")),
            Field('private', _("Private"), default=False,
                  descr=_("Make the item available only to logged-in users.")),
            Field('ord', _("Menu order"), width=5,
                  descr=_("Enter a number denoting the item order in the menu "
                          "or leave the field blank if you don't want this "
                          "item to appear in the menu.")))
        sorting = (('ord', ASC), ('identifier', ASC))
        bindings = {'Pages': pp.BindingSpec(_("Pages"), 'mapping_id')}
        columns = ('identifier', 'modtitle', 'published', 'private', 'ord')
        layout = ('identifier', 'mod_id', 'published', 'private', 'ord')
        cb = pp.CodebookSpec(display='identifier')
    _REFERER = 'identifier'
    _STATIC_MAPPING = {'_doc': 'Documentation',
                       '_wmi': 'WikingManagementInterface'}
    _REVERSE_STATIC_MAPPING = dict([(v,k) for k,v in _STATIC_MAPPING.items()])
    _mapping_cache = {}

    def _link_provider(self, req, row, cid, **kwargs):
        if req.wmi and cid == 'modtitle':
            return '/_wmi/' + row['modname'].value()
        return super(Mapping, self)._link_provider(req, row, cid, **kwargs)

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
                # We want to allow new user registration even if the user
                # listing is private.  Unfortunately there seems to be no
                # better solution than the terrible hack above...
                # May be we should ask the module?
                Roles.check(req, (Roles.USER,))
        return modname
    
    def get_identifier(self, modname):
        """Return the current identifier for given module name.

        None will be returned when there is no mapping item for the module, or
        when there is more than one item for the same module (which is also
        legal).
        
        """
        rows = self._data.get_rows(modname=modname, published=True)
        if len(rows) == 1:
            return rows[0]['identifier'].value()
        return self._REVERSE_STATIC_MAPPING.get(modname)
    
    def menu(self, req, lang):
        """Return the sequence of main navigation menu items.

        Arguments:
        
          req -- the current request object.
        
          lang -- denotes the language which should be used for localizing the
            item titles.  It is one of the language codes as returned by
            `Languages.languages()'.
            
        Returns a sequence of 'MenuItem' instances.
        
        """
        # TODO: Show also unpublished items when authorized.
        titles = self._module('Titles').titles(lang)
        return [MenuItem(str(row['identifier'].value()),
                         titles.get(row['mapping_id'].value(),
                                    row['identifier'].value()))
                for row in self._data.get_rows(sorting=self._sorting)
                if row['ord'].value() and row['published'].value()]
                #and row['parent'].value() is None]
                
    def title(self, lang, modname):
        """Return localized module title for given module name.

        The argument `lang' denotes the language which should be used for
        localizing the title.  It is one of the language codes as returned by
        `Languages.languages()'.

        """
        row = self._data.get_row(modname=modname)
        if row:
            titles = self._module('Titles').titles(lang)
            key = row['mapping_id'].value()
            return titles.get(key, row['identifier'].value())
        else:
            return _modtitle(modname)


class Documentation(Module):
    """Serve the on-line documentation.

    This module is not bound to a data object.  It only serves the on-line
    documentation from files on the disk.

    """
    def handle(self, req):
        path = req.path[1:]
        if path and path[0] == 'lcg':
            path = path[1:]
            basedir = lcg.config.doc_dir
        else:
            basedir = os.path.join(cfg.wiking_dir, 'doc', 'src')
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


class WikingManagementInterface(Module):
    """Wiking Management Interface.

    This module handles the WMI requestes by redirecting the request to the
    selected module.  The module name is part of the request URI.

    """
    def handle(self, req):
        Roles.check(req, (Roles.ADMIN,))
        req.wmi = True # Switch to WMI only after successful authorization.
        if len(req.path) == 1:
            req.path += ('Pages',)
        modname = req.path[1]
        return self._module(modname).handle(req)

    
class Modules(WikingModule):
    """This module allows management of available modules in WMI."""
    class Spec(pp.Specification):
        class _ModNameType(pd.String):
            VM_UNKNOWN_MODULE = 'VM_UNKNOWN_MODULE'
            _VM_UNKNOWN_MODULE_MSG = _("Unknown module.  You either "
                                       "misspelled the name or the module "
                                       "is not installed properly.")
            def _check_constraints(self, value):
                pd.String._check_constraints(self, value)
                try:
                    module = get_module(value)
                except AttributeError:
                    raise self._validation_error(self.VM_UNKNOWN_MODULE)
                if not issubclass(module, WikingModule):
                    raise self._validation_error(self.VM_UNKNOWN_MODULE)
                    
        title = _("Modules")
        help = _("Manage available Wiking modules.")
        fields = (
            Field('mod_id'),
            Field('name', _("Name"), type=_ModNameType(not_null=True)),
            Field('title', _("Title"), virtual=True,
                  computer=Computer(lambda r: _modtitle(r['name'].value()),
                                    depends=('name',))),
            Field('active', _("Active")),
            Field('ord', _("Menu order"), width=5),
            )
        columns = ('title', 'active', 'ord')
        layout = ('name', 'active', 'ord')
        sorting = (('ord', ASC),)
        cb = pp.CodebookSpec(display=(_modtitle, 'name'))
    _REFERER = 'name'
    
    def menu(self, prefix):
        modules = [str(r['name'].value()) for r in
                   self._data.get_rows(active=True, sorting=self._sorting)]
        for m in ('Modules', 'Config'):
            if m not in modules:
                modules.append(m)
        if 'Mapping' not in modules:
            modules.insert(0, 'Mapping')
        return [MenuItem(prefix+'/'+m, spec.title, descr=spec.help)
                for m, spec in [(m, _modspec(m)) for m in modules] if spec]


class Config(WikingModule):
    """Site specific configuration provider.

    This implementation stores the configuration variables as one row in a
    Pytis data object to allow their modification through WMI.

    """
    class Spec(pp.Specification):
        title = _("Config")
        help = _("Edit site configuration.")
        fields = (
            Field('config_id', ),
            Field('title', virtual=True,
                  computer=Computer(lambda r: _("Site Configuration"),
                                    depends=())),
            Field('site_title', _("Site title"), width=24),
            Field('site_subtitle', _("Site subtitle"), width=64),
            Field('login_panel',  _("Show login panel")),
            Field('allow_registration', _("Allow registration"), default=True),
            #Field('allow_wmi_link', _("Allow WMI link"), default=True),
            Field('force_https_login', _("Force HTTPS login"), default=False),
            Field('webmaster_addr', _("Webmaster address")),
            Field('theme', _("Theme"), codebook='Themes',
                  selection_type=CHOICE, not_null=False),
            )
        layout = ('site_title', 'site_subtitle', 'login_panel',
                  'allow_registration', 'force_https_login', 'webmaster_addr',
                  'theme')
    _TITLE_COLUMN = 'title'
    _DEFAULT_ACTIONS = (Action(_("Edit"), 'edit'),)

    class Configuration(object):
        allow_wmi_link = True
        allow_login_ctrl = True
        def __init__(self, row, server):
            self._server = server
            for key in row.keys():
                if key not in ('config_id', 'title'):
                    setattr(self, key, row[key].value() or \
                            hasattr(self, '_default_'+key) and \
                            getattr(self, '_default_'+key)() or None)
        def _default_webmaster_addr(self):
            domain = self._server.server_hostname
            if domain.startswith('www.'):
                domain = domain[4:]
            return 'webmaster@' + domain
    
    def _action_args(self, req):
        # We always work with just one record.
        return dict(record=self._record(self._data.get_row(config_id=0)))
    
    def config(self, server, lang):
        """Return the site-specific configuration object.

        The instance returned by this method must have the following public
        attributes: 'site_title', 'site_subtitle', 'login_panel',
        'webmaster_addr'.

        """
        row = self._data.get_row(config_id=0)
        return self.Configuration(row, server)

    def theme(self):
        """Return the current color theme as a dictionary.

        The returned dictionary assigns color values (strings in the '#rrggbb'
        format) to symbolic color names.  These colors will used for
        stlylesheet substitution.

        """

        theme_id = self._data.get_row(config_id=0)['theme'].value()
        return self._module('Themes').theme(theme_id)
    
    def action_view(self, *args, **kwargs):
        return self.action_show(*args, **kwargs)

        
    
class Panels(WikingModule, Publishable):
    class Spec(pp.Specification):
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
                  descr=_("Number denoting the order of the panel on the "
                          "page.")),
            Field('mapping_id', _("Module"), width=5, codebook='Mapping',
                  selection_type=CHOICE, not_null=False, 
                  display=(_modtitle, 'modname'), validity_condition=\
                  pd.AND(*[pd.NE('modname', pd.Value(pd.String(),_m))
                           for _m in _SYSMODULES+('Pages',)]),
                  descr=_("The items of the selected module will be shown by "
                          "the panel.  Leave blank for a text content "
                          "panel.")),
            Field('identifier', editable=NEVER),
            Field('modname'),
            Field('private'),
            Field('modtitle', _("Module"), virtual=True,
                  computer=Computer(lambda r: _modtitle(r['modname'].value()),
                                    depends=('modname',))),
            Field('size', _("Items count"), width=5,
                  descr=_("Number of items from the selected module, which "
                          "will be shown by the panel.")),
            Field('content', _("Content"), width=50, height=10,
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

    def panels(self, req, lang):
        panels = []
        parser = lcg.Parser()
        config = self._module('Config').config(req.server, lang)
        if config.login_panel and not req.wmi:
            user = req.user()
            content = lcg.p(LoginCtrl(user))
            if config.allow_registration and not user:
                uri = self._module('Users').registration_uri(req)
                if uri:
                    lnk = lcg.link(uri, _("New user registration"))
                    content = lcg.coerce((content, lnk))
            panels.append(Panel('login', _("Login"), content))
        for row in self._data.get_rows(lang=lang, published=True,
                                       sorting=self._sorting):
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
    class Spec(pp.Specification):
        title = _("Languages")
        help = _("Manage available languages.")
        fields = (
            Field('lang_id'),
            Field('lang', _("Code"), width=2, column_width=6,
                  filter=ALPHANUMERIC, post_process=LOWER, fixed=True),
            Field('name', _("Name"), virtual=True,
               computer=Computer(lambda r: lcg.language_name(r['lang'].value()),
                                 depends=())),
            )
        sorting = (('lang', ASC),)
        cb = pp.CodebookSpec(display=lcg.language_name)
        layout = ('lang',)
        columns = ('lang', 'name')
    _REFERER = 'lang'

    def languages(self):
        return [str(r['lang'].value()) for r in self._data.get_rows()]

    
class Titles(WikingModule):
    """Provide localized titles for 'Mapping' items."""
    class Spec(pp.Specification):
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
    
    def titles(self, lang):
        """Return a dictionary of localized item titles keyed by identifier."""
        return dict([(row['mapping_id'].value(), row['title'].value())
                     for row in self._data.get_rows(lang=lang)])

class Themes(WikingModule):
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
            return self.__class__(self._id, value or self._default,
                                  inherit=self._inherit)

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

    class Spec(pp.Specification):
        title = _("Themes")
        help = _("Manage available color themes. Go to Configuration to "
                 "change the currently used theme.")
        def fields(self):
            return (
                Field('theme_id'),
                Field('name', _("Name"), width=20),
                ) + tuple([
                Field(c.id(), c.id(), dbcolumn=c.id().replace('-','_'),
                      type=pd.Color())
                for c in Themes.COLORS])
        def layout(self):
            return ('name',) + tuple([c.id() for c in Themes.COLORS])
        columns = ('name',)
        cb = pp.CodebookSpec(display='name')
        
    def theme(self, theme_id):
        if theme_id is not None:
            row = self._data.get_row(theme_id=theme_id)
            colors = [c.clone(row[c.id()].value()) for c in self.COLORS]
        else:
            colors = self.COLORS
        return dict(color=self.Colors(colors))

# ==============================================================================
# The modules below are able to handle requests directly.  The modules above
# are system modules used internally by Wiking.
# ==============================================================================

class Pages(WikingModule, Publishable):
    class Spec(pp.Specification):
        title = _("Pages")
        help = _("Manage available pages of structured text content.")
        def fields(self): return (
            Field('page_id'),
            Field('mapping_id'),
            Field('identifier', _("Identifier"), editable=ONCE, not_null=True,
                  descr=_("The identifier may be used to refer to this page "
                          "from outside and also from other pages. "
                          "A valid identifier can only contain letters, "
                          "digits, dashes and underscores.  It must start "
                          "with a letter.")),
            Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                  selection_type=CHOICE, value_column='lang'),
            Field('title', _("Title")),
            Field('title_', _("Title"), virtual=True,
                  computer=Computer(self._title,
                                    depends=('title', 'identifier'))),
            Field('_content', _("Content"), compact=True, height=20, width=80,
                  descr=_STRUCTURED_TEXT_DESCR),
            Field('content'),
            Field('published', _("Published")),
            Field('status', _("Status"), virtual=True,
                  computer=Computer(self._status,
                                    depends=('content', '_content'))),
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
        sorting = (('identifier', ASC), ('lang', ASC),)
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
    
    _INSERT_MSG = _("New page was successfully created. Don't forget to "
                    "publish it when you are done. Please, visit the "
                    "'Mapping' module if you want to add the page to the "
                    "main menu.")
    _UPDATE_MSG = _("Page content was modified, however the changes remain "
                    "unpublished. Don't forget to publish the changes when "
                    "you are done.")
    
    _IS_OK = pd.NE('content', pd.Value(pd.String(), None))
    _ACTIONS = (Action(_("Publish changes"), 'sync', enabled=lambda r:
                       r['_content'].value() != r['content'].value(),
                       descr=_("Publish the current modified content")),
                Action(_("Preview"), 'preview',
                       enabled=lambda r: r['_content'].value() is not None,
                       descr=_("Display the current version of the page")),
                Action(_("Translate"), 'translate',
                       enabled=lambda r: r['_content'].value() is None,
                       descr=_("Create the content by translating another "
                               "language variant")),
                )

    def _variants(self, record):
        return [str(r['lang'].value()) for r in 
                self._data.get_rows(mapping_id=record['mapping_id'].value(),
                                    condition=self._IS_OK)]

    def handle(self, req):
        if not req.wmi and len(req.path) == 2:
            return self._module('Attachments').handle(req)
        return super(Pages, self).handle(req)

    def _resolve(self, req):
        if len(req.path) == 1:
            lang = req.param('lang')
            if lang is not None:
                row = self._data.get_row(identifier=req.path[0], lang=lang,
                                         condition=self._IS_OK)
                if row:
                    return row
            else:
                variants = self._data.get_rows(identifier=req.path[0],
                                               condition=self._IS_OK)
                if variants:
                    for lang in req.prefered_languages():
                        for row in variants:
                            if row['lang'].value() == lang:
                                return row
                    raise NotAcceptable([str(r['lang'].value())
                                         for r in variants])
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
                  lcg.WikiText(a.descr() or ''))
                 for a in attachments if a.listed()]
        attachments_section = items and lcg.Section(title=_("Attachments"),
                                                    content=lcg.ul(items))
        if text:
            sections = lcg.Parser().parse(text)
            if attachments_section:
                sections += [attachments_section]
            content = lcg.SectionContainer(sections, toc_depth=0)
        else:
            content = attachments_section
        return self._document(req, content, record, resources=attachments,
                              err=err, msg=msg)

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
            langs = [(str(row['lang'].value()),
                      lcg.language_name(row['lang'].value())) for row in 
                     self._data.get_rows(mapping_id=record['mapping_id'].value(),
                                         condition=cond)]
            if not langs:
                e = _("Content for this page does not exist in any language.")
                return self.action_show(req, record, err=e)
            d = pw.SelectionDialog('src_lang', _("Choose source language"),
                                   langs, action='translate',
                                   hidden=[(id, record[id].value()) for id in
                                           ('mapping_id', 'lang')])
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
            self._update_values(record, content=record['_content'].value())
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
            Field('page_attachment_id', computer=\
                  Computer(lambda r: '%d.%s' % (r['attachment_id'].value(),
                                                r['lang'].value()),
                           depends=('attachment_id', 'lang'))),
            Field('attachment_id'),
            Field('mapping_id', _("Page"), codebook='Mapping', editable=ONCE),
            Field('identifier'),
            Field('lang', _("Language"), codebook='Languages', 
                  selection_type=CHOICE, editable=ONCE, value_column='lang'),
            Field('page_id'),
            Field('file', _("File"), virtual=True, editable=ALWAYS,
                  type=pd.Binary(not_null=True, maxlen=3*MB),
                  computer=self._file_computer('file', '_filename',
                                               origname='filename',
                                               mime='mime_type'),
                  descr=_("Upload a file from your local system.  The file "
                          "name will be used to refer to the attachment "
                          "within the page content.")),
            Field('filename', _("Filename"),
                  computer=fcomp(lambda f: f.filename())),
            Field('mime_type', _("Mime-type"), width=22,
                  computer=fcomp(lambda f: f.type())),
            Field('title', _("Title"), width=30, maxlen=64,
                  descr=_("The name of the attachment (e.g. the full name of "
                          "the document). If empty, the file name will be "
                          "used instead.")),
            Field('description', _("Description"), width=60, height=3,
                  descr=_("Optional description used for the listing of "
                          "attachments (see below)."), maxlen=240),
            Field('ext', virtual=True,
                  computer=Computer(self._ext, ('filename',))),
            Field('bytesize', _("Byte size"),
                  computer=fcomp(lambda f: pp.format_byte_size(len(f)))),
            Field('listed', _("Listed"), default=True,
                  descr=_("Check if you want the item to appear in the "
                          "listing of attachments at the bottom of the "
                          "page.")),
            #Field('timestamp', type=DateTime()), #, default=now),
            # Fields supporting file storage.
            Field('dbname'),
            Field('_filename', virtual=True, computer=\
                  self._filename_computer('dbname', 'attachment_id', 'ext')),
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
        ('duplicate key violates unique constraint ' + \
         '"_attachments_mapping_id_key"',
         _("Attachment of the same filename already exists for this page.")),)
    
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
            row = self._data.get_row(identifier=req.path[0],
                                     filename=req.path[1])
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
        return (str(record['mime_type'].value()),
                record['file'].value().buffer())

    
class News(WikingModule):
    class Spec(pp.Specification):
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
            Field('content', _("Text"), height=3, width=60,
                  descr=_STRUCTURED_TEXT_DESCR + ' ' + \
                  _("It is, however, recommened to use the simplest possible "
                    "formatting, since the item may be also published through "
                    "an RSS channel, which does not support formatting.")),
            Field('author', _("Author"), codebook='Users'),
            Field('date_title', virtual=True,
                  computer=Computer(self._date_title,
                                    depends=('date', 'title'))))
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
    _CUSTOM_VIEW = CustomViewSpec('title', meta=('timestamp', 'author'),
                                  content='content', anchor="item-%s",
                                  custom_list=True)
        
    def _link_provider(self, req, row, cid, target=None, **kwargs):
        identifier = self._identifier(req)
        if not req.wmi and cid == 'title' and identifier is not None:
            anchor = '#item-'+ row[self._referer].export()
            return make_uri('/'+ identifier, **kwargs) + anchor
        elif not issubclass(target, Panel):
            return super(News, self)._link_provider(req, row, cid,
                                                    target=target, **kwargs)


class Planner(News):
    class Spec(pp.Specification):
        title = _("Planner")
        help = _("Announce future events by date in a callendar-like listing.")
        def fields(self): return (
            Field('planner_id', editable=NEVER),
            Field('start_date', _("Date"), width=10,
                  type=Date(not_null=True, constraints=(self._check_date,)),
                  descr=_("The date when the planned event begins. "
                          "Enter the date including the year. "
                          "Example: %(date)s",
                          date=lcg.LocalizableDateTime((now()+7).date))),
            Field('end_date', _("End date"), width=10, type=Date(),
                  descr=_("The date when the event ends if it is not the "
                          "same as the start date (for events which last "
                          "several days.")),
            Field('date', _("Date"), virtual=True,
                  computer=Computer(self._date,
                                    depends=('start_date', 'end_date'))),
            Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                  selection_type=CHOICE, value_column='lang'),
            Field('title', _("Briefly"), column_label=_("Event"), width=32,
                  descr=_("The event summary (title of the entry).")),
            Field('content', _("Text"), height=3, width=60,
                  descr=_STRUCTURED_TEXT_DESCR + ' ' + \
                  _("It is, however, recommened to use the simplest possible "
                    "formatting, since the item may be also published through "
                    "an RSS channel, which does not support formatting.")),
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
    _CUSTOM_VIEW = CustomViewSpec('date_title', meta=('author', 'timestamp'),
                                  content='content', anchor="item-%s",
                                  custom_list=True)
    _RSS_TITLE_COLUMN = 'date_title'
    _RSS_LINK_COLUMN = 'title'
    _RSS_DATE_COLUMN = None
    def _condition(self):
        return pd.OR(pd.GE('start_date', pd.Value(pd.Date(), today())),
                     pd.GE('end_date', pd.Value(pd.Date(), today())))

    
class Images(StoredFileModule):
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
                  type=pd.Image(not_null=True, maxlen=3*MB,
                                maxsize=(3000, 3000)), computer=
                  self._file_computer('image', '_image_filename',
                               compute=lambda r: self._resize(r, (800, 800)))),
            Field('thumbnail', virtual=True, type=pd.Image(), computer=
                  self._file_computer('thumbnail', '_thumbnail_filename',
                               compute=lambda r: self._resize(r, (130, 130)))),
            Field('filename', _("File"),
                  computer=fcomp(lambda f: f.filename())),
            Field('title', _("Title"), width=30),
            Field('author', _("Author"), width=30),
            Field('location', _("Location"), width=50),
            Field('description', _("Description"), width=80, height=5),
            Field('taken', _("Date of creation"), type=DateTime()),
            Field('format', computer=imgcomp(lambda i: i.format.lower())),
            Field('width', _("Width"), computer=imgcomp(lambda i: i.size[0])),
            Field('height', _("Height"), computer=imgcomp(lambda i: i.size[1])),
            Field('size', _("Pixel size"),
                  computer=imgcomp(lambda i: '%dx%d' % i.size)),
            Field('bytesize', _("Byte size"),
                  computer=fcomp(lambda f: pp.format_byte_size(len(f)))),
            Field('exif'),
            Field('timestamp', default=now),
            # Fields supporting image file storage.
            Field('dbname'),
            Field('_filename', virtual=True,
                  computer=self._filename_computer('-orig')),
            Field('_thumbnail_filename', virtual=True,
                  computer=self._filename_computer('-thumbnail')),
            Field('_image_filename', virtual=True,
                  computer=self._filename_computer()),
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

        layout = ('file', 'title', 'author', 'location', 'taken',
                  'description')
        columns = ('filename', 'title', 'author', 'location', 'taken',
                   'description')
        
    _STORED_FIELDS = (('file', '_filename'),
                      ('image', '_image_filename'),
                      ('thumbnail', '_thumbnail_filename'))
    _SEQUENCE_FIELDS = (('image_id', '_images_image_id_seq'),)
        
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
    
    
class Stylesheets(WikingModule):
    class Spec(pp.Specification):
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
    _MATCHER = re.compile(r"\$(\w[\w-]*)(?:\.(\w[\w-]*))?")

    def _subst(self, theme, name, key):
        value = theme[name]
        if key:
            value = value[key]
        return value

    def stylesheets(self):
        # TODO: Use self._identifier() ???
        identifier = self._module('Mapping').get_identifier(self.name())
        if identifier:
            return [lcg.Stylesheet(r['identifier'].value(),
                                   uri=('/'+ identifier + \
                                        '/'+ r['identifier'].value()))
                    for r in self._data.get_rows(active=True)]
        else:
            return []
            
    def action_view(self, req, record, msg=None):
        content = record['content'].value()
        if content is None:
            filename = os.path.join(cfg.wiking_dir, 'resources', 'css',
                                    record['identifier'].value())
            if os.path.exists(filename):
                content = "".join(file(filename).readlines())
            else:
                raise NotFound
        theme = self._module('Config').theme()
        f = lambda m: self._subst(theme, *m.groups())
        return ('text/css', self._MATCHER.sub(f, content))


class Users(WikingModule):
    class Spec(pp.Specification):
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
                  descr=_("Please write the new password into each of the two "
                          "fields.  Leave both fields blank if you are "
                          "editing an existing account and don't want to "
                          "change the password.")),
            Field('fullname', _("Full Name"), virtual=True, editable=NEVER,
                  computer=Computer(self._fullname,
                                    depends=('firstname','surname','login'))),
            Field('user', _("User"), dbcolumn='user_', computer=\
                  Computer(self._user, depends=('fullname', 'nickname'))),
            Field('firstname', _("First name")),
            Field('surname', _("Surname")),
            Field('nickname', _("Nickname")),
            Field('email', _("E-mail"), width=36),
            Field('phone', _("Phone")),
            Field('address', _("Address"), height=3),
            Field('uri', _("URI"), width=36),
            Field('since', _("Registered since"),
                  type=DateTime(show_time=False), default=now),
            Field('enabled', _("Enabled")),
            Field('contributor', _("Contribution privileges")),
            Field('author', _("Authoring privileges")),
            Field('admin', _("Admin privileges")),
            Field('session_key'),
            Field('session_expire'),
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
        return super(Users, self)._actions(req, record)
        
    def _redirect_after_insert(self, req, record):
        content = lcg.p(_("Registration completed successfuly. "
                          "Your account now awaits administrator's approval."))
        return self._document(req, content, subtitle=_("Registration"))
    
    def user(self, login):
        return self._record(self._data.get_row(login=login))

    def check_session(self, login, session_key):
        row = self._data.get_row(login=login, session_key=session_key)
        if row and row['session_expire'].value() > now():
            user = self._record(row)
            expire = now() + TimeDelta(hours=2)
            self._update_values(user, session_expire=expire)
            return user
        else:
            return  None

    def save_session(self, user, session_key):
        exp = now() + TimeDelta(hours=2)
        self._update_values(user, session_expire=exp, session_key=session_key)

    def close_session(self, user):
        self._update_values(user, session_expire=None, session_key=None)

    def registration_uri(self, req):
        identifier = self._identifier(req)
        return identifier and make_uri('/'+identifier, action='add') or None
        
        
class Rights(Users):
    class Spec(Users.Spec):
        title = _("Access Rights")
        help = _("Manage access rights of registered users.")
        layout = ('enabled', 'contributor', 'author', 'admin')
        columns = ('user', 'login', 'enabled', 'contributor', 'author','admin')
    _ALLOW_TABLE_LAYOUT_IN_FORMS = True
    _RIGHTS_add = _RIGHTS_insert = ()
    _RIGHTS_edit = _RIGHTS_update = Roles.ADMIN
    _RIGHTS_remove = ()


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
        
