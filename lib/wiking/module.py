# -*- coding: iso-8859-2 -*-
# Copyright (C) 2005, 2006, 2007 Brailcom, o.p.s.
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
    _LIST_BY_LANGUAGE = False
    _DEFAULT_ACTIONS_FIRST  = (Action(_("Edit"), 'edit'),)
    _DEFAULT_ACTIONS_LAST   = (Action(_("Remove"), 'remove'),
                               Action(_("List"), 'list', context=None),)
    _LIST_ACTIONS = (Action(_("New record"), 'add', context=None),)
    _EDIT_LABEL = None
    _RSS_TITLE_COLUMN = None
    _RSS_DESCR_COLUMN = None
    _RSS_DATE_COLUMN = None
    _PANEL_DEFAULT_COUNT = 3
    _PANEL_FIELDS = None
    
    _EXCEPTION_MATCHERS = (
        ('duplicate key violates unique constraint ' + \
         '"_?[a-z]+_(?P<id>[a-z_]+)_key"',
         _("This value already exists.  Enter a unique value.")),
        ('null value in column "(?P<id>[a-z_]+)" violates not-null constraint',
         _("Empty value.  This field is mandatory.")),
        )

    _INSERT_MSG = _("New record was successfully inserted.")
    _UPDATE_MSG = _("The record was successfully updated.")
    _DELETE_MSG = _("The record was deleted.")
    
    _spec_cache = {}
    
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
                                          self._module.name(),
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

        def update(self, **kwargs):
            data = self._data.make_row(**kwargs)
            try:
                self._data.update(self.key(), data)
            except pd.DBException, e:
                return self._module._analyze_exception(e)
            self.reload()
            return None

    class _GenericView(object):
        def _export_structured_text(self, text, exporter):
            content = lcg.Container(lcg.Parser().parse(text))
            content.set_parent(self.parent())
            return content.export(exporter)
            
    class View(pw.ShowForm):
        def __init__(self, data, view, resolver, object):
            row = object.row()
            pw.ShowForm.__init__(self, data, view, resolver, row)

    class GenericView(lcg.Content, _GenericView):
        def __init__(self, data, view, object):
            self._data = data
            self._view = view
            self._object = object
            lcg.Content.__init__(self)
            
    class ListView(pw.BrowseForm):
        def __init__(self, data, view, resolver, rows, link_provider):
            pw.BrowseForm.__init__(self, data, view, resolver, rows,
                                   link_provider=link_provider)

    class GenericListView(ListView, _GenericView):
        def _wrap_exported_rows(self, rows):
            from lcg import _html
            rows = [_html.div(row, cls='list-item') for row in rows]
            return _html.div(rows, cls="list-view")

    def spec(cls, resolver):
        try:
            spec = WikingModule._spec_cache[cls]
        except KeyError:
            if cls.Spec.table is None:
                table = pytis.util.camel_case_to_lower(cls.name(), '_')
                cls.Spec.table = table
            if hasattr(cls.Spec, 'actions'):
                cls.Spec.actions = list(cls.Spec.actions)
            else:
                cls.Spec.actions = []
            for base in cls.__bases__ + (cls,):
                if hasattr(base, '_ACTIONS'):
                    for action in base._ACTIONS:
                        if action not in cls.Spec.actions:
                            cls.Spec.actions.append(action)
            cls.Spec.actions = tuple(cls.Spec.actions)
            cls.Spec.data_cls = Data
            spec = WikingModule._spec_cache[cls] = cls.Spec(resolver)
        return spec
    spec = classmethod(spec)

    def name(cls):
        return cls.__name__
    name = classmethod(name)
    
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
        #log(OPR, 'New module instance: %s[%x]' % (self.name(),
        #                                          lcg.positive_id(self)))

    def _datetime_formats(self, req):
        lang = req.prefered_language(self._module('Languages').languages())
        return lcg.datetime_formats(translator(lang))
        
    def _validate(self, req, new=False):
        rdata = []
        errors = []
        kc = [c.id() for c in self._data.key()]
        for id in self._view.layout().order():
            if id in kc and not new:
                continue
            f = self._view.field(id)
            editable = f.editable()
            if editable == pp.Editable.NEVER or \
                   (editable == pp.Editable.ONCE and not new):
                continue
            type = f.type(self._data)
            if req.params.has_key(id):
                strvalue = req.params[id]
                if isinstance(strvalue, tuple):
                    strvalue = strvalue[-1]
            elif isinstance(type, pd.Boolean):
                strvalue = "F"
            else:
                strvalue = ""
            kwargs = {}
            if isinstance(type, (Date, DateTime)):
                formats = self._datetime_formats(req)
                format = formats['date']
                if isinstance(type, DateTime):
                    tf = type.is_exact() and 'exact_time' or 'time'
                    format += ' ' + formats[tf]
                kwargs['format'] = format
            value, error = type.validate(strvalue, **kwargs)
            #log(OPR, "Validation:", (id, strvalue, kwargs, error))
            if error:
                errors.append((id, error.message()))
            else:
                rdata.append((id, value))
        if errors:
            return None, errors
        else:
            row = pytis.data.Row(rdata)
            for check in self._view.check():
                prow = pp.PresentedRow(self._view.fields(), self._data, row)
                result = check(prow)
                if result:
                    if not isinstance(result, (list, tuple)):
                        retult = (result, _("Integrity check failed."))
                    return None, (result,)
            return row, None

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
        title = self._module('Mapping').title(lang, self.name())
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
        if not variants or req.wmi:
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

    def _actions(self, req, object=None, actions=None):
        if not req.wmi:
            return None
        if not actions:
            if object is not None:
                actions = self._DEFAULT_ACTIONS_FIRST + \
                          self._view.actions() + \
                          self._DEFAULT_ACTIONS_LAST
            else:
                actions = self._LIST_ACTIONS
        row = object and object.prow()
        return ActionMenu(req.uri, actions, self._data, row)

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
                    uri = '/_wmi/'+ self.name()
                return _html.uri(uri, *args)
        return None

    def _get_row_by_key(self, params):
        key = []
        for c in self._data.key():
            kc = c.id()
            if not params.has_key(kc):
                return None
            v = params[kc]
            if isinstance(v, tuple):
                v = v[-1]
            value, error = c.type().validate(v)
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
    
    def _default_prefill(self, req):
        if self._LIST_BY_LANGUAGE:
            lang = req.prefered_language(self._module('Languages').languages())
            if lang:
                return {'lang': lang}
        return None

    def _condition(self):
        # Can be used by a module to filter out invalid (ie outdated) records.
        return None
    
    def _rows(self, lang=None, limit=None):
        kwargs = dict(limit=limit,
                      sorting=self._sorting,
                      condition=self._condition())
        if lang and self._LIST_BY_LANGUAGE:
            kwargs['lang'] = lang
        return self._data.get_rows(**kwargs)
    
    def _list(self, req, lang=None, limit=None):
        if self._LIST_BY_LANGUAGE and not req.wmi:
            variants = [str(v.value()) for v in
                        self._data.distinct('lang', sort=pd.ASCENDENT)]
        else:
            variants = self._module('Languages').languages()
        if lang is None:
            lang = req.prefered_language(variants)
        return lang, variants, self._rows(lang=lang)

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
        fields = [self._view.field(id)
                  for id in self._PANEL_FIELDS or self._view.columns()]
        base_uri = '/'+identifier
        prow = pp.PresentedRow(self._view.fields(), self._data, None)
        items = []
        for row in self._rows(lang=lang, limit=count-1):
            prow.set_row(row)
            items.append(PanelItem([(f.id(), prow[f.id()].export(),
                                     self._link_provider(prow, f, base_uri))
                                    for f in fields]))
        if items:
            return items
        else:
            return (lcg.TextContent(_("No records.")),)

    # ===== Action handlers =====
    
    def rss(self, req):
        if not self._RSS_TITLE_COLUMN:
            raise NotFound
        lang, variants, rows = self._list(req, lang=req.param('lang'), limit=8)
        from xml.sax.saxutils import escape
        col = self._view.field(self._TITLE_COLUMN)
        base_uri = req.abs_uri()
        args = lang and (('setlang', lang),) or ()
        prow = pp.PresentedRow(self._view.fields(), self._data, None)
        items = []
        import mx.DateTime as dt
        config = self._module('Config').config(req.server, lang)
        tr = translator(lang)
        for row in rows:
            prow.set_row(row)
            title = escape(tr.translate(prow[self._RSS_TITLE_COLUMN].export()))
            uri = self._link_provider(row, col, base_uri, args=args)
            if self._RSS_DESCR_COLUMN:
                exported = prow[self._RSS_DESCR_COLUMN].export()
                descr = escape(tr.translate(exported))
            else:
                descr = None
            if self._RSS_DATE_COLUMN:
                v = prow[self._RSS_DATE_COLUMN].value()
                date = dt.ARPA.str(v.localtime())
            else:
                date = None
            author = config.webmaster_addr
            items.append((title, uri, descr, date, author))
        title = config.site_title +' - '+ self._real_title(lang)
        result = rss(title, base_uri, items, config.site_subtitle,
                     lang=lang, webmaster=config.webmaster_addr)
        return ('application/xml', result)
    
    def list(self, req, err=None, msg=None):
        def link_provider(row, col):
            return self._link_provider(row, col, req.uri, wmi=req.wmi)
        lang, variants, rows = self._list(req)
        form = req.wmi and pw.BrowseForm or self.ListView
        content = [self._form(form, rows, link_provider)]
        if req.wmi:
            uri = '/_doc/'+self.name()
            h = lcg.Link(lcg.Link.ExternalTarget(uri, _("Help")))
            content.extend((self._actions(req) , h))
        elif self._RSS_TITLE_COLUMN:
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
        form = self._form(pw.ShowForm, object.row())
        return self._document(req, (form, self._actions(req, object)), object,
                              err=err, msg=msg)

    def view(self, req, object, err=None, msg=None):
        view = self.View(self._data, self._view, object)
        return self._document(req, view, object, err=err, msg=msg)
    
    def add(self, req, prefill=None, errors=()):
        #req.check_auth(pd.Permission.INSERT)
        form = self._form(pw.EditForm, None, handler=req.uri, new=True,
                          prefill=prefill or self._default_prefill(req),
                          errors=errors, action='insert')
        return self._document(req, form, subtitle=_("new record"))

    def edit(self, req, object, errors=(), prefill=None):
        form = self._form(pw.EditForm, object.row(), handler=req.uri,
                          errors=errors, prefill=prefill, action='update')
        return self._document(req, form, object, subtitle=_("edit form"))

    def remove(self, req, object, err=None):
        form = self._form(pw.ShowForm, object.row())
        actions = self._actions(req, object, (Action(_("Remove"), 'delete'),))
        msg = _("Please, confirm removing the record permanently.")
        return self._document(req, (form, actions), object,
                              err=err, subtitle=_("removing"), msg=msg)

    # ===== Methods which modify the database =====

    def insert(self, req):
        if not req.wmi:
            return
        row, errors = self._validate(req, new=True)
        if not errors:
            #log(OPR, "New record:", row.items())
            try:
                new_row, success = self._data.insert(row)
                if req.wmi:
                    return self.list(req, msg=self._INSERT_MSG)
                else:
                    object = self.Object(self, self._view, self._data, new_row)
                    return self.view(req, object, msg=self._INSERT_MSG)
            except pd.DBException, e:
                errors = self._analyze_exception(e)
        return self.add(req, prefill=req.params, errors=errors)
            
    def update(self, req, object):
        if not req.wmi:
            return
        row, errors = self._validate(req)
        if not errors:
            #log(OPR, "Updating record:", str(object))
            try:
                self._data.update(object.key(), row)
                object.reload()
                action = req.wmi and self.show or self.view
                return action(req, object, msg=self._UPDATE_MSG)
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
            return self.list(req, msg=self._DELETE_MSG)
        else:
            return self.remove(req, object,
                               err=err or _("Unable to delete record."))
