# -*- coding: iso-8859-2 -*-
# Copyright (C) 2005, 2006 Brailcom, o.p.s.
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

_ = lcg.TranslatableTextFactory('wiking')

class WikingModule(object):
    _REFERER = None
    _TITLE_COLUMN = None
    _RSS_TITLE_COLUMN = None
    _RSS_DESCR_COLUMN = None
    _LIST_BY_LANGUAGE = False
    _DEFAULT_ACTIONS = (Action(_("Edit"), 'edit'),
                        Action(_("Remove"), 'remove'),
                        Action(_("List"), 'list', context=None),
                        )
    _EDIT_LABEL = None
    _PANEL_DEFAULT_COUNT = 3
    _PANEL_FIELDS = None
    
    _EXCEPTION_MATCHERS = (
        ('duplicate key violates unique constraint ' + \
         '"_?[a-z]+_(?P<id>[a-z_]+)_key"',
         _("This value already exists.  Enter a unique value.")),
        ('null value in column "(?P<id>[a-z_]+)" violates not-null constraint',
         _("Empty value.  This field is mandatory.")),
        )

    class Object(object):
        def __init__(self, module, view, data, row):
            self._module = module
            self._data = data
            self._prow = pp.PresentedRow(view.fields(), data, row)
            
        def __getitem__(self, key):
            return self._prow[key].value()

        def __str__(self):
            keys = ["%s=%s" % (c.id(), self._prow[c.id()].export())
                    for c in self._data.key()]
            return "<%s module=%s %s>" % (self.__class__.__name__,
                                          self._module.__class__.__name__,
                                          " ".join(keys))

        def export(self, key):
            return self._prow[key].export()
        
        def keys(self):
            return self._prow.keys()

        def key(self):
            return [self._prow[c.id()] for c in self._data.key()]

        def row(self):
            return self._prow.row()

        def prow(self):
            return self._prow

        def reload(self):
            self._prow.set_row(self._data.row(self.key()))

    class _GenericView(object):
        def _export_structured_text(self, text, exporter):
            content = lcg.Container(lcg.Parser().parse(text))
            content.set_parent(self.parent())
            return content.export(exporter)
            
    class View(pytis.web.ShowForm):
        def __init__(self, data, view, resolver, object):
            row = object.row()
            pytis.web.ShowForm.__init__(self, data, view, resolver, row)

    class GenericView(lcg.Content, _GenericView):
        def __init__(self, data, view, object):
            self._data = data
            self._view = view
            self._object = object
            lcg.Content.__init__(self)
            
    class ListView(pytis.web.BrowseForm):
        def __init__(self, data, view, resolver, rows, link_provider):
            pytis.web.BrowseForm.__init__(self, data, view, resolver, rows,
                                          link_provider=link_provider)

    class GenericListView(ListView, _GenericView):
        def _wrap_exported_rows(self, rows):
            from lcg import _html
            rows = [_html.div(row, cls='list-item') for row in rows]
            return _html.div(rows, cls="list-view")

    def spec(cls, resolver):
        try:
            spec = cls._spec
        except AttributeError:
            if cls.Spec.table is None:
                table = pytis.util.camel_case_to_lower(cls.__name__, '_')
                cls.Spec.table = table
            if not hasattr(cls.Spec, 'actions'):
                cls.Spec.actions = ()
            for base in cls.__bases__:
                if hasattr(base, '_ACTIONS'):
                    cls.Spec.actions += base._ACTIONS
            cls.Spec.data_cls = Data
            spec = cls._spec = cls.Spec(resolver)
        return spec
    spec = classmethod(spec)
            
    # Instance methods
    
    def __init__(self, dbconnection, resolver, get_module):
        self._dbconnection = dbconnection
        self._module = get_module
        self._resolver = resolver
        spec = self.spec(resolver)
        self._data = spec.data_spec().create(dbconnection_spec=dbconnection)
        self._view = spec.view_spec()
        key = self._data.key()
        self._sorting = self._view.sorting()
        if self._sorting is None:
            self._sorting = [(c.id(), pytis.data.ASCENDENT) for c in key]
        self._exception_matchers = [(re.compile('ERROR:  '+regex+'\n'), msg)
                                    for regex, msg in self._EXCEPTION_MATCHERS]
        self._referer = self._REFERER
        if not self._referer and len(key) == 1:
            self._referer = key[0].id()
        if self._referer:
            self._referer_type = self._data.find_column(self._referer).type()
        #log(OPR, 'New module instance: %s[%x]' % (self.__class__.__name__,
        #                                          lcg.positive_id(self)))

    def _validate(self, values, new=False):
        rdata = []
        errors = []
        kc = [c.id() for c in self._data.key()]
        for id in self._view.layout().order():
            if id in kc:
                continue
            f = self._view.field(id)
            editable = f.editable()
            if editable == pp.Editable.NEVER or \
                   (editable == pp.Editable.ONCE and not new):
                continue
            type = f.type(self._data)
            if values.has_key(id):
                strvalue = values[id]
            elif isinstance(type, pd.Boolean):
                strvalue = "F"
            else:
                strvalue = ""
            value, error = type.validate(strvalue)
            #log(OPR, "Validation:", (id, strvalue, error))
            if error:
                errors.append((id, error.message()))
            else:
                rdata.append((id, value))
        if errors:
            return None, errors
        else:
            return pytis.data.Row(rdata), None

    def _analyze_exception(self, e):
        if e.exception():
            for matcher, msg in self._exception_matchers:
                match = matcher.match(str(e.exception()))
                if match:
                    if match.groupdict().has_key('id'):
                        return ((match.group('id'), msg),)
                    return msg
        return unicode(e.exception())

    def _form(self, form, *args, **kwargs):
        return form(self._data, self._view, self._resolver, *args, **kwargs)
    
    def _real_title(self, lang):
        # This is quite a hack...
        title = self._module('Mapping').title(lang, self.__class__.__name__)
        return title or self._view.title()
    
    def _document(self, req, content, obj=None, subtitle=None,
                  lang=None, variants=None, err=None, msg=None):
        if obj:
            # This seems strange, but it is what we want...
            if not subtitle and self._TITLE_COLUMN:
                title = obj.export(self._TITLE_COLUMN)
            else:
                title = self._view.singular()
            lang = self._lang(obj)
            variants = self._variants(obj)
            edit_label = None #self._EDIT_LABEL
        else:
            edit_label = None
        if not variants:
            variants = self._module('Languages').languages()
        if isinstance(content, (list, tuple)):
            content = tuple([c for c in content if c is not None])
        else:
            content = (content,)
        if msg:
            content = (Message(msg),) + tuple(content)
        if err:
            content = (ErrorMessage(err),) + tuple(content)
        if lang is None or req.wmi:
            lang = req.prefered_language(variants)
        if not obj:
            if req.wmi:
                title = self._view.title()
            else:
                title = self._real_title(lang)
        if subtitle:
            title = concat(title, ' :: ', subtitle)
        return Document(title, content, lang=lang, variants=variants,
                        edit_label=edit_label)

    def _actions(self):
        return tuple(self._DEFAULT_ACTIONS) + self._view.actions()

    def _link_provider(self, row, col, uri, wmi=False, args=()):
        if col.id() == self._TITLE_COLUMN:
            from lcg import _html
            if self._referer is not None and not wmi:
                return _html.uri(uri + '/' + row[self._referer].export(),
                                 *args)
            else:
                args += tuple([(c.id(), row[c.id()].export())
                               for c in self._data.key()])
                if wmi:
                    args += (('action', 'show'), )
                    uri = '/_wmi/'+ self.__class__.__name__
                return _html.uri(uri, *args)
        return None

    def _get_row_by_key(self, params):
        key = []
        for c in self._data.key():
            kc = c.id()
            if not params.has_key(kc):
                return None
            value, error = c.type().validate(params[kc])
            if error:
                raise error
            key.append(value)
        row = self._data.row(key)
        if row is None:
            raise NotFound()
        return row
        
    def _resolve(self, req, path):
        # Returns Row, None or raises HttpError.
        if len(path) <= 1:
            return None
        elif self._referer and len(path) == 2:
            value = path[1]
            if not isinstance(self._referer_type, pd.String):
                v, e = self._referer_type.validate(path[1])
                if not e:
                    value = v.value()
                else:
                    raise NotFound()
            return self._data.get_row(**{self._referer: value})
        else:
            raise NotFound()

    def _lang(self, object):
        if self._LIST_BY_LANGUAGE:
            return str(object['lang'])
        else:
            return None
        
    def _variants(self, object):
        return None
    
    def _list(self, req, lang=None):
        if self._LIST_BY_LANGUAGE and not req.wmi:
            variants = [str(v.value()) for v in
                        self._data.distinct('lang', sort=pd.ASCENDENT)]
        else:
            variants = self._module('Languages').languages()
        if lang is None:
            lang = req.prefered_language(variants)
        condition = self._LIST_BY_LANGUAGE and {'lang': lang} or {}
        rows = self._data.get_rows(sorting=self._sorting, **condition)
        return lang, variants, rows

    def resolve(self, req, path=None):
        # If path is None, only resolution by key is allowed.
        row = self._get_row_by_key(req.params)
        if row is None and path is not None:
            row = self._resolve(req, path)
        if row is not None:
            return self.Object(self, self._view, self._data, row)
        return None

    def panelize(self, identifier, lang, count):
        count = count or self._PANEL_DEFAULT_COUNT
        columns = self._PANEL_FIELDS or self._view.columns()
        fields = [self._view.field(id) for id in columns]
        kwargs = dict(limit=count-1, sorting=self._sorting)
        if self._LIST_BY_LANGUAGE:
            kwargs['lang'] = lang
        prow = pp.PresentedRow(self._view.fields(), self._data, None)
        items = []
        base_uri = '/'+identifier
        for row in self._data.get_rows(**kwargs):
            prow.set_row(row)
            items.append(PanelItem([(f.id(), prow[f.id()].export(),
                                     self._link_provider(prow, f, base_uri))
                                    for f in fields]))
        return items

    # ===== Action handlers =====
    
    def rss(self, req):
        if self._RSS_TITLE_COLUMN is None:
            result = ''
        else:
            lang, variants, rows = self._list(req, lang=req.param('lang'))
            from xml.sax.saxutils import escape
            col = self._view.field(self._TITLE_COLUMN)
            uri = req.abs_uri()
            args = lang and (('setlang', lang),) or ()
            items = [(escape(row[self._RSS_TITLE_COLUMN].export()),
                      self._link_provider(row, col, uri, args=args),
                      self._RSS_DESCR_COLUMN and \
                      escape(row[self._RSS_DESCR_COLUMN].export()) or None)
                     for row in rows[:8]]
            config_module = self._module('Config')
            config = config_module.config(req.server, lang)
            title = config.site_title +' - '+ self._real_title(lang)
            result = rss(title, uri, items, descr=config.site_subtitle)
        return ('application/xml', result)
    
    def list(self, req, err=None, msg=None):
        def link_provider(row, col):
            return self._link_provider(row, col, req.uri, wmi=req.wmi)
        lang, variants, rows = self._list(req)
        form = req.wmi and pytis.web.BrowseForm or self.ListView
        content = [self._form(form, rows, link_provider)]
        if req.wmi:
            a = ActionMenu(req.uri,
                           (Action(_("New record"), 'add', context=None),))
            uri = '/_doc/'+self.__class__.__name__
            h = lcg.Link(lcg.Link.ExternalTarget(uri, _("Help")))
            content.extend((a, h))
        elif self._RSS_DESCR_COLUMN:
            rss = lcg.Link.ExternalTarget(req.uri +'.'+ lang +'.rss',
                                          self._real_title(lang) + ' RSS')
            doc = lcg.Link.ExternalTarget('_doc/rss?display=inline',
                                          _("more about RSS"))
            text = _("An RSS channel is available for this section:") + ' '
            p = (lcg.TextContent(text),
                 lcg.Link(rss, type='application/rss+xml'),
                 lcg.TextContent(" ("), lcg.Link(doc), lcg.TextContent(")"))
            content.append(lcg.Paragraph(p))
        return self._document(req, content, lang=lang, variants=variants,
                              err=err, msg=msg)

    def show(self, req, object, err=None, msg=None):
        form = self._form(pytis.web.ShowForm, object.row())
        actions = ActionMenu(req.uri, self._actions(), self._data, object.row())
        return self._document(req, (form, req.wmi and actions or None), object,
                              err=err, msg=msg)

    def view(self, req, object, err=None, msg=None):
        view = self.View(self._data, self._view, object)
        return self._document(req, view, object, err=err, msg=msg)
    
    def add(self, req, prefill=None, errors=()):
        #req.check_auth(pd.Permission.INSERT)
        form = self._form(pytis.web.EditForm, None, handler=req.uri, new=True,
                          prefill=prefill, errors=errors, action='insert')
        return self._document(req, form, subtitle=_("new record"))

    def edit(self, req, object, errors=(), prefill=None):
        form = self._form(pytis.web.EditForm, object.row(), handler=req.uri,
                          errors=errors, prefill=prefill, action='update')
        return self._document(req, form, object, subtitle=_("edit form"))

    def remove(self, req, object, err=None):
        form = self._form(pytis.web.ShowForm, object.row())
        actions = ActionMenu(req.uri, (Action(_("Remove"), 'delete'),),
                             self._data, object.row())
        msg = _("Please, confirm removing the record permanently.")
        return self._document(req, (form, actions), object,
                              err=err, subtitle=_("removing"), msg=msg)

    # ===== Methods which modify the database =====

    def insert(self, req):
        if not req.wmi:
            return
        row, errors = self._validate(req.params, new=True)
        if not errors:
            #log(OPR, "New record:", row.items())
            try:
                new_row, success = self._data.insert(row)
                msg = _("New record was successfully inserted.")
                if req.wmi:
                    return self.list(req, msg=msg)
                else:
                    object = self.Object(self, self._view, self._data, new_row)
                    return self.view(req, object, msg=msg)
            except pd.DBException, e:
                errors = self._analyze_exception(e)
        return self.add(req, prefill=req.params, errors=errors)
            
    def update(self, req, object):
        if not req.wmi:
            return
        row, errors = self._validate(req.params)
        if not errors:
            #log(OPR, "Updating record:", str(object))
            try:
                self._data.update(object.key(), row)
                object.reload()
                action = req.wmi and self.show or self.view
                return action(req, object,
                              msg=_("The record was successfully updated."))
            except pd.DBException, e:
                errors = self._analyze_exception(e)
        return self.edit(req, object, prefill=req.params, errors=errors)

    def delete(self, req, object):
        if not req.wmi:
            return
        #log(OPR, "Deleting record:", str(object))
        deleted, err = (False, None)
        try:
            deleted = self._data.delete(object.key())
        except pd.DBException, e:
            err = self._analyze_exception(e)
        if deleted:
            return self.list(req, msg=_("The record was deleted."))
        else:
            return self.remove(req, object,
                               err=err or _("Unable to delete record."))
