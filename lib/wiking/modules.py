# Copyright (C) 2006 Brailcom, o.p.s.
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

from pytis.presentation import Computer, CbComputer
from mx.DateTime import now, today, TimeDelta
from lcg import _html
import re, types

CHOICE = pp.SelectionType.CHOICE
ALPHANUMERIC = pp.TextFilter.ALPHANUMERIC
LOWER = pp.PostProcess.LOWER
ONCE = pp.Editable.ONCE
NEVER = pp.Editable.NEVER
ASC = pd.ASCENDENT
DESC = pd.DESCENDANT

_ = lcg.TranslatableTextFactory('wiking')

def _modtitle(m):
    """Return a localizable module title by module name."""
    if m is None:
        return ''
    cls = globals().get(m)
    return cls and cls.Spec.title or concat(m,' (',_("unknown"),')')

# This constant lists names of modules which don't handle requests directly and
# thus should not appear in the module selection for the Mapping items.
# It should be considered a temporary hack, but the list should be maintained.
_SYSMODULES = ('Languages', 'Modules', 'Config', 'Mapping','Panels', 'Titles')

class Publishable(object):
    "Mix-in class for modules where the records can be published/unpublished."
    _MSG_PUBLISHED = _("The item was published.")
    _MSG_UNPUBLISHED = _("The item was unpublished.")

    def _change_published(row):
        data = row.data()
        key = [row[c.id()] for c in data.key()]
        values = data.make_row(published=not row['published'].value())
        data.update(key, values)
    _change_published = staticmethod(_change_published)
    
    _ACTIONS = (Action(_("Publish"), 'publish',
                       handler=lambda r: Publishable._change_published(r),
                       enabled=lambda r: not r['published'].value()),
                Action(_("Unpublish"), 'unpublish',
                       handler=lambda r: Publishable._change_published(r),
                       enabled=lambda r: r['published'].value()),
                )
    
    def publish(self, req, object, publish=True):
        err, msg = (None, None)
        #log(OPR, "Publishing item:", str(object))
        try:
            if publish != object['published']:
                Publishable._change_published(object.prow())
            object.reload()
            msg = publish and self._MSG_PUBLISHED or self._MSG_UNPUBLISHED
        except pd.DBException, e:
            err = self._analyze_exception(e)
        action = req.wmi and self.show or self.view
        return action(req, object, msg=msg, err=err)

    def unpublish(self, req, object):
        return self.publish(req, object, publish=False)


    
class Translatable(object):
    _ACTIONS = (Action(_("Translate"), 'translate'),)
    def translate(self, req, object):
        prefill = [(k, object.export(k)) for k in object.keys() if k != 'lang']
        return self.add(req, prefill=dict(prefill))
    
    
class Modules(WikingModule):
    class Spec(pp.Specification):
        class _ModNameType(pd.String):
            VM_UNKNOWN_MODULE = 'VM_UNKNOWN_MODULE'
            _VM_UNKNOWN_MODULE_MSG = _("Unknown module.  You either "
                                       "misspelled the name or the module "
                                       "is not installed properly.")
            def _check_constraints(self, value):
                pd.String._check_constraints(self, value)
                if not globals().has_key(value) or \
                       not issubclass(globals()[value], WikingModule):
                    raise self._validation_error(self.VM_UNKNOWN_MODULE)
        title = _("Modules")
        fields = (
            Field('mod_id'),
            Field('name', _("Name"), type=_ModNameType()),
            Field('title', _("Title"), virtual=True,
                  computer=Computer(lambda r: _modtitle(r['name'].value()),
                                    depends=('name',))),
            Field('active', _("Active")),
            )
        columns = ('title', 'active')
        layout = ('name', 'active')
        sorting = (('name', ASC),)
        cb = pp.CodebookSpec(display=(_modtitle, 'name'))
    
    _REFERER = 'name'
    _TITLE_COLUMN = 'title'
    
    def menu(self, prefix):
        modules = [str(r['name'].value())
                   for r in self._data.get_rows(active=True)]
        for m in ('Modules', 'Config'):
            if m not in modules:
                modules.append(m)
        if 'Mapping' not in modules:
            modules.insert(0, 'Mapping')
        return [MenuItem(prefix+'/'+m, _modtitle(m)) for m in modules]

    
