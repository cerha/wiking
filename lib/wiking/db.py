# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2017 OUI Technology Ltd.
# Copyright (C) 2019-2020, 2022, 2025 Tomáš Cerha <t.cerha@gmail.com>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import collections
import datetime
import io
import mimetypes
import re
import string
import weakref
import json
import urllib.parse

import pytis
import pytis.data as pd
import pytis.output
import pytis.presentation as pp
from pytis.presentation import Action, Field
import pytis.util
import pytis.web as pw
from pytis.web import UriType
import lcg
import wiking
from wiking import AuthorizationError, BadRequest, Forbidden, NotFound, Redirect

_ = lcg.TranslatableTextFactory('wiking')


class DBException(pd.DBException):
    """Exception to abort database operations within the application code.

    This exception is recognized within PytisModule._analyze_exception() and
    thus it can be thrown inside the database operation methods, such as
    PytisModule._insert(), PytisModule._update() or PytisModule._delete().  It
    will cause the operation to be aborted (with the whole transaction) and the
    user interface form is displayed again with given error message.  If a
    'column' is passed (string identifier), the error message will refer to a
    particular form field.  The effect is similar as if the error occured
    within the database itself.

    Unlike 'pd.DBException' which wraps an error within the database
    backend, 'wiking.DBException' is designed to be raised within the
    application code.

    """

    def __init__(self, message, column=None):
        self._message = message
        self._column = column
        super(DBException, self).__init__(message, None)

    def column(self):
        return self._column


