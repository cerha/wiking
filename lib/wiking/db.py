# -*- coding: utf-8 -*-
# Copyright (C) 2005-2012 Brailcom, o.p.s.
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

import collections
import re, cStringIO as StringIO

from wiking import *
from pytis.presentation import Action
from pytis.web import UriType

_ = lcg.TranslatableTextFactory('wiking')


class PytisModule(Module, ActionHandler):
    """Module bound to a Pytis data object.

    Each subclass of this module must define a pytis specification by defining
    the class named 'Spec' derived from 'pytis.presentation.Specification'.
    Each instance is then bound to a pytis data object, which is automatically
    created on module instantiation.
    
    Most actions (such as 'view', 'update', 'delete') in this class work with a
    pytis record and expect a 'PytisModule.Record' instance as the 'record'
    argument of the action handler method.  Some actions (such as 'list') don't
    expect any arguments since they don't operate on a particular record.

    The pytis data records are mapped to URIs through so called 'referer'
    column (see 'ViewSpec' for a docstring).  This should be a unique column
    with values, which may be used in URI (don't contain special characters,
    etc.).  If not defined, the key column is used by default.  For example a
    record with the value 123 in the referer column will be mapped to the uri
    '/module-uri/123'.  This URI will be resolved automatically to calling an
    action method with 'record' argument holding a 'PytisModule.Record'
    instance corresponding to the data row with 123 in the key value.  Referer
    column values are converted to strings and back through standard pytis
    value export/validation according to referer column type.
    
    """
    _REFERER = None
    """DEPRECARED!  Use the Pytis specification option 'referer' instead.

    Currently overrides the specification option 'referer' of Pytis ViewSpec,
    but is deprecated.

       
    """
    _TITLE_COLUMN = None
    _TITLE_TEMPLATE = None
    _HONOUR_SPEC_TITLE = False
    _USE_BINDING_PARENT_TITLE = True
    _LIST_BY_LANGUAGE = False
    _EXCEPTION_MATCHERS = (
        ('Row with this key already exists',
         _("Row with this key already exists.")),
        ('duplicate key (value )?violates unique constraint "(?P<id>[a-z_]+)"',
         _("This value already exists.  Enter a unique value.")),
        ('null value in column "(?P<id>[a-z_]+)" violates not-null constraint',
         # Translators: This is about an empty (not filled in) value in a web form. Field means a
         # form field.
         _("Empty value.  This field is mandatory.")),
        ('update or delete on table .* violates foreign key constraint .*',
         # Translators: This is delete action failure message in a web page.
         _("Record couldn't be deleted because other records refer to it.")),
        )
    """Specification of error messages for different database exceptions.

    The purpose of this specification is to provide user readable error messages
    for known database exceptions through matching the exception string and
    possibly also identify the form field, which caused the error.

    The specification is a tuple of 2-tuples.  

    The first element of the 2-tuple is a regular expression that matches the
    database exception string.  The regular expression may include a group named
    'id' which is the name of database table/view column (or any other
    identifier) to which the error relates.

    The second element of the 2-tuple defines the custom error message displayed
    in the user interface when the exception occurs during a database operation.
    This can be the error message directly, or a 2-tuple of field_id and error
    message.  In the second case, the field_id determines the form field which
    caused the error.  When field_id is not defined, the value of the group
    named 'id' in the regular expression (if present) is used for the same
    purpose.  When field_id is defined, it must be a valid identifier of a field
    present in the specification.  If field_id is not defined, it means that the
    error message is either not related to a particular form field or that it is
    not possible to determine which field it is.

    See also '_analyze_exception()' and '_error_message()' methods for more
    details.

    Note, that the error messages are usually specific per database backend and
    handling exceptions at this level is not portable.  It should be used as a
    last resort when it is not possible to catch the problem during validation.

    """
    _UNIQUE_CONSTRAINT_FIELD_MAPPING = {}
    """Mapping of database unique constraint ids to real field_ids.

    Database errors caused by unique constraint violations are detected by
    wiking through `_EXCEPTION_MATCHERS'.  The errorr contains the name of the
    unique index (in PostgreSQL), typically something like
    `<table_name>_<column_name>_key'.  If <column_name> is one of
    specification's fields, the message printed to the user will contain the
    (translated) form field label and an explanation.  If the index name doesn't
    contain a field name directly (which may happen for several valid reasons),
    you should define an entry in this mapping to indicate which form field
    caused the error.  This will result in a more understandable error message
    for the users.
    
    """
    # Translators: Button label for new database record creation (computer terminology).
    _INSERT_LABEL = _("New record")
    # Translators: Tooltip of new database record creation button (computer terminology).
    _INSERT_DESCR = _("Create a new record")
    # Translators: Button label for database record modification (verb in imperative,
    # computer terminology).
    _UPDATE_LABEL = _("Edit")
    # Translators: Tooltip of database record modification button (computer terminology)
    _UPDATE_DESCR = _("Modify the record")
    # Translators: Button label for database record display (verb in imperative).
    _VIEW_LABEL = _("View")
    # Translators: Tooltip of database record display button (computer terminology)
    _VIEW_DESCR = _("Display the record")
    # Translators: Button label for database record deletion (verb in imperative,
    # computer terminology).
    _DELETE_LABEL = _("Remove")
    # Translators: Tooltip of database record deletion button (computer terminology).
    _DELETE_DESCR = _("Remove the record permanently")
    # Translators: Prompt before database record deletion (computer terminology).
    _DELETE_PROMPT = _("Please, confirm removing the record permanently.")
    # Translators: Button label for database record copying (verb in imperative,
    # computer terminology).
    _COPY_LABEL = _("Copy")
    # Translators: Tooltip of database record copy button (computer terminology).
    _COPY_DESCR = _("Create new record initialized by values of this record")
    # Translators: Button label for returning from a single record view to the listing of all
    # database records (computer terminology).
    _LIST_LABEL = _("Back to list")
    # Translators: Tooltip of a button for returning from a single record view to the
    # listing of all records (computer terminology).
    _LIST_DESCR = _("Back to the list of all records")
    # Translators: Button label (verb in imperative, computer terminology).
    _EXPORT_LABEL = _("Export")
    # Translators: Button tooltip.  Don't translate `CSV', it is an
    # internationally recognized computer abbreviation.
    _EXPORT_DESCR = _("Export the listing into a CSV format")
    # Translators: Message displayed after new database record creation (computer terminology).
    _INSERT_MSG = _("New record was successfully inserted.")
    # Translators: Message displayed after a database record modification (computer terminology).
    _UPDATE_MSG = _("The record was successfully updated.")
    # Translators: Message displayed after a database record deletion (computer terminology).
    _DELETE_MSG = _("The record was deleted.")
    
    _OWNER_COLUMN = None
    _SUPPLY_OWNER = True
    _SEQUENCE_FIELDS = ()
    _ARRAY_FIELDS = ()
    """Specification of array fields with automatically updated linking tables.

    Tuple of tuples where the inner tuples consist of (FIELD_ID, SPEC_NAME,
    LINKING_COLUMN, VALUE_COLUMN).  FIELD_ID is the id of the array field
    (type=pytis.data.Array), SPEC_NAME is the name of the linking table
    specification, LINKING_COLUMN is the id of the column in the linking table
    which refers to the key column of this module (where the array field is
    used) and VALUE_COLUMN is the id of the column in the linking table, which
    contains the array values.

    The purpose of the whole thing is to implement automatic linking table
    updates on the Wiking side, since Pytis data operations don't know how to
    handle Array values.  The array field will usually be virtual to prevent
    passing it to Pytis data operations and Wiking will attempt to
    automatically update the linking table on insert/update operations and will
    also read the field values when displaying a form (pytis web forms can
    handle array fields).
    
    """
    _DB_FUNCTIONS = {}
    """Specification of available DB functions and their arguments.

    Dictionary keyed by function name, where values are sequences of pairs (NAME, TYPE) describing
    function arguments and their pytis data types.
    
    """
    _BROWSE_FORM_LIMITS = (50, 100, 200, 500)
    """Default value to pass to 'pytis.web.BrowseForm' 'limits' constructor argument."""
    _BROWSE_FORM_DEFAULT_LIMIT = 50
    """Default value to pass to 'pytis.web.BrowseForm' 'limit' constructor argument."""
    _ALLOW_QUERY_SEARCH = None
    """Default value to pass to 'pytis.web.BrowseForm' 'allow_query_search' constructor argument."""
    _TOP_ACTIONS = False
    "If true, action menu is put above BrowseForm/ListView forms."
    _BOTTOM_ACTIONS = True
    "If true, action menu is put below BrowseForm/ListView forms."
    _ROW_ACTIONS = False
    "If true, action menu created also for each table row in BrowseForm/ListView forms."
    
    _SUBMIT_BUTTONS = {}
    "Dictionary of form buttons keyed by action name (see '_submit_buttons()' method)."
    _LAYOUT = {}
    "Dictionary of form layouts keyed by action name (see '_layout()' method)."

    # Just a hack, see its use.  If you redefine _record_uri method, set it the
    # flag value to False.
    _OPTIMIZE_LINKS = True
    
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

        def key(self):
            """Return the value of record's key for data operations."""
            return (self[self._data.key()[0].id()],)

        def reload(self, transaction=None):
            """Reload record data from the database."""
            self.set_row(self._data.row(self.key(), transaction=transaction))

        def update(self, transaction=None, **kwargs):
            """Update the record in the database by values of given keyword args."""
            self._data.update(self.key(), self._data.make_row(**kwargs), transaction=transaction)
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
                if value.value() is None and not update:
                    # Omit empty values for insert to allow DB default values.
                    continue
                dbcolumn = f.dbcolumn()
                if dbcolumn in dbcolumns:
                    # Avoid multiple assignments to the same DB column.
                    continue
                dbcolumns.append(dbcolumn)
                rdata.append((id, value))
            return pd.Row(rdata)
            
    @classmethod
    def title(cls):
        return cls.Spec.title
    
    @classmethod
    def descr(cls):
        return cls.Spec.help
    
    # Instance methods
    
    def __init__(self, name):
        self._link_cache = {}
        self._link_cache_req = None
        super(PytisModule, self).__init__(name)
        import config
        self._dbconnection = config.dbconnection.select(self.Spec.connection)
        del config
        resolver = wiking.cfg.resolver
        self._data_spec = resolver.get(name, 'data_spec')
        self._view = resolver.get(name, 'view_spec')
        self._exception_matchers = [(re.compile(regex), msg)
                                    for regex, msg in self._EXCEPTION_MATCHERS]
        self._db_function = {}
        self._title_column = self._TITLE_COLUMN or self._view.columns()[0]

    def __getattr__(self, name):
        if name not in ('_data', '_key', '_sorting', '_referer', '_links', '_type'):
            try:
                return super(PytisModule, self).__getattr__(name)
            except AttributeError: # can be thrown in absence of __getattr__ itself!
                raise AttributeError(name)
        self._delayed_init()
        return getattr(self, name)

    def _delayed_init(self):
        self._data = self._data_spec.create(connection_data=self._dbconnection)
        self._key = key = self._data.key()[0].id()
        self._sorting = self._view.sorting()
        if self._sorting is None:
            self._sorting = ((key, pytis.data.ASCENDENT),)
        self._referer = self._REFERER or self._view.referer() or key
        self._array_fields = []
        resolver = wiking.cfg.resolver
        for fid, spec_name, linking_column, value_column in self._ARRAY_FIELDS:
            data_spec = resolver.get(spec_name, 'data_spec')
            data = data_spec.create(connection_data=self._dbconnection)
            self._array_fields.append((fid, data, linking_column, value_column))
        fields = self._view.fields()
        # We sometimes need to know the data type of certain field without having access to the
        # record at the same time, so we create a record here just to save the data types of all
        # fields for future use.
        record = pp.PresentedRow(fields, self._data, None, resolver=resolver)
        self._type = dict([(key, record.type(key)) for key in record.keys()])
        self._links = {}
        for f in fields:
            if f.codebook():
                cb_field = f
            elif isinstance(f.computer(), pp.CbComputer):
                cb_field = self._view.field(f.computer().field())
            else:
                continue
            column = cb_field.id()
            codebook = cb_field.codebook()
            enumerator = self._type[column].enumerator()
            if codebook and enumerator:
                referer = cb_field.inline_referer()
                value_column = enumerator.value_column()
                if not referer and wiking.module(codebook).referer() == value_column:
                    # If the inline_referer column was not specified explicitly
                    # and the module's referer column is the same as the
                    # codebook's value_column, we can use the codebook column
                    # as the inline referer (it is the same value).
                    referer = column
                self._links[f.id()] = (codebook, referer, column, value_column)
        
    def _record(self, req, row, new=False, prefill=None):
        """Return the Record instance initialized by given data row."""
        return self.Record(req, self._view.fields(), self._data, row,
                           prefill=prefill, resolver=wiking.cfg.resolver, new=new)

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
                col = self._type[binding_column].enumerator().value_column()
                return (binding_column, fw.arg('record')[col].value())
        return None, None
    
    def _validate(self, req, record, layout):
        # TODO: This should go to pytis.web....
        errors = []
        order = layout.order()
        # Validate the changed field last (for AJAX update request) to invoke computers correctly.
        changed_field = req.param('_pytis_form_changed_field')
        if changed_field:
            order = [id for id in order if id != changed_field] + [str(changed_field)]
        for id in order:
            f = self._view.field(id)
            if not record.editable(id):
                continue
            if changed_field and f.computer() and changed_field in f.computer().depends():
                # Ignore fields which depend on the field currently changed by
                # the user during AJAX form updates.
                continue
            type = record.type(id)
            kwargs = {}
            if req.has_param(id):
                value = req.param(id)
                if isinstance(value, tuple):
                    if len(value) == 2 and isinstance(type, pd.Password):
                        value, kwargs['verify'] = value
                    elif not isinstance(type, pd.Array):
                        value = value[-1]
                elif isinstance(value, FileUpload):
                    if isinstance(type, pd.Binary):
                        fname = value.filename()
                        if fname:
                            kwargs['filename'] = fname
                            kwargs['mime_type'] = value.mime_type()
                            value = value.file()
                        else:
                            value = None
                    else:
                        value = value.filename()
                elif isinstance(type, pd.Array):
                    value = pytis.util.xtuple(value)
                elif value == '' and isinstance(type, pd.Binary):
                    value = None
            elif isinstance(type, pd.Binary):
                value = None
            elif isinstance(type, pd.Boolean) and f.selection_type() is None:
                # Imply False only for checkbox (when selection_type is None)
                # to allow not null check for radio and choice selections
                # (force the user to select the True or False option
                # explicitly.
                value = "F"
            else:
                value = ""
            if isinstance(type, pd.Float):
                locale_data = req.localizer().locale_data()
                if isinstance(type, pd.Monetary):
                    decimal_point = locale_data.mon_decimal_point
                    thousands_sep = locale_data.mon_thousands_sep
                else:
                    decimal_point = locale_data.decimal_point
                    thousands_sep = locale_data.thousands_sep
                # Convert the value to 'C' locale formatting before validation.
                if thousands_sep:
                    value = value.replace(thousands_sep, '')
                if decimal_point != '.':
                    value = value.replace(decimal_point, '.')
            if isinstance(type, pd.DateTime):
                locale_data = req.localizer().locale_data()
                if isinstance(type, pd.Date):
                    format = locale_data.date_format
                else:
                    if not isinstance(type, (DateTime, Time)) or type.exact():
                        # wiking.Time and wiking.DateTime allow locale independent format options.
                        time_format = locale_data.exact_time_format
                    else:
                        time_format = locale_data.time_format
                    if isinstance(type, pd.Time):
                        format = time_format
                    else:
                        format = locale_data.date_format +' '+ time_format
                kwargs['format'] = format
            if isinstance(type, (pd.Binary, pd.Password)) and not value:
                try:
                    size = int(req.param('_pytis_file_size_'+id))
                except (ValueError, TypeError):
                    pass
                else:
                    # Handle AJAX request for validation of file size (only
                    # size is sent by the form to prevent uploading potentially
                    # large files through AJAX requests before form submission).
                    from pytis.util import format_byte_size
                    if type.minlen() is not None and size < type.minlen():
                        # Take the string from the pytis domain as the
                        # validation belongs to pytis anyway so when it is
                        # moved, this hack will vanish.
                        error = lcg.TranslatableText(u"Minimal size %(minlen)s not satisfied",
                                                     minlen=format_byte_size(type.minlen()),
                                                     _domain='pytis')
                        errors.append((id, error))
                    if type.maxlen() is not None and size > type.maxlen():
                        error = lcg.TranslatableText(u"Maximal size %(maxlen)s exceeded",
                                                     maxlen=format_byte_size(type.maxlen()),
                                                     _domain='pytis')
                        errors.append((id, error))
                    # Don't perform real type validation as we don't have the real
                    # value to validate here.
                    continue
                if not record.new():
                    # Keep the original file if no file is uploaded.
                    continue 
            if isinstance(type, pd.Password) and kwargs.get('verify') is None:
                kwargs['verify'] = not type.verify() and value or ''
            error = record.validate(id, value, **kwargs)
            #log(OPR, "Validation:", (id, value, kwargs, error))
            if error:
                errors.append((id, error.message()))
        if not errors:
            if record.new() and self._LIST_BY_LANGUAGE and record['lang'].value() is None:
                lang = req.preferred_language(raise_error=False)
                record['lang'] = pd.Value(record.type('lang'), lang)
            for check in self._view.check():
                result = check(record)
                if result:
                    if isinstance(result, (str, unicode)):
                        result = (result, _("Integrity check failed."))
                    else:
                        assert isinstance(result, tuple) and len(result) == 2, \
                            ('Invalid check() result:', result)
                    errors.append(result)
        return errors

    def _analyze_exception(self, e):
        """Translate exception error string to a custom error message.

        Uses _EXCEPTION_MATCHERS to match error string reported by
        'e.exception()'.  Returns a pair of field_id and error message, where
        field_id determines the form field which caused the error (one of field
        identifiers defined by the specification).  If field_id is None, it
        means that the error message is either not related to a particular form
        field or that it is not possible to determine which field it is.

        """
        if e.exception():
            error = str(e.exception()).strip()
        else:
            error = e.message()
        for matcher, msg in self._exception_matchers:
            match = matcher.match(error)
            if match:
                if isinstance(msg, tuple):
                    field_id, msg = msg
                elif 'id' in match.groupdict():
                    matched_id = match.group('id')
                    if matched_id.endswith('_key'):
                        # The identifier is (maybe) a name of a PostgreSQL UNIQUE index.
                        try:
                            # The corresponding field id is either defined explicitly.
                            field_id = self._UNIQUE_CONSTRAINT_FIELD_MAPPING[matched_id]
                        except KeyError:
                            # Or we will try to guess it from the PostgreSQL index name,
                            # relying on its default naming "<table>_<column-id>_key".
                            words = matched_id[:-4].split('_')
                            for i in range(len(words)):
                                maybe_field_id = '_'.join(words[i:])
                                if self._view.field(maybe_field_id):
                                    return (maybe_field_id, msg)
                    if self._view.field(matched_id):
                        field_id = matched_id
                    else:
                        field_id = None
                        # If the matched id doesn't belong to any existing
                        # field, just add it to the end of the error
                        # message.  It will be usually quite cryptic for the
                        # user, but it may provide a hint.
                        msg += ' (%s)' % matched_id
                else:
                    field_id = None
                return (field_id, msg)
        return (None, _("Unable to perform a database operation:") +' '+ error)

    def _error_message(self, fid, error):
        # Return an error message string out of _analyze_exception() result.
        if fid is not None:
            f = self._view.field(fid)
            if f:
                label = f.label()
            else:
                # TODO: This should not happen anymore, since
                # _analyze_exception() should now always return a valid
                # field_id.
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
        if self._USE_BINDING_PARENT_TITLE:
            fw = self._binding_forward(req)
            if fw and fw.arg('title'):
                if title:
                    title = fw.arg('title') +' :: '+ title
                else:
                    title = fw.arg('title')
        messages = req.messages(heading=True)
        if messages:
            if title is None:
                # Hm, why to construct the title sometimes here and sometimes
                # in Document.build?  I'm not going to copy the code from
                # there, so is it worse to change the title or omit the filter
                # information?  I guess that in most cases the menu title is
                # (or should be) equal to view specification title, so we
                # should be relatively safe by using it.
                title = self._view.title()
            # A bit complicated in order to preserve translations
            extra_title = messages[0][0]
            for m in messages[1:]:
                extra_title = extra_title + u'; ' + m[0]
            def interpolate(key, title=title, extra=extra_title):
                return dict(title=title, extra=extra)[key]
            title = lcg.TranslatableText('%(title)s (%(extra)s)').interpolate(interpolate)
        return title
        
    def _document(self, req, content, record=None, lang=None, err=None, msg=None, **kwargs):
        title = self._document_title(req, record)
        if record and lang is None and self._LIST_BY_LANGUAGE:
            lang = str(record['lang'].value())
        # Messages should be now stacked using the req.message() method directly, but they were
        # passed as _document arguments before, so this is just for backwards compatibility.
        if msg:
            req.message(msg)
        if err:
            req.message(err, type=req.ERROR)
        return Document(title, content, lang=lang, **kwargs)

    def _default_actions_first(self, req, record):
        return (Action('insert', self._INSERT_LABEL, descr=self._INSERT_DESCR,
                       context=pp.ActionContext.GLOBAL,
                       enabled=self._insert_enabled),
                Action('export', self._EXPORT_LABEL, descr=self._EXPORT_DESCR,
                       context=pp.ActionContext.GLOBAL),
                Action('view', self._VIEW_LABEL, descr=self._VIEW_DESCR),
                Action('update', self._UPDATE_LABEL, descr=self._UPDATE_DESCR,
                       enabled=lambda r: self._update_enabled(r.req(), r)),
                )

    def _default_actions_last(self, req, record):
        return (Action('copy', self._COPY_LABEL, descr=self._COPY_DESCR),
                Action('delete', self._DELETE_LABEL, descr=self._DELETE_DESCR,
                       enabled=lambda r: self._delete_enabled(r.req(), r)),
                Action('list', self._LIST_LABEL, descr=self._LIST_DESCR),
                )
    
    def _actions(self, req, record):
        """Return the list of all possible actions of this module.

        The returned list will include all defined actions in the order in
        which they should appear in the user interface.  It is preferred to
        define actions statically in specification (as Specification.actions),
        but you may override this method if you want to add/remove some actions
        dynamically (depending on some condition).

        Use '_form_actions' if you want to modify form actions for a particular
        form instance and use '_form_actions_argument()' if you want to pass
        the 'actions' argument to a pytis form constructor.

        """
        return tuple(self._default_actions_first(req, record) + 
                     self._view.actions() + 
                     self._default_actions_last(req, record))

    def _form_actions(self, req, record, form):
        """Return a list of actions available in form user interface.

        Override this method when you need to modify the list of actions
        available in a form, but use '_form_actions_argument()' if you want to
        pass the 'actions' argument to a form constructor.

        This method filters out the list of all available actions returned by
        '_actions()' to include only those, which are permitted to the current
        web user and which make sense in the current context (actions with
        'ActionContext.GLOBAL' when 'record' is None and 'ActionContext.RECORD'
        otherwise.
        

        """
        if isinstance(form, pw.BrowseForm):
            exclude = ('list',)
        elif isinstance(form, pw.ShowForm):
            exclude = ('view',)
        else:
            exclude = ()
        # Action context filtering is redundant here (it is done by the
        # form as well), but we need it here because `_authorized()'
        # methods in applications may historically not expect out of
        # context actions.
        if record is not None:
            required_context = pp.ActionContext.RECORD
        else:
            required_context = pp.ActionContext.GLOBAL
        return [action for action in self._actions(req, record)
                if action.id() not in exclude and action.context() == required_context
                and self._authorized(req, action=action.id(), record=record)]
    
    def _form_actions_argument(self, req):
        """Return a callable to be passed to 'actions' form constructor argument.

        This method returns a callable object to be passed to 'actions'
        argument of a pytis form constructor.  The callable is actually just a
        wrapper for the method '_form_actions()' which actually creates the
        list of form actions permitted to the current web user.  So use this
        method when you need to pass 'actions' to a form constructor, but
        override '_form_actions()' if you want to modify the list of actions
        available in a form.

        """
        return lambda form, record: self._form_actions(req, record, form)
    
    def _insert_enabled(self, req):
        """Return true iff the default 'insert' action is enabled for given request.

        Please, note the difference between disabled actions and actions
        unavailable due to insuffucient access rights as described in User
        Interface Design Guidelines in Wiking Developers Documentation.
        
        """
        return True
    
    def _update_enabled(self, req, record):
        """Return true iff the default 'update' action is enabled for given record.

        Please, note the difference between disabled actions and actions
        unavailable due to insuffucient access rights as described in User
        Interface Design Guidelines in Wiking Developers Documentation.
        
        """
        return True
    
    def _delete_enabled(self, req, record):
        """Return true iff the default 'delete' action is enabled for given record.

        Please, note the difference between disabled actions and actions
        unavailable due to insuffucient access rights as described in User
        Interface Design Guidelines in Wiking Developers Documentation.
        
        """
        return True
    
    def _link_provider(self, req, uri, record, cid, **kwargs):
        """Return a link target for given form field.

        Arguments:
          req -- current request as 'Request' instance
          uri -- base URI of the form requesting the field link
          record -- form record as a 'PytisModule.Record' instance
          cid -- string identifier of the form field/column for which the link
            is requested or None if the URI of the whole record is requested.
          kwargs -- dictionary of request parameters to encode into the
            returned URI.  When '_link_provider() is called by a pytis form,
            the parameters are always empty.  However if passed, the default
            implementation respects them and encodes them to the returned URI.
            So the typical use of these parameters from the perspective of an
            application developer is passing additional parameters when calling
            '_link_provider()' from within application code.  For example
            "self._link_provider(req, uri, record, None, action='update')" will
            return the link to the update action of the current record.  If you
            override this method to define an URI for a certain field, you may
            choose to ignore or use those arguments because you (should) know
            whether the application makes use of them in given context.

        The return value may be None for fields which don't link anywhere,
        string URI if the field links to that URI or a 'pytis.web.Link'
        instance if it is necessary to specify also some extended link
        attributes, such as title (tooltip text) or target (such as _blank).
        For array fields (when 'cid' belongs to a field of type
        'pytis.data.Array'), the return value must be a function of one
        argument -- the internal python value of the field's inner type.  The
        function will return an URI or Link instance as above for given array
        value.

        The default implementation automatically generates links for codebook
        fields (as returned by the codebook module's 'link()' method), fields
        with 'pp.CbComputer' (as if they were codebook fields) and for fields
        with 'links' specification, where only the first item in 'links' is
        taken into account (just one link for each field is supported here).
        Override this method if you want to add links to other fields or
        suppress or change the default links.

        This method is primarily used by web forms to create links from field
        values, but it is also legal to call the method from within application
        code.

        """
        if cid is None:
            return uri and req.make_uri(uri +'/'+ record[self._referer].export(), **kwargs)
        try:
            codebook, referer, column, value_column = self._links[cid]
        except KeyError:
            pass
        else:
            if referer:
                return req.record_uri(codebook, record[referer].export())
            # TODO: If the referer is not defined, we temporarily use the old
            # method, but it is deprecated.  Inline referer should be defined
            # everywhere (if it is not the value_column) or links will not
            # be displayed.
            try:
                mod = wiking.module(codebook)
            except AttributeError:
                return None
            return mod.link(req, {value_column: record[column].value()}, **kwargs)
        return None

    def _image_provider(self, req, record, cid, uri):
        return None

    def _print_uri_provider(self, req, uri, record, cid):
        if self._authorized(req, action='print_field', record=record):
            return self._link_provider(req, uri, record, None, action='print_field', field=cid)
        else:
            return None
    
    def _file_browser_uri_provider(self, req, uri, record, cid, images=False):
        """Return URI for HTML form field file browser (see 'pytis.web.UriType.FILE_BROWSER')."""
        return None
    
    def _file_upload_uri_provider(self, req, uri, record, cid, images=False):
        """Return URI for HTML form field file upload (see 'pytis.web.UriType.FILE_BROWSER')."""
        return None
        
    def _record_uri(self, req, record, *args, **kwargs):
        # Return the absolute URI of module's record if a direct mapping of the module exists.  
        # Use the method '_current_record_uri()' to get URI in the context of the current request.
        return req.record_uri(self.name(), record[self._referer].export(), *args, **kwargs)

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

    def _form(self, form, req, record=None, action=None, new=False, prefill=None,
              invalid_prefill=None, handler=None, binding_uri=None, hidden_fields=(), **kwargs):
        """Form instance creation wrapper.

        You may override this method if you need to tweek form constructor
        arguments or override the default form classes used by built-in
        actions.  You should, however, not modify it to return anything else
        than a 'pytis.web.Form' instance compatible with the original set of
        arguments (but see the TODO below).  Methods like
        '_list_form_content()' (and similar for other actions) should be used
        to append additional content to the form instance returned by this
        method.

        You should use this method for creation of 'pytis.web.Form' instances
        instead of calling their arguments directly.

        When overriding this method, you will typically tweek the arguments
        passed to the base method, do something on the returned value, but you
        are supposed to call the base method.  If not, you are responsible to
        take care of all the processing implemented by the base method
        yourself.

        TODO: Note, that the definition of this method was not clear in the
        past and some applications (namely Wiking Biblio and WPB Intranet)
        return arbitrary content rather than a form instance.  Thus it is not
        possible to rely on the return type unless we make an incompatible
        change.  It should be doable to make this change on next Wiking Biblio
        development cycle.

        """
        if binding_uri is not None:
            uri = binding_uri
        else:
            uri = self._current_base_uri(req, record)
        if issubclass(form, pw.BrowseForm):
            default_kwargs = dict(
                limits = self._BROWSE_FORM_LIMITS,
                limit = self._BROWSE_FORM_DEFAULT_LIMIT,
                allow_query_search = self._ALLOW_QUERY_SEARCH,
                top_actions = self._TOP_ACTIONS,
                bottom_actions = self._BOTTOM_ACTIONS,
                row_actions = self._ROW_ACTIONS,
                immediate_filters = wiking.cfg.immediate_filters,
                filter_fields = self._filter_fields(req),
                actions = (), # Display no actions by default, rather than just spec actions.
                )
            kwargs = dict(default_kwargs, **kwargs)
        layout = kwargs.get('layout')
        if layout is not None and not isinstance(layout, pp.GroupSpec):
            kwargs['layout'] = self._layout_instance(layout)
        if action:
            hidden_fields += tuple(self._hidden_fields(req, action, record))
        form_record = self._record(req, record and record.row(), prefill=prefill, new=new)
        for fid, data, linking_column, value_column in self._array_fields:
            rows = data.get_rows(condition=pd.EQ(linking_column, form_record[self._key]))
            values = tuple([r[value_column] for r in rows])
            form_record[fid] = pd.Value(form_record.type(fid), values)
        form_instance = form(self._view, req, form_record, handler=handler or req.uri(),
                             name=self.name(), prefill=invalid_prefill,
                             uri_provider=self._uri_provider(req, uri),
                             hidden=hidden_fields, **kwargs)
        if binding_uri is None:
            # We use heading_info only for main form, not for binding side
            # forms.  That's why we test binding_uri here (not very nice...).
            heading_info = form_instance.heading_info()
            if heading_info:
                # TODO: Am I the only one who thinks that passing the heading
                # info through req.message() is an ugly hack?  What about
                # creating a generic mechanism to pass internal processing data
                # through request instance (since it is available everywhere).
                # Some other hacks to achieve the same exist, such as passing
                # data through req.set_param().
                req.message(heading_info, req.HEADING)
        return form_instance

    def _uri_provider(self, req, uri):
        """Return the uri_provider function to pass the pytis form."""
        def uri_provider(record, cid, type=UriType.LINK):
            kwargs = {}
            if record is None:
                assert type == UriType.LINK
                return uri
            elif type == UriType.LINK:
                method = self._link_provider
            elif type == UriType.IMAGE:
                method = self._image_provider
            elif type == UriType.PRINT:
                method = self._print_uri_provider
            elif type in (UriType.FILE_BROWSER, UriType.IMAGE_BROWSER):
                method = self._file_browser_uri_provider
                kwargs = dict(images=(type==UriType.IMAGE_BROWSER))
            elif type in (UriType.FILE_UPLOAD, UriType.IMAGE_UPLOAD):
                method = self._file_upload_uri_provider
                kwargs = dict(images=(type==UriType.IMAGE_UPLOAD))
            return method(req, uri, record, cid, **kwargs)
        return uri_provider
    
    def _layout_instance(self, layout):
        if layout is None:
            layout = self._view.layout().group()
        if isinstance(layout, (tuple, list)):
            layout = pp.GroupSpec(layout, orientation=pp.Orientation.VERTICAL)
        return layout

    def _layout(self, req, action, record=None):
        """Return the form layout for given action and record.

        This method may be overriden to change form layout dynamically based on
        the combination of record, action and current request properties.  You
        may, for example, determine the layout according to field values or the
        currently logged in user.

        Arguments:
          req -- current request
          action -- name of the action as a string (determines also the form
            type)
          record -- the current record instance or None (for actions which
            don't work on an existing record, such as 'insert')

        The returned value may be a 'pytis.presentation.GroupSpec' instance, a
        sequence of field identifiers or 'pytis.presentation.GroupSpec'
        instances or 'None' to use the default layout defined by specification.
        If you ever need to call this method (you most often just define it),
        use the '_layout_instance()' method to convert the returned value into
        a 'pytis.presentation.GroupSpec' instance.

        The default implementation returns one of (statical) layouts defined in
        '_LAYOUTS' (dictionary keyed by action name) or None if no specific
        layout is defined for given action (to use the default layout from
        specification).

        """
        return self._LAYOUT.get(action)

    def _hidden_fields(self, req, action, record=None):
        """Return the hidden form fields for given action and record.

        This method may be overriden to change hidden form fields dynamically
        based on the combination of record, action and current request
        properties.

        Arguments:
          req -- current request
          action -- name of the action as a string (determines also the form
            type)
          record -- the current record instance or None (for actions which
            don't work on an existing record, such as 'insert')

        Returns a list of pairs (field, value) as accepted by the argument
        'hidden' of 'pytis.web.Form' constructor.

        The default implementation returns the list [('action', action),
        ('submit', 'submit')] as these parameters are used by wiking itself.
            
        """
        return [('action', action),
                ('submit', 'submit')]

    def _submit_buttons(self, req, action, record=None):
        """Return the sequence of form submit buttons as pairs (LABEL, NAME).

        This method may be overriden to change form buttons dynamically based
        on the combination of record, action and current request properties.

        Arguments:
          req -- current request
          action -- name of the action as a string (determines also the form
            type)
          record -- the current record instance or None (for actions which
            don't work on an existing record, such as 'insert')

        The returned value is a sequence of pairs (LABEL, NAME), where LABEL is
        the button label and NAME is the name of the corresponding request
        parameter, which will be submitted along with the form when the button
        is pressed.  The parameter's value is the button LABEL, but you will
        not want to check against the label if your application is
        internationalized (you get different labels for different languages).

        The default implementation returns one of (statical) button
        specifications defined by in '_SUBMIT_BUTTONS' constant (dictionary
        keyed by action name) or None if no specific buttons are defined for
        given action (to use the default from buttons).

        """
        return self._SUBMIT_BUTTONS.get(action)

    def _columns(self, req):
        """Return a sequence of BrowseForm columns.

        Override this metod to dynamically change the list of visible
        BrowseForm columns.  The default implementation returns the list of
        columns defined by the specification.

        """
        return self._view.columns()

    def _exported_columns(self, req):
        """Return a list of columns present in CSV export (action 'export').
        
        Override this metod to dynamically change the list of columns present
        in exported data.  The default implementation returns the same as
        '_columns()'.

        """
        return self._columns(req)

    def _export_filename(self, req):
        """Return the filename (string) of the CSV export download (action 'export')."""
        return 'export.csv'
    
    def _profiles(self, req):
        """Return dynamically created profiles.

        'None' means to use the default list of form profiles defined by the
        specification.  Otherwise a sequence 'pytis.presentation.Profile'
        instances or a 'pytis.presentation.Profiles' instance is expected.

        Override this metod to dynamically change the list of user visible form
        profiles in the BrowseForm/ListView form.  The default implementation
        returns 'None' (to use the default static list from specification).

        """
        return None

    def _filter_sets(self, req):
        """Return dynamically created filter sets.

        'None' means to use the default list of filter sets defined by the
        specification.  Otherwise a sequence 'pytis.presentation.FilterSet'
        instances is expected.

        Override this metod to dynamically change the list of user visible
        filter sets in the BrowseForm/ListView form.  The default
        implementation returns 'None' (to use the default static list from
        specification).

        """
        filters = self._filters(req)
        if filters:
            return (pp.FilterSet('filter', _("Filter"), filters),)
        else:
            return None

    def _filters(self, req):
        """Return a list of dynamic filters as 'pytis.presentation.Filter' instances or None.

        This is just a more convenient filter set definition for cases when
        there is just one set of filters.  Use '_filter_sets()' in all other
        cases.

        """
        return None

    def _filter_fields(self, req):
        """Return the list of editable fitler field specifications.

        The returned value is passed to 'pytis.web.BrowseForm'
        'filter_fields' constructor argument.  See 'pytis.web.BrowseForm'
        documentation for exact specification.

        """
        return None
        
    
    def _action_args(self, req):
        """Resolve request path and/or parameters into action method arguments.

        Pytis module resolves to 'record' argument if the URI corresponds to a
        particular record through the referer column or to no arguments if the
        URI is just a base URI of the modue (no subpath).  'NotFound' is raised
        when the URI refers to an inexistent record.

        """
        row = self._resolve(req)
        if row is not None:
            args = dict(record=self._record(req, row))
        else:
            args = dict()
        return args
    
    def _default_action(self, req, record=None):
        """Return the name of the action to perform if 'action' request parameter was not passed.

        If you ever override this method in a derived class, it should accept
        all arguments which may be returned by '_action_args()'.  This
        practically means, that if you want to stay forward compatible with
        possible additions to this class, you should accept ANY arguments
        through '**kwargs' and only inspect the arguments of your interest.

        """
        if record is None:
            return 'list'
        else:
            return 'view'

    def _resolve(self, req):
        # Returns Row, None or raises RequestError.
        if req.unresolved_path:
            row = self._refered_row(req, req.unresolved_path[0])
            # If no error was raised, the path was resolved.
            del req.unresolved_path[0]
            return row
        elif req.has_param(self._key) and req.param('action') != 'insert':
            return self._get_row_by_key(req, req.param(self._key))
        else:
            return None

    def _get_row_by_key(self, req, value):
        if isinstance(value, tuple):
            value = value[-1]
        type = self._data.key()[0].type()
        v, error = type.validate(value, strict=False)
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
        type = self._type[self._referer]
        if not isinstance(type, pd.String):
            v, error = type.validate(value, strict=False)
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
            values['lang'] = req.preferred_language(raise_error=False)
        return values
    
    def _refered_row(self, req, value):
        """Return a 'pytis.data.Row' instance corresponding to the refered record.

        The argument is a string representation of the module's referer column value (from URI
        path).  Raise 'NotFound' error if the refered row doesn't exist.

        """
        values = self._refered_row_values(req, value)
        row = self._data.get_row(arguments=self._arguments(req), **values)
        if row is None:
            raise NotFound()
        return row
        
    def check_owner(self, user, record):
        if self._OWNER_COLUMN is not None:
            owner = record[self._OWNER_COLUMN].value()
            return user.uid() == owner
        return False
    
    def _prefill(self, req):
        """Return the new record prefill values as a dictionary.
        
        The dictionary is passed as 'prefill' argument to the
        L{PytisModule.Record} constructor for the new record on insertinon.  The
        dictionary keys are field identifiers and values are internal Python
        values of the corresponding fields.

        You may need to override this method if you want to set default values
        depending on the current request object (which is not available for
        field 'default' specifications.

        The base class implementation automatically handles binding column
        prefill in binding forwarded requests, record owner column prefill if
        '_SUPPLY_OWNER' is True and default language if '_LIST_BY_LANGUAGE' is
        True.
        
        """
        # TODO: The same prefill should also be used by the form when
        # initializing it's `Record' instance, since visible form fields
        # may depend on this prefill too.
        prefill = {}
        fw = self._binding_forward(req)
        if fw:
            # Supply the value of the binding column (if this is a binding
            # forwarded request).
            binding = fw.arg('binding')
            binding_record = fw.arg('record')
            binding_prefill = binding.prefill()
            if binding_prefill:
                prefill = binding_prefill(binding_record)
            elif binding.binding_column():
                binding_column = binding.binding_column()
                main_form_column = self._type[binding_column].enumerator().value_column()
                prefill[binding_column] = binding_record[main_form_column].value()
        if self._OWNER_COLUMN and self._SUPPLY_OWNER and req.user() \
               and self._OWNER_COLUMN not in prefill:
            prefill[self._OWNER_COLUMN] = req.user().uid()
        if self._LIST_BY_LANGUAGE and 'lang' not in prefill:
            lang = req.preferred_language(raise_error=False)
            if lang:
                prefill['lang'] = lang
        return prefill
    
    def _invalid_prefill(self, req, record, layout):
        # Note, this method is only used for prefilling the fields in a
        # displayed form.  It has no effect on the 'prefill' passed to the
        # created 'Record' instances.  The returned dictionary values must be
        # user input string which didn't pass validation, but the form should
        # still display them in fields so that the user can fix them and try
        # validation again.
        prefill = {}
        for key in layout.order():
            invalid_string = record.invalid_string(key)
            if invalid_string != None:
                prefill[key] = invalid_string
        return prefill

    def _binding_condition(self, binding, record):
        """Return a binding condition as a 'pytis.data.Operator' instance.

        Arguments:

          binding -- 'pytis.presentation.Binding()' instance coming from parent
            module's 'bindings' specification.
          record -- parent module's 'wiking.PytisModule.Record()' instance.

        Returns a condition for filtering this module's records based on a
        relation to the parent module's record, where the relation is described
        by given binding specification.
        
        """
        cfunc = binding.condition()
        if cfunc:
            condition = cfunc(record)
        else:
            condition = None
        binding_column = binding.binding_column()
        if binding_column:
            type = self._type[binding_column]
            enumerator = type.enumerator()
            if enumerator is None:
                raise Exception("Column '%s' of '%s' is used as a binding column but "
                                "has no enumerator defined." % (binding_column,
                                                                self.__class__.__name__))
            value = record[enumerator.value_column()].value()
            bcond = pd.EQ(binding_column, pd.Value(type, value))
            if condition:
                condition = pd.AND(condition, bcond)
            else:
                condition = bcond
        return condition
        
    def _condition(self, req):
        """Return the filtering condition as a pytis.data.Operator instance or None.

        Returns the condition for filtering records visible to the current
        request user.  This condition is used for filtering the rows visible
        through action 'list' and should be also used in all other situations,
        where data rows become visible in the user interface in some form.

        You may need to override this method if you want to filter visible rows
        according to some application specific condition, which may be
        determined from the request object (most typically access rights of the
        current user).

        The base class implementation automatically includes the binding
        condition (see '_binding_condition()') if the current module is handled
        through binding forwarding.  Binding forwarding is used to access data
        through pytis 'binding' specification.  The URI of a binding forwarded
        request has a form '/xyz/key/binding-id', where 'xyz' is the URI of the
        parent module, 'key' is the reference to a record of the parent module
        and 'binding-id' is the id of the 'pytis.presentation.Binding' used in
        the parent module's 'binding' specification.  In this case, the binding
        condition will limit the listing of this module only to records related
        to the parent module's record (satisfying the binding condition).  It
        is called binding forwarding because the parent module forwards the
        request to the submodule within '_handle_subpath()'.

        """
        fw = self._binding_forward(req)
        if fw:
            binding = fw.arg('binding')
            record = fw.arg('record')
            return self._binding_condition(binding, record)
        else:
            return None
        
    def _arguments(self, req):
        """Return runtime database table function arguments.

        Return None or a dictionary of 'pytis.data.Value' instances.  The dictionary is passed as
        'arguments' to 'pytis.data.DBData.select()' call.  Note that you must define the arguments
        in the specification, to get them used for the data object.

        """
        return None
        
    def _binding_arguments(self, binding, record):
        function = binding.arguments()
        if function:
            arguments = function(record)
        else:
            arguments = None
        return arguments
        
    def _rows(self, req, condition=None, lang=None, limit=None, sorting=None):
        return list(self._rows_generator(req, condition=condition, lang=lang, limit=limit,
                                         sorting=sorting))
    
    def _rows_generator(self, req, condition=None, lang=None, limit=None, sorting=None):
        def generator(cond, args):
            data = self._data
            count = 0
            try:
                data.select(condition=cond, arguments=args, sort=sorting or self._sorting)
                while True:
                    if limit is not None and count >= limit:
                        break
                    row = data.fetchone()
                    if row is None:
                        break
                    count += 1
                    yield row
            finally:
                try:
                    data.close()
                except:
                    pass
        # Note, condition and arguments must be computed here, not within the
        # generator function itself because it depends on the current state of
        # 'req'.  In practise it means, that binding forward condition would
        # not be included in condition because req._forwards is popped after
        # handle() returns (see 'Request.forward()') and the generator will run
        # after that.
        if self._LIST_BY_LANGUAGE:
            if lang is None:
                lang = req.preferred_language()
            lcondition = pd.EQ('lang', pd.sval(lang))
        else:
            lcondition = None
        return generator(pd.AND(self._condition(req), condition, lcondition),
                         self._arguments(req))

    def _records(self, req, condition=None, lang=None, limit=None, sorting=None):
        record = self._record(req, None)
        # Call self._rows_generator() outside the generator function to compute
        # the condition and other `req' dependent data now, not when the
        # generator runs.
        rows = self._rows_generator(req, condition=condition, lang=lang, limit=limit,
                                    sorting=sorting)
        def generator():
            for row in rows:
                record.set_row(row)
                yield record
        return generator()

    def _handle(self, req, action, **kwargs):
        record = kwargs.get('record')
        if record is not None and req.unresolved_path:
            unresolved_subpath = True
        else:
            unresolved_subpath = False
        if action != 'list' or unresolved_subpath:
            # Handle Pytis redirection first.  The 'list' action is the only
            # operation which is not subject to redirection.  Everything else
            # (including 'insert') may be redirected to a more specific module
            # according to request parameters or record values.  We also want
            # the redirection to take place, when the 'list' action doesn't
            # belong to the current module, but another module in the
            # unresolved subpath.  The action on the current module is actually
            # 'view' in this case.
            redirect = self._view.redirect()
            if redirect:
                modname = redirect(req, record)
                if modname is not None and modname != self.name():
                    # Set the unresolved_path back to let the redirected module
                    # do request resolution again.
                    for fw in reversed(req.forwards()):
                        if fw.module().name() == self.name():
                            req.unresolved_path = list(fw.unresolved_path())
                            break
                    else:
                        req.unresolved_path = list(req.path)
                    return req.forward(wiking.module(modname), pytis_redirect=True)
        # Handle request to a subpath (pytis bindings are represented by request uri paths).
        if unresolved_subpath:
            self._authorize(req, action='view', record=record)
            return self._handle_subpath(req, record)
        return super(PytisModule, self)._handle(req, action, **kwargs)

    def _handle_subpath(self, req, record):
        for binding in self._bindings(req, record):
            if req.unresolved_path[0] == binding.id():
                del req.unresolved_path[0]
                # TODO: respect the binding condition in the forwarded module.
                mod = wiking.module(binding.name())
                return req.forward(mod, binding=binding, record=record,
                                   title=self._document_title(req, record))
        if req.unresolved_path[0] in [b.id() for b in self._view.bindings()]:
            # If a binding is present in `view.bindings()', but not in
            # self._bindings(), it is disabled (its `enabled' function
            # returns False.  Thus the URI is valid, but not accessible
            # for some reason.
            raise Forbidden()
        else:
            raise NotFound()

    def _binding_enabled(self, req, record, binding):
        if isinstance(binding, wiking.Binding):
            enabled = binding.enabled()
            if enabled is None:
                return True
            elif isinstance(enabled, collections.Callable):
                return enabled(record)
            else:
                return bool(enabled)
        else:
            return True

    def _bindings(self, req, record):
        return [b for b in self._view.bindings() if self._binding_enabled(req, record, b)]

    def _call_rows_db_function(self, name, *args, **kwargs):
        """Call database function NAME with given arguments and return the result.

        'args' are Python values wich will be automatically wrapped into
        'pytis.data.Value' instances.  'kwargs' may contain 'transaction'
        argument to be passed to the database function.
        
        """
        transaction = kwargs.get('transaction')
        try:
            function, arg_spec = self._db_function[name]
        except KeyError:
            function = pytis.data.DBFunctionDefault(name, self._dbconnection,
                                                    connection_name=self.Spec.connection)
            arg_spec = self._DB_FUNCTIONS[name]
            self._db_function[name] = function, arg_spec
        assert len(args) == len(arg_spec), \
               "Wrong number of arguments for '%s': %r" % (name, args)
        arg_data = [(spec[0], pd.Value(spec[1], value)) for spec, value in zip(arg_spec, args)]
        return function.call(pytis.data.Row(arg_data), transaction=transaction)

    def _call_db_function(self, name, *args, **kwargs):
        """Call database function NAME with given arguments and return the first result.

        If the result and its first row are non-empty, return the first value
        of the first row; otherwise return 'None'.

        'args' are Python values wich will be automatically wrapped into
        'pytis.data.Value' instances.  'kwargs' may contain 'transaction'
        argument to be passed to the database function.
        
        """
        transaction = kwargs.get('transaction')
        row = self._call_rows_db_function(name, *args, transaction=transaction)[0]
        if row:
            result = row[0].value()
        else:
            result = None
        return result

    def _is_ajax_request(self, req):
        """Return True if the request is an AJAX request.

        If the current request is a pytis form update request, return True,
        Otherwise return False.  If True is returned, request processing should
        be passed to the method '_handle_ajax_request()'.
        
        """
        return req.param('_pytis_form_update_request') is not None

    def _handle_ajax_request(self, req, record, layout, errors):
        """Handle the AJAX request and return the result.

        This method should be called when the method '_is_ajax_request()'
        returns true.

        """
        uri = self._current_base_uri(req, record)
        response = pw.EditForm.ajax_response(req, record, layout, errors, req.localizer(),
                                             uri_provider=self._uri_provider(req, uri))
        return wiking.Response(response, content_type='application/json')
         

    def _list_form_content(self, req, form, uri=None):
        """Return the page content for the 'list' action form as a list of 'lcg.Content' instances.

        Arguments:
          req -- current 'Request' instance.
          form -- 'pytis.web.BrowseForm' instance.
          uri -- binding URI if the 'form' is a side form or None if 'form' is
            a main form.  The URI normally has the form
            '<main_form_uri>/<binding_id>'.
        
        You may override this method to modify page content for the list form
        in derived classes.

        """
        return [form]

    def _print_field_title(self, req, record, field):
        """Return the document title used by the 'print_field' action.
        
        @type req: C{wiking.Request}
        @param req: current request object
        @type record: C{wiking.PytisModule.Record}
        @param record: the record containing the field data to be printed
        @type field: C{pytis.presentation.Field}
        @param field: the field to be printed (exported into a PDF document)
        @rtype: basestring
        @return: Main heading of the PDF document containing the exported field
           content.

        The default title is the label of the printed field.

        """
        return field.label()
        
    def _print_field_filename(self, req, record, field):
        """Return the file name of the PDF document produced by the 'print_field' action.
        
        @type req: C{wiking.Request}
        @param req: current request object
        @type record: C{wiking.PytisModule.Record}
        @param record: the record containing the field data to be printed
        @type field: C{pytis.presentation.Field}
        @param field: the field to be printed (exported into a PDF document)
        @rtype: basestring
        @return: File name sent within the 'Content-disposition' HTTP response
          header.

        The default file name is '<record id>-<field id>.pdf', where record id
        is the value of the referer field (see L{PytisModule._REFERER}).

        """
        return record[self._referer].export() +'-'+ field.id() +'.pdf'
        
    def _print_field_content(self, req, record, field):
        """Build the content to export into PDF for the 'print_field' action.
        
        @type req: C{wiking.Request}
        @param req: current request object
        @type record: C{wiking.PytisModule.Record}
        @param record: the record containing the field data to be printed
        @type field: C{pytis.presentation.Field}
        @param field: the field to be printed (exported into a PDF document)
        @rtype: C{lcg.Content}
        @return: Full content of the document

        The default implementation returns an 'lcg.Container' containing the
        result of parsing the string value of the printed field by LCG.  You
        may override this method to wrap its result in additional content or do
        any such tweaks.

        """
        text = record[field.id()].value()
        parser = lcg.Parser()
        # Translation is needed before parsing, because the text may contain 'lcg.Translatable'
        # instances, which would be destroyed during parsing (think of virtual fields with text
        # constructed in runtime).
        content = parser.parse(req.localize(text))
        return lcg.Container(content)
    
    def _transaction(self):
        """Create a new transaction and return it as 'pd.DBTransactionDefault' instance."""
        return pd.DBTransactionDefault(self._dbconnection, connection_name=self.Spec.connection)

    def _in_transaction(self, transaction, operation, *args, **kwargs):
        """Perform operation within given transaction and return the result.

        @type transaction: C{pytis.data.DBTransactionDefault} or C{None}.
        @param transaction: transaction object encapsulating the database
            operation environment or 'None' (meaning default environment).
        @type operation: callable
        @param transaction: function or method to be called with given *args and **kwargs.

        If transaction is not None, exceptions during operation execution are handled and
        transaction is rolled back if any exception occurs.  If no exception occurs, the
        transaction is commited and result is returned.
        
        If transaction is None, the operation is simply called and result is returned.

        @note: All this method basically does is handling commit/rollback
        operations of C{transaction}.  You are still responsible for passing
        the transaction argument to database operations inside C{operation}.

        """
        if transaction is None:
            return operation(*args, **kwargs)
        else:
            try:
                result = operation(*args, **kwargs)
            except:
                try:
                    transaction.rollback()
                except:
                    pass
                raise
            else:
                transaction.commit()
                return result

    def _insert_transaction(self, req, record):
        """Return the transaction for the 'insert' action operation.

        This method returns None in the base class, but if a derived class needs to enclose the
        '_insert()' method execution (invoked within the default 'action_insert()' handler) in a
        transaction, the method may be overriden to return a transaction instance.  In other words,
        the result of this method is passed as 'transaction' argument to the '_insert()' method in
        'action_insert()' handler.

        """
        if self._array_fields:
            return self._transaction()
        else:
            return None
            
    def _update_transaction(self, req, record):
        """Return the transaction for the 'update' action operation.

        This method returns None in the base class, but if a derived class needs to enclose the
        '_update()' method execution (invoked within the default 'action_update()' handler) in a
        transaction, the method may be overriden to return a transaction instance.  In other words,
        the result of this method is passed as 'transaction' argument to the '_update()' method in
        'action_update()' handler.

        """
        if self._array_fields:
            return self._transaction()
        else:
            return None
            
    def _delete_transaction(self, req, record):
        """Return the transaction for the 'delete' action operation.

        This method returns None in the base class, but if a derived class needs to enclose the
        '_delete()' method execution (invoked within the default 'action_delete()' handler) in a
        transaction, the method may be overriden to return a transaction instance.  In other words,
        the result of this method is passed as 'transaction' argument to the '_delete()' method in
        'action_delete()' handler.

        """
        return None
        
    # ===== Methods which modify the database =====

    def _update_linking_tables(self, req, record, transaction):
        for fid, data, linking_column, value_column in self._array_fields:
            values = record[fid].value() or ()
            key = record.key()[0]
            data.delete_many(condition=pd.AND(pd.EQ(linking_column, key),
                                              *[pd.NE(value_column, v) for v in values]),
                             transaction=transaction)
            for value in values:
                try:
                    count = data.select(condition=pd.AND(pd.EQ(linking_column, key),
                                                  pd.EQ(value_column, value)),
                                        transaction=transaction)
                finally:
                    try:
                        data.close()
                    except:
                        pass
                if count != 1:
                    row = pd.Row([(linking_column, key), (value_column, value)])
                    data.insert(row, transaction=transaction)
    
    def _insert(self, req, record, transaction):
        """Insert new row into the database and return a Record instance.

        The 'transaction' is C{None} in the base class.  Override '_insert_transaction()' if you
        want the operation to be enclosed in a transaction (typically when you override this method
        to perform additional operations.

        """
        for key, seq in self._SEQUENCE_FIELDS:
            if record[key].value() is None:
                counter = pd.DBCounterDefault(seq, self._dbconnection,
                                              connection_name=self.Spec.connection)
                value = counter.next(transaction=transaction)
                record[key] = pd.Value(record.type(key), value)
        result, success = self._data.insert(record.rowdata(), transaction=transaction)
        #debug(":::", success, result)
        if not success:
            raise pd.DBException(result)
        elif result is not None:
            # The result is typically None, when inserting into a view which
            # has no "returning" statement in the insert rule.
            # We can't use set_row(), since it would destroy virtual file
            # fields (used in CMS).
            for key in result.keys():
                # The 'result' row may contain automatically appended data
                # columns, such as inline_display, so we must check their
                # presence in record.
                if key in record:
                    record[key] = result[key]
            self._update_linking_tables(req, record, transaction)
        
    def _update(self, req, record, transaction):
        """Update the record data in the database.

        The 'transaction' is C{None} in the base class.  Override '_update_transaction()' if you
        want the operation to be enclosed in a transaction (typically when you override this method
        to perform additional operations.

        """
        self._data.update(record.key(), record.rowdata(), transaction=transaction)
        self._update_linking_tables(req, record, transaction)

    def _delete(self, req, record, transaction):
        """Delete the record from the database.

        The 'transaction' is C{None} in the base class.  Override '_delete_transaction()' if you
        want the operation to be enclosed in a transaction (typically when you override this method
        to perform additional operations.

        """
        self._data.delete(record.key(), transaction=transaction)
        
    # ===== Public methods =====
    
    def referer(self):
        """Temporary internal method.  Don't use in application code."""
        # This temporary method is used within PytisModule._delayed_init() to
        # retrieve module's referer column name.  As soon as the referer column
        # is specified in ViewSpec and not through the deprecated
        # PytisModule._REFERER constant, we will be able to retrieve it through
        # the resolver and we will not need this method.
        return self._referer
        
    def link(self, req, key, *args, **kwargs):
        """DEPRACATED!

        Don't use in application code and don't rely on implicit links which
        require subqueries.  See also the comment in
        'PytisModule._link_provider()'.

        """
        if self._link_cache_req is not req:
            self._link_cache = {}
            self._link_cache_req = req
        if not args and not kwargs:
            if isinstance(key, dict):
                cache_key = tuple(key.items())
            else:
                cache_key = key
            try:
                if cache_key in self._link_cache:
                    return self._link_cache[cache_key]
            except TypeError:           # catch unhashable keys
                pass
            # TODO: The following is an important optimization hack.  It is an
            # incorrect hack because if a successor redefines _record_uri
            # method, the redefined method doesn't get called.  At least we
            # provide escape path by the _OPTIMIZE_LINKS flag.
            if (self._OPTIMIZE_LINKS and
                self._key == self._referer and
                (not isinstance(key, dict) or key.keys() == [self._key])):
                if isinstance(key, dict):
                    key = key[self._key]
                if isinstance(key, pd.Value):
                    key = key.value()
                uri = self._base_uri(req)
                if uri:
                    return req.make_uri('%s/%s' % (uri, key,))
                else:
                    return None
        if isinstance(key, dict):
            row = self._data.get_row(arguments=self._arguments(req), **key)
        else:
            row = self._data.row(key)
        if row:
            result = self._record_uri(req, self._record(req, row), *args, **kwargs)
        else:
            result = None
        if not args and not kwargs:
            try:
                self._link_cache[cache_key] = result
            except TypeError:           # catch unhashable keys
                pass
        return result
        
    def related(self, req, binding, record, uri):
        """Return the listing of records related to other module's record by given binding."""
        if isinstance(binding, Binding) and binding.form_cls() is not None:
            form_cls = binding.form_cls()
            form_kwargs = binding.form_kwargs()
        else:
            form_cls, form_kwargs = pw.ListView, {}
        columns = [c for c in self._columns(req) if c != binding.binding_column()]
        lang = req.preferred_language(raise_error=False)
        if self._LIST_BY_LANGUAGE:
            lcondition = pd.AND(pd.EQ('lang', pd.sval(lang)))
        else:
            lcondition = None
        condition = pd.AND(self._condition(req),
                           self._binding_condition(binding, record),
                           lcondition)
        binding_uri = uri +'/'+ binding.id()
        form = self._form(form_cls, req, columns=columns, binding_uri=binding_uri,
                          condition=condition,
                          arguments=self._binding_arguments(binding, record),
                          profiles=self._profiles(req), filter_sets=self._filter_sets(req),
                          actions=self._form_actions_argument(req),
                          **form_kwargs)
        content = self._list_form_content(req, form, uri=binding_uri)
        return lcg.Container(content)

    # ===== Action handlers =====
    
    def action_list(self, req, record=None):
        if record is not None:
            raise Redirect(self._current_base_uri(req, record),
                           search=record[self._key].export(), form_name=self.name())
        # Don't display the listing alone, but display the original main form,
        # when this list is accessed through bindings as a related form.
        self._binding_parent_redirect(req, search=req.param('search'), form_name=self.name())
        # If this is not a binding forwarded request, display the listing.
        lang = req.preferred_language()
        condition = self._condition(req)
        if self._LIST_BY_LANGUAGE:
            condition = pd.AND(condition, pd.EQ('lang', pd.sval(lang)))
        form = self._form(pw.ListView, req,
                          columns=self._columns(req),
                          condition=condition,
                          arguments=self._arguments(req),
                          profiles=self._profiles(req),
                          filter_sets=self._filter_sets(req),
                          actions=self._form_actions_argument(req),
                          )
        content = self._list_form_content(req, form)
        return self._document(req, content, lang=lang)

    def _binding_parent_uri(self, req):
        fw = self._binding_forward(req)
        if fw:
            path = fw.uri().lstrip('/').split('/')
            if path and path[-1] == fw.arg('binding').id():
                return '/'+ '/'.join(path[:-1])
        return None
    
    def _binding_parent_redirect(self, req, **kwargs):
        uri = self._binding_parent_uri(req)
        if uri is not None:
            raise Redirect(uri, **kwargs)
        
    def _related_content(self, req, record):
        """Return the content related to given record as a list of 'lcg.Content' instances.

        Arguments:
          req -- current 'Request' instance.
          record -- the current record of the form as 'PytisModule.Record'.

        The returned content is displayed within the 'view' action under the
        record details.  The default implementadion returns a list of forms
        according to the 'bindings' specification.  You may override this
        method to adjust this default behavior.

        """
        sections = []
        active = None
        for binding in self._bindings(req, record):
            modname = binding.name()
            mod = wiking.module(modname)
            content = mod.related(req, binding, record, uri=self._current_record_uri(req, record))
            if content:
                anchor = 'binding-'+binding.id()
                if req.param('form_name') == modname:
                    active = anchor
                sections.append(lcg.Section(title=binding.title(), descr=binding.descr(),
                                            anchor=anchor, content=content))
        if sections:
            return [wiking.Notebook(sections, name='bindings-'+self.name(), active=active)]
        else:
            return []

    def _view_form_content(self, req, form, record):
        """Return page content for 'view' action form as a list of 'lcg.Content' instances.

        Arguments:
          req -- current 'Request' instance.
          form -- 'pytis.web.ShowForm' instance.
          record -- the current record of the form as 'PytisModule.Record'.
        
        You may override this method to modify page content for the view form
        in derived classes.  The default implementation returns the form
        itself and the result of '_related_content()' packed in one list.

        """
        return [form] + self._related_content(req, record)
    
    def _update_form_content(self, req, form, record):
        """Return page content for 'update' action form as a list of 'lcg.Content' instances.

        Arguments:
          req -- current 'Request' instance.
          form -- 'pytis.web.EditForm' instance.
          record -- the current record of the form as 'PytisModule.Record'.
        
        You may override this method to modify page content for the edit form
        in derived classes.  The default implementation returns just the form
        itself.

        """
        return [form]
        
    def action_view(self, req, record, err=None, msg=None):
        # The arguments `msg' and `err' are DEPRECATED!  Please don't use.
        # They are currently still used in Eurochance LMS.
        form = self._form(pw.ShowForm, req, record=record,
                          layout=self._layout(req, 'view', record),
                          actions=self._form_actions_argument(req),
                          )
        content = self._view_form_content(req, form, record)
        return self._document(req, content, record, err=err, msg=msg)

    # ===== Action handlers which modify the database =====

    def action_insert(self, req, prefill=None, action='insert'):
        # 'prefill' is passed eg. on copying an existing record.  It is only
        # used to initialize form fields and is ignored on form submission (the
        # submitted form should pass those values through request arguments).
        layout = self._layout_instance(self._layout(req, action))
        if req.param('submit'):
            record = self._record(req, None, new=True, prefill=self._prefill(req))
            errors = self._validate(req, record, layout)
            if self._is_ajax_request(req):
                return self._handle_ajax_request(req, record, layout, errors)
            if not errors:
                try:
                    transaction = self._insert_transaction(req, record)
                    self._in_transaction(transaction, self._insert, req, record, transaction)
                except pd.DBException as e:
                    errors = (self._analyze_exception(e),)
                else:
                    return self._redirect_after_insert(req, record)
            # The record created above is not passed to the form, so we must
            # pass the values through prefill/invalid_prefill to the newly
            # displayed form.
            invalid_prefill = self._invalid_prefill(req, record, layout)
            prefill = dict([(key, record[key].value()) for key in layout.order()
                            if record.field_changed(key)])
        else:
            errors = ()
            prefill = dict(self._prefill(req), **(prefill or {}))
            invalid_prefill = {}
            for key in layout.order():
                # Use values passed as request arguments as form prefill.
                if req.has_param(key):
                    type = self._type[key]
                    if not isinstance(type, (pd.Binary, pd.Password)):
                        string_value = req.param(key)
                        value, error = type.validate(string_value, strict=False)
                        if not error:
                            prefill[key] = value.value()
                        else:
                            invalid_prefill[key] = string_value
        # TODO: Redirect handler to HTTPS if wiking.cfg.force_https_login is true?
        # The primary motivation is to protect registration form data.  The
        # same would apply for action_edit.
        form = self._form(pw.EditForm, req, new=True, action=action,
                          layout=layout,
                          prefill=prefill,
                          invalid_prefill=invalid_prefill,
                          submit=self._submit_buttons(req, action),
                          errors=errors)
        return self._document(req, form, subtitle=self._action_subtitle(req, action))

    def action_copy(self, req, record, action='insert'):
        # Copy values of the existing record as prefill values for the new
        # record.  Exclude Password and Binary values, key column, computed
        # columns depending on key column and fields with 'nocopy'.
        key = self._key
        base_uri = self._current_base_uri(req, record)
        if req.uri() != base_uri:
            # Invoke the same action for the same record but without the
            # referer in the uri.
            raise Redirect(base_uri, action='copy', **{key: record[key].export()})
        prefill = {}
        layout = self._layout_instance(self._layout(req, action))
        for fid in layout.order():
            if not isinstance(self._type[fid], (pd.Password, pd.Binary)):
                field = self._view.field(fid)
                if fid != key and not field.nocopy():
                    computer = field.computer()
                    if not computer or key not in computer.depends():
                        prefill[fid] = record[fid].value()
        return self.action_insert(req, prefill=prefill, action=action)
            
    def action_update(self, req, record, action='update'):
        layout = self._layout_instance(self._layout(req, action, record))
        if req.param('submit'):
            errors = self._validate(req, record, layout)
            if self._is_ajax_request(req):
                return self._handle_ajax_request(req, record, layout, errors)
        else:
            errors = ()
        if req.param('submit') and not errors:
            try:
                transaction = self._update_transaction(req, record)
                self._in_transaction(transaction, self._update, req, record, transaction)
                record.reload()
            except pd.DBException as e:
                errors = (self._analyze_exception(e),)
            else:
                return self._redirect_after_update(req, record)
        form = self._form(pw.EditForm, req, record=record, action=action,
                          layout=layout,
                          invalid_prefill=self._invalid_prefill(req, record, layout),
                          submit=self._submit_buttons(req, action, record),
                          errors=errors)
        content = self._update_form_content(req, form, record)
        return self._document(req, content, record,
                              subtitle=self._action_subtitle(req, action, record=record))

    def action_delete(self, req, record):
        if req.param('submit'):
            try:
                transaction = self._delete_transaction(req, record)
                self._in_transaction(transaction, self._delete, req, record, transaction)
            except pd.DBException as e:
                req.message(self._error_message(*self._analyze_exception(e)), type=req.ERROR)
            else:
                return self._redirect_after_delete(req, record)
        if req.param('__invoked_from') == 'ListView':
            back_action = 'list'
        else:
            back_action = 'view'
        form = self._form(pw.ShowForm, req, record=record,
                          layout=self._layout(req, 'delete', record),
                          actions=(Action('delete', self._DELETE_LABEL, submit=1),
                                   # Translators: Back button label. Standard computer terminology.
                                   Action(back_action, _("Back"))))
        req.message(self._delete_prompt(req, record))
        return self._document(req, form, record,
                              subtitle=self._action_subtitle(req, 'delete', record))
        
    def action_export(self, req):
        columns = self._exported_columns(req)
        export_kwargs = dict([(cid, isinstance(self._type[cid], pytis.data.Float)
                               and dict(locale_format=False) or {}) for cid in columns])
        def generator(records):
            data = ''
            buffer_size = 1024*512
            for record in records:
                coldata = []
                for cid in columns:
                    value = record.display(cid) or record[cid].export(**export_kwargs[cid])
                    coldata.append(';'.join(value.splitlines()).replace('\t', '\\t'))
                data += '\t'.join(coldata).encode('utf-8') + '\n'
                if len(data) >= buffer_size:
                    yield data
                    data = ''
            if data:
                yield data
        return wiking.Response(generator(self._records(req)),
                               content_type='text/plain; charset=utf-8',
                               filename=self._export_filename(req))


    def action_jsondata(self, req):
        try:
            import json
        except:
            import simplejson as json
        columns = list(self._columns(req))
        if self._key not in columns:
            columns.insert(0, self._key)
        # Inspect column types in advance as it is cheaper than calling
        # isinstance for all exported values.
        datetime_columns = [cid for cid in columns
                            if isinstance(self._type[cid], (pd.DateTime, pd.Time,))]
        def export_value(record, cid):
            value = record[cid]
            if cid in datetime_columns:
                result = value.export()
            else:
                result = value.value()
            return result
        data = [dict([(cid, export_value(record, cid)) for cid in columns])
                for record in self._records(req)]
        return wiking.Response(json.dumps(data), content_type='application/json')
                
    def action_print_field(self, req, record):
        field = self._view.field(req.param('field'))
        if not field:
            raise BadRequest()
        if not field.printable():
            raise AuthorizationError()
        exporter = lcg.pdf.PDFExporter(translations=wiking.cfg.translation_path)
        node = lcg.ContentNode(req.uri().encode('utf-8'),
                               title=self._print_field_title(req, record, field),
                               content=self._print_field_content(req, record, field))
        context = exporter.context(node, req.preferred_language())
        result = exporter.export(context)
        return wiking.Response(result, content_type='application/pdf',
                               filename=self._print_field_filename(req, record, field))
    
    def _action_subtitle(self, req, action, record=None):
        actions = sorted(self._actions(req, record), key=lambda a: len(a.kwargs()), reverse=True)
        for a in actions:
            if a.id() == action:
                kwargs = a.kwargs()
                if not kwargs or kwargs == dict([(key, req.param(key)) for key in kwargs.keys()]):
                    return a.title()
        map = {'insert': self._INSERT_LABEL,
               'update': self._UPDATE_LABEL,
               'delete': self._UPDATE_LABEL}
        return map.get(action)
        
    def _delete_prompt(self, req, record):
        return self._DELETE_PROMPT
    
    # ===== Feedback messages after successful data operations =====

    def _insert_msg(self, req, record):
        return self._INSERT_MSG
        
    def _update_msg(self, req, record):
        return self._UPDATE_MSG
        
    def _delete_msg(self, req, record):
        return self._DELETE_MSG
    
    # ===== Request redirection after successful data operations =====
    # HTTP redirect is used to prevent multiple submissions (see
    # http://en.wikipedia.org/wiki/Post/Redirect/Get).

    def _redirect_after_insert_uri(self, req, record, **kwargs):
        """Return the URI for HTTP redirection after succesful record insertion.

        The default redirection URI leads to the list action of the
        same module.
        
        @rtype: tuple of (basestring, dict)
        @return: Pair (uri, kwargs), where 'uri' is the base URI and
        'kwargs' is the dictionary of URI parameters to encoded into
        the final redirection URI.
    
        """
        return self._current_base_uri(req, record), kwargs
        
    def _redirect_after_update_uri(self, req, record, **kwargs):
        """Return the URI for HTTP redirection after succesful record insertion.

        The default redirection URI leads to the view action of the
        same record.

        @rtype: tuple of (basestring, dict)
        @return: Pair (uri, kwargs), where 'uri' is the base URI and
        'kwargs' is the dictionary of URI parameters to encoded into
        the final redirection URI.
    
        """
        if req.param('__invoked_from') == 'ListView':
            kwargs.update(form_name=self.name(), search=record[self._key].export())
            return self._current_base_uri(req, record), kwargs
        else:
            return self._current_record_uri(req, record), kwargs
        
    def _redirect_after_delete_uri(self, req, record, **kwargs):
        """Return the URI for HTTP redirection after succesful record insertion.

        The default redirection URI leads to the list action of the
        same module.

        @rtype: tuple of (basestring, dict)
        @return: Pair (uri, kwargs), where 'uri' is the base URI and
        'kwargs' is the dictionary of URI parameters to encoded into
        the final redirection URI.
    
        """
        return self._current_base_uri(req, record), kwargs
    
    def _redirect_after_insert(self, req, record):
        req.message(self._insert_msg(req, record))
        uri, kwargs = self._redirect_after_insert_uri(req, record)
        raise Redirect(uri, **kwargs)
        
    def _redirect_after_update(self, req, record):
        req.message(self._update_msg(req, record))
        uri, kwargs = self._redirect_after_update_uri(req, record)
        raise Redirect(uri, **kwargs)
        
    def _redirect_after_delete(self, req, record):
        req.message(self._delete_msg(req, record))
        uri, kwargs = self._redirect_after_delete_uri(req, record)
        raise Redirect(uri, **kwargs)

        