class Mapping(WikingModule, Publishable):
    class Spec(pp.Specification):
        title = _("Mapping")
        fields = (
            Field('mapping_id', width=5, editable=NEVER),
            #Field('parent', _("Parent"), codebook='Mapping'),
            Field('identifier', _("Identifier"),
                  filter=ALPHANUMERIC, post_process=LOWER, fixed=True,
                  type=pd.Identifier(maxlen=32), width=20),
            Field('mod_id', _("Module"), selection_type=CHOICE,
                  codebook='Modules',
                  validity_condition=pd.AND(*[pd.NE('name',
                                                    pd.Value(pd.String(),_m))
                                              for _m in _SYSMODULES])),
            Field('modname', _("Module")),
            Field('modtitle', _("Module"), virtual=True,
                  computer=Computer(lambda r: _modtitle(r['modname'].value()),
                                    depends=('modname',))),
            Field('published', _("Published")),
            Field('ord', _("Menu order"), width=5))
        sorting = (('ord', ASC), ('identifier', ASC))
        bindings = {'Content': pp.BindingSpec(_("Page content"), 'mapping_id')}
        columns = ('identifier', 'modtitle', 'published', 'ord')
        layout = ('identifier', 'mod_id', 'published', 'ord')
        cb = pp.CodebookSpec(display='identifier')
    _REFERER = _TITLE_COLUMN = 'identifier'

    def _link_provider(self, row, col, uri, wmi=False, args=()):
        if wmi and col.id() == 'modtitle':
            return '/_wmi/' + row['modname'].value()
        else:
            return super(Mapping, self)._link_provider(row, col, uri, wmi=wmi,
                                                       args=args)
            
    def modname(self, identifier):
        row = self._data.get_row(identifier=identifier, published=True)
        if row is None:
            raise NotFound()
        return row['modname'].value()
    
    def identifier(self, modname):
        row = self._data.get_row(modname=modname, published=True)
        return row and row['identifier'].value() or None
    
    def menu(self, lang):
        titles = self._module('Titles').titles(lang)
        return [MenuItem(str(row['identifier'].value()),
                         titles.get(row['mapping_id'].value(),
                                    row['identifier'].value()))
                for row in self._data.get_rows(sorting=self._sorting)
                if row['ord'].value() and row['published'].value()]
                #and row['parent'].value() is None]
                
    def title(self, lang, modname):
        row = self._data.get_row(modname=modname)
        if row:
            titles = self._module('Titles').titles(lang)
            key = row['mapping_id'].value()
            return titles.get(key, row['identifier'].value())
        else:
            return _modtitle(modname)
        


class Config(WikingModule):
    class Spec(pp.Specification):
        title = _("Config")
        fields = (
            Field('config_id', ),
            Field('title', virtual=True,
                  computer=Computer(lambda r: _("Site Configuration"),
                                    depends=())),
            Field('site_title',     _("Site title"), width=24),
            Field('site_subtitle',  _("Site subtitle"), width=64),
            Field('login_panel',    _("Show login panel")),
            Field('webmaster_addr', _("Webmaster address")),
            Field('theme', _("Theme"), codebook='Themes',
                  selection_type=CHOICE, not_null=False),
            )
        layout = ('site_title', 'site_subtitle', 'login_panel',
                  'webmaster_addr', 'theme')
    _TITLE_COLUMN = 'title'
    _DEFAULT_ACTIONS = (Action(_("Edit"), 'edit'),)

    class Configuration(object):
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
    
    def resolve(self, req, path=None):
        # If path is None, only resolution by key is allowed.
        row = self._data.get_row(config_id=0)
        return self.Object(self, self._view, self._data, row)
    
    def view(self, *args, **kwargs):
        return self.show(*args, **kwargs)

    def config(self, server, lang):
        row = self._data.get_row(config_id=0)
        return self.Configuration(row, server)

    def theme(self):
        theme_id = self._data.get_row(config_id=0)['theme'].value()
        return self._module('Themes').theme(theme_id)
        
    
