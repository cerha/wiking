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
    _RELATED_MODULES = ()
    
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
        self._bindings = spec.binding_spec()
        self._key = key = self._data.key()[0].id()
        self._sorting = self._view.sorting()
        if self._sorting is None:
            self._sorting = ((key, pytis.data.ASCENDENT),)
        self._exception_matchers = [(re.compile(regex), msg)
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
        # TODO: This should go to pytis.web....
        errors = []
        for f in self._view.fields():
            id = f.id()
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
            elif id in self._view.layout().order():
                value_ = ""
            else:
                continue
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
                match = matcher.match(str(e.exception()).strip())
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

    def _actions(self, req, record=None, actions=None, args=None, uri=None):
        if not req.wmi:
            return None
        if not actions:
            if record is not None:
                actions = self._DEFAULT_ACTIONS_FIRST + \
                          self._view.actions() + \
                          self._DEFAULT_ACTIONS_LAST
            else:
                actions = self._LIST_ACTIONS
        return ActionMenu(actions, record, args=args, uri=uri)

    def _link_provider(self, row, cid, wmi=False, **kwargs):
        if cid == self._title_column or cid == self._key:
            if wmi:
                uri = '/_wmi/'+ self.name()
                referer = self._key
            else:
                uri = '/'+ self._identifier
                referer = self._referer
            uri += '/'+ row[referer].export()
            from lcg import _html
            return _html.uri(uri, **kwargs)
        return None

    def _form(self, form, req, *args, **kwargs):
        kwargs['link_provider'] = lambda row, cid: \
                                  self._link_provider(row, cid, wmi=req.wmi)
        #if isinstance(form, pw.EditForm) and req.params.has_key('module'):
        #    kwargs['hidden'] = kwargs.get('hidden', ()) + \
        #                       (('module', req.params['module']),)
        return form(self._data, self._view, self._resolver, *args, **kwargs)
    
    def _get_row_by_key(self, value):
        if isinstance(value, tuple):
            value = value[-1]
        type = self._data.key()[0].type()
        v, error = type.validate(value)
        if error:
            raise NotFound()
        row = self._data.row((v,))
        if row is None:
            raise NotFound()
        return row
        
    def _redirect(self, req):
        return None
    
    def _resolve(self, req):
        # Returns Row, None or raises HttpError.
        if len(req.path) <= 1:
            return None
        elif len(req.path) == 2:
            value = req.path[1]
            if not isinstance(self._referer_type, pd.String):
                v, e = self._referer_type.validate(req.path[1])
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
    
    def _prefill(self, req, new=False):
        keys = [f.id() for f in self._view.fields()]
        prefill = dict([(k, req.params[k]) for k in keys
                        if req.params.has_key(k)])
        if new and not prefill.has_key('lang') and self._LIST_BY_LANGUAGE:
            lang = req.prefered_language(self._module('Languages').languages())
            if lang:
                prefill['lang'] = lang
        return prefill

    def _condition(self):
        # Can be used by a module to filter out invalid (ie outdated) records.
        return None
    
    def _rows(self, lang=None, **kwargs):
        if not kwargs.has_key('sorting'):
            kwargs['sorting'] = self._sorting
        if not kwargs.has_key('condition'):
            kwargs['condition'] = self._condition()
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
        """Return the Record instance initialized by given data row."""
        return self.Record(self._view.fields(), self._data, row, new=new)
    
    def _reload(self, record):
        """Update record data from the database."""
        record.set_row(self._data.row(record.key()))

    # ===== Methods which modify the database =====
    
    def _insert(self, record):
        """Insert a new row into the database and return a Record instance."""
        new_row, success = self._data.insert(record.rowdata())
        if success:
            record.set_row(new_row)
        
    def _update(self, record):
        """Update the record data in the database."""
        self._data.update(record.key(), record.rowdata())
        self._reload(record)

    def _update_values(self, record, **kwargs):
        """Update the record in the database by values of given keyword args."""
        self._data.update(record.key(), self._data.make_row(**kwargs))
        self._reload(record)
    
    def _delete(self, record):
        """Delete the record from the database."""
        if not self._data.delete(record.key()):
            raise pd.DBException('???', Exception("Unable to delete record."))

    # ===== Public methods which are not action handlers =====
    
    def identifier(self):
        """Return current mapping identifier of the module as a string."""
        return self._identifier

    def redirect(self, req):
        """Return the module responsible for handling the request or None."""
        return self._redirect(req)
    
    def resolve(self, req):
        """Return the Record corresponding to the request or None."""
        if req.wmi:
            if len(req.path) == 2: # or req.params.has_key('module'):
                key = req.param(self._key)
                if key is None:
                    row = None
                else:
                    row = self._get_row_by_key(key)
            elif len(req.path) == 3:
                row = self._get_row_by_key(req.path[2])
            else:
                raise NotFound()
        else:
            row = self._resolve(req)
        if row is not None:
            return self._record(row)
        return None

    def record(self, value):
        """Return the record corresponding to given key value."""
        return self._record(self._data.row((value,)))
        
    def related(self, req, binding, modname, record):
        """Return the listing of records related to other module's record."""
        bcol, sbcol = binding.binding_column(), binding.side_binding_column()
        args = {sbcol: record[bcol].value()}
        if self._LIST_BY_LANGUAGE:
            args['lang'] = record['lang'].value()
        content = (
            self._form(ListView, req, self._rows(**args), custom_spec=\
                       (not req.wmi and self._CUSTOM_VIEW or None)),
            self._actions(req, args=args, uri='/_wmi/' + self.name()))
        #lang = req.prefered_language(self._module('Languages').languages())
        #title = self._real_title(lang)
        return lcg.Section(title=self._view.title(), content=content)

    # ===== Action handlers =====
    
    def action_list(self, req, err=None, msg=None):
        lang, variants, rows = self._list(req)
        content = [self._form(ListView, req, rows, custom_spec=\
                              (not req.wmi and self._CUSTOM_VIEW or None))]
        if req.wmi:
            content.extend((self._actions(req),
                            lcg.link('/_doc/'+self.name(), _("Help"))))
        elif self._RSS_TITLE_COLUMN:
            # TODO: This belongs to RssModule.
            content.append(lcg.p(
                _("An RSS channel is available for this section:"), ' ',
                lcg.link(req.uri +'.'+ lang +'.rss',
                         self._real_title(lang) + ' RSS',
                         type='application/rss+xml'), " (",
                lcg.link('_doc/rss?display=inline', _("more about RSS")), ")"))
        return self._document(req, content, lang=lang, variants=variants,
                              err=err, msg=msg)

    def action_show(self, req, record, err=None, msg=None):
        form = self._form(pw.ShowForm, req, record.row())
        content = [form, self._actions(req, record)]
        for modname in self._RELATED_MODULES:
            module, binding = self._module(modname), self._bindings[modname]
            content.append(module.related(req, binding, self.name(), record))
        return self._document(req, content, record, err=err, msg=msg)

    def action_view(self, req, record, err=None, msg=None):
        # `show()' always uses ShowForm, while `view()' may be overriden
        # by the module (using _CUSTOM_VIEW).
        form = self._form(RecordView, req, record.row(),
                          custom_spec=self._CUSTOM_VIEW)
        return self._document(req, form, record, err=err, msg=msg)
    
    def action_add(self, req, errors=()):
        #req.check_auth(pd.Permission.INSERT)
        form = self._form(pw.EditForm, req, None, handler=req.uri, new=True,
                          prefill=self._prefill(req, new=True),
                          errors=errors, action='insert')
        return self._document(req, form, subtitle=_("new record"))

    def action_edit(self, req, record, errors=()):
        form = self._form(pw.EditForm, req, record.row(), handler=req.uri,
                          errors=errors, prefill=self._prefill(req),
                          action='update')
        return self._document(req, form, record, subtitle=_("edit form"))

    def action_remove(self, req, record, err=None):
        form = self._form(pw.ShowForm, req, record.row())
        actions = self._actions(req, record, (Action(_("Remove"), 'delete'),))
        msg = _("Please, confirm removing the record permanently.")
        return self._document(req, (form, actions), record,
                              err=err, subtitle=_("removing"), msg=msg)

    # ===== Action handlers which actually modify the database =====

    def action_insert(self, req):
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
                return self._redirect_after_insert(req, record)
        return self.action_add(req, errors=errors)
            
    def action_update(self, req, record):
        if not req.wmi:
            return
        errors = self._validate(req, record)
        if not errors:
            try:
                self._update(record)
            except pd.DBException, e:
                errors = self._analyze_exception(e)
            else:
                return self._redirect_after_update(req, record)
        return self.action_edit(req, record, errors=errors)

    def action_delete(self, req, record):
        if not req.wmi:
            return
        try:
            self._delete(record)
        except pd.DBException, e:
            err = self._analyze_exception(e)
            return self.action_remove(req, record, err=err)
        else:
            return self._redirect_after_delete(req, record)
        
    # ===== Request redirection after data operations ====-
        
    def _redirect_after_update(self, req, record):
        action = req.wmi and self.action_show or self.action_view
        return action(req, record, msg=self._UPDATE_MSG)
        
    def _redirect_after_insert(self, req, record):
        if req.wmi:
            return self.action_list(req, msg=self._INSERT_MSG)
        else:
            return self.action_view(req, record, msg=self._INSERT_MSG)
        
    def _redirect_after_delete(self, req, record):
        return self.action_list(req, msg=self._DELETE_MSG)
    
        
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

    def action_rss(self, req):
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
                    kwargs = dict([(arg, str(row[fid].value()))
                                   for arg, fid in (('filename', origname),
                                                    ('type', mime)) if fid])
                    result = type.Buffer(row[filename].value(), **kwargs)
                return result
            return pp.Computer(func, depends=())
        
        def _filename_computer(self, subdir, name, ext, append=''):
            """Return a computer computing filename for storing the file."""
            def func(row):
                fname = row[name].export() + append + '.' + row[ext].value()
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
    """Mix-in class for modules with publishable/unpublishable records."""
    
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
    
    def action_publish(self, req, record, publish=True):
        err, msg = (None, None)
        try:
            if publish != record['published'].value():
                Publishable._change_published(record)
            self._reload(record)
            msg = publish and self._MSG_PUBLISHED or self._MSG_UNPUBLISHED
        except pd.DBException, e:
            err = self._analyze_exception(e)
        action = req.wmi and self.action_show or self.action_view
        return action(req, record, msg=msg, err=err)

    def action_unpublish(self, req, record):
        return self.action_publish(req, record, publish=False)

    
class Translatable(object):
    # TODO: This is currently unused, since it has an opposite logic to the
    # "Translate" action implemented for the 'Pages' module.  The ideal
    # solution would be to generalize the "Translate action from 'Pages' and
    # use it as this mixin for all translatable items.  Morover this doesn't
    # work in the new WMI URI schema...
    
    _ACTIONS = (Action(_("Translate"), 'translate'),)
    
    def action_translate(self, req, record):
        req.params.update(dict([(k, record[k].export())
                                for k in record.keys() if k != 'lang']))
        return self.action_add(req)


