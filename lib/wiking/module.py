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
    """Abstract base class defining the basic Wiking module."""
    
    def name(cls):
        """Return the module name as a string."""
        return cls.__name__
    name = classmethod(name)

    def __init__(self, get_module, resolver, **kwargs):
        """Initialize the instance.

        Arguments:

          get_module -- a callable object which returns the module instance
            when called with a module name as an argument.
          resolver -- Pytis 'Resolver' instance.

        """
        self._module = get_module
        self._resolver = resolver
        super(Module, self).__init__(**kwargs)

    
class RequestHandler(object):
    """Mix-in class for modules capable of handling requests."""
    
    def handle(self, req):
        """Handle the request and return the result.

        The result may be either a 'Document' instance or a pair (MIME_TYPE,
        DATA).  The document instance will be exported into HTML, the MIME data
        will be served directly.

        """
        pass


class ActionHandler(RequestHandler):
    """Mix-in class for modules providing ``actions'' to handle requests.

    The actions are handled by implementing public methods named `action_*',
    where the asterisk is replaced by the action name.  The request parameter
    'action' denotes which action will be used to handle the request.  Each
    action must accept the 'WikingRequest' instance as the first argument, but
    it may also require additional arguments.  The dictionary of additional
    arguments is constructed by the method '_action_args()' depending on the
    request.  When the request doesn't provide the information needed to
    construct all the arguments for the action, the action call will
    automatically fail.  This approach may be legally used to make sure that
    the request contains all the necessary information for calling the action.

    If the request parameter 'action' is not defined, the method
    '_default_action()' will be used to find out which action should be used.
    
    """
    
    def _action_args(self, req):
        """Return the dictionary of additional action arguments."""
        return {}
    
    def _default_action(self, req, **kwargs):
        """Return the name of the default action as a string."""
        return None

    def _action(self, req, action, **kwargs):
        method = getattr(self, 'action_' + action)
        return method(req, **kwargs)

    def handle(self, req):
        kwargs = self._action_args(req)
        if req.params.has_key('action'):
            action = req.param('action')
        else:
            action = self._default_action(req, **kwargs)
        return self._action(req, action, **kwargs)