# ==============================================================================
# Module extensions 
# ==============================================================================


class RssModule(object):
    """Deprecated in favour od PytisRssModule defined below."""
    _RSS_TITLE_COLUMN = None
    _RSS_DESCR_COLUMN = None
    _RSS_DATE_COLUMN = None
    _RSS_AUTHOR_COLUMN = None
    _RSS_LIMIT = 10

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
        return req.uri() +'.'+ req.preferred_language() +'.rss'

    def _rss_info(self, req, lang=None):
        # Argument lang is unused (defined only for backwards compatibility).
        if self._RSS_TITLE_COLUMN is not None:
            # Translators: RSS channel is a computer idiom, see Wikipedia.
            return lcg.p(_("An RSS channel is available for this section:"), ' ',
                         lcg.link(self._rss_channel_uri(req),
                                  self._rss_channel_title(req)+' RSS',
                                  type='application/rss+xml'),
                         " (", lcg.link('_doc/wiking/user/rss', _("more about RSS")), ")")
        return None

    def _rss_title(self, req, record):
        return record[self._RSS_TITLE_COLUMN].export()
    
    def _rss_uri(self, req, record, lang=None):
        return self._record_uri(req, record, setlang=lang)

    def _rss_description(self, req, record):
        return None
        
    def _rss_structured_text_description(self, req, record):
        text = self._rss_column_description(req, record)
        parser = lcg.Parser()
        content = lcg.Container(parser.parse(text))
        node = lcg.ContentNode('', content=content)
        exporter = lcg.HtmlExporter()
        context = exporter.context(node, None)
        return node.content().export(context)
        
    def _rss_column_description(self, req, record):
        return record[self._RSS_DESCR_COLUMN].export()

    def _rss_date(self, req, record):
        if self._RSS_DATE_COLUMN:
            return record[self._RSS_DATE_COLUMN].value()
        else:
            return None
        
    def _rss_author(self, req, record):
        if self._RSS_AUTHOR_COLUMN:
            return record[self._RSS_AUTHOR_COLUMN].export()
        else:
            return wiking.cfg.webmaster_address
        
    def has_channel(self):
        # TODO: If the methods `_rss_channel_title()' and `_rss_channel_uri()' can be used
        # globally, this method can be replaced by a new method returning a `Channel' instance
        # directly.
        return self._RSS_TITLE_COLUMN is not None

    def action_rss(self, req, relation=None):
        import wiking
        if not self._RSS_TITLE_COLUMN:
            raise NotFound
        descr_column = self._RSS_DESCR_COLUMN
        if descr_column is None:
            get_description = self._rss_description
        elif self._view.field(descr_column).text_format() == pp.TextFormat.LCG:
            get_description = self._rss_structured_text_description
        else:
            get_description = self._rss_column_description
        lang = req.preferred_language()
        if relation:
            condition = self._binding_condition(*relation)
        else:
            condition = None
        base_uri = req.server_uri(current=True)
        buff = StringIO.StringIO()
        writer = RssWriter(buff)
        writer.start(base_uri,
                     req.localize(wiking.cfg.site_title +' - '+ self._rss_channel_title(req)),
                     description=req.localize(wiking.cfg.site_subtitle),
                     webmaster=wiking.cfg.webmaster_address,
                     generator='Wiking %s' % wiking.__version__,
                     language=lang)
        for record in self._records(req, condition=condition, lang=lang, limit=self._RSS_LIMIT):
            title = req.localize(self._rss_title(req, record))
            uri = self._rss_uri(req, record, lang=lang)
            if uri:
                uri = base_uri + uri
            description = get_description(req, record)
            if description:
                description = req.localize(description)
            date = self._rss_date(req, record)
            author = self._rss_author(req, record)
            writer.item(link=uri,
                        title=title,
                        description=description,
                        author=author,
                        pubdate=date)
        writer.finish()
        return wiking.Response(buff.getvalue(), content_type='application/xml')


