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



class PytisModule(Module, ActionHandler):
    """Module bound to a Pytis data object.

    Each subclass of this module must define a pytis specification by defining
    the class named 'Spec' derived from 'pytis.presentation.Specification'.
    Each instance is then bound to a pytis data object, which is automatically
    created on module instantiation.
    
    """
    _REFERER = None
    _TITLE_COLUMN = None
    _TITLE_TEMPLATE = None
    _LIST_BY_LANGUAGE = False
    _REFERER_PATH_LEVEL = 2
    _DEFAULT_ACTIONS_FIRST = (Action(_("Edit"), 'edit',
                                     descr=_("Modify the record")),)
    _DEFAULT_ACTIONS_LAST =  (Action(_("Remove"), 'remove',
                                     descr=_("Remove the record permanently")),
                              Action(_("List"), 'list', context=None,
                                     descr=_("Back to the list of all "
                                             "records")))
    _LIST_ACTIONS = (Action(_("New record"), 'add', context=None,
                            descr=_("Create a new record")),)
    
    _EXCEPTION_MATCHERS = (
        ('duplicate key violates unique constraint "_?[a-z]+_(?P<id>[a-z_]+)_key"',
         _("This value already exists.  Enter a unique value.")),
        ('null value in column "(?P<id>[a-z_]+)" violates not-null constraint',
         _("Empty value.  This field is mandatory.")),
        )
    _RELATED_MODULES = ()
    
    _INSERT_MSG = _("New record was successfully inserted.")
    _UPDATE_MSG = _("The record was successfully updated.")
    _DELETE_MSG = _("The record was deleted.")
    
    _OWNER_COLUMN = None
    _SUPPLY_OWNER = True
    _RELATION_FIELDS = ()

    _LIST_LAYOUT = None
    _ALLOW_TABLE_LAYOUT_IN_FORMS = True
    _SUBMIT_BUTTONS = None

    _spec_cache = {}

    class Record(pp.PresentedRow):
        """An abstraction of one record within the module's data object."""

        def key(self):
            """Return the value of record's key for data operations."""
            return (self[self._data.key()[0].id()],)

        def reload(self):
            """Reload record data from the database."""
            self.set_row(self._data.row(self.key()))

        def update(self, **kwargs):
            """Update the record in the database by values of given keyword args."""
            self._data.update(self.key(), self._data.make_row(**kwargs))
            self.reload()
    
        def rowdata(self):
            """Return record's row data for insert/update operations."""
            key = self._data.key()[0].id()
            rdata = [(k, v) for k, v in self.row().items()
                     if k != key or v.value() is not None]
            return pd.Row(rdata)

    @classmethod
    def title(cls):
        return cls.Spec.title
    
    @classmethod
    def descr(cls):
        return cls.Spec.help
    
    # Instance methods
    
    def __init__(self, get_module, resolver, dbconnection, **kwargs):
        super(PytisModule, self).__init__(get_module, **kwargs)
        self._resolver = resolver
        self._dbconnection = dbconnection
        spec = self._spec(resolver)
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
        self._links = dict([(f.id(), f.codebook()) for f in self._view.fields() if f.codebook()])

    def _spec(self, resolver):
        return self.__class__.Spec(self.__class__, resolver)

    def _datetime_formats(self, req):
        lang = req.prefered_language(raise_error=False)
        return lcg.datetime_formats(translator(lang))
        
    def _validate(self, req, record):
        # TODO: This should go to pytis.web....
        errors = []
        fields = self._view.layout().order()
        if record.new():
            for id in self._RELATION_FIELDS:
                if req.has_param(id):
                    fields += (id,)
                    break
        for id in fields:
            f = self._view.field(id)
            if not record.editable(id):
                continue
            type = record[id].type()
            kwargs = {}
            if req.params.has_key(id):
                value_ = req.params[id]
                if isinstance(value_, tuple):
                    if len(value_) == 2 and isinstance(type, pd.Password):
                        value_, kwargs['verify'] = value_
                    else:
                        value_ = value_[-1]
                elif isinstance(value_, FileUpload):
                    if isinstance(type, pd.Binary):
                        fname = value_.filename()
                        if fname:
                            # MSIE sends full file path...
                            kwargs['filename'] = fname.split('\\')[-1]
                            kwargs['type'] = value_.type()
                            value_ = value_.file()
                        else:
                            value_ = None
                    else:
                        value_ = value_.filename()
            elif isinstance(type, pd.Binary):
                value_ = None
            elif isinstance(type, pd.Boolean):
                value_ = "F"
            else:
                value_ = ""
            if isinstance(type, (Date, DateTime)):
                formats = self._datetime_formats(req)
                format = formats['date']
                if isinstance(type, DateTime):
                    tf = type.is_exact() and 'exact_time' or 'time'
                    format += ' ' + formats[tf]
                kwargs['format'] = format
            if isinstance(type, (pd.Binary, pd.Password)) and not value_ and not record.new():
                continue # Keep the original file if no file is uploaded.
            if isinstance(type, pd.Password) and kwargs.get('verify') is None:
                kwargs['verify'] = not type.verify() and value_ or ''
            value, error = type.validate(value_, **kwargs)
            #log(OPR, "Validation:", (id, value_, kwargs, error))
            if error:
                errors.append((id, error.message()))
            else:
                record[id] = value
        if errors:
            return errors
        else:
            if record.new() and self._LIST_BY_LANGUAGE and record['lang'].value() is None:
                lang = req.prefered_language(raise_error=False)
                record['lang'] = pd.Value(record['lang'].type(), lang)
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

    def _document(self, req, content, record=None, lang=None, err=None, msg=None, **kwargs):
        if record:
            if self._TITLE_TEMPLATE:
                title = self._TITLE_TEMPLATE.interpolate(lambda key: record[key].export())
            else:
                title = record[self._title_column].export()
            if lang is None and self._LIST_BY_LANGUAGE:
                lang = str(record['lang'].value())
        else:
            title = None # Current menu title will be substituted.
        if isinstance(content, (list, tuple)):
            content = tuple(content)
        else:
            content = (content,)
        if msg:
            content = (Message(msg),) + tuple(content)
        if err:
            content = (ErrorMessage(err),) + tuple(content)
        return Document(title, content, lang=lang, **kwargs)

    def _actions(self, req, record):
        if record is not None:
            return self._DEFAULT_ACTIONS_FIRST + \
                   self._view.actions() + \
                   self._DEFAULT_ACTIONS_LAST
        else:
            return self._LIST_ACTIONS
    
    def _action_menu(self, req, record=None, actions=None, **kwargs):
        actions = [action for action in actions or self._actions(req, record)
                   if isinstance(action, Action) and \
                   self._application.authorize(req, self, action=action.name(), record=record)]
        if not actions:
            return None
        else:
            if req.wmi:
                uri = '/_wmi/' + self.name()
            else:
                uri = '/' + '/'.join(req.path[:self._REFERER_PATH_LEVEL-1])
                kwargs['separate'] = True
            return ActionMenu(uri, actions, self._referer, record, **kwargs)

    def _link_provider(self, req, row, cid, target=None, **kwargs):
        if cid == self._title_column or cid == self._key:
            uri = self._base_uri(req)
            if not uri:
                return None
            return make_uri(uri +'/'+ row[self._referer].export(), **kwargs)
        if self._links.has_key(cid):
            try:
                module = self._module(self._links[cid])
            except AttributeError:
                return None
            return module.link(req, row[cid])
        return None

    def _form(self, form, req, action=None, hidden=(), **kwargs):
        def link_provider(row, cid):
            return self._link_provider(req, row, cid, target=form)
        kwargs['link_provider'] = link_provider
        #if issubclass(form, pw.EditForm) and req.params.has_key('module'):
        #    kwargs['hidden'] = kwargs.get('hidden', ()) + \
        #                       (('module', req.params['module']),)
        if issubclass(form, pw.EditForm):
            kwargs['allow_table_layout'] = self._ALLOW_TABLE_LAYOUT_IN_FORMS
            kwargs['submit'] = self._SUBMIT_BUTTONS
        elif issubclass(form, pw.BrowseForm):
            kwargs['req'] = req
        if issubclass(form, pw.ListView) and not req.wmi and self._LIST_LAYOUT:
            kwargs['layout'] = self._LIST_LAYOUT
        if action is not None:
            hidden += (('action', action),)
        return form(self._data, self._view, self._resolver, handler=req.uri, name=self.name(),
                    hidden=hidden, **kwargs)
    
    def _default_action(self, req, record=None):
        if record is None:
            return 'list'
        else:
            return 'view'
        
    def _action_args(self, req):
        # The request path may resolve to a 'record' argument, no arguments or
        # raise one of HttpError exceptions.
        row = self._resolve(req)
        if row is not None:
            return dict(record=self._record(row))
        else:
            return {}
    
    def _resolve(self, req):
        # Returns Row, None or raises HttpError.
        pathlen = len(req.path)
        level = self._REFERER_PATH_LEVEL
        if pathlen in (level-1, level) and req.has_param(self._key):
            return self._get_row_by_key(req.param(self._key))
        elif pathlen == level:
            return self._get_referered_row(req, req.path[level-1])
        elif pathlen < level:
            return None
        else:
            raise NotFound()

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

    def _get_referered_row(self, req, value):
        if not isinstance(self._referer_type, pd.String):
            v, error = self._referer_type.validate(value)
            if error is not None:
                raise NotFound()
            else:
                value = v.value()
        kwargs = {self._referer: value}
        if self._LIST_BY_LANGUAGE:
            kwargs['lang'] = req.prefered_language()
        row = self._data.get_row(**kwargs)
        if row is None:
            raise NotFound()
        return row
        
    def check_owner(self, user, record):
        if self._OWNER_COLUMN is not None:
            owner = record[self._OWNER_COLUMN].value()
            return user.uid() == owner
        return False
        
    def _prefill(self, req, new=False):
        prefill = dict([(f.id(), req.params[f.id()]) for f in self._view.fields()
                        if req.params.has_key(f.id()) and \
                        not isinstance(f.type(), (pd.Binary, pd.Password))])
        if new and not prefill.has_key('lang') and self._LIST_BY_LANGUAGE:
            lang = req.prefered_language(raise_error=False)
            if lang:
                prefill['lang'] = lang
        return prefill

    def _condition(self, req, lang=None, **kwargs):
        # Can be used by a module to filter out invalid (ie. outdated) records.
        conds = [pd.EQ(k, pd.Value(self._data.find_column(k).type(), v))
                 for k, v in kwargs.items()]
        if lang and self._LIST_BY_LANGUAGE:
            conds.append(pd.EQ('lang', pd.Value(pd.String(), lang)))
        if conds:
            return pd.AND(*conds)
        else:
            return None
    
    def _rows(self, req, lang=None, limit=None):
        return self._data.get_rows(sorting=self._sorting, limit=limit,
                                   condition=self._condition(req, lang=lang))
    
    def _record(self, row, new=False, prefill=None):
        """Return the Record instance initialized by given data row."""
        return self.Record(self._view.fields(), self._data, row, prefill=prefill, new=new)
    

    # ===== Methods which modify the database =====
    
    def _insert(self, record):
        """Insert new row into the database and return a Record instance."""
        new_row, success = self._data.insert(record.rowdata())
        #log(OPR, ":::", (new_row, success, [(k, record.rowdata()[k].value())
        #                                    for k in record.rowdata().keys()]))
        if success and new_row is not None:
            # We can't use set_row(), since it would destroy file fields (they are virtual).
            for key in new_row.keys():
                record[key] = new_row[key]
        
    def _update(self, record):
        """Update the record data in the database."""
        self._data.update(record.key(), record.rowdata())

    def _delete(self, record, raise_error=True):
        """Delete the record from the database."""
        if not self._data.delete(record.key()) and raise_error:
            raise pd.DBException('???', Exception("Unable to delete record."))

    # ===== Public methods =====
    
    def record(self, value):
        """Return the record corresponding to given key value."""
        return self._record(self._data.row((value,)))
        
    def link(self, req, value):
        """Return a uri for given key value."""
        record = self._record(self._data.row((value,)))
        return self._link_provider(req, record, self._key)
        
    def related(self, req, binding, modname, record):
        """Return the listing of records related to other module's record."""
        bcol, sbcol = binding.binding_column(), binding.side_binding_column()
        args = {sbcol: record[bcol].value()}
        content = (self._form(pw.ListView, req, condition=self._condition(req, **args),
                              columns=[c for c in self._view.columns() if c!=sbcol]),
                   self._action_menu(req, args=args))
        return lcg.Section(title=self._view.title(), content=[c for c in content if c])

    # ===== Action handlers =====
    
    def action_list(self, req, err=None, msg=None):
        lang = req.prefered_language()
        content = ()
        if req.wmi:
            help = lcg.p(self._view.help() or '', ' ', lcg.link('/_doc/'+self.name(), _("Help")))
            content += (help,)
        content += (self._form(pw.ListView, req, condition=self._condition(req, lang=lang)),)
        if isinstance(self, RssModule) and not req.wmi and lang:
            content += (self._rss_info(req, lang),)
        content += (self._action_menu(req),)
        return self._document(req, content, lang=lang, err=err, msg=msg)

    def action_view(self, req, record, err=None, msg=None):
        content = [self._form(pw.ShowForm, req, row=record.row()),
                   self._action_menu(req, record)]
        for modname in self._RELATED_MODULES:
            module, binding = self._module(modname), self._bindings[modname]
            content.append(module.related(req, binding, self.name(), record))
        return self._document(req, content, record, err=err, msg=msg)

    def action_add(self, req, errors=()):
        # TODO: Redirect handler to HTTPS if cfg.force_https_login is true?
        # The primary motivation is to protect registration form data.  The
        # same would apply for action_edit.
        form = self._form(pw.EditForm, req, row=None, new=True, action='insert',
                          prefill=self._prefill(req, new=True), errors=errors)
        return self._document(req, form, subtitle=_("new record"))

    def action_edit(self, req, record, errors=(), msg=None):
        form = self._form(pw.EditForm, req, row=record.row(), action='update',
                          prefill=self._prefill(req), errors=errors)
        return self._document(req, form, record, subtitle=_("edit form"), msg=msg)

    def action_remove(self, req, record, err=None):
        form = self._form(pw.ShowForm, req, row=record.row())
        actions = self._action_menu(req, record, (Action(_("Remove"), 'delete'),))
        return self._document(req, (form, actions), record, err=err, subtitle=_("removing"),
                              msg=_("Please, confirm removing the record permanently."))

    # ===== Action handlers which actually modify the database =====

    def action_insert(self, req):
        if self._OWNER_COLUMN and self._SUPPLY_OWNER and req.user():
            prefill = {self._OWNER_COLUMN: req.user().uid()}
        else:
            prefill = None
        record = self._record(None, new=True, prefill=prefill)
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
        errors = self._validate(req, record)
        if not errors:
            try:
                self._update(record)
                record.reload()
            except pd.DBException, e:
                errors = self._analyze_exception(e)
            else:
                return self._redirect_after_update(req, record)
        return self.action_edit(req, record, errors=errors)

    def action_delete(self, req, record):
        try:
            self._delete(record)
        except pd.DBException, e:
            err = self._analyze_exception(e)
            return self.action_remove(req, record, err=err)
        else:
            return self._redirect_after_delete(req, record)
        
    # ===== Request redirection after successful data operations =====

    def _update_msg(self, record):
        return self._UPDATE_MSG
        
    def _insert_msg(self, record):
        return self._INSERT_MSG
        
    def _delete_msg(self, record):
        return self._DELETE_MSG
    
    def _redirect_after_update(self, req, record):
        return self.action_view(req, record, msg=self._update_msg(record))
        
    def _redirect_after_insert(self, req, record):
        return self.action_list(req, msg=self._insert_msg(record))
        
    def _redirect_after_delete(self, req, record):
        return self.action_list(req, msg=self._delete_msg(record))
    
        
