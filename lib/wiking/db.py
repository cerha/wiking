# Copyright (C) 2005-2009 Brailcom, o.p.s.
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
    _HONOUR_SPEC_TITLE = False
    _LIST_BY_LANGUAGE = False
    _EXCEPTION_MATCHERS = (
        ('duplicate key (value )?violates unique constraint "_?[a-z]+_(?P<id>[a-z_]+)_key"',
         _("This value already exists.  Enter a unique value.")),
        ('null value in column "(?P<id>[a-z_]+)" violates not-null constraint',
         _("Empty value.  This field is mandatory.")),
        )
    
    _INSERT_LABEL = _("New record")
    _INSERT_DESCR = _("Create a new record")
    _UPDATE_LABEL = _("Edit")
    _UPDATE_DESCR = _("Modify the record")
    _DELETE_LABEL = _("Remove")
    _DELETE_DESCR = _("Remove the record permanently")
    _DELETE_PROMPT = _("Please, confirm removing the record permanently.")
    _LIST_LABEL = _("Back to list")
    _LIST_DESCR = _("Back to the list of all records")
    _INSERT_MSG = _("New record was successfully inserted.")
    _UPDATE_MSG = _("The record was successfully updated.")
    _DELETE_MSG = _("The record was deleted.")
    
    _OWNER_COLUMN = None
    _SUPPLY_OWNER = True
    _SEQUENCE_FIELDS = ()
    _DB_FUNCTIONS = {}
    """Specification of available DB functions and their arguments.

    Dictionary keyed by function name, where values are sequences of pairs (NAME, TYPE) describing
    function arguments and their pytis data types.
    
    """

    _ALLOW_TABLE_LAYOUT_IN_FORMS = True
    _SUBMIT_BUTTONS = {}
    _LAYOUT = {}

    class Record(pp.PresentedRow):
        """An abstraction of one record within the module's data object.

        The current request is stored within the record data to make it available within computer
        functions.

        Warning: Instances of this class should not persist across multiple requests!
        
        """
        def __init__(self, req, *args, **kwargs):
            self._req = req
            super(PytisModule.Record, self).__init__(*args, **kwargs)

        def req(self):
            return self._req
            
        def module(self, name, **kwargs):
            return self._resolver.wiking_module(name, **kwargs)
            
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
            update = not self.new()
            rdata = []
            dbcolumns = []
            for f in self._fields:
                if f.virtual():
                    continue
                id, value = f.id(), self[f.id()]
                if value is None and not update:
                    # Omit empty values for insert to allow DB default values.
                    continue
                dbcolumn = f.dbcolumn()
                if dbcolumn in dbcolumns:
                    # Avoid multiple assignments to the same DB column.
                    continue
                dbcolumns.append(dbcolumn)
                rdata.append((id, value))
            debug("**", rdata)
            return pd.Row(rdata)

        def user_roles(self):
            """Return sequence of the current user roles."""
            user = self.req().user()
            if user is None:
                roles = ()
            else:
                roles = user.roles()
            return roles

    @classmethod
    def title(cls):
        return cls.Spec.title
    
    @classmethod
    def descr(cls):
        return cls.Spec.help
    
    # Instance methods
    
    def __init__(self, resolver, dbconnection, **kwargs):
        super(PytisModule, self).__init__(resolver, **kwargs)
        self._dbconnection = dbconnection
        spec = self._spec(resolver)
        self._data = spec.data_spec().create(connection_data=dbconnection)
        self._view = spec.view_spec()
        self._key = key = self._data.key()[0].id()
        self._sorting = self._view.sorting()
        self._db_function = {}
        if self._sorting is None:
            self._sorting = ((key, pytis.data.ASCENDENT),)
        self._exception_matchers = [(re.compile(regex), msg)
                                    for regex, msg in self._EXCEPTION_MATCHERS]
        self._referer = self._REFERER or key
        self._referer_type = self._data.find_column(self._referer).type()
        self._title_column = self._TITLE_COLUMN or self._view.columns()[0]
        self._links = {}
        def cb_link(field):
            e = field.type(self._data).enumerator()
            return e and pp.Link(field.codebook(), e.value_column())
        for f in self._view.fields():
            if f.links():
                self._links[f.id()] = (f.id(), f.links()[0])
            elif f.codebook():
                link = cb_link(f)
                if link:
                    self._links[f.id()] = (f.id(), link)
            elif isinstance(f.computer(), pp.CbComputer):
                cb_field = f.computer().field()
                link = cb_link(self._view.field(cb_field))
                if link: # and link.name() not in [x[1].name() for x in self._links.values()]:
                    self._links[f.id()] = (cb_field, link)
            

    def _spec(self, resolver):
        return self.__class__.Spec(self.__class__, resolver)

    def _record(self, req, row, new=False, prefill=None):
        """Return the Record instance initialized by given data row."""
        return self.Record(req, self._view.fields(), self._data, row, prefill=prefill,
                           resolver=self._resolver, new=new)

    def _locale_data(self, req):
        lang = req.prefered_language(raise_error=False)
        return translator(lang).locale_data()

    def _binding_forward(self, req):
        # Return the ForwardInfo instance for the last forward made because of the binding
        # dependency (this module is in bindings of the forwarding module).
        for fw in reversed(req.forwards()):
            if fw.arg('binding') is not None:
                if self.name() == fw.module().name():
                    return fw
                else:
                    return None
        return None

    def _binding_column(self, req):
        # Return the current binding column id and its binding value as a tuple.
        fw = self._binding_forward(req)
        if fw:
            binding_column = fw.arg('binding').binding_column()
            if binding_column:
                col = self._data.find_column(binding_column).type().enumerator().value_column()
                return (binding_column, fw.arg('record')[col].value())
        return None, None
        
    def _validate(self, req, record, layout=None):
        # TODO: This should go to pytis.web....
        errors = []
        if layout is None:
            layout = self._view.layout()
        if record.new():
            # Suppply the value of the binding column (if this is a binding forwarded request).
            binding_column, value = self._binding_column(req)
            if binding_column:
                if req.param(binding_column) == record[binding_column].type().export(value):
                    record[binding_column] = pd.Value(record[binding_column].type(), value)
                else:
                    errors.append((binding_column, _("Invalid binding column value.")))
        for id in layout.order():
            f = self._view.field(id)
            if not record.editable(id):
                continue
            type = record[id].type()
            kwargs = {}
            if req.has_param(id):
                value = req.param(id)
                if isinstance(value, tuple):
                    if len(value) == 2 and isinstance(type, pd.Password):
                        value, kwargs['verify'] = value
                    else:
                        value = value[-1]
                elif isinstance(value, FileUpload):
                    if isinstance(type, pd.Binary):
                        fname = value.filename()
                        if fname:
                            kwargs['filename'] = fname
                            kwargs['type'] = value.type()
                            value = value.file()
                        else:
                            value = None
                    else:
                        value = value.filename()
            elif isinstance(type, pd.Binary):
                value = None
            elif isinstance(type, pd.Boolean):
                value = "F"
            else:
                value = ""
            if isinstance(type, (Date, Time, DateTime)):
                kwargs['format'] = type.locale_format(self._locale_data(req))
            if isinstance(type, (pd.Binary, pd.Password)) and not value and not record.new():
                continue # Keep the original file if no file is uploaded.
            if isinstance(type, pd.Password) and kwargs.get('verify') is None:
                kwargs['verify'] = not type.verify() and value or ''
            error = record.validate(id, value, **kwargs)
            #log(OPR, "Validation:", (id, value, kwargs, error))
            if error:
                errors.append((id, error.message()))
        if errors:
            return errors
        else:
            if record.new() and self._LIST_BY_LANGUAGE and record['lang'].value() is None:
                lang = req.prefered_language(raise_error=False)
                record['lang'] = pd.Value(record['lang'].type(), lang)
            for check in self._view.check():
                result = check(record)
                if result:
                    if isinstance(result, (str, unicode)):
                        result = (result, _("Integrity check failed."))
                    else:
                        assert isinstance(result, tuple) and len(result) == 2, \
                               ('Invalid check() result:', e, result)
                    return (result,)
            return None

    def _analyze_exception(self, e):
        if e.exception():
            for matcher, msg in self._exception_matchers:
                match = matcher.match(str(e.exception()).strip())
                if match:
                    if isinstance(msg, tuple):
                        return msg
                    elif match.groupdict().has_key('id'):
                        return (match.group('id'), msg)
                    else:
                        return (None, msg)
        return (None, unicode(e.exception()))

    def _error_message(self, fid, error):
        # Return an error message string out of _analyze_exception() result.
        if fid is not None:
            f = self._view.field(fid)
            if f:
                label = f.label()
            else:
                label = fid
            error = label + ": " + error
        return error

    def _document_title(self, req, record):
        if record:
            if self._TITLE_TEMPLATE:
                title = self._TITLE_TEMPLATE.interpolate(lambda key: record[key].export())
            else:
                title = record[self._title_column].export()
        else:
            if self._HONOUR_SPEC_TITLE:
                title = self._view.title()
            else:
                title = None # Current menu title will be substituted.
        fw = self._binding_forward(req)
        if fw and fw.arg('title'):
            if title:
                title = fw.arg('title') +' :: '+ title
            else:
                title = fw.arg('title')
            #    title += fw.arg('binding').title()
            #else:
        return title
        
    def _document(self, req, content, record=None, lang=None, err=None, msg=None, **kwargs):
        title = self._document_title(req, record)
        if record and lang is None and self._LIST_BY_LANGUAGE:
            lang = str(record['lang'].value())
        # msg and err may be passed as request params on redirection (see action_list()).
        # Maybe we could do this directly in the request constructor?
        if req.has_param('msg'):
            req.message(req.param('msg'))
        if req.has_param('err'):
            req.message(req.param('err'), type=req.ERROR)
        # Messages should be now stacked using the req.message() method directly, but they were
        # passed as _document arguments before, so this is just for backwards compatibility.
        if msg:
            req.message(msg)
        if err:
            req.message(err, type=req.ERROR)
        return Document(title, content, lang=lang, **kwargs)

    def _default_actions_first(self, req, record):
        return (Action(self._INSERT_LABEL, 'insert', descr=self._INSERT_DESCR, context=None),
                Action(self._UPDATE_LABEL, 'update', descr=self._UPDATE_DESCR),)

    def _default_actions_last(self, req, record):
        return (Action(self._DELETE_LABEL, 'delete', descr=self._DELETE_DESCR, allow_referer=False),
                Action(self._LIST_LABEL, 'list', descr=self._LIST_DESCR, allow_referer=False))

    def _actions(self, req, record):
        actions = self._default_actions_first(req, record) + \
                  self._view.actions() + \
                  self._default_actions_last(req, record)
        if record is not None:
            context = pp.ActionContext.CURRENT_ROW
        else:
            context = None
        return tuple([a for a in actions if a.context() == context])

    def _action_menu(self, req, record=None, actions=None, uri=None, **kwargs):
        actions = [action for action in actions or self._actions(req, record)
                   if isinstance(action, Action) and action.name() is not None and \
                   self._application.authorize(req, self, action=action.name(), record=record)]
        if not actions:
            return None
        if uri is None:
            uri = self._current_base_uri(req, record)
        return ActionMenu(uri, actions, self._referer, self.name(), record, **kwargs)

    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid is None:
            return uri and make_uri(uri +'/'+ record[self._referer].export(), **kwargs)
        if self._links.has_key(cid):
            value_column, link = self._links[cid]
            try:
                module = self._module(link.name())
            except AttributeError:
                return None
            uri = module.link(req, {link.column(): record[value_column].value()}, **kwargs)
            if link.label():
                return pw.Link(uri, title=link.label())
            else:
                return uri
        return None

    def _image_provider(self, req, record, cid, uri):
        return None

    def _record_uri(self, req, record, *args, **kwargs):
        # Return the absolute URI of module's record if a direct mapping of the module exists.  
        # Use the method '_current_record_uri()' to get URI in the context of the current request.
        uri = self._base_uri(req)
        if uri:
            return make_uri(uri +'/'+ record[self._referer].export(), *args, **kwargs)
        else:
            return None

    def _current_base_uri(self, req, record=None):
        # Return the module base URI in the context of the current request.
        uri = req.uri().rstrip('/')
        if record:
            # If the referer value is changed, the URI still contains the original value.
            referer = record.original_row()[self._referer].export()
            if uri.endswith('/'+referer):
                uri = uri[:-(len(referer)+1)]
        return uri

    def _current_record_uri(self, req, record):
        # Return the URI of given record in the context of the current request.
        return self._current_base_uri(req, record) +'/'+ record[self._referer].export()

    def _form(self, form, req, record=None, action=None, hidden=(), new=False, prefill=None,
              handler=None, binding_uri=None, **kwargs):
        if binding_uri is not None:
            uri = binding_uri or None
        else:
            uri = self._current_base_uri(req, record)
        def uri_provider(record_, cid, type=pw.UriType.LINK):
            if type == pw.UriType.LINK:
                method = self._link_provider
            elif type == pw.UriType.IMAGE:
                method = self._image_provider
            return method(req, uri, record_, cid)
        if issubclass(form, pw.EditForm):
            kwargs['allow_table_layout'] = self._ALLOW_TABLE_LAYOUT_IN_FORMS
        elif issubclass(form, pw.BrowseForm):
            kwargs['req'] = req
        if action is not None:
            hidden += (('action', action),
                       ('submit', 'submit'))
        valid_prefill = {}
        if prefill:
            for key, value in prefill.items():
                type = self._view.field(key).type(self._data)
                value, error = type.validate(value, strict=False)
                if not error:
                    valid_prefill[key] = value
        form_record = self._record(req, record and record.row(), prefill=valid_prefill, new=new)
        return form(self._view, form_record, handler=handler or req.uri(), name=self.name(),
                    hidden=hidden, prefill=prefill, uri_provider=uri_provider, **kwargs)

    def _layout(self, req, action, record=None):
        layout = self._LAYOUT.get(action)
        if isinstance(layout, (tuple, list)):
            layout = pp.GroupSpec(layout, orientation=pp.Orientation.VERTICAL)
        return layout

    def _action(self, req, record=None):
        if record is not None and req.unresolved_path:
            return 'subpath'
        else:
            return super(PytisModule, self)._action(req, record=record)

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
            args = dict(record=self._record(req, row))
        else:
            args = dict()
        return args
    
    def _resolve(self, req):
        # Returns Row, None or raises HttpError.
        if req.unresolved_path:
            row = self._refered_row(req, req.unresolved_path[0])
            # If no error was raised, the path was resolved.
            del req.unresolved_path[0]
            return row
        elif req.has_param(self._key):
            return self._get_row_by_key(req, req.param(self._key))
        else:
            return None

    def _get_row_by_key(self, req, value):
        if isinstance(value, tuple):
            value = value[-1]
        type = self._data.key()[0].type()
        v, error = type.validate(value)
        if error:
            raise NotFound()
        row = self._data.row((v,))
        if row is None:
            raise NotFound()
        binding_column, value = self._binding_column(req)
        if binding_column and row[binding_column].value() != value:
            raise NotFound()
        return row

    def _refered_row_values(self, req, value):
        """Return a dictionary of row values identifying unambiguously the refered record.

        The argument is a string representation of the module's referer column value (from URI
        path).

        """
        if not isinstance(self._referer_type, pd.String):
            v, error = self._referer_type.validate(value)
            if error is not None:
                raise NotFound()
            else:
                value = v.value()
        # The referer value from URI is the most important, but not always the only needed value.
        values = {self._referer: value}
        # Add a binding column value if we are in a binding forwarded request.
        binding_column, value = self._binding_column(req)
        if binding_column:
            values[binding_column] = value
        # Add the current prefered language in language dependent modules.
        if self._LIST_BY_LANGUAGE:
            values['lang'] = req.prefered_language(raise_error=False)
        return values
    
    def _refered_row(self, req, value):
        """Return a 'pytis.data.Row' instance corresponding to the refered record.

        The argument is a string representation of the module's referer column value (from URI
        path).  Raise 'NotFound' error if the refered row doesn't exist.

        """
        values = self._refered_row_values(req, value)
        row = self._data.get_row(**values)
        if row is None:
            raise NotFound()
        return row
        
    def check_owner(self, user, record):
        if self._OWNER_COLUMN is not None:
            owner = record[self._OWNER_COLUMN].value()
            return user.uid() == owner
        return False
        
    def _prefill(self, req, new=False):
        prefill = dict([(f.id(), req.param(f.id())) for f in self._view.fields()
                        if req.has_param(f.id()) and \
                        not isinstance(f.type(self._data), (pd.Binary, pd.Password))])
        binding_column, value = self._binding_column(req)
        if binding_column:
            type = self._view.field(binding_column).type(self._data)
            prefill[binding_column] = type.export(value)
        if new and not prefill.has_key('lang') and self._LIST_BY_LANGUAGE:
            lang = req.prefered_language(raise_error=False)
            if lang:
                prefill['lang'] = lang
        return prefill

    def _binding_condition(self, binding, record):
        cfunc = binding.condition()
        if cfunc:
            condition = cfunc(record)
        else:
            condition = None
        binding_column = binding.binding_column()
        if binding_column:
            type = self._data.find_column(binding_column).type()
            value = record[type.enumerator().value_column()].value()
            bcond = pd.EQ(binding_column, pd.Value(type, value))
            if condition: 
                condition = pd.AND(condition, bcond)
            else:
                condition = bcond
        return condition
        
    def _condition(self, req, lang=None, condition=None, values=None):
        # Can be used by a module to further restrict the listed records.
        conds = []
        if condition:
            conds.append(condition)
        if values:
            for k, v in values.items():
                conds.append(pd.EQ(k, pd.Value(self._data.find_column(k).type(), v)))
        if lang and self._LIST_BY_LANGUAGE:
            conds.append(pd.EQ('lang', pd.Value(pd.String(), lang)))
        if conds:
            return pd.AND(*conds)
        else:
            return None
    
    def _rows(self, req, lang=None, condition=None, limit=None):
        return self._data.get_rows(sorting=self._sorting, limit=limit,
                                   condition=self._condition(req, lang=lang, condition=condition))

    def _handle(self, req, action, **kwargs):
        record = kwargs.get('record')
        if record is not None:
            redirect = self._view.redirect()
            if redirect:
                module = redirect(record)
                if module is not None and module != self.name():
                    for fw in reversed(req.forwards()):
                        if fw.module().name() == self.name():
                            req.unresolved_path = list(fw.unresolved_path())
                            break
                    else:
                        req.unresolved_path = list(req.path)
                    return req.forward(self._module(module))
        return super(PytisModule, self)._handle(req, action, **kwargs)

    def _binding_enabled(self, binding, record):
        return 

    def _bindings(self, req, record):
        return [b for b in self._view.bindings()
                if not isinstance(b, Binding) or b.enabled() is None or b.enabled()(record)]

    def _call_db_function(self, name, *args):
        """Call database function NAME with given arguments and return the result.

        Arguments are Python values wich will be automatically wrapped into 'pytis.data.Value'
        instances.
        
        """
        try:
            function, arg_spec = self._db_function[name]
        except KeyError:
            function = pytis.data.DBFunctionDefault(name, self._dbconnection)
            arg_spec = self._DB_FUNCTIONS[name]
            self._db_function[name] = function, arg_spec
        assert len(args) == len(arg_spec), \
               "Wrong number of arguments for '%s': %r" % (name, args)
        arg_data = [(spec[0], pd.Value(spec[1], value)) for spec, value in zip(arg_spec, args)]
        result = function.call(pytis.data.Row(arg_data))
        #debug("**", name, result[0][0].value())
        return result[0][0].value()

    # ===== Methods which modify the database =====
    
    def _insert(self, record):
        """Insert new row into the database and return a Record instance."""
        for key, seq in self._SEQUENCE_FIELDS:
            if record[key].value() is None:
                value = pd.DBCounterDefault(seq, self._dbconnection).next()
                record[key] = pd.Value(record[key].type(), value)
        new_row, success = self._data.insert(record.rowdata())
        #debug(":::", success, new_row and [(k, new_row[k].value()) for k in new_row.keys()])
        if success and new_row is not None:
            # We can't use set_row(), since it would destroy file fields (they are virtual).
            for key in new_row.keys():
                record[key] = new_row[key]
        
    def _update(self, record):
        """Update the record data in the database."""
        self._data.update(record.key(), record.rowdata())

    def _delete(self, record):
        """Delete the record from the database."""
        self._data.delete(record.key())
        
    # ===== Public methods =====
    
    def record(self, req, value):
        """Return the record corresponding to given key value."""
        row = self._data.row((value,))
        return row and self._record(req, row)
        
    def link(self, req, key, *args, **kwargs):
        """Return a uri for given key value."""
        if isinstance(key, dict):
            row = self._data.get_row(**key)
        else:
            row = self._data.row(key)
        if row:
            return self._record_uri(req, self._record(req, row), *args, **kwargs)
        else:
            return None
        
    def related(self, req, binding, record, uri):
        """Return the listing of records related to other module's record by given binding."""
        if isinstance(binding, Binding) and binding.form() is not None:
            form = binding.form()
        else:
            form = pw.ListView
        condition = self._binding_condition(binding, record)
        columns = [c for c in self._view.columns() if c != binding.binding_column()]
        lang = req.prefered_language(raise_error=False)
        if binding.id():
            binding_uri = uri +'/'+ binding.id()
        else:
            # Special value indicating that this is a related form, but uri is not available.
            binding_uri = ''
        content = self._form(form, req, uri=uri, columns=columns, binding_uri=binding_uri,
                             condition=self._condition(req, condition=condition, lang=lang))
        if binding_uri:
            menu = self._action_menu(req, uri=binding_uri)
            if menu:
                content = lcg.Container((content, menu))
        return content

    # ===== Action handlers =====
    
    def action_list(self, req, err=None, msg=None):
        # Don't display the listing alone, but display the original form with bindings,
        # when this list is accessed through a related form.
        # The messages are passed to support redirection after update/insert/delete, but it
        # might be better to make a redirect directly in the _redirect_after_* methods.
        result = self._binding_parent_redirect(req, err=err, msg=msg,
                                               search=req.param('search'),
                                               form_name=req.param('form_name'))
        if result is not None:
            return result
        # If this is not a binding forwarded request, display the listing.
        lang = req.prefered_language()
        content = (self._form(pw.ListView, req, condition=self._condition(req, lang=lang)),
                   self._action_menu(req))
        return self._document(req, content, lang=lang, err=err, msg=msg)

    def _binding_parent_redirect(self, req, err=None, msg=None, **kwargs):
        fw = self._binding_forward(req)
        if fw:
            binding_id = fw.arg('binding').id()
            if binding_id and fw.uri().endswith(binding_id):
                t = translator(req.prefered_language()).translate
                for text, type in req.messages():
                    if type == req.ERROR:
                        err = err and err +'\n'+ text or text
                    else:
                        msg = msg and msg +'\n'+ text or text
                uri = fw.uri()[:-(len(binding_id)+1)]
                return req.redirect(make_uri(uri, err=t(err), msg=t(msg), **kwargs))
        return None
        
    def _related_content(self, req, record):
        # Return content related to given record to be displayed within the view action under the
        # record details.  Returns a list of lcg.Content instances.  Binding forms are displayed by
        # default (may be overriden in derived classes).
        result = []
        for binding in self._bindings(req, record):
            module = self._module(binding.name())
            content = module.related(req, binding, record,
                                     uri=self._current_record_uri(req, record))
            result.append(lcg.Section(title=binding.title(), content=content))
        return result
    
    def action_view(self, req, record, err=None, msg=None):
        content = [self._form(pw.ShowForm, req, record=record,
                              layout=self._layout(req, 'view', record)),
                   self._action_menu(req, record)] + \
                   self._related_content(req, record)
        return self._document(req, content, record, err=err, msg=msg)

    def action_subpath(self, req, record):
        for binding in self._bindings(req, record):
            if req.unresolved_path[0] == binding.id():
                del req.unresolved_path[0]
                # TODO: respect the binding condition in the forwarded module.
                module = self._module(binding.name())
                return req.forward(module, binding=binding, record=record,
                                   title=self._document_title(req, record))
        if req.unresolved_path[0] in [b.id() for b in self._view.bindings()]:
            raise Forbidden()
        else:
            raise NotFound()

    # ===== Action handlers which modify the database =====

    def _action_insert_data(self, req, layout):
        if self._OWNER_COLUMN and self._SUPPLY_OWNER and req.user():
            prefill = {self._OWNER_COLUMN: req.user().uid()}
        else:
            prefill = None
        record = self._record(req, None, new=True, prefill=prefill)
        errors = self._validate(req, record, layout=layout)
        if not errors:
            try:
                self._insert(record)
            except pd.DBException, e:
                errors = (self._analyze_exception(e),)
        return record, errors

    def _action_insert_success(self, req, layout, record):
        return self._redirect_after_insert(req, record)        
        
    def _action_insert_failure(self, req, layout, errors):
        return self._action_insert_form(req, layout, errors=errors)
        
    def _action_insert_form(self, req, layout, errors=()):
        # TODO: Redirect handler to HTTPS if cfg.force_https_login is true?
        # The primary motivation is to protect registration form data.  The
        # same would apply for action_edit.
        form = self._form(pw.EditForm, req, new=True, action='insert',
                          prefill=self._prefill(req, new=True), layout=layout, 
                          submit=self._SUBMIT_BUTTONS.get('insert'),
                          errors=errors)
        return self._document(req, form, subtitle=self._insert_subtitle(req))

    def action_insert_perform(self, req):
        """Perform insert action for given 'req', without generating output.

        Return tripple (RECORD, ERRORS, LAYOUT), where RECORD is resulting
        'Record' instance or 'None' (in case there is nothing to insert),
        ERRORS is a sequence of errors (what exactly?) and LAYOUT is the form
        'Layout' instance.

        """
        layout = self._layout(req, 'insert')
        if req.param('submit'):
            record, errors = self._action_insert_data(req, layout)
        else:
            record, errors = None, ()
        return record, errors, layout

    def action_insert_document(self, req, layout, errors, record):
        """Generate and return output document for insert action."""
        if errors:              # unsuccessful insert
            document = self._action_insert_failure(req, layout, errors)
        elif record is not None: # successful insert
            document = self._action_insert_success(req, layout, record)
        else:                   # empty form
            document = self._action_insert_form(req, layout, errors=())
        return document
        
    def action_insert(self, req, errors=()):
        record, errors, layout = self.action_insert_perform(req)
        document = self.action_insert_document(req, layout, errors, record)
        return document
            
    def action_update(self, req, record, action='update', msg=None):
        layout = self._layout(req, action, record)
        if req.param('submit'):
            errors = self._validate(req, record, layout=layout)
        else:
            errors = ()
        if req.param('submit') and not errors:
            try:
                self._update(record)
                record.reload()
            except pd.DBException, e:
                errors = (self._analyze_exception(e),)
            else:
                return self._redirect_after_update(req, record)
        form = self._form(pw.EditForm, req, record=record, action=action, layout=layout,
                          submit=self._SUBMIT_BUTTONS.get(action),
                          prefill=self._prefill(req), errors=errors)
        subtitle = self._update_subtitle(req, record, action)
        return self._document(req, form, record, subtitle=subtitle, msg=msg)

    def action_delete(self, req, record):
        err = None
        if req.param('submit'):
            try:
                self._delete(record)
            except pd.DBException, e:
                err = self._error_message(*self._analyze_exception(e))
            else:
                return self._redirect_after_delete(req, record)
        form = self._form(pw.ShowForm, req, record)
        actions = (Action(self._DELETE_LABEL, 'delete', allow_referer=False, submit=1),
                   Action(_("Back"), 'view'))
        action_menu = self._action_menu(req, record, actions)
        return self._document(req, (form, action_menu), record, err=err,
                              subtitle=self._delete_subtitle(req, record),
                              msg=self._delete_prompt(req, record))
        
    def _insert_subtitle(self, req):
        return self._INSERT_LABEL
        
    def _update_subtitle(self, req, record, action):
        for a in self._actions(req, record):
            if a.name() == action:
                return a.title()
        return self._UPDATE_LABEL
        
    def _delete_subtitle(self, req, record):
        return self._DELETE_LABEL
    
    def _delete_prompt(self, req, record):
        return self._DELETE_PROMPT
    
    # ===== Request redirection after successful data operations =====

    def _insert_msg(self, record):
        return self._INSERT_MSG
        
    def _update_msg(self, record):
        return self._UPDATE_MSG
        
    def _delete_msg(self, record):
        return self._DELETE_MSG
    
    # ===== Request redirection after successful data operations =====

    def _redirect_after_insert(self, req, record):
        return self.action_list(req, msg=self._insert_msg(record))
        
    def _redirect_after_update(self, req, record):
        return self.action_view(req, record, msg=self._update_msg(record))
        
    def _redirect_after_delete(self, req, record):
        return self.action_list(req, msg=self._delete_msg(record))
    
        