class Panels(WikingModule, Publishable, Translatable):
    class Spec(pp.Specification):
        title = _("Panels")
        fields = (
            Field('panel_id', width=5, editable=NEVER),
            Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                  selection_type=CHOICE, value_column='lang'),
            Field('ptitle', _("Title"), width=30),
            Field('mtitle'),
            Field('title', _("Title"), virtual=True, width=30,
                  computer=Computer(lambda row: row['ptitle'].value() or \
                                    row['mtitle'].value() or \
                                    _modtitle(row['modname'].value()),
                                    depends=('ptitle', 'mtitle', 'modname',))),
            Field('ord', _("Order"), width=5),
            Field('mapping_id', _("Overview"), width=5, codebook='Mapping',
                  selection_type=CHOICE, not_null=False),
            Field('identifier', editable=NEVER),
            Field('modname'),
            Field('modtitle', _("Module"), virtual=True,
                  computer=Computer(lambda r: _modtitle(r['modname'].value()),
                                    depends=('modname',))),
            Field('size', _("Items count"), width=5),
            Field('content', _("Content"), width=50, height=10),
            Field('published', _("Published"), default=lambda : True),
            )
        sorting = (('ord', ASC),)
        columns = ('title', 'ord', 'modtitle', 'size', 'published')
        layout = ('lang', 'ptitle', 'ord',  'mapping_id', 'size',
                  'content', 'published')
    _TITLE_COLUMN = 'title'
    _LIST_BY_LANGUAGE = True

    def panels(self, lang):
        parser = lcg.Parser()
        panels = []
        for row in self._data.get_rows(lang=lang, published=True,
                                       sorting=self._sorting):
            panel_id = row['identifier'].value() or str(row['panel_id'].value())
            title = row['ptitle'].value() or row['mtitle'].value() or \
                    _modtitle(row['modname'].value())
            content = ()
            if row['modname'].value():
                mod = self._module(row['modname'].value())
                content = tuple(mod.panelize(row['identifier'].value(),
                                             lang, row['size'].value()))
            if row['content'].value():
                content += tuple(parser.parse(row['content'].value()))
            panels.append(Panel(panel_id, title, lcg.Container(content)))
        return panels
                
                
class Languages(WikingModule):
    class Spec(pp.Specification):
        title = _("Languages")
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
    _REFERER = _TITLE_COLUMN = 'lang'

    def languages(self):
        return [str(r['lang'].value()) for r in self._data.get_rows()]

    
class Titles(WikingModule, Translatable):
    class Spec(pp.Specification):
        title = _("Titles")
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

    _TITLE_COLUMN = 'identifier'
    _LIST_BY_LANGUAGE = True
    _EXCEPTION_MATCHERS = (
        ('duplicate key violates unique constraint "titles_mapping_id_key"',
         _("The title is already defined for this page in given language.")),)+\
         WikingModule._EXCEPTION_MATCHERS
    
    def titles(self, lang):
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
        Color('frame-bg', '#eee'),
        Color('frame-border', '#ddd', inherit='border'),
        Color('link', '#03b'),
        Color('link-visited', inherit='link'),
        Color('link-hover', '#d60'),
        Color('table-cell', '#f8fafb', inherit='background'),
        Color('table-cell2', '#eaeaff', inherit='table-cell'),
        Color('top-fg', inherit='foreground'),
        Color('top-bg', '#efebe7', inherit='background'),
        Color('top-border', '#9ab', inherit='border'),
        Color('highlight-bg', '#fc8', inherit='heading-bg'), # cur. lang. bg.
        Color('inactive-folder', '#d2d8e0'),
        Color('button-fg', inherit='foreground'),
        Color('button', inherit='heading-bg'),
        Color('button-border', '#9af', inherit='border'),
        Color('error-fg', inherit='foreground'),
        Color('error-bg', '#fdb'),
        Color('error-border', '#fba', inherit='border'),
        Color('message-fg', inherit='foreground'),
        Color('message-bg', '#cfc'),
        Color('message-border', '#aea', inherit='border'),
        )

    class Spec(pp.Specification):
        title = _("Themes")
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
        
    _TITLE_COLUMN = 'name'

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