# ==============================================================================
# Module extensions 
# ==============================================================================


class RssModule(object):
    
    _RSS_TITLE_COLUMN = None
    _RSS_LINK_COLUMN = None
    _RSS_DESCR_COLUMN = None
    _RSS_DATE_COLUMN = None
    _RSS_AUTHOR_COLUMN = None
    _RSS_LIMIT = 10

    def _descr_provider(self, req, row, translator):
        from xml.sax.saxutils import escape
        if self._RSS_DESCR_COLUMN:
            exported = row[self._RSS_DESCR_COLUMN].export()
            descr = escape(translator.translate(exported))
        else:
            descr = None
        return descr

    def _real_title(self, req):
        def find(items):
            for item in items:
                if item.id == req.uri:
                    return item.title()
                else:
                    title = find(item.submenu())
                    if title:
                        return title
            return None
        return find(self._application.menu(req)) or self._view.title()

    def _rss_info(self, req, lang):
        if self._RSS_TITLE_COLUMN is None:
            return None
        return lcg.p(_("An RSS channel is available for this section:"), ' ',
                     lcg.link(req.uri +'.'+ lang +'.rss',
                              lcg.join((lcg.Title('/'.join(req.path)), 'RSS')),
                              type='application/rss+xml'), " (",
                     lcg.link('_doc/rss', _("more about RSS")), ")")
        
    def action_rss(self, req):
        if not self._RSS_TITLE_COLUMN:
            raise NotFound
        lang = str(req.param('lang'))
        rows = self._rows(req, lang=lang, limit=self._RSS_LIMIT)
        from xml.sax.saxutils import escape
        link_column = self._RSS_LINK_COLUMN or self._RSS_TITLE_COLUMN
        base_uri = req.abs_uri()[:-len(req.uri)]
        args = lang and dict(setlang=lang) or {}
        row = pp.PresentedRow(self._view.fields(), self._data, None)
        items = []
        import mx.DateTime as dt
        tr = translator(lang)
        users = self._module('Users')
        for data_row in rows:
            row.set_row(data_row)
            title = escape(tr.translate(row[self._RSS_TITLE_COLUMN].export()))
            uri = self._link_provider(req, row, link_column, **args)
            uri = uri and base_uri + uri or ''
            descr = self._descr_provider(req, row, tr)
            if self._RSS_DATE_COLUMN:
                v = row[self._RSS_DATE_COLUMN].value()
                date = dt.ARPA.str(v.localtime())
            else:
                date = None
            if self._RSS_AUTHOR_COLUMN:
                uid = row[self._RSS_AUTHOR_COLUMN]
                author = users.record(uid)['email'].export()
            else:
                author = cfg.webmaster_addr
            items.append((title, uri, descr, date, author))
        title = cfg.site_title +' - '+ tr.translate(self._real_title(req))
        result = rss(title, base_uri, items, cfg.site_subtitle,
                     lang=lang, webmaster=cfg.webmaster_addr)
        return ('application/xml', result)