# ==============================================================================
# Module extensions 
# ==============================================================================


class RssModule(object):
    
    _RSS_TITLE_COLUMN = None
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

    def _rss_channel_title(self, req):
        def find(items, item_id):
            for item in items:
                if item.id() == item_id:
                    return item.title()
                else:
                    title = find(item.submenu(), item_id)
                    if title:
                        return title
            return None
        return find(self._application.menu(req), req.path[0]) or self._view.title()

    def _rss_channel_uri(self, req):
        # TODO: This note applies to this method anf the above `_rss_channel_title()'.  They are
        # both limited to situations, where the RSS module is the final handler of the request.
        # This is the case for determination of the uri in `_rss_info()' and of the title in
        # `action_rss()'.  It is necessary to be able to determine the URI globally, but it is
        # currently not possible when a module is mapped more than once in CMS.
        return req.uri() +'.'+ req.prefered_language() +'.rss'

    def _rss_info(self, req, lang=None):
        # Argument lang is unused (defined only for backwards compatibility).
        if self._RSS_TITLE_COLUMN is not None:
            return lcg.p(_("An RSS channel is available for this section:"), ' ',
                         lcg.link(self._rss_channel_uri(req),
                                  self._rss_channel_title(req)+' RSS',
                                  type='application/rss+xml'),
                         " (", lcg.link('_doc/rss', _("more about RSS")), ")")
        return None

    def has_channel(self):
        # TODO: If the methods `_rss_channel_title()' and `_rss_channel_uri()' can be used
        # globally, this method can be replaced by a new method returning a `Channel' instance
        # directly.
        return self._RSS_TITLE_COLUMN is not None

    def action_rss(self, req, relation=None):
        if not self._RSS_TITLE_COLUMN:
            raise NotFound
        lang = req.prefered_language()
        if relation:
            condition = self._binding_condition(*relation)
        else:
            condition = None
        rows = self._rows(req, condition=condition, lang=lang, limit=self._RSS_LIMIT)
        from xml.sax.saxutils import escape
        base_uri = req.server_uri(current=True)
        record = self._record(req, None)
        items = []
        import mx.DateTime as dt
        tr = translator(str(lang))
        author_column = self._RSS_AUTHOR_COLUMN
        for row in rows:
            record.set_row(row)
            title = escape(tr.translate(record[self._RSS_TITLE_COLUMN].export()))
            uri = self._record_uri(req, record, setlang=lang)
            descr = self._descr_provider(req, record, tr)
            if self._RSS_DATE_COLUMN:
                v = record[self._RSS_DATE_COLUMN].value()
                date = dt.ARPA.str(v.localtime())
            else:
                date = None
            if author_column:
                if isinstance(author_column, tuple):
                    author = record.cb_value(*author_column).export()
                else:
                    author = record[author_column].export()
            else:
                author = cfg.webmaster_address
            items.append((title, uri and base_uri + uri, descr, date, author))
        title = cfg.site_title +' - '+ tr.translate(self._rss_channel_title(req))
        result = rss(title, base_uri, items, cfg.site_subtitle,
                     lang=lang, webmaster=cfg.webmaster_address)
        return ('application/xml', result)

    
# Mixin module classes

class Panelizable(object):

    _PANEL_DEFAULT_COUNT = 3
    _PANEL_FIELDS = None

    def panelize(self, req, lang, count, relation=None):
        count = count or self._PANEL_DEFAULT_COUNT
        fields = [self._view.field(id)
                  for id in self._PANEL_FIELDS or self._view.columns()]
        if relation:
            condition = self._binding_condition(*relation)
        else:
            condition = None
        record = self._record(req, None)
        items = []
        for row in self._rows(req, condition=condition, lang=lang, limit=count-1):
            record.set_row(row)
            item = PanelItem([(f.id(), record[f.id()].export(),
                               f.id() == self._title_column and \
                               self._record_uri(req, record)) or None
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
            err = self._error_message(*self._analyze_exception(e))
        return self.action_view(req, record, msg=msg, err=err)

    def action_unpublish(self, req, record):
        return self.action_publish(req, record, publish=False)