class Content(WikingModule, Publishable, Translatable):
    class Spec(pp.Specification):
        title = _("Pages")
        fields = (
            Field('content_id'),
            Field('mapping_id', _("Identifier"), codebook='Mapping',
                  editable=ONCE, selection_type=CHOICE,
                  validity_condition=pd.EQ('modname',
                                           pd.Value(pd.String(), 'Content'))),
            Field('identifier', _("Identifier")),
            Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                  selection_type=CHOICE, value_column='lang'),
            Field('title', _("Title")),
            Field('content', _("Content"),
                  compact=True, height=20, width=80),
            Field('published', _("Published")))
        sorting = (('mapping_id', ASC), ('lang', ASC),)
        layout = ('mapping_id', 'lang', 'title', 'content')
        columns = ('title', 'identifier', 'published')
        cb = pp.CodebookSpec(display='identifier')
        
    _REFERER = 'identifier'
    _TITLE_COLUMN = 'title'
    _EXCEPTION_MATCHERS = (
        ('duplicate key violates unique constraint "_content_mapping_id_key"',
         _("The page already exists in given language.")),) + \
         WikingModule._EXCEPTION_MATCHERS
    _EDIT_LABEL = _("Edit this page")
    _LIST_BY_LANGUAGE = True
    
    def _variants(self, object):
        return [str(r['lang'].value())
                for r in self._data.get_rows(mapping_id=object['mapping_id'])]

    def _resolve(self, req, path):
        if len(path) > 1:
            raise NotFound()
        lang = req.param('lang')
        if lang is not None:
            row = self._data.get_row(identifier=path[0], lang=lang,
                                     published=True)
            if not row:
                raise NotFound()
            return row
        else:
            variants = self._data.get_rows(identifier=path[0], published=True)
            if not variants:
                raise NotFound()
            for lang in req.prefered_languages():
                for row in variants:
                    if row['lang'].value() == lang:
                        return row
            raise NotAcceptable([str(r['lang'].value()) for r in variants])

    def view(self, req, object, err=None, msg=None):
        text = object['content']
        content = text and lcg.SectionContainer(lcg.Parser().parse(text),
                                                toc_depth=0) \
                  or lcg.TextContent("")
        return self._document(req, content, object, err=err, msg=msg)

class News(WikingModule, Translatable):
    class Spec(pp.Specification):
        title = _("News")
        def fields(self): return (
            Field('news_id', editable=NEVER),
            Field('timestamp', _("Date"), width=19, format='%Y-%m-%d %H:%M',
                  default=lambda: now().gmtime()),
            Field('date', _("Date"), dbcolumn='timestamp', format='%Y-%m-%d'),
            Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                  selection_type=CHOICE, value_column='lang'),
            Field('title', _("Briefly"), column_label=_("Message"), width=32),
            Field('rss_title', virtual=True,
                  computer=Computer(self._rss_title,
                                    depends=('title', 'date',))),
            Field('content', _("Text"), height=3, width=60))
        sorting = (('timestamp', DESC),)
        columns = ('title', 'date')
        layout = ('lang', 'timestamp', 'title', 'content')
        def _rss_title(self, row):
            return row['title'].value() +' ('+ row['date'].export() +')'
        
    _TITLE_COLUMN = 'title'
    _LIST_BY_LANGUAGE = True
    _PANEL_FIELDS = ('date', 'title')
    _ALLOW_RSS = True
    _RSS_TITLE_COLUMN = 'rss_title'
    _RSS_DESCR_COLUMN = 'content'
    
    class View(WikingModule.GenericView):
        def export(self, exporter):
            date = concat(_("Date"), ': ', self._object.export('timestamp'))
            text = self._export_structured_text(self._object['content'],
                                                exporter)
            return _html.div((_html.div(date, cls='date'), text),
                             cls='news-item')

    class ListView(WikingModule.GenericListView):
        def _export_row(self, exporter, row):
            heading = concat(row['date'].export(), ': ', row['title'].export())
            text = self._export_structured_text(row['content'].value(),
                                                exporter)
            name = 'item-' + row[self._view.fields()[0].id()].export()
            return (_html.div(_html.link(heading, None, name=name),
                              cls='list-heading'),
                    _html.div(text, cls='list-body'))
        
    def _link_provider(self, row, col, uri, wmi=False, args=()):
        if not wmi and col.id() == 'title':
            return _html.uri(uri, *args) +'#item-'+ row[self._referer].export()
        else:
            return super(News, self)._link_provider(row, col, uri, wmi=wmi,
                                                    args=args)