class PytisModule(wiking.Module, wiking.ActionHandler):
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
    database exception string.  The regular expression may include a group
    named 'id'.  If present, the string matched by this group will be used as
    the name of database table/view column to which the error relates.  The
    matched string may also not be the column name directly, but the name of
    the DB constraint, which is mapped to the column id by
    '_UNIQUE_CONSTRAINT_FIELD_MAPPING' described below.

    The second element of the 2-tuple defines the custom error message
    displayed in the user interface when the exception occurs during a database
    operation.  This can be the error message directly, or a 2-tuple of
    field_id and error message.  In the second case, the field_id determines
    the form field which caused the error.  When field_id is not defined, the
    value of the group named 'id' in the regular expression (if present) is
    used for the same purpose.  When field_id is defined, it must be a valid
    identifier of a field present in the specification.  If field_id is not
    defined, it means that the error message is either not related to a
    particular form field or that it is not possible to determine which field
    it is.  The error message is either a (translatable) string or a function
    returning the string.  The function will be called with one argument -- the
    're.Match' instance corresponding to the regular expression match object.

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

    _SEQUENCE_FIELDS = ()
    _ARRAY_FIELDS = ()
    """Specification of array fields with automatically updated linking tables.

    Tuple of tuples where the inner tuples consist of (FIELD_ID, SPEC_NAME,
    LINKING_COLUMN, VALUE_COLUMN).  FIELD_ID is the id of the array field
    (type=pd.Array), SPEC_NAME is the name of the linking table
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
    _BROWSE_FORM_CLASS = pw.ListView
    _BROWSE_FORM_LIMITS = (50, 100, 200, 500)
    """Default value to pass to 'pytis.web.BrowseForm' 'limits' constructor argument."""
    _BROWSE_FORM_DEFAULT_LIMIT = 50
    """Default value to pass to 'pytis.web.BrowseForm' 'limit' constructor argument."""
    _BROWSE_FORM_SHOW_SUMMARY = True
    _ALLOW_QUERY_SEARCH = None
    """Deprecated, use _ALLOW_TEXT_SEARCH."""
    _ALLOW_TEXT_SEARCH = None
    """Default value to pass to 'pytis.web.BrowseForm' 'allow_text_search' constructor argument."""
    _PERMANENT_TEXT_SEARCH = False
    """Default value to pass to 'pytis.web.BrowseForm' 'permanent_text_search' constr. argument."""
    _TOP_ACTIONS = False
    "If true, action menu is put above BrowseForm/ListView forms."
    _BOTTOM_ACTIONS = True
    "If true, action menu is put below BrowseForm/ListView forms."
    _ROW_ACTIONS = False
    "If true, action menu created also for each table row in BrowseForm/ListView forms."
    _ASYNC_LOAD = False
    "If true, form data are loaded asynchronously through AJAX."
    _ROW_EXPANSION = False
    "If true, BrowseForm rows can be expanded (see '_expand_row()' method)."
    _ASYNC_ROW_EXPANSION = False
    "If true, (and _ROW_EXPANSION is True) rows are expanded asynchronously (on demand)."
    _INLINE_EDITABLE = False
    "If true, rows are editable inline."

    _SUBMIT_BUTTONS = {}
    "Dictionary of form buttons keyed by action name (see '_submit_buttons()' method)."

    class Record(pp.PresentedRow):
        """An abstraction of one record within the module's data object.

        The current request is stored within the record data to make it available within computer
        functions.

        Warning: Instances of this class should not persist across multiple requests!

        """

        def __init__(self, req, module, *args, **kwargs):
            self._req = req
            self._module = module
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
            self.reload(transaction=transaction)

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

        def display(self, key, **kwargs):
            return super(PytisModule.Record, self).display(key, **kwargs)

        def module(self):
            return self._module

    @classmethod
    def title(cls):
        return cls.Spec.title

    @classmethod
    def descr(cls):
        return cls.Spec.help

    # Instance methods

    def __init__(self, name):
        super(PytisModule, self).__init__(name)
        self._dbconnection = pytis.config.dbconnection.select(self.Spec.connection)
        resolver = wiking.cfg.resolver
        self._data_spec = resolver.get(name, 'data_spec')
        self._view = resolver.get(name, 'view_spec')
        self._exception_matchers = [(re.compile(regex), msg)
                                    for regex, msg in self._EXCEPTION_MATCHERS]
        self._db_function = {}
        self._title_column = self._TITLE_COLUMN or self._view.columns()[0]

    def __getattr__(self, name):
        if name not in ('_data', '_key', '_table', '_sorting', '_referer', '_links', '_type'):
            try:
                return super(PytisModule, self).__getattr__(name)
            except AttributeError:  # can be thrown in absence of __getattr__ itself!
                raise AttributeError(name)
        self._delayed_init()
        return getattr(self, name)

    def _delayed_init(self):
        self._data = self._data_spec.create(connection_data=self._dbconnection)
        self._key = key = self._data.key()[0].id()
        self._table = self._data.table(key)
        self._sorting = self._view.sorting()
        if self._sorting is None:
            self._sorting = ((key, pd.ASCENDENT),)
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
        self._type = dict([(k, record.type(k)) for k in record.keys()])
        self._links = {}
        self._filenames = {}
        for f in fields:
            if f.filename():
                self._filenames[f.id()] = f.filename()
            if f.codebook():
                cb_field = f
            elif isinstance(f.computer(), pp.CbComputer):
                cb_field = self._view.field(f.computer().field())
            else:
                continue
            column = cb_field.id()
            codebook = cb_field.codebook()
            enumerator = self._type[column].enumerator()
            if codebook and isinstance(enumerator, pd.DataEnumerator):
                referer = cb_field.inline_referer()
                value_column = enumerator.value_column()
                if not referer and wiking.module(codebook).referer() == value_column:
                    # If the inline_referer column was not specified explicitly
                    # and the module's referer column is the same as the
                    # codebook's value_column, we can use the codebook column
                    # as the inline referer (it is the same value).
                    referer = column
                if referer:
                    self._links[f.id()] = (codebook, referer)
                elif wiking.cfg.debug and f.label() != f.id():
                    # Don't warn on unlabeled fields - they typically don't figure in the UI.
                    wiking.debug("Referer undefined for %s.%s: %s" %
                                 (self.name(), f.id(), codebook))

    def _record(self, req, row, new=False, prefill=None, transaction=None):
        """Return the Record instance initialized by given data row."""
        return self.Record(req, self, self._view.fields(), self._data, row,
                           prefill=prefill, resolver=wiking.cfg.resolver, new=new,
                           transaction=transaction)

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

    def _analyze_exception(self, e):
        """Translate exception error string to a custom error message.

        Uses _EXCEPTION_MATCHERS to match error string reported by
        'e.exception()'.  Returns a pair of field_id and error message, where
        field_id determines the form field which caused the error (one of field
        identifiers defined by the specification).  If field_id is None, it
        means that the error message is either not related to a particular form
        field or that it is not possible to determine which field it is.

        """
        if isinstance(e, wiking.DBException):
            return (e.column(), e.message())
        elif e.exception():
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
                if callable(msg):
                    msg = msg(match)
                return (field_id, msg)
        return (None, _("Unable to perform a database operation:") + ' ' + error)

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
                title = self._TITLE_TEMPLATE.interpolate(lambda key:
                                                         pw.localizable_export(record[key]))
            else:
                title = (record.display(self._title_column) or
                         pw.localizable_export(record[self._title_column]))
        else:
            if self._HONOUR_SPEC_TITLE:
                title = self._view.title()
            else:
                title = None  # Current menu title will be substituted.
        if self._USE_BINDING_PARENT_TITLE:
            fw = self._binding_forward(req)
            if fw and fw.arg('title'):
                if title:
                    title = fw.arg('title') + ' :: ' + title
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
                extra_title = extra_title + '; ' + m[0]

            def interpolate(key, title=title, extra=extra_title):
                return dict(title=title, extra=extra)[key]
            title = lcg.TranslatableText('%(title)s (%(extra)s)').interpolate(interpolate)
        return title

    def _document(self, req, content, record=None, lang=None, **kwargs):
        title = self._document_title(req, record)
        if record and lang is None and self._LIST_BY_LANGUAGE:
            lang = str(record['lang'].value())
        return wiking.Document(title, content, lang=lang, **kwargs)

    def _default_actions_first(self, req, record):
        return (Action('insert', self._INSERT_LABEL,
                       icon='create-icon',
                       descr=self._INSERT_DESCR,
                       context=pp.ActionContext.GLOBAL,
                       enabled=self._insert_enabled),
                Action('export', self._EXPORT_LABEL,
                       descr=self._EXPORT_DESCR,
                       context=pp.ActionContext.GLOBAL),
                Action('view', self._VIEW_LABEL,
                       icon='view-icon',
                       descr=self._VIEW_DESCR),
                Action('update', self._UPDATE_LABEL,
                       icon='edit-icon',
                       descr=self._UPDATE_DESCR,
                       enabled=lambda r: self._update_enabled(r.req(), r)),
                )

    def _default_actions_last(self, req, record):
        return (Action('copy', self._COPY_LABEL,
                       icon='copy-icon',
                       descr=self._COPY_DESCR),
                Action('delete', self._DELETE_LABEL,
                       icon='remove-icon',
                       descr=self._DELETE_DESCR,
                       enabled=lambda r: self._delete_enabled(r.req(), r)),
                Action('list', self._LIST_LABEL,
                       icon='arrow-up-icon',
                       descr=self._LIST_DESCR),
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

    def _form_actions(self, req, record, form, exclude=()):
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
        if isinstance(form, pw.ListView) and self._view.list_layout():
            exclude += ('list', 'view',)
        elif isinstance(form, pw.BrowseForm):
            exclude += ('list',)
        elif isinstance(form, pw.ShowForm):
            exclude += ('view',)
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

    def _form_actions_argument(self, req, exclude=()):
        """Return a callable to be passed to 'actions' form constructor argument.

        This method returns a callable object to be passed to 'actions'
        argument of a pytis form constructor.  The callable is actually just a
        wrapper for the method '_form_actions()' which actually creates the
        list of form actions permitted to the current web user.  So use this
        method when you need to pass 'actions' to a form constructor, but
        override '_form_actions()' if you want to modify the list of actions
        available in a form.

        """
        return lambda form, record: self._form_actions(req, record, form, exclude=exclude)

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
        'pd.Array'), the return value must be a function of one
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
        def record_uri(**kwargs):
            return req.make_uri(uri.rstrip('/') + '/' + record[self._referer].export(), **kwargs)

        if cid is None:
            if uri:
                return record_uri(**kwargs)
            else:
                return None
        elif cid in self._links:
            modname, referer = self._links[cid]
            return wiking.module(modname).record_uri(req, record[referer].export())
        elif cid in self._filenames:
            return record_uri(action='download', field=cid)
        else:
            return None

    def _image_provider(self, req, uri, record, cid):
        return None

    def _tooltip_provider(self, req, uri, record, cid):
        return None

    def _print_uri_provider(self, req, uri, record, cid):
        if self._authorized(req, action='print_field', record=record):
            return self._link_provider(req, uri, record, None, action='print_field', field=cid)
        else:
            return None

    def _action_uri_provider(self, req, uri, record, form_cls, action):
        params = dict([(name, value is True and 'true' or value)
                       for name, value in action.kwargs().items()],
                      action=action.id(),
                      __invoked_from=form_cls.__name__)
        return req.make_uri(uri.rstrip('/') + '/' + record[self._referer].export(), **params)

    def _record_uri(self, req, record, *args, **kwargs):
        # Return the absolute URI of module's record if a direct mapping of the module exists.
        # Use the method '_current_record_uri()' to get URI in the context of the current request.
        return self.record_uri(req, record[self._referer].export(), *args, **kwargs)

    def _current_base_uri(self, req, record=None):
        # Return the module base URI in the context of the current request.
        uri = req.uri().rstrip('/')
        if record:
            # If the referer value is changed, the URI still contains the original value.
            referer = record.original_row()[self._referer].export()
            if uri.endswith('/' + referer):
                uri = uri[:-(len(referer) + 1)]
        return req.make_uri(uri)

    def _current_record_uri(self, req, record):
        # Return the URI of given record in the context of the current request.
        return (self._current_base_uri(req, record).rstrip('/') + '/' +
                record[self._referer].export())

    def _form(self, form_cls, req, record=None, action=None, new=False, prefill=None,
              binding_uri=None, hidden_fields=(), **kwargs):
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
        if issubclass(form_cls, pw.BrowseForm):
            kwargs = dict(self._list_form_kwargs(req, form_cls), **kwargs)
        form_record = self._record(req, record and record.row(), prefill=prefill, new=new)
        if action:
            hidden_fields += tuple(self._hidden_fields(req, action, form_record))
        for fid, data, linking_column, value_column in self._array_fields:
            rows = data.get_rows(condition=pd.EQ(linking_column, form_record[self._key]))
            values = tuple([r[value_column] for r in rows])
            form_record[fid] = pd.Value(form_record.type(fid), values)
        form = form_cls(self._view, req, self._uri_provider(req, form_cls, uri),
                        form_record, name=self.name(), hidden=hidden_fields, **kwargs)
        if binding_uri is None:
            # We use heading_info only for main form, not for binding side
            # forms.  That's why we test binding_uri here (not very nice...).
            heading_info = form.heading_info()
            if heading_info:
                # TODO: Am I the only one who thinks that passing the heading
                # info through req.message() is an ugly hack?  What about
                # creating a generic mechanism to pass internal processing data
                # through request instance (since it is available everywhere).
                # Some other hacks to achieve the same exist, such as passing
                # data through req.set_param().
                req.message(heading_info, req.HEADING)
        return form

    def _uri_provider(self, req, form_cls, uri):
        """Return the uri_provider function to pass the pytis form."""
        def uri_provider(record, kind, target):
            if record is None:
                assert kind == UriType.LINK
                result = uri
            elif kind == UriType.ACTION:
                result = self._action_uri_provider(req, uri, record, form_cls, target)
            else:
                if kind == UriType.LINK:
                    method = self._link_provider
                elif kind == UriType.IMAGE:
                    method = self._image_provider
                elif kind == UriType.TOOLTIP:
                    method = self._tooltip_provider
                elif kind == UriType.PRINT:
                    method = self._print_uri_provider
                result = method(req, uri, record, target)
            return result
        return uri_provider

    def _cell_editable(self, req, record, cid):
        """Retrun True if table cell of given column id in given record is editable inline."""
        return False

    def _expand_row(self, req, record, form):
        """Return lcg.Content for expansion of given record in BrowseForm.

        Row expansion is additional content which may be displayed within table
        form below the actual row.  This content is initially collapsed, but
        may be expanded by the user.  By default, table forms don't have
        expandable rows, but you may set the module's constants
        '_ROW_EXPANSION' (and optionally '_ASYNC_ROW_EXPANSION') to true to
        enable expansion for a particular Wiking module.  When enabled, this
        method is called to obtain the actual content displayed for a
        particular row.

        The default implementation of this method is to return a ShowForm
        similar as for the 'view' action, but its layout is controlled
        independently by the method '_expand_row_layout()' and additional
        content is controlled by '_expand_row_view_form_content()'.

        """
        view_form = self._form(pw.ShowForm, req, record=record,
                               layout=self._expand_row_layout(req, record),
                               actions=self._form_actions_argument(req, exclude=('list',)))
        return lcg.Container(self._expand_row_view_form_content(req, view_form, record))

    def _expand_row_layout(self, req, record):
        """Return layout of ShowForm displayed by default '_expand_row()' implementation."""
        return self._layout(req, 'view', record=record)

    def _expand_row_view_form_content(self, req, form, record):
        """As '_view_form_content()', but specific for row expansion (see '_expand_row()')."""
        return self._view_form_content(req, form, record)

    def _layout_instance(self, layout):
        if layout is None:
            layout = self._view.layout()
        if isinstance(layout, (tuple, list)):
            layout = pp.GroupSpec(layout, orientation=pp.Orientation.VERTICAL)
        return layout

    def _layout(self, req, action, record=None):
        """Return the form layout for given action and record.

        This method may be overriden to change form layout dynamically based on
        the combination of record, action and current request properties.  You
        may, for example, determine the layout according to field values or the
        currently logged in user's permissions.

        Arguments:
          req -- current request
          action -- name of the action as a string (determines also the form
            type)
          record -- the current record instance or None (for actions which
            don't work on an existing record, such as 'insert')

        The returned value may be a 'pytis.presentation.GroupSpec' instance or
        a sequence of field identifiers, nested 'pytis.presentation.GroupSpec'
        instances and other items acceptable by 'pytis.presentation.GroupSpec'
        constructor.

        The default implementation returns the statical layout defined in from
        specification.

        """
        return self._view.layout()

    def _hidden_fields(self, req, action, record=None):
        """Return the hidden form fields for given action and record.

        This method may be overriden to change hidden form fields dynamically
        based on the combination of record, action and current request
        properties.

        Arguments:
          req -- current request
          action -- name of the action as a string (determines also the form
            type)
          record -- the current form record as 'PytisModule.Record' instance

        Returns a list of pairs (field, value) as accepted by the argument
        'hidden' of 'pytis.web.Form' constructor.

        The default implementation returns the list [('action', action),
        ('submit', 'submit')] as these parameters are used by wiking itself.

        """
        return [('action', action),
                ('submit', 'submit')]

    def _submit_buttons(self, req, action, record=None):
        """Return the sequence of form submit buttons as pairs (NAME, LABEL).

        This method may be overriden to change form buttons dynamically based
        on the combination of record, action and current request properties.

        Arguments:
          req -- current request
          action -- name of the action as a string (determines also the form
            type)
          record -- the current record instance or None (for actions which
            don't work on an existing record, such as 'insert')

        The returned value is a sequence of pairs (NAME, LABEL), where LABEL is
        the button label and NAME is the name of the corresponding request
        parameter which has the value '1' if the form was submitted using given
        submit button.  If NAME is None, no request parameter is sent by the
        button.

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
        columns = self._view.columns()
        fw = self._binding_forward(req)
        if fw:
            binding_column = fw.arg('binding').binding_column()
            columns = [c for c in columns if c != binding_column]
        return columns

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

    def _action_args(self, req):
        """Resolve request path and/or parameters into action method arguments.

        Pytis module resolves to 'record' argument if the URI corresponds to a
        particular record through the referer column or to no arguments if the
        URI is just a base URI of the module (no subpath).  'NotFound' is
        raised when the URI refers to an inexistent record.

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
            row = self._get_row_by_key(req, req.param(self._key))
            base_uri = self._current_base_uri(req, self._record(req, row))
            if req.uri() == base_uri and not req.has_param('action'):
                # It might be better to do this redirection generally,
                # but we don't want to break the previous behavior (no
                # redirection was done) so we are careful to redirect
                # only in the intended cases (such as /users?uid=12).
                # We rely on the fact, that reference by key is rarely
                # used without explicit action (it is most often present
                # in form submission where action is always present).
                record = self._record(req, row)
                if ((self._referer == self._key or
                     # Prevent leaking referer values when referer != key
                     # because authorization has not yet been checked here.
                     self._authorized(req, action='view', record=record))):
                    raise Redirect(self._current_record_uri(req, record))
            return row
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
        """Return a 'pd.Row' instance corresponding to the refered record.

        The argument is a string representation of the module's referer column value (from URI
        path).  Raise 'NotFound' error if the refered row doesn't exist.

        """
        values = self._refered_row_values(req, value)
        row = self._data.get_row(arguments=self._arguments(req), **values)
        if row is None:
            raise NotFound()
        return row

    def _check_uid(self, req, record, column):
        user = req.user()
        return user and user.uid() == record[column].value() or False

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
        prefill in binding forwarded requests and default language if
        '_LIST_BY_LANGUAGE' is True.

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
        if self._LIST_BY_LANGUAGE and 'lang' not in prefill:
            lang = req.preferred_language(raise_error=False)
            if lang:
                prefill['lang'] = lang
        return prefill

    def _binding_condition(self, binding, record):
        """Return a binding condition as a 'pd.Operator' instance.

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
        """Return the filtering condition as a pd.Operator instance or None.

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

        Return None or a dictionary of 'pd.Value' instances.  The dictionary is passed as
        'arguments' to 'pd.DBData.select()' call.  Note that you must define the arguments
        in the specification, to get them used for the data object.

        """
        fw = self._binding_forward(req)
        if fw:
            binding = fw.arg('binding')
            record = fw.arg('record')
            return self._binding_arguments(binding, record)
        else:
            return None
        return None

    def _binding_arguments(self, binding, record):
        function = binding.arguments()
        if function:
            arguments = function(record)
        else:
            arguments = None
        return arguments

    def _make_condition(self, req, condition=None, lang=None):
        if self._LIST_BY_LANGUAGE:
            if lang is None:
                lang = req.preferred_language()
            lang_condition = pd.EQ('lang', pd.sval(lang))
        else:
            lang_condition = None
        return pd.AND(self._condition(req), condition, lang_condition)

    def _rows_generator(self, req, condition=None, lang=None, limit=None, offset=0, sorting=None):
        count = 0
        self._data.select(
            condition=self._make_condition(req, condition, lang=lang),
            arguments=self._arguments(req),
            sort=sorting or self._sorting,
        )
        if offset:
            self._data.skip(offset)
        while limit is None or count < limit:
            count += 1
            row = self._data.fetchone()
            if row is not None:
                yield row

    def _rows(self, req, condition=None, lang=None, limit=None, offset=0, sorting=None):
        return list(self._rows_generator(req, condition=condition, lang=lang,
                                         limit=limit, offset=offset, sorting=sorting))

    def _records(self, req, condition=None, lang=None, limit=None, offset=0, sorting=None):
        for row in self._rows_generator(req, condition=condition, lang=lang, limit=limit, offset=offset,
                                        sorting=sorting):
            self._record.set_row(row)
            yield self._record

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

    def _bindings(self, req, record):
        return self._view.bindings()

    def _binding_enabled(self, req, record, binding):
        """Return True if the binding is active.

        When True is returned, it indicates that the binding is available to
        the current user.  One of the possible consequences is that URIs
        related to this binding are served through '_handle_subpath()'.

        By default, this method returns the value corresponding to the
        'enabled' attribute of the binding specification.

        """
        enabled = binding.enabled()
        if callable(enabled):
            enabled = enabled(record)
        return bool(enabled)

    def _binding_visible(self, req, record, binding):
        """Return True if the binding is displayed as a side form.

        When True is returned, it indicates that the side form represented by
        this binding should be displayed (typically in the notebook created by
        '_related_content()').

        By default, this method returns the result of '_binding_enabled()'.
        You may override this method to control the side form presence
        separately from the functional aspects of binding availability.

        """
        return self._binding_enabled(req, record, binding)

    def _perform_binding_forward(self, req, record, binding):
        # TODO: respect the binding condition in the forwarded module.
        mod = wiking.module(binding.name())
        return req.forward(mod, binding=binding, record=record, forwarded_by=self,
                           title=self._document_title(req, record))

    def _handle_subpath(self, req, record):
        for binding in self._bindings(req, record):
            if req.unresolved_path[0] == binding.id():
                del req.unresolved_path[0]
                if self._binding_enabled(req, record, binding):
                    return self._perform_binding_forward(req, record, binding)
                else:
                    # The URI is valid, but not accessible for some reason.
                    raise Forbidden()
        raise NotFound()

    def _call_rows_db_function(self, name, *args, **kwargs):
        """Call database function NAME with given arguments and return the result.

        'args' are Python values wich will be automatically wrapped into
        'pd.Value' instances.  'kwargs' may contain 'transaction'
        argument to be passed to the database function.

        """
        transaction = kwargs.get('transaction')
        try:
            function, arg_spec = self._db_function[name]
        except KeyError:
            function = pd.DBFunctionDefault(name, self._dbconnection,
                                            connection_name=self.Spec.connection)
            arg_spec = self._DB_FUNCTIONS[name]
            self._db_function[name] = function, arg_spec
        assert len(args) == len(arg_spec), \
            "Wrong number of arguments for '%s': %r" % (name, args)
        arg_data = [(spec[0], pd.Value(spec[1], value)) for spec, value in zip(arg_spec, args)]
        return function.call(pd.Row(arg_data), transaction=transaction)

    def _call_db_function(self, name, *args, **kwargs):
        """Call database function NAME with given arguments and return the first result.

        If the result and its first row are non-empty, return the first value
        of the first row; otherwise return 'None'.

        'args' are Python values wich will be automatically wrapped into
        'pd.Value' instances.  'kwargs' may contain 'transaction'
        argument to be passed to the database function.

        """
        transaction = kwargs.get('transaction')
        row = self._call_rows_db_function(name, *args, transaction=transaction)[0]
        if row:
            result = row[0].value()
        else:
            result = None
        return result

    def _list_form_kwargs(self, req, form_cls):
        return dict(
            limits=self._BROWSE_FORM_LIMITS,
            limit=self._BROWSE_FORM_DEFAULT_LIMIT,
            allow_text_search=self._ALLOW_QUERY_SEARCH or self._ALLOW_TEXT_SEARCH,
            permanent_text_search=self._PERMANENT_TEXT_SEARCH,
            top_actions=self._TOP_ACTIONS,
            bottom_actions=self._BOTTOM_ACTIONS,
            row_actions=self._ROW_ACTIONS,
            async_load=self._ASYNC_LOAD,
            immediate_filters=wiking.cfg.immediate_filters,
            actions=(),  # Display no actions by default, rather than just spec actions.
            cell_editable=lambda *args: self._cell_editable(req, *args),
            expand_row=((lambda *args: self._expand_row(req, *args))
                        if self._ROW_EXPANSION else None),
            async_row_expansion=self._ASYNC_ROW_EXPANSION,
            inline_editable=self._INLINE_EDITABLE,
            show_summary=self._BROWSE_FORM_SHOW_SUMMARY,
            on_update_row=lambda record: self._do_update(req, record),
        )

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
        @rtype: str
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
        @rtype: str
        @return: File name sent within the 'Content-disposition' HTTP response
          header.

        The default file name is '<record id>-<field id>.pdf', where record id
        is the value of the referer field (see L{PytisModule._REFERER}).

        """
        return record[self._referer].export() + '-' + field.id() + '.pdf'

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
        storage = record.attachment_storage(field.id())
        if storage:
            resources = storage.resources()
        else:
            resources = ()
        return lcg.Container(content, resources=resources)

    def _transaction(self):
        """Create a new transaction and return it as 'pd.DBTransactionDefault' instance."""
        return pd.DBTransactionDefault(self._dbconnection, connection_name=self.Spec.connection)

    def _in_transaction(self, transaction, operation, *args, **kwargs):
        """Perform operation within given transaction and return the result.

        @type transaction: C{pd.DBTransactionDefault} or C{None}.
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
            except Exception:
                try:
                    transaction.rollback()
                except Exception:
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
                    except Exception:
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
        # debug(":::", success, result)
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
        return result

    def _do_update(self, req, record):
        # Returns None on success and tuple (field_id, error_message) on error.
        # This method is not intended to be overriden in application code.
        # Override the _update() method if needed.
        try:
            transaction = self._update_transaction(req, record)
            self._in_transaction(transaction, self._update, req, record, transaction)
            record.reload()
        except pd.DBException as e:
            return self._analyze_exception(e)
        else:
            return None

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

    def record_uri(self, req, referer, *args, **kwargs):
        """Return URI of module's record determined by given referer value.

        The referer value will be appended to the module's base URI if the
        module has a unique global URI (otherwise None is returned).  The
        argument 'referer' must be the exported string value of the module's
        referer column and the calling side is responsible for passing a valid
        value (corresponding to an existing referer column value).  Any
        additional positional and keyword arguments are passed to
        'req.make_uri()' which is used to encode the returned URI properly.

        """
        base_uri = self._base_uri(req)
        if base_uri:
            result = req.make_uri(base_uri + '/' + referer, *args, **kwargs)
        else:
            result = None
        return result

    def related(self, req, binding, record, uri):
        """Return the binding side form content for other module's main form record.

        The side form is typically a listing of records related to the main
        form record (1:N binding) or details (show form) of a single side form
        record referenced by the main form record (1:1 binding -- when 'single'
        is True).

        """
        binding_uri = uri + '/' + binding.id()
        if isinstance(binding, wiking.Binding) and binding.form_cls() is not None:
            form_cls = binding.form_cls()
            form_kwargs = binding.form_kwargs()
        else:
            form_cls = pw.ShowForm if binding.single() else self._BROWSE_FORM_CLASS
            form_kwargs = {}
        if binding.single():
            binding_column = binding.binding_column()
            enumerator = record.type(binding_column).enumerator()
            if enumerator is None:
                raise Exception("Column '%s' of '%s' is used as a binding column but "
                                "has no enumerator defined." % (binding_column, uri))
            row = self._data.get_row(condition=binding.condition(),
                                     **{enumerator.value_column(): record[binding_column].value()})
            my_record = self._record(req, row)
            content = self._form(form_cls, req, record=my_record, binding_uri=binding_uri,
                                 layout=self._layout(req, 'view', record=my_record),
                                 actions=(),
                                 # self._form_actions_argument(req), #TODO: doesn't work
                                 **form_kwargs)
            # This would add another level of binding subforms.  They don't
            # seem to work now and we most likely don't want them.  content =
            # self._view_form_content(req, form, my_record)
        else:
            conditions = [self._condition(req),
                          self._binding_condition(binding, record)]
            if self._LIST_BY_LANGUAGE:
                conditions.append(pd.EQ('lang', pd.sval(req.preferred_language(raise_error=False))))
            form = self._form(form_cls, req,
                              binding_uri=binding_uri,
                              condition=pd.AND(*conditions),
                              columns=[c for c in self._columns(req)
                                       if c != binding.binding_column()],
                              arguments=self._binding_arguments(binding, record),
                              profiles=self._profiles(req),
                              actions=self._form_actions_argument(req),
                              **form_kwargs)
            if form.is_ajax_request(req) and req.param('form_name') == self.name():
                raise wiking.Abort(wiking.ajax_response(req, form))
            content = self._list_form_content(req, form, uri=binding_uri)
        return lcg.Container(content)

    def pdf(self, template_id, record, lang, translations=(), parameters=None, condition=None,
            sorting=None):
        """Return PDF string made from given output specification.

        Arguments:

          template_id -- name of the output specification; string
          record -- current record or 'None'
          lang -- to be passed to PDF exporter
          translations -- to be passed to PDF exporter
          parameters -- dictionary of user output parameters
          condition -- condition to use when accessing whole data
          sorting -- sorting to use when accessing whole data; if 'None' then
            use default module sorting

        """
        resolver = wiking.WikingResolver()

        class ErrorResolver(pytis.output.Resolver):

            def get(self, module_name, spec_name, **kwargs):
                if spec_name == 'body':
                    raise Exception("Output specification not found", module_name)
                raise pytis.util.ResolverError()
        output_resolvers = (pytis.output.FileResolver(wiking.cfg.print_spec_dir),
                            ErrorResolver(),)
        name = self.name()
        prefix = name + '/'
        key = None if record is None else record.key()
        if sorting is None:
            sorting = self._sorting
        output_parameters = {(pytis.output.P_NAME): name,
                             (prefix + pytis.output.P_CONDITION): condition,
                             (prefix + pytis.output.P_SORTING): sorting,
                             (prefix + pytis.output.P_KEY): key,
                             (prefix + pytis.output.P_ROW): record,
                             (prefix + pytis.output.P_DATA): self._data,
                             (prefix + pytis.output.P_LANGUAGE): lang,
                             }
        if parameters:
            output_parameters.update(parameters)
        if not translations:
            translations = wiking.cfg.translation_path
        formatter = pytis.output.Formatter(resolver, output_resolvers, template_id,
                                           parameters=output_parameters, translations=translations,
                                           language=lang)
        return formatter.pdf()

    # ===== Action handlers =====

    def action_list(self, req, record=None):
        if record is not None:
            uri = self._current_base_uri(req, record)
            # Back action returning to some menu item?
            http_referer = req.header('Referer')
            if http_referer:
                path = urllib.parse.urlparse(http_referer).path[1:]
                menu = wiking.module.Application.menu(req)

                def find(menu, menu_path):
                    for m in menu:
                        if m.id() == path:
                            return menu_path
                        found = find(m.submenu(), menu_path + [m])
                        if found is not None:
                            return found
                    return None
                menu_path = find(menu, [])
                return_path = None
                while menu_path:
                    m = menu_path.pop()
                    if not m.hidden():
                        return_path = m.id()
                        break
                if return_path is not None:
                    uri = req.server_uri() + '/' + return_path
            raise Redirect(uri, action='list',
                           search=record[self._key].export(), form_name=self.name())
        # Here we need to get dirty accessing pytis forms's internal parameters to be
        # able to detect form ajax requests because we don't want to rediredt these requests
        # through _binding_parent_redirect() below.
        async_load = self._ASYNC_LOAD and req.param('_pytis_async_load_request') is not None
        if not async_load and req.param('_pytis_form_update_request') is None:
            # Don't display the listing alone, but display the original main form,
            # when this list is accessed through bindings as a related form.
            if req.param('form_name') == self.name():
                params = [(p, req.param(p)) for p in req.params() if p != 'action']
            else:
                params = ()
            self._binding_parent_redirect(req, **dict(params))
        # If this is not a binding forwarded request, display the listing.
        lang = req.preferred_language()
        condition = self._condition(req)
        if self._LIST_BY_LANGUAGE:
            condition = pd.AND(condition, pd.EQ('lang', pd.sval(lang)))
        form = self._form(self._BROWSE_FORM_CLASS, req,
                          columns=self._columns(req),
                          condition=condition,
                          arguments=self._arguments(req),
                          profiles=self._profiles(req),
                          actions=self._form_actions_argument(req),
                          )
        if form.is_ajax_request(req):
            return wiking.ajax_response(req, form)
        if async_load:
            return form
        else:
            content = self._list_form_content(req, form)
            return self._document(req, content,
                                  subtitle=self._action_subtitle(req, 'list'), lang=lang)

    def _binding_parent_uri(self, req):
        fw = self._binding_forward(req)
        if fw:
            path = fw.uri().lstrip('/').split('/')
            if path and path[-1] == fw.arg('binding').id():
                return '/' + '/'.join(path[:-1])
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
            if self._binding_visible(req, record, binding):
                content = self._binding_content(req, record, binding)
                if content:
                    section_id = 'binding-' + binding.id()
                    if req.param('set_binding_id') == binding.id():
                        active = section_id
                    if active is None and req.param('form_name') == binding.name():
                        # Form name may not be unique, so always give a higher precedence to
                        # binding_id if present...
                        active = section_id
                    sections.append(lcg.Section(title=binding.title(), descr=binding.descr(),
                                                id=section_id, in_toc=False, content=content))
        if sections:
            return [lcg.Notebook(sections, name='bindings-' + self.name(), active=active)]
        else:
            return []

    def _binding_content(self, req, record, binding):
        """Return the related (side form) content for given record and binding.

        Arguments:
          req -- current 'Request' instance.
          record -- the current record of the form as 'PytisModule.Record'.
          binding -- 'pytis.presentation.Binding()' instance (one of those
            returned by '_bindings()').

        The returned value must be a list of 'lcg.Content' instances.  It
        becomes part of '_related_content()' result.

        """
        mod = wiking.module(binding.name())
        uri = self._current_record_uri(req, record)
        content = mod.related(req, binding, record, uri=uri)
        if content:
            return [content]
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

    def _insert_form_content(self, req, form, record):
        """Return page content for 'insert' action form as a list of 'lcg.Content' instances.

        Arguments:
          req -- current 'Request' instance.
          form -- 'pytis.web.EditForm' instance.
          record -- the current record of the form as 'PytisModule.Record'.

        You may override this method to modify page content for the edit form
        in derived classes.  The default implementation returns just the form
        itself.

        """
        return [form]

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

    def _delete_form_content(self, req, form, record):
        """Return page content for 'delete' action form as a list of 'lcg.Content' instances.

        Arguments:
          req -- current 'Request' instance.
          form -- 'pytis.web.ShowForm' instance.
          record -- the current record of the form as 'PytisModule.Record'.

        You may override this method to modify page content for the deletion
        confirmation form in derived classes.  The default implementation
        returns just the form itself.

        """
        return [form]

    def action_view(self, req, record):
        form = self._form(pw.ShowForm, req, record=record,
                          layout=self._layout(req, 'view', record=record),
                          actions=self._form_actions_argument(req),
                          )
        content = self._view_form_content(req, form, record)
        return self._document(req, content, record)

    # ===== Action handlers which modify the database =====

    def action_insert(self, req, action='insert', _prefill=None):
        # The argument '_prefill' is just a hack used in wiking.cms.Users.action_reinsert()
        # and should not be used anywhere else.
        prefill = self._prefill(req)
        if req.param('copy') and not req.param('submit'):
            # Prefill form values from given copied record.
            # Exclude Password and Binary values, key column, computed
            # columns depending on key column and fields with 'nocopy'.
            # See action_copy() below...
            key = self._key
            row = self._get_row_by_key(req, req.param('copy'))
            layout = self._layout_instance(self._layout(req, action))
            for fid in layout.order():
                if ((fid != key and fid in row.keys() and
                     not isinstance(self._type[fid], (pd.Password, pd.Binary)))):
                    field = self._view.field(fid)
                    if not field.nocopy():
                        computer = field.computer()
                        if not computer or key not in computer.depends():
                            prefill[fid] = row[fid].value()
        if _prefill and not req.param('submit'):
            prefill.update(_prefill)
        form = self._form(pw.EditForm, req, new=True, action=action,
                          layout=self._layout(req, action),
                          prefill=prefill,
                          submit_buttons=self._submit_buttons(req, action),
                          show_cancel_button=True)
        if form.is_ajax_request(req):
            return wiking.ajax_response(req, form)
        if req.param('_cancel'):
            # Check this AFTER AJAX handling, because AJAX requests have
            # all submit button parameters set.
            raise Redirect(req.uri())
        if not req.param('submit'):
            # Prefill form values from request parameters.
            form.prefill(req)
        elif form.validate(req):
            record = form.row()
            try:
                transaction = self._insert_transaction(req, record)
                self._in_transaction(transaction, self._insert, req, record, transaction)
            except pd.DBException as e:
                field_id, error = self._analyze_exception(e)
                form.set_error(field_id, error)
            else:
                return self._redirect_after_insert(req, record)
        content = self._insert_form_content(req, form, form.row())
        return self._document(req, content, subtitle=self._action_subtitle(req, action))

    def action_copy(self, req, record):
        raise Redirect(self._current_base_uri(req, record),
                       action='insert', copy=record[self._key].export(),
                       **{p: req.param(p) for p in req.params() if p != 'action'})

    def action_update(self, req, record, action='update'):
        form = self._form(pw.EditForm, req, record=record, action=action,
                          layout=self._layout(req, action, record=record),
                          submit_buttons=self._submit_buttons(req, action, record),
                          show_cancel_button=True)
        if form.is_ajax_request(req):
            return wiking.ajax_response(req, form)
        if req.param('_cancel'):
            # Check this AFTER AJAX handling, because AJAX requests have
            # all submit button parameters set.
            if req.param('__invoked_from') in ('ListView', 'ItemizedView'):
                raise Redirect(self._current_base_uri(req, record),
                               form_name=self.name(), search=record[self._key].export())
            else:
                raise Redirect(req.uri())
        if req.param('submit') and form.validate(req):
            # The form works with another Record instance (see '_form()') and we
            # need to save the instance that passed validation.  Maybe that
            # creation of another instance in _form() is no longer relevant?
            record = form.row()
            error = self._do_update(req, record)
            if error:
                form.set_error(*error)
            else:
                return self._redirect_after_update(req, record)
        return self._document(req, self._update_form_content(req, form, record), record,
                              subtitle=self._action_subtitle(req, action, record=record))

    def action_delete(self, req, record, action='delete'):
        if req.param('submit') and not req.param('_cancel'):
            try:
                transaction = self._delete_transaction(req, record)
                self._in_transaction(transaction, self._delete, req, record, transaction)
            except pd.DBException as e:
                req.message(self._error_message(*self._analyze_exception(e)), req.ERROR)
            else:
                return self._redirect_after_delete(req, record)
        form = self._form(pw.DeletionForm, req, record=record, action=action,
                          layout=self._layout(req, action, record=record),
                          prompt=wiking.Message(self._delete_prompt(req, record)),
                          show_cancel_button=True)
        if form.is_ajax_request(req):
            return wiking.ajax_response(req, form)
        if req.param('_cancel'):
            if req.param('__invoked_from') in ('ListView', 'ItemizedView'):
                raise Redirect(self._current_base_uri(req, record),
                               form_name=self.name(), search=record[self._key].export())
            else:
                raise Redirect(req.uri())
        return self._document(req, self._delete_form_content(req, form, record), record,
                              subtitle=self._action_subtitle(req, action, record))

    def action_export(self, req):
        columns = self._exported_columns(req)
        export_kwargs = dict([(cid, isinstance(self._type[cid], pd.Float)
                               and dict(locale_format=False) or {}) for cid in columns])

        def generator(records):
            data = ''
            buffer_size = 1024 * 512
            for record in records:
                coldata = []
                for cid in columns:
                    value = req.localize(record.display(cid) or
                                         record[cid].export(**export_kwargs[cid]))
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

    def action_print_field(self, req, record):
        field = self._view.field(req.param('field'))
        if not field:
            raise BadRequest()
        if not field.printable():
            raise AuthorizationError()
        exporter = lcg.pdf.PDFExporter(translations=wiking.cfg.translation_path)
        node = lcg.ContentNode(req.uri(),
                               title=self._print_field_title(req, record, field),
                               content=self._print_field_content(req, record, field))
        context = exporter.context(node, req.preferred_language())
        result = exporter.export(context)
        return wiking.Response(result, content_type='application/pdf',
                               filename=self._print_field_filename(req, record, field))

    def action_download(self, req, record):
        field = self._view.field(req.param('field'))
        if not field:
            raise BadRequest()
        filename_spec = field.filename()
        if not filename_spec:
            raise AuthorizationError()
        if callable(filename_spec):
            filename = filename_spec(record)
        else:
            filename = record[filename_spec].value()
        content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        return wiking.Response(record[field.id()].value(),
                               content_type=content_type,
                               filename=filename,
                               inline=field.inline())

    def _action_subtitle(self, req, action, record=None):
        if action == 'list':
            # Don't use subtitle for 'list' by default (avoid "Back to List" subtitle).
            return None
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

        @rtype: tuple of (str, dict)
        @return: Pair (uri, kwargs), where 'uri' is the base URI and
        'kwargs' is the dictionary of URI parameters to encoded into
        the final redirection URI.

        """
        if req.param('__invoked_from') in ('ListView', 'ItemizedView'):
            kwargs.update(form_name=self.name(), search=record[self._key].export())
        return self._current_base_uri(req, record), kwargs

    def _redirect_after_update_uri(self, req, record, **kwargs):
        """Return the URI for HTTP redirection after succesful record insertion.

        The default redirection URI leads to the view action of the
        same record.

        @rtype: tuple of (str, dict)
        @return: Pair (uri, kwargs), where 'uri' is the base URI and
        'kwargs' is the dictionary of URI parameters to encoded into
        the final redirection URI.

        """
        if req.param('__invoked_from') in ('ListView', 'ItemizedView'):
            kwargs.update(form_name=self.name(), search=record[self._key].export())
            return self._current_base_uri(req, record), kwargs
        else:
            return self._current_record_uri(req, record), kwargs

    def _redirect_after_delete_uri(self, req, record, **kwargs):
        """Return the URI for HTTP redirection after succesful record insertion.

        The default redirection URI leads to the list action of the
        same module.

        @rtype: tuple of (str, dict)
        @return: Pair (uri, kwargs), where 'uri' is the base URI and
        'kwargs' is the dictionary of URI parameters to encoded into
        the final redirection URI.

        """
        return self._current_base_uri(req, record), kwargs

    def _redirect_after_insert(self, req, record):
        req.message(self._insert_msg(req, record), req.SUCCESS)
        uri, kwargs = self._redirect_after_insert_uri(req, record)
        raise Redirect(uri, **kwargs)

    def _redirect_after_update(self, req, record):
        req.message(self._update_msg(req, record), req.SUCCESS)
        uri, kwargs = self._redirect_after_update_uri(req, record)
        raise Redirect(uri, **kwargs)

    def _redirect_after_delete(self, req, record):
        req.message(self._delete_msg(req, record), req.SUCCESS)
        uri, kwargs = self._redirect_after_delete_uri(req, record)
        raise Redirect(uri, **kwargs)


# ==============================================================================
# Module extensions
# ==============================================================================

class APIProvider:
    """Mix in class adding REST API support to a 'PytisModule'.

    This is an experimental attempt to seamlessly integrate REST API support to
    Wiking modules derived from PytisModule.  The API and usage may change.

    """
    _API_LIST_MAX_LIMIT = 1000
    """Maximal allowed value of 'limit' passed to '_api_list()'.

    The query parameter 'limit' limits the number of records in '_api_list()'
    response.  If the query produces more result rows than 'limit', the
    response will be paged (the client will have to ask for the following pages
    in further requests).  This constant determines the maximal acceptable
    value of 'limit' passed by the client.  This value is also used when the
    query parameter limit has the special value 'max'.

    Limiting the maximal limit aims to be a very basic protection against
    malicious clients requesting gigantic amounts of data through the API.
    Such danger, however, very much depends on the potential number of records
    in the module's database view and their size, so this constant may be
    overriden in derived classes to make sense for given module.  Set to 'None'
    when listing all records at once doesn't pose a threat to the server.

    """
    _API_LIST_DEFAULT_LIMIT = 100
    """Default maximal number of result rows in '_api_list()' response when 'limit' not passed.

    See '_API_LIST_MAX_LIMIT' for more detailed explanation.

    """

    def __init__(self, *args, **kwargs):
        super(APIProvider, self).__init__(*args, **kwargs)

    def _api_serializer(self, column_id):
        ctype = self._type[column_id]
        if isinstance(ctype, pd.DateTime):
            return self._api_datetime_serializer
        elif isinstance(ctype, pd.Float):
            return self._api_float_serializer
        elif isinstance(ctype, pd.Array):
            return self._api_array_serializer
        elif isinstance(ctype, pw.Content):
            return self._api_content_serializer
        else:
            return self._api_default_serializer

    def _api_default_serializer(self, req, record, cid):
        return record[cid].value()

    def _api_datetime_serializer(self, req, record, cid):
        return record[cid].export()

    def _api_float_serializer(self, req, record, cid):
        # Avoid "TypeError: Decimal('0') is not JSON serializable"
        return float(record[cid].value())

    def _api_array_serializer(self, req, record, cid):
        return [v.value() for v in record[cid].value()]

    def _api_content_serializer(self, req, record, cid):
        return None  # TODO: export?

    def _api_serializers(self, columns):
        try:
            serializers = self._api_serializers_
        except AttributeError:
            # Inspect column types in advance as it is cheaper than calling
            # isinstance for all exported rows and columns.
            serializers = dict([(f.id(), self._api_serializer(f.id()))
                                for f in self._view.fields()])
            self._api_serializers_ = serializers
        return [(cid, serializers[cid]) for cid in columns if serializers[cid]]

    def _api_columns(self, req):
        """Return a list of columns present in '_api_list()' response.

        Override this metod to dynamically change the list of columns present
        in exported data.  The default implementation returns the same as
        '_columns()' but it also includes the key column.

        """
        columns = list(self._columns(req))
        if self._key not in columns:
            columns.insert(0, self._key)
        return columns

    def _api_list_condition(self, req):
        """Return the condition used for filtering rows in '_api_list()' output."""
        return None

    def _api_list_sorting(self, req):
        """Return the Pytis sorting specification for sorting '_api_list()' output."""
        return self._sorting

    def _api_list(self, req):
        serializers = self._api_serializers(self._api_columns(req))
        try:
            plimit = req.param('limit')
            if plimit is None:
                limit = self._API_LIST_DEFAULT_LIMIT
            elif plimit == 'max':
                limit = self._API_LIST_MAX_LIMIT
            else:
                limit = int(plimit)
            offset = int(req.param('offset', 0))
        except ValueError:
            raise wiking.BadRequest()
        if limit is not None and (limit <= 0 or limit > self._API_LIST_MAX_LIMIT) or offset < 0:
            raise wiking.BadRequest()
        records = self._records(req, condition=self._api_list_condition(req),
                                sorting=self._api_list_sorting(req), limit=limit, offset=offset)
        rows = [dict([(cid, serializer(req, record, cid)) for cid, serializer in serializers])
                for record in records]
        data = dict(rows=rows, total=len(records))
        return wiking.Response(json.dumps(data), content_type='application/json')

    def action_list(self, req, record=None):
        if record is None and req.is_api_request():
            return self._api_list(req)
        else:
            return super(APIProvider, self).action_list(req, record=record)

    def _api_view(self, req, record):
        serializers = self._api_serializers(self._api_columns(req))
        data = dict([(cid, serializer(req, record, cid)) for cid, serializer in serializers])
        return wiking.Response(json.dumps(data), content_type='application/json')

    def action_view(self, req, record):
        if req.is_api_request():
            return self._api_view(req, record)
        else:
            return super(APIProvider, self).action_view(req, record=record)


class RssModule:
    """Deprecated in favour of PytisRssModule defined below."""
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
        return find(wiking.module.Application.menu(req), req.path[0]) or self._view.title()

    def _rss_channel_uri(self, req):
        # TODO: This note applies to this method anf the above `_rss_channel_title()'.  They are
        # both limited to situations, where the RSS module is the final handler of the request.
        # This is the case for determination of the uri in `_rss_info()' and of the title in
        # `action_rss()'.  It is necessary to be able to determine the URI globally, but it is
        # currently not possible when a module is mapped more than once in CMS.
        return req.uri() + '.' + req.preferred_language() + '.rss'

    def _rss_info(self, req, lang=None):
        # Argument lang is unused (defined only for backwards compatibility).
        if self._RSS_TITLE_COLUMN is not None:
            # Translators: RSS channel is a computer idiom, see Wikipedia.
            return lcg.p(_("An RSS channel is available for this section:"), ' ',
                         lcg.link(self._rss_channel_uri(req),
                                  self._rss_channel_title(req) + ' RSS',
                                  type='application/rss+xml'),
                         " (", lcg.link('_doc/wiking/user/rss', _("more about RSS")), ")")
        return None

    def _rss_title(self, req, record):
        return record[self._RSS_TITLE_COLUMN].export()

    def _rss_uri(self, req, record, lang=None):
        return self._record_uri(req, record, setlang=lang)

    def _rss_description(self, req, record):
        return None

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
        else:
            def export(content):
                node = lcg.ContentNode('', content=content)
                exporter = lcg.HtmlExporter()
                context = exporter.context(node, None)
                return node.content(None).export(context)
            text_format = self._view.field(descr_column).text_format()
            if text_format == pp.TextFormat.LCG:
                parser = lcg.Parser()

                def get_description(req, record):
                    text = self._rss_column_description(req, record)
                    return export(lcg.Container(parser.parse(text)))
            elif text_format == pp.TextFormat.HTML:
                processor = lcg.HTMLProcessor()

                def get_description(req, record):
                    text = self._rss_column_description(req, record)
                    return export(processor.html2lcg(text))
            else:
                get_description = self._rss_column_description
        lang = req.preferred_language()
        if relation:
            condition = self._binding_condition(*relation)
        else:
            condition = None
        base_uri = req.server_uri(current=True)
        buff = io.StringIO()
        writer = wiking.RssWriter(buff)
        writer.start(base_uri,
                     req.localize(wiking.cfg.site_title + ' - ' + self._rss_channel_title(req)),
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
        return uri + '/' + channel.id() + '.rss'

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
            elif callable(spec):
                return lambda record: localize(spec(req, record))
            elif raw:
                return lambda record: localize(record[spec].value())
            # TODO: allow HTML formatting as in the old RssModule (hopefully more efficient).
            # elif ...:
            #     return lambda record: format(localize(record[spec].export()))
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
        buff = io.StringIO()
        writer = wiking.RssWriter(buff)
        writer.start(base_uri,
                     localize(wiking.cfg.site_title + ' - ' + channel.title()),
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


class CachedTables(PytisModule):
    """Management of information about cached database tables.

    It maintains information about versions of data tables.  It is supposed to
    be used only by 'CachingPytisModule'.  It provides the following methods to
    the module: 'reload_info()' to reload the information from the database;
    and 'current_version()' to get version of given database data.

    """
    class Spec(wiking.Specification):
        table = 'cached_tables'
        fields = (
            Field('object_schema'),
            Field('object_name'),
            Field('version'),
            Field('stamp'),
        )

    def __init__(self, *args, **kwargs):
        super(CachedTables, self).__init__(*args, **kwargs)

        class Key:
            pass
        self._no_transaction_key = Key()
        self._table_info = weakref.WeakKeyDictionary()
        self.reload_info(None)

    def reload_info(self, req, transaction=None):
        """Reload version information from the database.

        This is typically to be done at the beginning of each HTTP request to
        ensure some synchronization with other application processes, and then
        anytime some cached data changes in this application process.

        Arguments:

          transaction -- particular transaction for which the version
            information should  be reloaded

        Be careful about all the changes which may happen to the data.  Data
        may be changed in many situations, e.g. on direct database writes in a
        given transaction, on commits (the changes become visible outside the
        transaction) or perhaps indirectly by triggers or database functions.
        It is not important what particular has changed, just calling the
        reload on any relevant change is enough.

        """
        transaction_key = self._no_transaction_key if transaction is None else transaction
        info = self._table_info.get(transaction_key)
        if info is None:
            info = self._table_info[transaction_key] = {}
        else:
            info.clear()

        def add(row):
            key = row['object_schema'].value() + '.' + row['object_name'].value()
            info[key] = (row['version'].value(), row['stamp'].value(),)
        self._data.select_map(add, transaction=transaction)

    def current_stamp(self, schema, table, transaction=None):
        """Return current version and timestamp.

        Arguments:

          schema -- schema of the database object; string
          table -- name of the database object; string.  The database object
            may be a table or a view.
          transaction -- transaction for which the information should be
            reported or 'None'; note that different transactions may report
            different object stamps at the same moment.

        The return value is the pair (VERSION, TIMESTAMP,).  See
        'current_version()' for information about VERSION.  TIMESTAMP is a
        datetime instance containg the last modification time of the given
        version of the table.  Both VERSION and TIMESTAMP may be 'None' if no
        information is available about the table.

        """
        if transaction is None:
            transaction = self._no_transaction_key
        info = self._table_info.get(transaction)
        if info is None:
            info = self._table_info.get(self._no_transaction_key, {})
        key = schema + '.' + table
        stamp = info.get(key)
        if stamp is None:
            return None, None
        return stamp


class CachingPytisModule(PytisModule):
    """Pytis module with general caching ability.

    It supports caching of database data accross HTTP requests with automated
    refreshes from the database.  It should make data caching as simple as
    possible but it is still important to understand all the caching rules.

    Each subclass may use any number of caches.  Each cache has its name which
    must be present in '_cache_ids' attribute (tuple of strings).  The default
    cache name is stored in '_DEFAULT_CACHE_ID' attribute (string).  All the
    caches specified in '_cache_ids' are created as empty dictionaries
    automatically by default.  If you want to redefine the initialization
    process (it's rarely useful) you may do so by overriding '_init_cache()'
    and '_flush_cache()' methods.  Note the methods serve for cache
    initialization, not for loading the data.

    If cached data depends on objects other than the module table then the
    other objects must be specified in '_cache_dependencies' attribute (tuple
    of strings).  Each of the objects may be either a module name, starting
    with an uppercase letter, or a database object name, starting with a
    lowercase letter.

    Data can be loaded into the caches in two ways.  The first way is to load
    all the data at once by extending '_load_cache()' method.  It is important
    to store current database object versions at the same time; the default
    '_load_cache()' implementation does exactly that (and nothing more).  Often
    you do not want to load all data at once but only on demand.  In such a
    case you can redefine '_load_value()' to return the proper value for the
    given key.  Default '_load_value()' implementation returns
    'pytis.util.UNDEFINED' meaning the value is not available in the cache.  If
    you use more than one cache, you may define other value retrieval methods,
    more on that below.

    Each piece of data is retrieved by its key, it may be any object which can
    be used as Python dictionary key.  Data is retrieved using '_get_value()'
    method.  It takes the key as argument.  There are additional keyword
    arguments: current transaction (don't forget to use it when needed), cache
    name (if not the default), loader permitting to specify other data loading
    function than '_load_value()' which is very useful when using multiple
    caches, and default value to return in case of key error (preventing
    retrieval of any database values if the cache is up-to-date).  If the given
    value is not present the cache or the cache is dirty, the method tries to
    retrieve the value using 'loader' or (if no loader was specified)
    '_load_value()'.  If it returns 'pytis.util.UNDEFINED' then '_get_value()'
    tries to load all data using '_load_cache' and get the value again.  This
    way you usually don't have to load any data explicitly, it's just enough to
    redefine or extend one or more methods and using proper '_get_value()'
    arguments.  '_get_value()' provides complete cache handling and value
    retrieval implementation and shouldn't be redefined.

    The request object is intentionally unavailable within caching methods,
    because cached values should be request independent (they live across
    multiple requests and may be shared among multiple users.  Pass values
    obtained from the request explicitly as a part of the key when really
    desired (and think of the consequences).

    A given cache may be accessed directly using '_get_cache()' method.  But
    there is seldom need to handle caches this way outside the direct cache
    management methods.

    It's sometimes useful to check for data freshness, using '_check_cache()'
    method.  The method returns true if the cache is up-to-date, and false
    otherwise.  If the cache is dirty, it's flushed.  Additionally, if the
    optional argument 'load' is true then the dirty cache is also reloaded
    using '_load_cache()'.

    Enjoy your caching and be careful!

    """
    _cache_ids = ('default',)
    _DEFAULT_CACHE_ID = 'default'
    _cache_dependencies = ()

    def __init__(self, *args, **kwargs):
        super(CachingPytisModule, self).__init__(*args, **kwargs)
        self._init_cache()

    def _init_cache(self):
        self._caches = [(id_, {},) for id_ in self._cache_ids]
        self._cache_versions = {}

    def _flush_cache(self):
        self._init_cache()

    def _update_cache_versions(self, transaction=None):
        versions = self._cache_versions
        versions[None] = self._cached_table_version(transaction=transaction)
        for d in self._cache_dependencies:
            if self._database_dependency(d):
                versions[d] = self._cached_table_version(d, transaction=transaction)

    _cached_tables_module = None

    def _cached_table_stamp(self, table=None, transaction=None):
        cache_module = CachingPytisModule._cached_tables_module
        if cache_module is None:
            cache_module = CachingPytisModule._cached_tables_module = wiking.module.CachedTables
        if table is None:
            table = self._table
        return cache_module.current_stamp('public', table, transaction=transaction)

    def _cached_table_version(self, table=None, transaction=None):
        version = self._cached_table_stamp(table=table, transaction=transaction)[0]
        return version or 0

    def _cached_table_timestamp(self, table=None, transaction=None):
        return self._cached_table_stamp(table=table, transaction=transaction)[1]

    def cached_table_version(self, transaction=None):
        """Return the version number of the module's cached table data as int."""
        return self._cached_table_version(transaction=transaction)

    def cached_table_timestamp(self, transaction=None, utc=False):
        """Return the timestamp of the module's cached table data as datetime instance.

        Arguments:
          transaction -- the current DB transaction or None
          utc -- if True, the timestamp will be converted to a naive datetime
            instance in UTC timezone.  Otherwise the timestamp is a timezone
            aware instance.

        Returns None if no information is available about the table.

        """
        dt = self._cached_table_timestamp(transaction=transaction)
        if dt and utc:
            dt = datetime.datetime(dt.year, dt.month, dt.day,
                                   dt.hour, dt.minute, dt.second, dt.microsecond)
        return dt

    def _database_dependency(self, dependency):
        return dependency[0] in string.ascii_lowercase

    def _load_cache(self, transaction=None):
        self._update_cache_versions(transaction=transaction)

    def _load_value(self, key, transaction=None, **kwargs):
        return pytis.util.UNDEFINED

    def _get_value(self, key, transaction=None, cache_id=None, loader=None,
                   default=pytis.util.UNDEFINED, **kwargs):
        self._check_cache(transaction=transaction, load=True)
        if cache_id is None:
            cache_id = self._DEFAULT_CACHE_ID
        cache = self._get_cache(cache_id)
        value = cache.get(key, pytis.util.UNDEFINED)
        if value is pytis.util.UNDEFINED:
            if default is not pytis.util.UNDEFINED:
                return default
            if loader is None:
                loader = self._load_value
            value = loader(key, transaction=transaction, **kwargs)
            if value is pytis.util.UNDEFINED:
                self._flush_cache()
                self._load_cache(transaction=transaction)
                value = self._get_cache(cache_id)[key]
            else:
                cache[key] = value
        return value

    def _get_cache(self, cache_id):
        cache_cell = pytis.util.assoc(cache_id, self._caches)
        assert cache_cell is not None, ('Invalid cache name: ' + cache_id)
        return cache_cell[1]

    def _check_cache(self, load=False, transaction=None):
        cache_version = self._cached_table_version(transaction=transaction)
        db_version = self._cache_versions.get(None)
        up_to_date = (cache_version == db_version)
        if up_to_date:
            for d in self._cache_dependencies:
                if self._database_dependency(d):
                    if self._cache_versions.get(d) != self._cached_table_version(d):
                        up_to_date = False
                        break
                else:
                    if not wiking.module(d)._check_cache(transaction=transaction):
                        up_to_date = False
                        break
        if not up_to_date:
            self._flush_cache()
            if load:
                self._load_cache(transaction=transaction)
            else:
                self._update_cache_versions(transaction=transaction)
        return up_to_date


class CbCachingPytisModule(CachingPytisModule):
    """Pytis module caching codebook exports.

    It automatically caches fields whose ids are in '_cached_field_ids'
    attribute.  Technically any field displayed using 'Record.display()' method
    can be cached here, not just codebooks.

    """
    _cached_field_ids = ()
    _cache_ids = ('default', 'fields',)

    class Record(CachingPytisModule.Record):

        def _load_value(self, key, transaction=None, **kwargs):
            return CachingPytisModule.Record.display(self, key[-2])

        def display(self, key, **kwargs):
            module = self._module
            if key in module._cached_field_ids:
                cache_key = self.key() + (key, self[key].value(),)
                return module._get_value(cache_key, cache_id='fields',
                                         loader=self._load_value, transaction=self._transaction)
            return super(CbCachingPytisModule.Record, self).display(key, **kwargs)

    def __init__(self, *args, **kwargs):
        super(CbCachingPytisModule, self).__init__(*args, **kwargs)
        for f in self._view.fields():
            if f.id() in self._cached_field_ids:
                codebook = f.codebook()
                if codebook is not None:
                    # This may sometimes unnecessarily invalidate other caches.
                    self._cache_dependencies = self._cache_dependencies + (codebook,)
