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

class Module(object):
    _REFERER = None
    _TITLE_COLUMN = None
    _LIST_BY_LANGUAGE = False
    _DEFAULT_ACTIONS_FIRST  = (Action(_("Edit"), 'edit'),)
    _DEFAULT_ACTIONS_LAST   = (Action(_("Remove"), 'remove'),
                               Action(_("List"), 'list', context=None),)
    _LIST_ACTIONS = (Action(_("New record"), 'add', context=None),)
    
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
    _CUSTOM_VIEW = None
    
    _spec_cache = {}

    class Record(pp.PresentedRow):
        """An abstraction of one record within the module's data object."""

        def key(self):
            """Return the value of record's key for data operations."""
            return (self[self._data.key()[0].id()],)
    
        def rowdata(self):
            """Return record's row data for insert/update operations."""
            key = self._data.key()[0].id()
            rdata = [(k, v) for k, v in self.row().items()
                     if k != key or v.value() is not None]
            return pd.Row(rdata)
        
    def spec(cls, resolver):
        try:
            spec = Module._spec_cache[cls]
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
            spec = Module._spec_cache[cls] = cls.Spec(resolver)
        return spec
    spec = classmethod(spec)

    def name(cls):
        return cls.__name__
    name = classmethod(name)
    
    # Instance methods
    
    def __init__(self, dbconnection, resolver, get_module, identifier=None):
        self._dbconnection = dbconnection
        self._module = get_module
        self._resolver = resolver
        if identifier is None and self.name() != 'Mapping':
            identifier = self._module('Mapping').get_identifier(self.name())
        self._identifier = identifier
        spec = self.spec(resolver)
        self._data = spec.data_spec().create(dbconnection_spec=dbconnection)
        self._view = spec.view_spec()
        key = self._data.key()[0].id()
        self._sorting = self._view.sorting()
        if self._sorting is None:
            self._sorting = ((key, pytis.data.ASCENDENT),)
        self._exception_matchers = [(re.compile('ERROR:  '+regex+'\n'), msg)
                                    for regex, msg in self._EXCEPTION_MATCHERS]
        self._referer = self._REFERER or key
        self._referer_type = self._data.find_column(self._referer).type()
        self._title_column = self._TITLE_COLUMN or self._view.columns()[0]
        #log(OPR, 'New module instance: %s[%x]' % (self.name(),
        #                                          lcg.positive_id(self)))

    def _datetime_formats(self, req):
        lang = req.prefered_language(self._module('Languages').languages())
        return lcg.datetime_formats(translator(lang))
        
    def _validate(self, req, record):
        errors = []
        for id in self._view.layout().order():
            if not record.editable(id):
                continue
            type = record[id].type()
            kwargs = {}
            if req.params.has_key(id):
                value_ = req.params[id]
                if isinstance(value_, tuple):
                    value_ = value_[-1]
                elif isinstance(value_, FileUpload):
                    if isinstance(type, pd.Binary):
                        if value_.filename():
                            kwargs['filename'] = value_.filename()
                            kwargs['type'] = value_.type()
                            value_ = value_.file()
                        else:
                            value_ = None
                    else:
                        value_ = value_.filename()
            elif isinstance(type, pd.Boolean):
                value_ = "F"
            elif isinstance(type, pd.Binary):
                value_ = None
            else:
                value_ = ""
            if isinstance(type, (Date, DateTime)):
                formats = self._datetime_formats(req)
                format = formats['date']
                if isinstance(type, DateTime):
                    tf = type.is_exact() and 'exact_time' or 'time'
                    format += ' ' + formats[tf]
                kwargs['format'] = format
            if isinstance(type, pd.Binary) and not value_ and not record.new():
                continue # Keep the original file if no file is uploaded.
            value, error = type.validate(value_, **kwargs)
            #log(OPR, "Validation:", (id, type.not_null(), value_, kwargs, error))
            if error:
                errors.append((id, error.message()))
            else:
                record[id] = value
        if errors:
            return errors
        else:
            for check in self._view.check():
                result = check(record)
                if result:
                    if not isinstance(result, (list, tuple)):
                        result = (result, _("Integrity check failed."))
                    return (result,)
            return None

    def _analyze_exception(self, e):
        if e.exception():
            for matcher, msg in self._exception_matchers:
                match = matcher.match(str(e.exception()))
                if match:
                    if match.groupdict().has_key('id'):
                        return ((match.group('id'), msg),)
                    return msg
        return unicode(e.exception())

    def _real_title(self, lang):
        # This is quite a hack...
        title = self._module('Mapping').title(lang, self.name())
        return title or self._view.title()
    
    def _document(self, req, content, record=None, subtitle=None,
                  lang=None, variants=None, err=None, msg=None):
        if record:
            if not subtitle and self._title_column:
                title = record[self._title_column].export()
            else:
                title = self._view.singular()
            lang = self._lang(record)
            variants = self._variants(record)
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
        if not record:
            if req.wmi:
                title = self._view.title()
            else:
                title = self._real_title(lang)
        if subtitle:
            title = concat(title, ' :: ', subtitle)
        return Document(title, content, lang=lang, variants=variants)

    def _actions(self, req, record=None, actions=None):
        if not req.wmi:
            return None
        if not actions:
            if record is not None:
                actions = self._DEFAULT_ACTIONS_FIRST + \
                          self._view.actions() + \
                          self._DEFAULT_ACTIONS_LAST
            else:
                actions = self._LIST_ACTIONS
        return ActionMenu(req.uri, actions, self._data, record)

    def _link_provider(self, row, cid, wmi=False, **kwargs):
        key = self._data.key()[0].id()
        if cid == self._title_column or cid == key:
            if self._identifier is not None and not wmi:
                uri = '/'+ self._identifier
            else:
                kwargs['action'] = kwargs.get('action', 'show')
                uri = '/_wmi/'+ self.name()
            if self._referer is not None and not wmi:
                uri += '/'+ row[self._referer].export()
            else:
                kwargs[key] = row[key].export()
            from lcg import _html
            return _html.uri(uri, **kwargs)
        return None

    def _form(self, form, req, *args, **kwargs):
        kwargs['link_provider'] = lambda row, cid: \
                                  self._link_provider(row, cid, wmi=req.wmi)
        return form(self._data, self._view, self._resolver, *args, **kwargs)
    
    def _get_row_by_key(self, params):
        kc = self._data.key()[0]
        key, type = kc.id(), kc.type()
        if not params.has_key(key):
            return None
        v = params[key]
        if isinstance(v, tuple):
            v = v[-1]
        value, error = type.validate(v)
        if error:
            raise error
        row = self._data.row((value,))
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

    def _lang(self, record):
        if self._LIST_BY_LANGUAGE:
            return str(record['lang'].value())
        else:
            return None
        
    def _variants(self, record):
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

    def _record(self, row, new=False):
        """Return the Record instance representing given data row."""
        return self.Record(self._view.fields(), self._data, row, new=new)
    
    def _reload(self, record):
        """Update record data from the database."""
        record.set_row(self._data.row(record.key()))
    
    def _insert(self, record):
        """Insert a new row into the database and return a Record instance."""
        new_row, success = self._data.insert(record.rowdata())
        if success:
            record.set_row(new_row)
        
    def _update(self, record):
        """Update the record data in the database."""
        self._data.update(record.key(), record.rowdata())

    def _update_values(self, record, **kwargs):
        """Update the record in the database by values of given keyword args."""
        return self._update(record, self._data.make_row(**kwargs))
    
    def _delete(self, record):
        """Delete the record from the database."""
        if not self._data.delete(record.key()):
            raise pd.DBException('???', Exception("Unable to delete record."))

    def identifier(self):
        return self._identifier
            
    def resolve(self, req, path):
        # Path is ignored in WMI (only resolution by key is allowed).
        row = self._get_row_by_key(req.params)
        if row is None and not req.wmi:
            row = self._resolve(req, path)
        if row is not None:
            return self._record(row)
        return None

    # ===== Action handlers =====
    
    def list(self, req, err=None, msg=None):
        lang, variants, rows = self._list(req)
        content = [self._form(ListView, req, rows,
                              custom_spec=(not req.wmi and self._CUSTOM_VIEW
                                           or None))]
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

    def show(self, req, record, err=None, msg=None):
        form = self._form(pw.ShowForm, req, record.row())
        return self._document(req, (form, self._actions(req, record)), record,
                              err=err, msg=msg)

    def view(self, req, record, err=None, msg=None):
        # `show()' always uses ShowForm, while `view()' may be overriden
        # by the module (using _CUSTOM_VIEW).
        form = self._form(RecordView, req, record.row(),
                          custom_spec=self._CUSTOM_VIEW)
        return self._document(req, form, record, err=err, msg=msg)
    
    def add(self, req, prefill=None, errors=()):
        #req.check_auth(pd.Permission.INSERT)
        form = self._form(pw.EditForm, req, None, handler=req.uri, new=True,
                          prefill=prefill or self._default_prefill(req),
                          errors=errors, action='insert')
        return self._document(req, form, subtitle=_("new record"))

    def edit(self, req, record, errors=(), prefill=None):
        form = self._form(pw.EditForm, req, record.row(), handler=req.uri,
                          errors=errors, prefill=prefill, action='update')
        return self._document(req, form, record, subtitle=_("edit form"))

    def remove(self, req, record, err=None):
        form = self._form(pw.ShowForm, req, record.row())
        actions = self._actions(req, record, (Action(_("Remove"), 'delete'),))
        msg = _("Please, confirm removing the record permanently.")
        return self._document(req, (form, actions), record,
                              err=err, subtitle=_("removing"), msg=msg)

    # ===== Action handlers which actually modify the database =====

    def insert(self, req):
        if not req.wmi:
            return
        record = self._record(None, new=True)
        errors = self._validate(req, record)
        if not errors:
            try:
                self._insert(record)
            except pd.DBException, e:
                errors = self._analyze_exception(e)
            else:
                if req.wmi:
                    return self.list(req, msg=self._INSERT_MSG)
                else:
                    return self.view(req, record, msg=self._INSERT_MSG)
        return self.add(req, prefill=req.params, errors=errors)
            
    def update(self, req, record):
        if not req.wmi:
            return
        errors = self._validate(req, record)
        if not errors:
            try:
                self._update(record)
            except pd.DBException, e:
                errors = self._analyze_exception(e)
            else:
                action = req.wmi and self.show or self.view
                return action(req, record, msg=self._UPDATE_MSG)
        return self.edit(req, record, prefill=req.params, errors=errors)

    def delete(self, req, record):
        if not req.wmi:
            return
        try:
            self._delete(record)
        except pd.DBException, e:
            return self.remove(req, record, err=self._analyze_exception(e))
        else:
            return self.list(req, msg=self._DELETE_MSG)