class Planner(News):
    class Spec(pp.Specification):
        title = _("Planner")
        def fields(self): return (
            Field('planner_id', editable=NEVER),
            #TODO: mindate is computed when the spec is read!
            Field('date', _("Date"), width=19, format='%Y-%m-%d',
                  mindate=today().date),
            Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                  selection_type=CHOICE, value_column='lang'),
            Field('title', _("Briefly"), column_label=_("Event"), width=32),
            Field('rss_title', virtual=True,
                  computer=Computer(self._rss_title,
                                    depends=('title', 'date',))),
            Field('content', _("Text"), height=3, width=60))
        sorting = (('date', ASC),)
        columns = ('date', 'title')
        layout = ('lang', 'date', 'title', 'content')
        def _rss_title(self, row):
            return row['date'].export() +': '+ row['title'].value()
    def _condition(self):
        return pd.GT('date', pd.Value(pd.Date(), today()))

    
class Stylesheets(WikingModule):
    class Spec(pp.Specification):
        title = _("Styles")
        fields = (
            Field('stylesheet_id'),
            Field('identifier',  _("Identifier"), width=16),
            Field('active',      _("Active")),
            Field('description', _("Description"), width=40),
            Field('content',     _("Content"), height=20, width=80),
            )
        layout = ('identifier', 'active', 'description', 'content')
        columns = ('identifier', 'active', 'description')
        
    _REFERER = _TITLE_COLUMN = 'identifier'
    _MATCHER = re.compile(r"\$(\w[\w-]*)(?:\.(\w[\w-]*))?")

    def _subst(self, theme, name, key):
        value = theme[name]
        if key:
            value = value[key]
        return value

    def stylesheets(self):
        return [str(r['identifier'].value())
                for r in self._data.get_rows(active=True)]
        
    def view(self, req, object, msg=None):
        content = object['content']
        if content is None:
            filename = os.path.join(cfg.wiking_dir, 'resources', 'css',
                                    object['identifier'])
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
                  type=pd.Identifier(maxlen=16)),
            Field('password', _("Password")),
            Field('fullname', _("Full Name"), virtual=True,
                  computer=Computer(self._fullname,
                                    depends=('firstname','surname','login'))),
            Field('user', _("Name/Nickname"), virtual=True,
                  computer=Computer(self._user,
                                    depends=('fullname', 'nickname'))),
            Field('firstname', _("First name")),
            Field('surname', _("Surname")),
            Field('nickname', _("Nickname")),
            Field('email', _("E-mail"), width=24),
            Field('phone', _("Phone")),
            Field('address', _("Address"), height=3),
            Field('uri', _("URI")),
            Field('enabled', _("Enabled")),
            Field('since', _("Registered since"), format='%Y-%m-%d %H:%M'),
            Field('session_key'),
            Field('session_expire'),
            )
        columns = ('fullname', 'nickname', 'email')
        layout = ('login', 'password', 'firstname', 'surname',
                  'nickname', 'email', 'phone', 'address', 'uri')
    _REFERER = 'login'
    _PANEL_FIELDS = ('fullname',)
    _TITLE_COLUMN = 'fullname'

    def _user(self, row):
        return pp.PresentedRow(self._view.fields(), self._data, row)
        
    def _update(self, user, **kwargs):
        key = [user[c.id()] for c in self._data.key()]
        self._data.update(key, self._data.make_row(**kwargs))

    def user(self, login):
        return self._user(self._data.get_row(login=login))

    def check_session(self, login, session_key):
        user = self._data.get_row(login=login, session_key=session_key)
        if user and user['session_expire'].value() > now().gmtime():
            expire = now().gmtime() + TimeDelta(hours=1)
            self._update(user, session_expire=expire)
            return self._user(user)
        else:
            return  None

    def save_session(self, user, session_key):
        expire = now().gmtime() + TimeDelta(hours=1)
        self._update(user, session_expire=expire, session_key=session_key)

    def close_session(self, user):
        self._update(user, session_expire=None, session_key=None)
        