class StoredFileModule(PytisModule):
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
    _SEQUENCE_FIELDS = ()
    
    class Spec(Specification):
        
        def _file_computer(self, id, filename, origname=None, mime=None, compute=None):
            """Return a computer loading the field value from a file."""
            def func(row):
                result = row[id].value()
                # We let the `compute' function decide whether it wants to recompute the value.  If
                # it returns None, we will load the file.
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
                path = (cfg.storage, row[subdir].export(), self.table, fname)
                return os.path.join(*path)
            return pp.Computer(func, depends=(subdir, name, ext))
        
    def _save_files(self, record):
        if not os.path.exists(cfg.storage) \
               or not os.access(cfg.storage, os.W_OK):
            import getpass
            raise Exception("The configuration option 'storage' points to '%(dir)s', but this "
                            "directory does not exist or is not writable by user '%(user)s'." %
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
        for id, seq in self._SEQUENCE_FIELDS:
            if record[id].value() is None:
                value = pd.DBCounterDefault(seq, self._dbconnection).next()
                record[id] = pd.Value(record[id].type(), value)
        super(StoredFileModule, self)._insert(record)
        try:
            self._save_files(record)
        except:
            # TODO: Rollback the transaction instead of deleting the record.
            self._delete(record, raise_error=False)
            raise
        
    def _update(self, record):
        super(StoredFileModule, self)._update(record)
        self._save_files(record)
        
    def _delete(self, record, raise_error=True):
        super(StoredFileModule, self)._delete(record, raise_error=raise_error)
        for id, filename_id in self._STORED_FIELDS:
            fname = record[filename_id].value()
            if os.path.exists(fname):
                os.unlink(fname)
    
# Mixin module classes

class Panelizable(object):

    _PANEL_DEFAULT_COUNT = 3
    _PANEL_FIELDS = None

    def panelize(self, req, lang, count):
        count = count or self._PANEL_DEFAULT_COUNT
        fields = [self._view.field(id)
                  for id in self._PANEL_FIELDS or self._view.columns()]
        prow = pp.PresentedRow(self._view.fields(), self._data, None)
        items = []
        for row in self._rows(req, lang=lang, limit=count-1):
            prow.set_row(row)
            item = PanelItem([(f.id(), prow[f.id()].export(),
                               self._link_provider(req, prow, f.id(),
                                                   target=Panel))
                              for f in fields])
            items.append(item)
        if items:
            return items
        else:
            return (lcg.TextContent(_("No records.")),)


                
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
                       enabled=lambda r: not r['published'].value(),
                                         #and r['_content'].value() is not None),
                       descr=_("Make the item visible to website visitors")),
                Action(_("Unpublish"), 'unpublish',
                       handler=lambda r: Publishable._change_published(r),
                       enabled=lambda r: r['published'].value(),
                       descr=_("Make the item invisible to website visitors")),
                )

    # This is all quite ugly.  It would be much better to solve invoking pytis
    # actions in some more generic way, so that we don't need to implement an
    # action handler method for each pytis action.
    
    def action_publish(self, req, record, publish=True):
        err, msg = (None, None)
        try:
            if publish != record['published'].value():
                Publishable._change_published(record)
                record.reload()
            msg = publish and self._MSG_PUBLISHED or self._MSG_UNPUBLISHED
        except pd.DBException, e:
            err = self._analyze_exception(e)
        return self.action_view(req, record, msg=msg, err=err)

    def action_unpublish(self, req, record):
        return self.action_publish(req, record, publish=False)