class PytisRssModule(PytisModule):
    """Pytis module with RSS support."""

    def _channels(self, req):
        """Define available channels as a sequence of 'Channel' instances."""
        return ()
    
    def _action_args(self, req):
        # Resolves to 'channel' and 'lang' arguments if the URI corrensponds to
        # an existing RSS channel.  Otherwise postpones the resolution to the
        # parent class.
        if req.param('action') == 'rss':
            channel_id = req.param('channel')
            if not channel_id:
                raise BadRequest('Channel not specified.')
            for channel in self._channels(req):
                if channel.id() == channel_id:
                    lang = req.param('lang') or req.preferred_language(raise_error=False)
                    return dict(channel=channel, lang=lang)
            else:
                raise BadRequest('Unknown channel: %s' % channel_id)
        elif len(req.unresolved_path) == 1 and req.unresolved_path[0].endswith('.rss'):
            # Convert RSS path in form '<channel-id>.<lang>.rss' to args 'channel' and 'lang'.
            channel_id = req.unresolved_path[0][:-4]
            if len(channel_id) > 3 and channel_id[-3] == '.' and channel_id[-2:].isalpha():
                lang = str(channel_id[-2:])
                channel_id = channel_id[:-3]
            else:
                lang = req.preferred_language(raise_error=False)
            for channel in self._channels(req):
                if channel.id() == channel_id:
                    return dict(channel=channel, lang=lang)
            # If there is no matching channel, try to resolve the URI as a
            # record referer, since the referer actually may contain values
            # ending with '.rss'.  The developer must only care not to define a
            # channel with a possibly conflicting URI.  This is actually quite
            # a theoretical problem, since referer columns are often numeric.
        return super(PytisRssModule, self)._action_args(req)

    def _default_action(self, req, channel=None, lang=None, **kwargs):
        if channel is not None:
            return 'rss'
        else:
            return super(PytisRssModule, self)._default_action(req, **kwargs)

    def _rss_channel_uri(self, req, channel, uri):
        if uri is None:
            uri = self._current_base_uri(req)
        return uri +'/'+ channel.id() +'.rss'
        
    def _list_form_content(self, req, form, uri=None):
        content = super(PytisRssModule, self)._list_form_content(req, form, uri=uri)
        channel_links = [lcg.link(self._rss_channel_uri(req, ch, uri), ch.title(),
                                  descr=_('RSS channel "%s"', ch.title()),
                                  type='application/rss+xml')
                         for ch in self._channels(req)]
        if channel_links:
            # Translators: RSS channel is a computer idiom, see Wikipedia.  Don't translateg 'RSS'.
            doc_link = lcg.link('/_doc/wiking/user/rss', _("more about RSS"))
            if len(channel_links) == 1:
                rss_info = lcg.p(_("An RSS channel is available for this section:"), ' ',
                                 channel_links[0], " (", doc_link, ")")
            else:
                rss_info = lcg.p(_("RSS channels are available for this section"),
                                 " (", doc_link, "):", lcg.ul(channel_links))
            content.append(rss_info)
        return content
        
    def action_rss(self, req, channel, lang):
        # TODO: 'lang' may be None here.
        def localize(value):
            if value is None:
                return value
            else:
                return req.localize(value)
        def func(spec, default=None, raw=False):
            # Return a function of one argument (record) returning the channel
            # item value according to specification.
            if spec is None:
                if default:
                    return default
                else:
                    return lambda record: None
            elif isinstance(spec, collections.Callable):
                return lambda record: localize(spec(req, record))
            elif raw:
                return lambda record: localize(record[spec].value())
            # TODO: allow HTML formatting as in the old RssModule (hopefully more efficient).
            #elif ...:
            #    return lambda record: format(localize(record[spec].export()))
            else:
                return lambda record: localize(record[spec].export())
        import wiking
        spec = channel.content()
        # Create anonymous functions for each channel item field to save
        # repetitive specification processing in the cycle.
        base_uri = req.server_uri(current=True)
        link = func(spec.link(),
                    default=lambda r: base_uri + self._record_uri(req, r, setlang=lang))
        title = func(spec.title())
        descr = func(spec.descr())
        author = func(spec.author())
        date = func(spec.date(), raw=True)
        #
        buff = StringIO.StringIO()
        writer = RssWriter(buff)
        writer.start(base_uri,
                     localize(wiking.cfg.site_title +' - '+ channel.title()),
                     description=localize(channel.descr() or wiking.cfg.site_subtitle),
                     webmaster=channel.webmaster() or wiking.cfg.webmaster_address,
                     generator='Wiking %s' % wiking.__version__,
                     language=lang)
        for record in self._records(req, condition=channel.condition(), lang=lang,
                                    limit=channel.limit(), sorting=channel.sorting()):
            writer.item(link=link(record),
                        title=title(record),
                        description=descr(record),
                        author=author(record),
                        pubdate=date(record))
        writer.finish()
        return wiking.Response(buff.getvalue(), content_type='application/xml')
        
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
        for row in self._rows(req, condition=condition, lang=lang, limit=count):
            record.set_row(row)
            item = PanelItem([(f.id(), record[f.id()].export(),
                               f.id() == self._title_column and \
                               self._record_uri(req, record)) or None
                              for f in fields])
            items.append(item)
        if items:
            return items
        else:
            # Translators: Record as in `database record'.
            return (lcg.TextContent(_("No records.")),)


                