class PytisModule(Module, ActionHandler):
    """Module bound to a Pytis data object.

    Each subclass of this module must define a pytis specification by defining
    the class named 'Spec' derived from 'pytis.presentation.Specification'.
    Each instance is then bound to a pytis data object, which is automatically
    created on module instantiation.
    
    """
    _REFERER = None
    _TITLE_COLUMN = None
    _LIST_BY_LANGUAGE = False
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
    
    _RIGHTS_view = Roles.ANYONE
    _RIGHTS_show = Roles.ANYONE
    _RIGHTS_list = Roles.ANYONE
    _RIGHTS_add    = _RIGHTS_insert = Roles.ADMIN
    _RIGHTS_edit   = _RIGHTS_update = Roles.ADMIN
    _RIGHTS_remove = _RIGHTS_delete = Roles.ADMIN
    
    _OWNER_COLUMN = None
    _NON_LAYOUT_FIELDS = ()

    _ALLOW_TABLE_LAYOUT_IN_FORMS = True
    
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
            spec = PytisModule._spec_cache[cls]
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
            spec = PytisModule._spec_cache[cls] = cls.Spec(resolver)
        return spec
    spec = classmethod(spec)

    # Instance methods
    
    def __init__(self, get_module, resolver, dbconnection, **kwargs):
        super(PytisModule, self).__init__(get_module, resolver, **kwargs)
        self._dbconnection = dbconnection
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
        self._cached_identifier = (None, None)
        self._links = dict([(f.id(), f.codebook())
                            for f in self._view.fields() if f.codebook()])
        #log(OPR, 'New module instance: %s[%x]' % (self.name(),
        #                                          lcg.positive_id(self)))

    def _identifier(self, req):
        """Return module's current mapping identifier as a string or None."""
        # Since the identifiers may be used many times, they are cached at
        # least for the duration of one request.  We cannot cache them over
        # requests, sice there is no way to invalidate them in the multiprocess
        # server invironment.
        req_, identifier = self._cached_identifier
        if req is not req_:
            identifier = self._module('Mapping').get_identifier(self.name())
            self._cached_identifier = (req, identifier)
        return identifier
        
    def _datetime_formats(self, req):
        lang = req.prefered_language(self._module('Languages').languages(),
                                     raise_error=False)
        return lcg.datetime_formats(translator(lang))
        
    def _validate(self, req, record):
        # TODO: This should go to pytis.web....
        errors = []
        for id in self._view.layout().order() + list(self._NON_LAYOUT_FIELDS):
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
                            # MSIE sends the full file path on windows...
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
            if isinstance(type, (pd.Binary, pd.Password)) \
                   and not value_ and not record.new():
                continue # Keep the original file if no file is uploaded.
            value, error = type.validate(value_, **kwargs)
            #log(OPR, "Validation:", (id, value_, kwargs, error))
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
        # This is quite a hack... It would not work for modules with multiple
        # mapping entries.
        title = self._module('Mapping').title(lang, self.name())
        return title or self._view.title()
    
    def _document(self, req, content, record=None, subtitle=None,
                  lang=None, variants=None, err=None, msg=None, **kwargs):
        if record:
            title = record[self._title_column].export()
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
            title = lcg.concat(title, ' :: ', subtitle)
        return Document(title, content, lang=lang, variants=variants, **kwargs)

    def _actions(self, req, record):
        if record is not None:
            return self._DEFAULT_ACTIONS_FIRST + \
                   self._view.actions() + \
                   self._DEFAULT_ACTIONS_LAST
        else:
            return self._LIST_ACTIONS
    
    def _action_menu(self, req, record=None, actions=None, args=None,
                     uri=None):
        #if not req.wmi:
        #    return None
        actions = [action for action in actions or self._actions(req, record)
                   if self._check_action_rights(req, action.name(), record,
                                                raise_error=False)]
        if not actions:
            return None
        else:
            return ActionMenu(actions, record, args=args, uri=uri)

    def _link_provider(self, req, row, cid, target=None, **kwargs):
        if cid == self._title_column or cid == self._key:
            if req.wmi:
                uri = '/_wmi/'+ self.name()
                referer = self._key
            else:
                identifier = self._identifier(req)
                if not identifier:
                    return None
                uri = '/'+ identifier
                referer = self._referer
            uri += '/'+ row[referer].export()
            return make_uri(uri, **kwargs)
        if self._links.has_key(cid):
            module = self._module(self._links[cid])
            return module.link(req, row[cid])
        return None

    def _form(self, form, req, *args, **kwargs):
        kwargs['link_provider'] = lambda row, cid: \
                         self._link_provider(req, row, cid, target=form)
        #if issubclass(form, pw.EditForm) and req.params.has_key('module'):
        #    kwargs['hidden'] = kwargs.get('hidden', ()) + \
        #                       (('module', req.params['module']),)
        if issubclass(form, pw.EditForm):
            kwargs['allow_table_layout'] = self._ALLOW_TABLE_LAYOUT_IN_FORMS
        return form(self._data, self._view, self._resolver, *args, **kwargs)
    
    def _default_action(self, req, record=None):
        if record is None:
            return 'list'
        else:
            return req.wmi and 'show' or 'view'
        
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

    def _action_args(self, req):
        # The request path may resolve to a 'record' argument, no arguments or
        # raise one of HttpError exceptions.
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
            return dict(record=self._record(row))
        return {}

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

    def _check_action_rights(self, req, action, record, raise_error=True):
        roles = getattr(self, '_RIGHTS_'+action)
        if not isinstance(roles, (tuple, list)):
            roles = (roles,)
        if Roles.OWNER in roles and self._OWNER_COLUMN and record is not None:
            owner_uid = record[self._OWNER_COLUMN].value()
        else:
            owner_uid = None
        return Roles.check(req, roles, owner_uid=owner_uid, raise_error=raise_error)
    
        
    def _action(self, req, action, **kwargs):
        self._check_action_rights(req, action, kwargs.get('record'))
        return super(PytisModule, self)._action(req, action, **kwargs)
    
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

    def _record(self, row, new=False, prefill=None):
        """Return the Record instance initialized by given data row."""
        return self.Record(self._view.fields(), self._data, row,
                           prefill=prefill, new=new)
    
    def _reload(self, record):
        """Update record data from the database."""
        record.set_row(self._data.row(record.key()))

    # ===== Methods which modify the database =====
    
    def _insert(self, record):
        """Insert new row into the database and return a Record instance."""
        new_row, success = self._data.insert(record.rowdata())
        #log(OPR, ":::", (new_row, [(k, record.rowdata()[k].value())
        #                           for k in record.rowdata().keys()]))
        if success and new_row is not None:
            record.set_row(new_row)
        
    def _update(self, record):
        """Update the record data in the database."""
        self._data.update(record.key(), record.rowdata())
        self._reload(record)

    def _update_values(self, record, **kwargs):
        """Update the record in the database by values of given keyword args."""
        self._data.update(record.key(), self._data.make_row(**kwargs))
        self._reload(record)
    
    def _delete(self, record, raise_error=True):
        """Delete the record from the database."""
        if not self._data.delete(record.key()) and raise_error:
            raise pd.DBException('???', Exception("Unable to delete record."))

    # ===== Public methods which are not action handlers =====
    
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
        if self._LIST_BY_LANGUAGE:
            args['lang'] = record['lang'].value()
        content = (
            self._form(ListView, req, self._rows(**args), custom_spec=\
                       (not req.wmi and self._CUSTOM_VIEW or None)),
            self._action_menu(req, args=args, uri='/_wmi/' + self.name()))
        #lang = req.prefered_language(self._module('Languages').languages())
        #title = self._real_title(lang)
        return lcg.Section(title=self._view.title(), content=content)

    # ===== Action handlers =====
    
    def action_list(self, req, err=None, msg=None):
        lang, variants, rows = self._list(req)
        content = req.wmi and \
                  (lcg.p(self._view.help() or '', ' ',
                         lcg.link('/_doc/'+self.name(), _("Help"))),) or ()
        content += (self._form(ListView, req, rows, custom_spec=\
                               (not req.wmi and self._CUSTOM_VIEW or None)),
                    self._action_menu(req))
        if not req.wmi and self._RSS_TITLE_COLUMN:
            # TODO: This belongs to RssModule.
            content += (lcg.p(
                _("An RSS channel is available for this section:"), ' ',
                lcg.link(req.uri +'.'+ lang +'.rss',
                         self._real_title(lang) + ' RSS',
                         type='application/rss+xml'), " (",
                lcg.link('_doc/rss?display=inline',
                         _("more about RSS")), ")"),)
        return self._document(req, content, lang=lang, variants=variants,
                              err=err, msg=msg)

    def action_show(self, req, record, err=None, msg=None, custom=False):
        if not custom:
            form = self._form(pw.ShowForm, req, record.row())
        else:
            form = self._form(RecordView, req, record.row(),
                              custom_spec=self._CUSTOM_VIEW)
        content = [form, self._action_menu(req, record)]
        for modname in self._RELATED_MODULES:
            module, binding = self._module(modname), self._bindings[modname]
            content.append(module.related(req, binding, self.name(), record))
        return self._document(req, content, record, err=err, msg=msg)

    def action_view(self, req, record, err=None, msg=None):
        # `show()' always uses ShowForm, while `view()' may be overriden
        # by the module (using _CUSTOM_VIEW).
        return self.action_show(req, record, err=err, msg=msg, custom=True)
    
    def action_add(self, req, errors=()):
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
        actions = self._action_menu(req, record,
                                    (Action(_("Remove"), 'delete'),))
        msg = _("Please, confirm removing the record permanently.")
        return self._document(req, (form, actions), record,
                              err=err, subtitle=_("removing"), msg=msg)

    # ===== Action handlers which actually modify the database =====

    def action_insert(self, req):
        if self._OWNER_COLUMN and req.user():
            prefill = {self._OWNER_COLUMN: req.user()['uid']}
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
        
    # ===== Request redirection after data operations ====-
        
    def _redirect_after_update(self, req, record):
        action = req.wmi and self.action_show or self.action_view
        return action(req, record, msg=self._UPDATE_MSG)
        
    def _redirect_after_insert(self, req, record):
        return self.action_list(req, msg=self._INSERT_MSG)
        
    def _redirect_after_delete(self, req, record):
        return self.action_list(req, msg=self._DELETE_MSG)
    
        