# ==============================================================================
# Module extensions 
# ==============================================================================


class PanelizableModule(Module):

    _PANEL_DEFAULT_COUNT = 3
    _PANEL_FIELDS = None

    def panelize(self, lang, count):
        count = count or self._PANEL_DEFAULT_COUNT
        fields = [self._view.field(id)
                  for id in self._PANEL_FIELDS or self._view.columns()]
        prow = pp.PresentedRow(self._view.fields(), self._data, None)
        items = []
        for row in self._rows(lang=lang, limit=count-1):
            prow.set_row(row)
            item = PanelItem([(f.id(), prow[f.id()].export(),
                               self._link_provider(prow, f.id()))
                              for f in fields])
            items.append(item)
        if items:
            return items
        else:
            return (lcg.TextContent(_("No records.")),)


class RssModule(Module):
    
    _RSS_TITLE_COLUMN = None
    _RSS_DESCR_COLUMN = None
    _RSS_DATE_COLUMN = None

    def rss(self, req):
        if not self._RSS_TITLE_COLUMN:
            raise NotFound
        lang, variants, rows = self._list(req, lang=req.param('lang'), limit=8)
        from xml.sax.saxutils import escape
        col = self._view.field(self._title_column)
        base_uri = req.abs_uri()[:-len(req.uri)]
        kwargs = lang and dict(setlang=lang) or {}
        prow = pp.PresentedRow(self._view.fields(), self._data, None)
        items = []
        import mx.DateTime as dt
        config = self._module('Config').config(req.server, lang)
        tr = translator(lang)
        for row in rows:
            prow.set_row(row)
            title = escape(tr.translate(prow[self._RSS_TITLE_COLUMN].export()))
            uri = base_uri + self._link_provider(row, col.id(), **kwargs)
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