class Publishable(object):
    """Mix-in class for modules with publishable/unpublishable records."""
    
    # Translators: `Item' is intentionally general. Could be webpage, notice or something else.
    _MSG_PUBLISHED = _("The item was published.")
    _MSG_UNPUBLISHED = _("The item was unpublished.")

    def _change_published(row):
        data = row.data()
        key = (row[data.key()[0].id()],)
        values = data.make_row(published=not row['published'].value())
        data.update(key, values)
    _change_published = staticmethod(_change_published)
    
    # TODO: Using the _ACTIONS module attribute is DEPRECATED!  Use Spec.actions instead!
    _ACTIONS = (Action('publish', _("Publish"),
                       handler=lambda r: Publishable._change_published(r),
                       enabled=lambda r: not r['published'].value(),
                       descr=_("Make the item visible to website visitors")),
                Action('unpublish', _("Unpublish"),
                       handler=lambda r: Publishable._change_published(r),
                       enabled=lambda r: r['published'].value(),
                       descr=_("Make the item invisible to website visitors")),
                )

    # This is all quite ugly.  It would be much better to solve invoking pytis
    # actions in some more generic way, so that we don't need to implement an
    # action handler method for each pytis action.
    
    def action_publish(self, req, record, publish=True):
        try:
            if publish != record['published'].value():
                Publishable._change_published(record)
                record.reload()
        except pd.DBException as e:
            req.message(self._error_message(*self._analyze_exception(e)), type=req.ERROR)
        else:
            req.message(publish and self._MSG_PUBLISHED or self._MSG_UNPUBLISHED)
        raise Redirect(self._current_record_uri(req, record))

    def action_unpublish(self, req, record):
        return self.action_publish(req, record, publish=False)