# ==============================================================================
# Module extensions 
# ==============================================================================


class PanelizableModule(PytisModule):

    _PANEL_DEFAULT_COUNT = 3
    _PANEL_FIELDS = None

    def panelize(self, req, lang, count):
        count = count or self._PANEL_DEFAULT_COUNT
        fields = [self._view.field(id)
                  for id in self._PANEL_FIELDS or self._view.columns()]
        prow = pp.PresentedRow(self._view.fields(), self._data, None)
        items = []
        for row in self._rows(lang=lang, limit=count-1):
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


class RssModule(PytisModule):
    
    _RSS_TITLE_COLUMN = None
    _RSS_LINK_COLUMN = None
    _RSS_DESCR_COLUMN = None
    _RSS_DATE_COLUMN = None
    _RSS_AUTHOR_COLUMN = None

    _RIGHTS_rss = Roles.ANYONE
    
    def action_rss(self, req):
        if not self._RSS_TITLE_COLUMN:
            raise NotFound
        lang, variants, rows = self._list(req, lang=req.param('lang'), limit=8)
        from xml.sax.saxutils import escape
        link_column = self._RSS_LINK_COLUMN or self._RSS_TITLE_COLUMN
        base_uri = req.abs_uri()[:-len(req.uri)]
        args = lang and dict(setlang=lang) or {}
        prow = pp.PresentedRow(self._view.fields(), self._data, None)
        items = []
        import mx.DateTime as dt
        config = self._module('Config').config(req.server, lang)
        tr = translator(lang)
        users = self._module('Users')
        for row in rows:
            prow.set_row(row)
            title = escape(tr.translate(prow[self._RSS_TITLE_COLUMN].export()))
            uri = self._link_provider(req, row, link_column, **args)
            uri = uri and base_uri + uri or None
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
            if self._RSS_AUTHOR_COLUMN:
                uid = prow[self._RSS_AUTHOR_COLUMN]
                author = users.record(uid)['email'].export()
            else:
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
    _SEQUENCE_FIELDS = ()
    
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
                       descr=_("Make the item visible to website visitors")),
                Action(_("Unpublish"), 'unpublish',
                       handler=lambda r: Publishable._change_published(r),
                       enabled=lambda r: r['published'].value(),
                       descr=_("Make the item invisible to website visitors")),
                )

    # This is all quite ugly.  It would be much better to solve invoking pytis
    # actions in some more generic way, so that we don't need to implement an
    # action handler method for each pytis action.
    
    _RIGHTS_publish = _RIGHTS_unpublish = Roles.ADMIN
    
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
    
    _RIGHTS_translate = Roles.ADMIN
    
    def action_translate(self, req, record):
        req.params.update(dict([(k, record[k].export())
                                for k in record.keys() if k != 'lang']))
        return self.action_add(req)