class WikingModule(PanelizableModule, RssModule):
    """The default base class for all modules."""

class StoredFileModule(WikingModule):
    """Module which stores its data in files.

    This class can be used by modules with binary data fields, such as images,
    documents etc.  Pytis supports storing binary data types directly in the
    database, however the current implementation is unfortunately too slow for
    web usage.  Thus we workaround that making the field virtual, storing its
    value in a file and loading it back by its 'computer'.

    """
    
    _STORED_FIELDS = ()
    """A sequence of pairs, where the first item is the identifier of the
    binary field to store, and the second is the identifier of the filename
    field.  The filename field provides the absolute path for saving the
    file."""

    class Spec(pp.Specification):
        
        def _file_computer(self, id, filename, origname=None, mime=None,
                           compute=None):
            """Return a computer loading the field value from a file."""
            def func(row):
                result = row[id].value()
                # We let the `compute' function decide whether it wants to
                # recompute the value.  If it returns None, we will load the
                # file.
                if result is None and compute is not None:
                    result = compute(row)
                if result is None and not row.new():
                    #log(OPR, "Loading file:", row[filename].value())
                    type = row[id].type()
                    kwargs = dict([(arg, row[fid].value())
                                   for arg, fid in (('filename', origname),
                                                    ('type', mime)) if fid])
                    result = type.Buffer(row[filename].value(), **kwargs)
                return result
            return pp.Computer(func, depends=())
        
        def _filename_computer(self, subdir, name, ext, append=''):
            """Return a computer computing filename for storing the file."""
            def func(row):
                fname = row[name].export() +append+'.'+ row[ext].value()
                path = (cfg.storage, row[subdir].value(), self.table, fname)
                return os.path.join(*path)
            return pp.Computer(func, depends=(subdir, name, ext))
        
    def _save_files(self, record):
        if not os.path.exists(cfg.storage) \
               or not os.access(cfg.storage, os.W_OK):
            import getpass
            raise Exception("The configuration option 'storage' points to "
                            "'%(dir)s', but this directory does not exist "
                            "or is not writable by user '%(user)s'." %
                            dict(dir=cfg.storage, user=getpass.getuser()))
        for id, filename_id in self._STORED_FIELDS:
            fname = record[filename_id].value()
            dir = os.path.split(fname)[0]
            if not os.path.exists(dir):
                os.makedirs(dir, 0700)
            buf = record[id].value()
            log(OPR, "Saving file:", (fname, pp.format_byte_size(len(buf))))
            buf.save(fname)
        
    def _insert(self, record):
        super(StoredFileModule, self)._insert(record)
        try:
            self._save_files(record)
        except:
            # TODO: Rollback the transaction instead of deleting the record.
            self._delete(record)
            raise
        
    def _update(self, record):
        super(StoredFileModule, self)._update(record)
        self._save_files(record)
        
    def _delete(self, record):
        super(StoredFileModule, self)._delete(record)
        for id, filename_id in self._STORED_FIELDS:
            fname = record[filename_id].value()
            if os.path.exists(fname):
                os.unlink(fname)
    
# Mixin module classes

class Publishable(object):
    "Mix-in class for modules where the records can be published/unpublished."
    _MSG_PUBLISHED = _("The item was published.")
    _MSG_UNPUBLISHED = _("The item was unpublished.")

    def _change_published(row):
        data = row.data()
        key = (row[data.key()[0].id()],)
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

    # This is all quite ugly.  It would be much better to solve invoking pytis
    # actions in some more generic way, so that we don't need to implement an
    # action handler method for each pytis action.
    
    def publish(self, req, record, publish=True):
        err, msg = (None, None)
        try:
            if publish != record['published'].value():
                Publishable._change_published(record)
            self._reload(record)
            msg = publish and self._MSG_PUBLISHED or self._MSG_UNPUBLISHED
        except pd.DBException, e:
            err = self._analyze_exception(e)
        action = req.wmi and self.show or self.view
        return action(req, record, msg=msg, err=err)

    def unpublish(self, req, record):
        return self.publish(req, record, publish=False)

    
class Translatable(object):
    _ACTIONS = (Action(_("Translate"), 'translate'),)
    def translate(self, req, record):
        prefill = [(k, record[k].export())
                   for k in record.keys() if k != 'lang']
        return self.add(req, prefill=dict(prefill))


