# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2018 OUI Technology Ltd.
# Copyright (C) 2019-2022, 2024, 2025 Tomáš Cerha <t.cerha@gmail.com>
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

"""Definition of Wiking CMS modules.

The actual contents served by CMS modules, as well as its structure and application configuration,
is stored in database and can be managed using a web browser.

"""
import lcg
import pytis.data as pd
import pytis.presentation as pp
import pytis.web as pw
import wiking
import wiking.dbdefs
import wiking.cms

import collections
import datetime
import difflib
import io
import mimetypes
import os
import re
import string
import unicodedata
import operator
import json

import pytis.data
import pytis.util
from pytis.util import OPERATIONAL, Attribute, Structure, format_byte_size, log, find
from pytis.presentation import (
    Action, Binding, CodebookSpec, Field, FieldSet, HGroup, computer,
)
from wiking import (
    Forbidden, MenuItem, NotFound, Redirect, Response, Role, Specification
)

import urllib.parse
import urllib.error

_ = lcg.TranslatableTextFactory('wiking-cms')

CHOICE = pp.SelectionType.CHOICE
RADIO = pp.SelectionType.RADIO
ALPHANUMERIC = pp.TextFilter.ALPHANUMERIC
LOWER = pp.PostProcess.LOWER
ONCE = pp.Editable.ONCE
NEVER = pp.Editable.NEVER
ALWAYS = pp.Editable.ALWAYS
ASC = pd.ASCENDENT
DESC = pd.DESCENDANT
now = pytis.data.DateTime.datetime


def enum(seq):
    return pd.FixedEnumerator(seq)


class ContentField(Field):

    def __init__(self, name, label=None, descr=None, text_format=None, **kwargs):
        if text_format is None:
            editor = wiking.cms.cfg.content_editor
            if editor == 'plain':
                text_format = pp.TextFormat.LCG
            elif editor == 'html':
                text_format = pp.TextFormat.HTML
            else:
                raise Exception("Invalid value of 'wiking.cms.cfg.content_editor': %s" % editor)
        if text_format == pp.TextFormat.LCG:
            if descr:
                descr += ' '
            else:
                descr = ''
            uri = wiking.cms.cfg.formatting_manual_uri
            if uri:
                descr += (_("The content should be formatted as LCG structured text. "
                            "See the formatting manual:") + ' ' +
                          lcg.HtmlEscapedUnicode(
                              lcg.format('<a target="help" href="%(uri)s">%(label)s</a>',
                                         # The label can not be translated inside escaped unicode.
                                         uri=uri, label=uri),
                              escape=False))

        Field.__init__(self, name, label, descr=descr, text_format=text_format, **kwargs)


_parser = lcg.Parser()
_processor = lcg.HTMLProcessor()


def text2content(req, text):
    if text is not None:
        try:
            if wiking.cms.cfg.content_editor == 'plain':
                content = lcg.Container(_parser.parse(text))
            else:
                content = _processor.html2lcg(text)
        except Exception:
            content = [wiking.Message(_("Error processing document content."), kind='error')]
            error = wiking.InternalServerError()
            if wiking.cfg.debug:
                content.append(lcg.HtmlContent(error.traceback(detailed=True, format='html')))
            content = lcg.Container(content)
            wiking.module.Application.report_error(req, error)
    else:
        content = None
    return content


def _modtitle(name, default=None):
    """Return a localizable module title by module name."""
    if name is None:
        title = ''
    else:
        try:
            cls = wiking.cfg.resolver.wiking_module_cls(name)
        except Exception:
            title = default or lcg.concat(name, ' (', _("unknown"), ')')
        else:
            title = cls.title()
    return title


class WikingManagementInterface(wiking.Module, wiking.RequestHandler):
    """Wiking Management Interface.

    This module handles the WMI requestes by redirecting the request to the selected module.  The
    module name is part of the request URI.

    """
    _MENU = (
        # Translators: Heading and menu title.
        ('users', _("Users"),
         _("Manage user accounts, privileges and perform other user related tasks."),
         ['Users', 'ApplicationRoles', 'SessionHistory', 'LoginFailures',
          'EmailSpool', 'CryptoNames']),
        # Translators: Heading and menu title. Computer idiom meaning configuration of appearance
        # (colors, sizes, positions, graphical presentation...).
        ('style', _("Look & Feel"),
         _("Customize the appearance of your site."),
         ['StyleSheets', 'Themes']),
        # Translators: Heading and menu title for configuration.
        ('setup', _("Setup"),
         _("Edit global properties of your web site."),
         ['Config', 'Languages', 'Countries', 'Texts', 'Emails']),
    )

    def _handle(self, req):
        req.wmi = True  # Switch to WMI only after successful authorization!
        if not req.unresolved_path:
            raise Redirect('/_wmi/users/Users')
        for section, title, descr, modnames in self._MENU:
            if req.unresolved_path[0] == section:
                del req.unresolved_path[0]
                if not req.unresolved_path:
                    # Redirect to the first module of given section.
                    raise Redirect('/_wmi/' + section + '/' + modnames[0])
                elif req.unresolved_path[0] in modnames:
                    mod = wiking.module(req.unresolved_path[0])
                    del req.unresolved_path[0]
                    return req.forward(mod)
                else:
                    raise NotFound()
        raise NotFound()

    def _authorized(self, req):
        return req.check_roles(Roles.USER_ADMIN, Roles.SETTINGS_ADMIN, Roles.STYLE_ADMIN,
                               Roles.MAIL_ADMIN)

    def authorized(self, req):
        return self._authorized(req)

    def menu(self, req):
        variants = wiking.module.Application.languages()
        return [MenuItem('/_wmi/' + section, title, descr=descr,
                         foldable=True, variants=variants,
                         submenu=[MenuItem('/_wmi/' + section + '/' + m.name(),
                                           m.title(),
                                           descr=m.descr(),
                                           variants=variants,
                                           submenu=m.submenu(req),
                                           foldable=True)
                                  for m in [wiking.module(modname) for modname in modnames]])
                for section, title, descr, modnames in self._MENU]

    def module_uri(self, req, modname):
        """Return the WMI URI of given module or None if it is not available through WMI."""
        for section, title, descr, modnames in self._MENU:
            if modname in modnames:
                return '/_wmi/' + section + '/' + modname
        return None


class Roles(wiking.Roles):
    """Additional roles used by Wiking CMS and Wiking CMS applications.

    The class defines the following extensions:

     - New predefined user roles (see class constants).

     - It reads user roles from the database, thus enabling access to user
       defined application roles.  I{User defined roles} are additional roles
       defined by the administrator of the application.  They are not
       specifically supported in the application but they can be used for
       combining role based access rights or grouping users for messaging
       purposes etc.  User roles can be edited using L{ApplicationRoles}
       module.

     - User roles that are assigned to users explicitly by application
       administrator.  The roles defined by the base class L{wiking.Roles} are
       all special purpose roles.  Whether a user belongs to any such special
       role is determined only by application code and users can't be assigned
       to those roles explicitly.  In this subclass all predefined roles are
       explicitly assigned roles unless their documentation says otherwise;
       applications should follow this convention.  User defined roles are
       always explicitly assigned roles.

    """
    # Translators: Name of a special purpose user group.
    USER = Role('user', _("Authenticated approved user"))
    """Any authenticated user who is fully enabled in the application.
    I{Fully enabled} means the user registration process is fully completed and
    the user access to the application is not blocked.

    This is a special purpose role, you can't assign users to this role explicitly.
    """
    # Translators: Name of a special purpose user group.
    REGISTERED = Role('registered', _("Successfully registered user"))
    """Authenticated user who has at least completed registration succesfully.

    Users with this role must have at least successfully confirmed the registration activation
    code.  They may not yet be fully enabled in the application (approved by the administator).
    Approved accounts as well as blocked accounts also belong to this role.  This role may be used
    for very weak authorization checks.  It is stronger than L{wiking.Roles.AUTHENTICATED}
    (contains also users who registered, but didn't confirm the activation code yet), but weaker
    than L{wiking.cms.Roles.USER} (contains only users approved by the administrator).

    This is a special purpose role, you can't assign users to this role explicitly.
    """
    # Translators: Name of a predefined user group.
    USER_ADMIN = Role('cms-user-admin', _("User administrator"))
    """User administrator."""
    # Translators: Name of a predefined user group.
    CRYPTO_ADMIN = Role('cms-crypto-admin', _("Crypto administrator"))
    """Crypto stuff administrator."""
    # Translators: Name of a predefined user group.
    CONTENT_ADMIN = Role('cms-content-admin', _("Content administrator"))
    """Content administrator."""
    # Translators: Name of a predefined user group.
    SETTINGS_ADMIN = Role('cms-settings-admin', _("Settings administrator"))
    """Settings administrator."""
    # Translators: Name of a predefined user group.
    MAIL_ADMIN = Role('cms-mail-admin', _("Mail administrator"))
    """Bulk mailing user and administrator."""
    # Translators: Name of a predefined user group.
    STYLE_ADMIN = Role('cms-style-admin', _("Style administrator"))
    """Administrator of stylesheets, color themes and other web design related settings."""
    # Translators: Name of a predefined user group.
    ADMIN = Role('cms-admin', _("Administrator"))
    """Administrator containing all administration roles.
    This is a container role, including all the C{*_ADMIN} roles defined here.
    Applications may include their own administration roles into this role by
    adding corresponding entries to the database table C{role_sets}.
    """

    def __getitem__(self, role_id):
        try:
            return super(Roles, self).__getitem__(role_id)
        except KeyError:
            role = wiking.module.ApplicationRoles.get_role(role_id)
            if role is None:
                raise KeyError(role_id)
            return role

    def all_roles(self):
        standard_roles = super(Roles, self).all_roles()
        user_defined_roles = wiking.module.ApplicationRoles.user_defined_roles()
        return standard_roles + user_defined_roles


class CMSModule(wiking.PytisModule, wiking.RssModule):
    """Base class for all CMS modules."""

    _DB_FUNCTIONS = dict(wiking.PytisModule._DB_FUNCTIONS,
                         cms_crypto_lock_passwords=(('uid', pd.Integer(),),),
                         cms_crypto_unlock_passwords=(('uid', pd.Integer(),),
                                                      ('password', pd.String(),),
                                                      ('cookie', pd.String(),),),
                         cms_crypto_cook_passwords=(('uid', pd.Integer(),),
                                                    ('cookie', pd.String(),),),
                         )
    _PANEL_DEFAULT_COUNT = 3
    _PANEL_FIELDS = None
    _CRYPTO_COOKIE = 'wiking_cms_crypto'

    def _authorized(self, req, action, **kwargs):
        if hasattr(self, 'RIGHTS_' + action):
            # Maintain backwards compatibility with existing RIGHTS_* specifications.
            # When RIGHTS_* are removed everywhere (in boss), this can be removed.
            roles = getattr(self, 'RIGHTS_' + action)
            return req.check_roles(roles)
        elif action in ('view', 'list', 'rss', 'print_field'):
            return True
        elif action in ('insert', 'update', 'delete'):
            return req.check_roles(Roles.ADMIN)
        else:
            # Actions 'export' and 'copy' denied by default.  Enable explicitly when needed.
            return super(CMSModule, self)._authorized(req, action, **kwargs)

    def _embed_binding(self, modname):
        """Helper method to get a binding instance if given module is EmbeddableCMSModule."""
        try:
            cls = wiking.cfg.resolver.wiking_module_cls(modname)
        except Exception:
            cls = None
        if cls and issubclass(cls, EmbeddableCMSModule):
            binding = cls.binding()
        else:
            binding = None
        return binding

    def _check_crypto_passwords(self, req):
        crypto_names = self._data.crypto_names()
        if not crypto_names:
            return
        user = req.user()
        if user is None:
            return
        uid = user.uid()
        crypto_cookie = req.cookie(self._CRYPTO_COOKIE)
        if not crypto_cookie:
            crypto_cookie = self._generate_crypto_cookie()
            req.set_cookie(self._CRYPTO_COOKIE, crypto_cookie, secure=True)
        password = req.decryption_password()
        if password is not None:
            self._call_db_function('cms_crypto_unlock_passwords', uid, password, crypto_cookie)
        available_names = set([row[0].value()
                               for row in self._call_rows_db_function('cms_crypto_cook_passwords',
                                                                      uid, crypto_cookie)])
        unavailable_names = (set(crypto_names) - available_names -
                             set(wiking.cfg.ignored_crypto_names))
        if unavailable_names:
            raise wiking.Abort(wiking.Document(
                title=_("Attempting to Access Encrypted Area"),
                content=wiking.DecryptionDialog(unavailable_names.pop()),
            ))

    def _generate_crypto_cookie(self):
        return wiking.module.Session.new_session_key()

    def _panel_condition(self, req, relation):
        if relation:
            return self._binding_condition(*relation)
        else:
            return None

    def handle(self, req):
        self._check_crypto_passwords(req)
        return super(CMSModule, self).handle(req)

    def submenu(self, req):
        return []

    def _panel_rows(self, req, relation, lang, count):
        return self._data.get_rows(condition=self._panel_condition(req, relation),
                                   lang=lang, limit=count)

    def _export_panel_row(self, context, element, record, fields, row):
        g = context.generator()
        record.set_row(row)
        return g.div([self._export_panel_field(context, record, f) for f in fields], cls='item')

    def _export_panel_field(self, context, record, field):
        g = context.generator()
        req = context.req()
        content = record[field.id()].export()
        if field.text_format() != pp.TextFormat.PLAIN:
            content = text2content(req, content).export(context)
        else:
            uri = self._record_uri(req, record)
            if uri:
                content = g.a(content, href=uri)
        return g.span(content, cls="panel-field-" + field.id())

    def panelize(self, req, lang, count, relation=None):
        fields = [self._view.field(fid) for fid in self._PANEL_FIELDS or self._view.columns()]
        record = self._record(req, None)
        return ([lcg.HtmlContent(self._export_panel_row, record, fields, row)
                 for row in self._panel_rows(req, relation, lang,
                                             count or self._PANEL_DEFAULT_COUNT)]
                # Translators: Record as in `database record'.
                or [lcg.TextContent(_("No records."))])


class _ManagementModule(CMSModule):
    """Base class for modules used for site management."""

    _ADMIN_ROLES = ()

    def _authorized(self, req, action, **kwargs):
        if action in ('insert', 'update', 'delete'):
            return req.check_roles(*self._ADMIN_ROLES)
        else:
            return super(_ManagementModule, self)._authorized(req, action, **kwargs)

    def _list_form_content(self, req, form, uri=None):
        # Add short module help text above the list form.
        content = []
        description = self._view.help()
        if description:
            content = [lcg.p(description)]
        return content + super(CMSModule, self)._list_form_content(req, form, uri=uri)


class ContentManagementModule(_ManagementModule):
    """Base class for WMI modules managed by L{Roles.CONTENT_ADMIN}."""
    _ADMIN_ROLES = (Roles.CONTENT_ADMIN,)


class SettingsManagementModule(_ManagementModule):
    """Base class for WMI modules managed by L{Roles.SETTINGS_ADMIN}."""
    _ADMIN_ROLES = (Roles.SETTINGS_ADMIN,)


class UserManagementModule(_ManagementModule):
    """Base class for WMI modules managed by L{Roles.USER_ADMIN}."""
    _ADMIN_ROLES = (Roles.USER_ADMIN,)


class StyleManagementModule(_ManagementModule):
    """Base class for WMI modules managed by L{Roles.STYLE_ADMIN}."""
    _ADMIN_ROLES = (Roles.STYLE_ADMIN,)


class MailManagementModule(_ManagementModule):
    """Base class for WMI modules managed by L{Roles.MAIL_ADMIN}."""
    _ADMIN_ROLES = (Roles.MAIL_ADMIN,)


class Embeddable:
    """Mix-in class for modules which may be embedded into page content.

    Wiking CMS allows setting an extension module for each page in its global
    options.  The list of available modules always consists of all available
    modules derived from this class.  The derived classes must implement the
    'embed()' method to produce content, which is then embedded into the page
    content together with the page text.  This content normally appears below
    the page text, but if the page text contains the delimitter consisting of
    four or more equation signs on a separate line, the embedded content will
    be placed within the text in the place of this delimetter.

    Except for the actual embedded content, the derived classes may also define
    menu items to be automatically added into the main menu.  See the method
    'submenu()'.

    """

    def embed(self, req):
        """Return a list of content instances extending the page content."""
        pass

    def submenu(self, req):
        """Return a list of 'MenuItem' instances to insert into the main menu.

        The submenu will appear in the main menu under the item of a page which embeds the module.
        The items returned by this method will always be placed above any items defined within the
        CMS (items for descendant pages).

        """
        return []


class EmbeddableCMSModule(CMSModule, Embeddable):
    _EMBED_BINDING_COLUMN = None

    @staticmethod
    def _embed_binding_condition(row):
        return None

    @classmethod
    def binding(cls):
        """Return a Binding describing embedded module's relation to a page.

        We use a Binding instance for this purpose, because embedding data
        modules works exactly as pytis bindings.  The module's data are in a
        relation to the current page record and the 'Binding' specification has
        all the power to describe this relation.  In addition, we can use the
        existing PytisModule methods to render embedded forms inside the page
        and perform forwarding the requests from a page to the embedded module.

        """
        return Binding('data', cls.title(), cls.name(), cls._EMBED_BINDING_COLUMN,
                       condition=cls._embed_binding_condition)

    def embed(self, req):
        content = [self.related(req, self.binding(), req.page_record, req.uri())]
        rss_info = self._rss_info(req)
        if rss_info:
            content.append(rss_info)
        return content


class CMSExtension(wiking.Module, Embeddable, wiking.RequestHandler):
    """Generic base class for CMS extensions which consist of multiple (sub)modules.

    Many CMS extensions will use multiple modules to implement their functionality.  This class
    serves as a collection of a set of modules which is easilly embeddable into an existing site
    based on Wiking CMS.  A module derived from this class will serve as a front page for such an
    extension.  A page, which is set to use this module, will automatically have a submenu pointing
    to different submodules of the extension and the module will automatically redirect requests to
    them.

    To implement an extension, just derive a module from this class and define the '_MENU'
    attribute (and usually also '_TITLE' and '_DESCR').  Take care to only include modules derived
    from 'CMSExtensionModule' in the menu.

    """
    class MenuItem:
        """Specification of a menu item bound to a submodule of an extension."""

        def __init__(self, modname, id=None, submenu=(), enabled=None, **kwargs):
            """Arguments:

               modname -- string name of the submodule derived from 'CMSExtensionModule'

               id -- item identifier as a string.  The default value is determined by transforming
                 'modname' to lower case using dashes to separate camel case words.  This
                 identifier is used as part of the URI of the item.
               enabled -- function of one argument (the request object) determining whether the
                 item is enabled (visible) in given context.  Note that the URI of a disabled item
                 remains valid, so you still need to restrict access to the module by defining
                 access rights or any other means appropriate for the reason of unavalability of
                 the item.  This option only controls the presence of the item in the menu.  If
                 None (default), the item is always visible.
               submenu -- sequence of subordinate 'CMSExtension.MenuItem' instances.

            All other keyword arguments will be passed to 'MenuItem' constructor when converting
            the menu definition into a Wiking menu.

            """
            if __debug__:
                assert isinstance(modname, str), modname
                assert enabled is None or callable(enabled), enabled
                for item in submenu:
                    assert isinstance(item, CMSExtension.MenuItem), item
            self.modname = modname
            self.id = id or pytis.util.camel_case_to_lower(modname, '-')
            self.submenu = submenu
            self.enabled = enabled
            self.kwargs = kwargs

    _MENU = ()
    """Define the menu as a sequence of 'CMSExtension.MenuItem' instances."""

    def __init__(self, *args, **kwargs):
        super(CMSExtension, self).__init__(*args, **kwargs)
        self._mapping = {}
        self._rmapping = {}

        def init(items):
            for item in items:
                self._mapping[item.id] = item.modname
                self._rmapping[item.modname] = item.id
                wiking.module(item.modname).set_parent(self)
                init(item.submenu)
        init(self._MENU)

    def embed(self, req):
        uri = self.submenu(req)[0].id()
        raise Redirect(uri)

    def submenu(self, req):
        def menu_item(item):
            submodule = wiking.module(item.modname)
            identifier = self.submodule_uri(req, item.modname)[1:]
            submenu = [menu_item(i) for i in item.submenu
                       if i.enabled is None or i.enabled(req)] + submodule.submenu(req)
            kwargs = dict(dict(title=submodule.title(), descr=submodule.descr()), **item.kwargs)
            return MenuItem(identifier, submenu=submenu, **kwargs)
        return [menu_item(item) for item in self._MENU
                if item.enabled is None or item.enabled(req)]

    def handle(self, req):
        if not req.unresolved_path:
            uri = self.submenu(req)[0].id()
            raise Redirect(uri)
        try:
            modname = self._mapping[req.unresolved_path[0]]
        except KeyError:
            raise NotFound()
        del req.unresolved_path[0]
        return req.forward(wiking.module(modname))

    def submodule_uri(self, req, modname):
        return self._base_uri(req) + '/' + self._rmapping[modname]


class CMSExtensionMenuModule:
    """Mixin class for modules to be used in 'CMSExtension' menu."""

    def __init__(self, *args, **kwargs):
        self._parent = None
        super(CMSExtensionMenuModule, self).__init__(*args, **kwargs)

    def set_parent(self, parent):
        assert isinstance(parent, CMSExtension)
        self._parent = parent

    def parent(self):
        return self._parent

    def submenu(self, req):
        return []


class CMSExtensionModule(CMSModule, CMSExtensionMenuModule):
    """CMS module to be used within a 'CMSExtension'."""
    _HONOUR_SPEC_TITLE = True


class Config(SettingsManagementModule, wiking.CachingPytisModule):
    """Site specific configuration provider.

    This implementation stores the configuration variables as one row in a
    Pytis data object to allow their modification through WMI.

    """
    class Spec(Specification):

        class _Field(Field):

            def __init__(self, name, label=None, descr=None, transform_default=None, **kwargs):
                if hasattr(wiking.cfg, name):
                    option = wiking.cfg.option(name)
                elif hasattr(wiking.cms.cfg, name):
                    option = wiking.cms.cfg.option(name)
                else:
                    option = None
                    default = None
                if option:
                    default = option.value()
                    if label is None:
                        label = option.description()
                    if descr is None:
                        descr = option.documentation()
                    if transform_default is None:
                        if isinstance(option, wiking.cfg.BooleanOption):
                            def transform_default(x):
                                return x and _("checked") or _("unchecked")
                        else:
                            def transform_default(x):
                                return x is None and _("empty value") or repr(x)
                    descr += ' ' + _("The default setting is %s.", transform_default(default))
                self._cfg_option = option
                self._default_value = default
                Field.__init__(self, name, label, descr=descr, compact=True, **kwargs)

            def cfg_option(self):
                return self._cfg_option

            def default_value(self):
                return self._default_value
        # Translators: Website heading and menu item
        title = _("Basic Configuration")
        help = _("Edit site configuration.")
        table = 'cms_config'

        def fields(self):
            F = self._Field
            return (
                F('site'),
                F('theme_id', not_null=True, codebook='Themes', selection_type=CHOICE),
                F('site_title', width=24),
                F('site_subtitle', width=50),
                F('webmaster_address',
                  descr=_("This address is used as public contact address for your site. "
                          "It is displayed at the bottom of each page, in error messages, RSS "
                          "feeds and so on.  Please make sure that this address is valid "
                          "(e-mail sent to it is delivered to a responsible person).")),
                F('default_sender_address',
                  descr=_("E-mail messages sent by the system, such as automatic notifications, "
                          "password reminders, bug-reports etc. will use this sender address. "
                          "Please make sure that this address is valid, since users may reply "
                          "to such messages if they encounter problems.")),
                F('allow_registration'),
                F('force_https_login'),
                F('upload_limit',
                  transform_default=lambda n: repr(n) + ' (' + format_byte_size(n) + ')'),
            )
        layout = ('site_title', 'site_subtitle', 'webmaster_address', 'default_sender_address',
                  'allow_registration', 'force_https_login', 'upload_limit')
    _TITLE_TEMPLATE = _("Basic Configuration")

    def _resolve(self, req):
        # We always work with just one record.
        return self._data.get_row(site=wiking.cfg.server_hostname)

    def _default_action(self, req, **kwargs):
        return 'update'

    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid is None and not kwargs:
            return self._base_uri(req)
        return super(Config, self)._link_provider(req, uri, record, cid, **kwargs)

    def _redirect_after_update(self, req, record):
        req.message(self._update_msg(req, record), req.SUCCESS)
        raise Redirect(req.uri())

    def configure(self, req):
        """Update configuration acording to the current database contents.

        This method is called at the beginning of every request to synchronize
        the global configuration object with configuration values stored in the
        database (those values may be changed at any time by another process).

        This method is similar to 'Aplication.initialize()', but this method is
        called for every request, while 'Aplication.initialize()' is only
        called once on Application initialization.

        """
        if self._check_cache(load=True) and hasattr(self, '_theme_id'):
            return
        site = wiking.cfg.server_hostname
        row = self._data.get_row(site=site)
        if row is None:
            row = self._data.get_row(site='*')
            # This may happen in two cases: A) After DB initialization, as the
            # init.sql script is currently static and doesnt have the
            # information about real site name, B) After application of
            # upgrade.30.sql.
            if row:
                self._data.update((row['site'],), self._data.make_row(site=site))
        assert row is not None, site
        for field in self._view.fields():
            option = field.cfg_option()
            if option:
                value = row[field.id()].value()
                if value is None:
                    value = field.default_value()
                option.set_value(value)
        self._theme_id = row['theme_id'].value()

    def set_theme_id(self, req, theme_id):
        row = self._data.get_row(site=wiking.cfg.server_hostname)
        record = self._record(req, row)
        try:
            record.update(theme_id=theme_id)
        except pd.DBException as e:
            return self._error_message(*self._analyze_exception(e))
        else:
            self._theme_id = theme_id

    def theme_id(self):
        return self._theme_id

    def site_title(self, site):
        """Return site title for given 'site' if available.

        If it is unknown, return 'None'.

        Arguments:

          site -- site name; string

        """
        row = self._data.get_row(site=site)
        if row is None:
            title = None
        else:
            title = row['site_title'].value()
        if ((title is None and site == wiking.cfg.server_hostname or
             wiking.cfg.server_hostname is None)):
            title = wiking.cfg.site_title
        return title


class SiteSpecificContentModule(ContentManagementModule):

    def _refered_row_values(self, req, value):
        return dict(super(SiteSpecificContentModule, self)._refered_row_values(req, value),
                    site=wiking.cfg.server_hostname)

    def _condition(self, req):
        return pd.AND(super(SiteSpecificContentModule, self)._condition(req),
                      pd.EQ('site', pd.sval(wiking.cfg.server_hostname)))

    def _prefill(self, req):
        return dict(super(SiteSpecificContentModule, self)._prefill(req),
                    site=wiking.cfg.server_hostname)


class PageTitles(SiteSpecificContentModule):
    """Simplified version of the 'Pages' module for 'PageStructure' enumerator.

    This module is needed to prevent recursive enumerator definition in 'PageStructure'.

    """
    class Spec(Specification):
        table = 'cms_v_pages'
        fields = [Field(_f) for _f in ('page_key', 'page_id', 'site', 'lang', 'title')]


class PageStructure(SiteSpecificContentModule):
    """Provide a set of available URIs -- page identifiers bound to particular pages.

    This module contains a unique record for each page identifier, while
    'Pages' define the content for each page identifier in one particular
    language.  This module is needed for the reference integrity specification
    in 'Pages', 'Attachments' and other modules, where records are related to
    (language independent) page structure nodes.

    """
    class Spec(Specification):
        table = 'cms_pages'
        fields = (Field('page_id', not_null=True, enumerator='PageTitles'),
                  Field('site'),
                  Field('kind'),
                  Field('identifier'),
                  Field('modname'),
                  Field('parent'),
                  Field('ord'),
                  Field('menu_visibility'),
                  Field('tree_order'),
                  Field('owner'),
                  Field('read_role_id'),
                  Field('write_role_id'),
                  )
        sorting = (('tree_order', ASC), ('identifier', ASC),)

        def _display(self, row):
            indent = '   ' * (len(row['tree_order'].value().split('.')) - 2)
            return self._module._page_title(row, indent)

        def cb(self):
            return pp.CodebookSpec(display=self._display, prefer_display=True)

    @staticmethod
    def _page_title(row, indent=''):
        enumerator = row['page_id'].type().enumerator()
        condition = pd.AND(pd.EQ('page_id', row['page_id']),
                           pd.NE('title', pd.Value(pd.String(), None)))
        translations = dict([(r['lang'].value().lower(), indent + r['title'].value())
                             for r in enumerator.rows(condition=condition)])
        return lcg.SelfTranslatableText(indent + row['identifier'].value(),
                                        translations=translations)

    def page_position_selection(self, site, parent, page_id):
        """Return the available values for page order selection.

        Used for the 'ord' field of 'Pages'.  Arguments 'site', 'parent' and
        'page_id' represent the inner values of the corresponding fields of the
        'Pages' record for which the available order selection is requested.

        Returns a list of integers representing available positions in page
        order at the same level of page hierarchy.  Each integer is actually an
        instance of 'Order' class, which carries also the corresponding
        selection label as the value of the attributte 'label'.

        """
        class Order(int):

            def __new__(cls, order, label):
                return int.__new__(cls, order)

            def __init__(self, order, label):
                self.label = label
        result = []
        last_row = None
        for row in self._data.get_rows(site=site, parent=parent,
                                       condition=pd.NE('menu_visibility', pd.sval('never')),
                                       sorting=(('ord', ASC),)):
            if row['page_id'].value() != page_id:
                if not result:
                    # Translators: Label in page order selection.
                    label = _("First")
                else:
                    # Translators: Label in page order selection.  %s is replaced by a page
                    # title.  Selecting this item will put the current page in
                    # advance of the named page in the sequential order.
                    label = _('Prior to "%s"', self._page_title(row))
                if last_row and last_row['page_id'].value() == page_id:
                    order = last_row['ord'].value()
                else:
                    order = row['ord'].value()
                result.append(Order(order, label))
            last_row = row
        if result:
            if last_row and last_row['page_id'].value() == page_id:
                order = last_row['ord'].value()
            else:
                order = result[-1] + 1
            # Translators: Label in page order selection.
            result.append(Order(order, _("Last")))
        else:
            result.append(Order(1, _("First")))
        return result


class Panels(SiteSpecificContentModule, wiking.CachingPytisModule):
    """Manage a set of side panels.

    The panels are stored in a Pytis data object to allow their management through WMI.

    """
    class Spec(Specification):
        # Translators: Panels are small windows containing different things (such as recent news,
        # application specific controls, sponsorship reference etc.) displayed by the side of a
        # webpage.  To avoid confusion, we should avoid terms such as "windows", "frames"
        # etc. which all have their specific meaning in computer terminology.
        title = _("Panels")
        table = 'cms_v_panels'

        def fields(self):
            return (
                Field('panel_id', width=5, editable=NEVER),
                Field('site'),
                Field('lang', _("Language"), not_null=True, editable=ONCE,
                      codebook='Languages', selection_type=CHOICE, value_column='lang'),
                # Translators: Title in the meaning of a heading
                Field('title', _("Title"), width=30, not_null=True),
                # Translators: Stylesheet is a computer term (CSS), make sure you use the usual
                # translation.
                Field('identifier', _("Identifier"), width=30,
                      type=pd.RegexString(maxlen=32, not_null=False,
                                          regex='^[a-zA-Z][0-9a-zA-Z_-]*$'),
                      descr=_("Assign an optional unique panel identifier if you need to refer "
                              "to this panel in the stylesheet.")),
                # Translators: Order in the meaning of sequence. A noun, not verb.
                Field('ord', _("Order"), width=5,
                      descr=_("Number denoting the order of the panel on the page.")),
                # Translators: List items can be news, webpages, names of users.
                # Intentionally general.
                Field('page_id', _("List items"), width=5, not_null=False,
                      codebook='PageStructure', selection_type=CHOICE,
                      runtime_filter=computer(lambda r, site: pd.EQ('site', pd.sval(site))),
                      descr=_("The items of the extension module used by the selected page will be "
                              "shown by the panel.  Leave blank for a text content panel.")),
                Field('modname'),
                Field('read_role_id'),
                # Translators: Computer term for a part of application.
                Field('modtitle', _("Module"), virtual=True,
                      computer=computer(lambda r, modname: _modtitle(modname))),
                # Translators: As number of items in a table.
                Field('size', _("Items count"), width=5,
                      descr=_("Number of items from the selected module, which "
                              "will be shown by the panel.")),
                # Translators: Content of a page (text or something else)
                ContentField('content', _("Content"), height=10, width=80,
                             descr=_("Additional text content displayed on the panel.")),
                # Translators: Yes/no option whether the item is publicly
                # visible. Followed by a checkbox.
                Field('published', _("Published"), default=True,
                      descr=_("Controls whether the panel is actually displayed.")),
            )
        sorting = (('ord', ASC),)
        columns = ('title', 'identifier', 'ord', 'modtitle', 'size', 'published', 'content')
        layout = ('title', 'identifier', 'ord', 'page_id', 'size', 'content', 'published')
        actions = (
            Action('publish', _("Publish"), icon='circle-up-icon',
                   enabled=lambda r: not r['published'].value(),
                   descr=_("Make the panel visible in production mode")),
            Action('unpublish', _("Unpublish"), icon='undo-icon',
                   enabled=lambda r: r['published'].value(),
                   descr=_("Make the panel invisible in production mode")),
        )

    _LIST_BY_LANGUAGE = True
    _HONOUR_SPEC_TITLE = True

    def _authorized(self, req, action, **kwargs):
        if action in ('list', 'view'):
            return False
        elif action in ('publish', 'unpublish'):
            return req.check_roles(*self._ADMIN_ROLES)
        else:
            return super(Panels, self)._authorized(req, action, **kwargs)

    def _resolve(self, req):
        # Don't allow resolution by uri, panels have no URI so the
        # identification must be passed as a parameter.
        if req.has_param(self._key):
            return self._get_row_by_key(req, req.param(self._key))
        else:
            return None

    def _current_record_uri(self, req, record):
        return req.uri()

    def _hidden_fields(self, req, action, record=None):
        hidden_fields = super(Panels, self)._hidden_fields(req, action, record=record)
        hidden_fields.extend((('_manage_cms_panels', '1'),
                              ('panel_id', record['panel_id'].export())))
        return hidden_fields

    def _load_value(self, key, transaction=None):
        lang, preview_mode = key
        if preview_mode:
            restriction = {}
        else:
            restriction = {'published': True}
        return self._data.get_rows(site=wiking.cfg.server_hostname, lang=lang,
                                   sorting=self._sorting, **restriction)

    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid is None and not kwargs:
            return '/'
        return super(Panels, self)._link_provider(req, uri, record, cid, **kwargs)

    def panels(self, req, lang):
        panels = []
        roles = wiking.module.Users.Roles()
        for row in self._get_value((lang, wiking.module.Application.preview_mode(req))):
            role_id = row['read_role_id'].value()
            if role_id is not None and not req.check_roles(roles[role_id]):
                continue
            panel_id = row['identifier'].value() or str(row['panel_id'].value())
            title = row['title'].value()
            content = ()
            channel = None
            modname = row['modname'].value()
            if modname:
                mod = wiking.module(modname)
                binding = self._embed_binding(modname)
                content = tuple(mod.panelize(req, lang, row['size'].value(),
                                             relation=binding and (binding, row)))
                if mod.has_channel():
                    channel = '/' + '.'.join((row['identifier'].value(), lang, 'rss'))
            if row['content'].value():
                content += (text2content(req, row['content'].value()),)
            content = lcg.Container(content)
            if req.check_roles(Roles.CONTENT_ADMIN):
                record = self._record(req, row)

                def is_enabled(action):
                    enabled = action.enabled()
                    if callable(enabled):
                        enabled = enabled(record)
                    return enabled
                items = [lcg.PopupMenuItem(action.title(),
                                           tooltip=action.descr(),
                                           enabled=is_enabled(action),
                                           icon=action.icon(),
                                           uri=req.make_uri('/', _manage_cms_panels='1',
                                                            action=action.id(),
                                                            panel_id=row['panel_id'].export()))
                         for action in self._form_actions(req, record, None)]
                titlebar_content = lcg.PopupMenuCtrl(_("Popup the menu of actions for this panel"),
                                                     items)
            else:
                titlebar_content = None
            panels.append(wiking.Panel(panel_id, title, content,
                                       titlebar_content=titlebar_content, channel=channel))
        return panels

    def action_publish(self, req, record, publish=True):
        try:
            record.update(published=publish)
        except pd.DBException as e:
            req.message(self._error_message(*self._analyze_exception(e)), req.ERROR)
        else:
            if publish:
                msg = _("The panel was published.")
            else:
                msg = _("The panel was unpublished.")
            req.message(msg, req.SUCCESS)
        raise Redirect(req.uri())

    def action_unpublish(self, req, record):
        return self.action_publish(req, record, publish=False)


class Languages(SettingsManagementModule, wiking.CachingPytisModule):
    """List all languages available for given site.

    This implementation stores the list of available languages in a Pytis data
    object to allow their modification through WMI.

    """
    class Spec(Specification):
        # Translators: Heading and menu item for language configuration section.
        title = _("Languages")
        help = _("Manage available languages.")
        table = 'cms_languages'
        fields = (
            Field('lang_id'),
            # Translators: Language code, e.g. 'cs', 'sk' etc.
            Field('lang', _("Code"), width=2, column_width=6,
                  descr=_("Lower case alphanumeric ISO 639-1 two letter language code."),
                  filter=ALPHANUMERIC, post_process=LOWER, fixed=True),
            # Translators: Language name: e.g. Czech, Slovak etc.
            Field('name', _("Name"), virtual=True,
                  computer=computer(lambda r, lang: lcg.language_name(lang))),
        )
        sorting = (('lang', ASC),)
        cb = CodebookSpec(display=lcg.language_name, prefer_display=True)
        layout = ('lang',)
        columns = ('lang', 'name')
    _REFERER = 'lang'
    # Translators: Do not translate this.
    _TITLE_TEMPLATE = _('%(name)s')

    def languages(self):
        return self._get_value(None, loader=self._load_languages)

    def _load_languages(self, key, transaction=None):
        return [str(row['lang'].value()) for row in self._data.get_rows()]


class Countries(SettingsManagementModule):
    """Codebook of countries.

    The codebook of countries is currently not used by Wiking CMS itself, but
    may be practical for extension applications.  It is also planned to make
    use of it in Wiking CMS for definition of applicable locales.  Locales are
    combinations of language/country, such as en-US, en-GB, de-DE, de-AT.
    Wiking and Wiking CMS currently ignore countries and only care about
    languages.  This is quite restricting when it is necessary to care about
    country specifics.

    """
    class Spec(Specification):
        # Translators: Heading and menu item for language configuration section.
        title = _("Countries")
        table = 'cms_countries'
        fields = (
            Field('country_id'),
            # Translators: Language code, e.g. 'cs', 'sk' etc.
            Field('country', _("Code"), width=2, column_width=6,
                  descr=_("Upper case alphanumeric ISO 3166-1 two letter country code."),
                  filter=ALPHANUMERIC, post_process=LOWER, fixed=True),
            # Translators: Language name: e.g. Czech, Slovak etc.
            Field('name', _("Name"), virtual=True,
                  computer=computer(lambda r, country: lcg.country_name(country))),
        )
        sorting = (('country', ASC),)
        cb = CodebookSpec(display=lcg.country_name, prefer_display=True)
        layout = ('country',)
        columns = ('country', 'name')
    _REFERER = 'country'
    # Translators: Do not translate this.
    _TITLE_TEMPLATE = _('%(name)s')


class Themes(StyleManagementModule, wiking.CachingPytisModule):

    class Spec(Specification):

        class _Field(Field):

            def __init__(self, id, label, descr=None):
                Field.__init__(self, id, label, descr=descr, type=pd.Color(),
                               dbcolumn=id.replace('-', '_'))
        _FIELDS = (
            (_("Normal page colors"),
             (_Field('foreground', _("Text")),
              # Translators: Website background (e.g. color)
              _Field('background', _("Background")),
              _Field('highlight-bg', _("Highlight background"),
                     descr=_("Background highlighting may be used for emphasizing the current "
                             "language, etc.")),
              _Field('link', _("Link")),
              _Field('link-visited', _("Visited link")),
              # Translators: Computer terminology. Term for how a website hyperlink changes when
              # you move mouse cursor over it.
              _Field('link-hover', _("Hover link"),
                     descr=_("Used for changing the link color when the user moves the mouse "
                             "pointer over it.")),
              _Field('border', _("Borders")))),
            (_("Heading colors"),
             (_Field('heading-fg', _("Text")),
              _Field('heading-bg', _("Background")),
              _Field('heading-line', _("Underline"),
                     descr=_("Heading colors are used for section headings, panel headings and "
                             "other heading-like elements.  Depending on style sheets, some "
                             "heading types may be distinguished by a different background color "
                             "and others may be just underlined.")))),
            (_("Frames"),
             (_Field('frame-fg', _("Text")),
              _Field('frame-bg', _("Background")),
              _Field('frame-border', _("Border"),
                     descr=_("Frames are generally used for distinguishing separate areas of the "
                             "page, such as forms, tables of contents, etc.  The usage may vary "
                             "by stylesheet.")))),
            (_("Page surrounding colors"),
             (_Field('top-fg', _("Text")),
              _Field('top-bg', _("Background")),
              _Field('top-border', _("Border"),
                     descr=_("What is 'page surrounding' depends from the stylesheet. "
                             "In general it is the part of the page, which does not include "
                             "the actual contents. Most often it is the page header and "
                             "footer which usually remain unchanged throughout the whole "
                             "website.")))),
            (_("Error messages"),
             (_Field('error-fg', _("Text")),
              _Field('error-bg', _("Background")),
              _Field('error-border', _("Border")))),
            (_("Informational messages"),
             (_Field('message-fg', _("Text")),
              _Field('message-bg', _("Background")),
              _Field('message-border', _("Border")))),
            (_("Record meta data"),
             (_Field('meta-fg', _("Text")),
              _Field('meta-bg', _("Background"),
                     descr=_("These colors are used for additional items printed listings, such "
                             "as date and author of a message in news, etc.")))),
            (_("Misc"),
             (_Field('table-cell', _("Table cell")),
              _Field('table-cell2', _("Shaded table cell")),
              _Field('help', _("Form help text")),
              _Field('inactive-folder', _("Inactive folder")))),
        )
        # Translators: "Color Themes" is computer terminology.  Predefined sets of colors to be
        # used for changing the visual appearance of a web page/application.  Similar to color
        # styles.
        title = _("Color Themes")
        # Translators: Describes more precisely the meaing of "Color Themes" section.
        help = _("Manage available color themes.")
        table = 'cms_themes'

        def fields(self):
            fields = [Field('theme_id'),
                      Field('name', _("Name"), nocopy=True),
                      Field('active', virtual=True, type=pd.Boolean,
                            computer=computer(self._is_active)),
                      Field('title', virtual=True, computer=computer(self._title)),
                      ]
            for label, group in self._FIELDS:
                fields.extend(group)
            return fields

        def _is_active(self, row, theme_id):
            return wiking.module.Config.theme_id() == theme_id

        def _title(self, row, name, active):
            return name + (active and ' (' + _("active") + ')' or '')

        def _preview(self, record):
            # TODO: It would be better to have a special theme demo page, which
            # would display all themable constructs.
            # TODO: Disable user interaction within the iframe.
            req = record.req()
            # We can't rely on redirection here as it would not pass the
            # preview_theme argument.
            menu = [item for item in wiking.module.Pages.menu(req) if not item.hidden()]
            if menu:
                uri = menu[0].id()
            else:
                uri = req.module_uri('Users')
            uri += '?preview_theme=%d' % record['theme_id'].value()
            return wiking.IFrame(uri, width=800, height=220)

        def layout(self):
            return ('name',) + tuple([FieldSet(label, [f.id() for f in fields])
                                      for label, fields in self._FIELDS])

        def list_layout(self):
            return pp.ListLayout('title', content=self._preview)
        cb = CodebookSpec(display='name', prefer_display=True)
        actions = (
            # Translators: Button label
            Action('activate', _("Activate"), icon='circle-up-icon',
                   descr=_("Activate this color theme"),
                   enabled=lambda r: not r['active'].value()),
            # Translators: Button label
            Action('activate', _("Activate default"), icon='circle-up-icon',
                   context=pp.ActionContext.GLOBAL,
                   descr=_("Activate the default color theme"),
                   enabled=lambda r: wiking.module.Config.theme_id() is not None),
        )

    _ROW_ACTIONS = True

    def _authorized(self, req, action, **kwargs):
        if action in ('copy', 'activate'):
            return req.check_roles(*self._ADMIN_ROLES)
        else:
            return super(Themes, self)._authorized(req, action, **kwargs)

    def theme(self, theme_id):
        return self._get_value(theme_id)

    def _load_value(self, key, transaction=None):
        row = self._data.get_row(theme_id=key, transaction=transaction)
        colors = dict([(c.id(), row[c.id()].value())
                       for c in wiking.Theme.COLORS if row[c.id()].value() is not None])
        return wiking.Theme(colors)

    def action_activate(self, req, record=None):
        if record:
            theme_id = record['theme_id'].value()
            name = record['name'].value()
        else:
            theme_id = None
            name = _("Default")
        err = wiking.module.Config.set_theme_id(req, theme_id)
        if err is None:
            req.message(_("The color theme \"%s\" has been activated.", name), req.SUCCESS)
            max_age = wiking.cfg.resource_client_cache_max_age
            if max_age:
                req.message(_("The server is configured to let clients cache resource files "
                              "for %d seconds. It is necessary to force-reload the page to "
                              "see the changes to take effect within this period "
                              "(holding the Shift key while reloading in most browsers). "
                              "This may be changed by the configuration option "
                              "'resource_client_cache_max_age'."),
                            req.WARNING)
        else:
            req.message(err, req.ERROR)
        req.set_param('search', theme_id)
        raise Redirect(self._current_base_uri(req, record))


# ==============================================================================
# The modules below handle the actual content.
# The modules above are system modules used internally by Wiking.
# ==============================================================================

class Pages(SiteSpecificContentModule, wiking.CachingPytisModule):
    """Define available pages and their content and allow their management.

    This module implements the key CMS functionality.  Pages, their hierarchy, content and other
    properties are managed throug a Pytis data object.

    """
    class PagePositionEnumerator(pytis.data.Enumerator):

        def values(self, **kwargs):
            return wiking.module.PageStructure.page_position_selection(**kwargs)

        def last_position(self, row, site, parent, page_id):
            return self.values(site=site, parent=parent, page_id=page_id)[-1]

    class MenuVisibility(pp.Enumeration):
        enumeration = (('always', _("Always visible")),
                       ('authorized', _("Visible only to authorized users")),
                       ('never', _("Always hidden")),
                       )
        default = 'always'

    class Spec(Specification):
        # Translators: Heading and menu item. Meaning web pages.
        title = _("Pages")
        help = _("Note: Please, reload the page if the list has just one item "
                 "(temporary workaround for a known issue).")
        table = 'cms_v_pages'

        def fields(self):
            return (
                Field('page_key'),
                Field('page_id'),
                Field('site'),
                Field('kind', default='page'),
                Field('identifier', _("Identifier"), width=20, fixed=True, editable=ONCE,
                      type=pd.RegexString(not_null=True, regex='^[a-zA-Z][0-9a-zA-Z_-]*$'),
                      computer=computer(self._default_identifier),
                      descr=_("The identifier may be used to refer to this page from "
                              "outside and also from other pages. The same identifier "
                              "is used for all language variants of one page. A valid "
                              "identifier can only contain letters, digits, dashes and "
                              "underscores.  It must start with a letter.")),
                Field('lang', _("Language"), editable=ONCE, not_null=True,
                      codebook='Languages', selection_type=CHOICE, value_column='lang'),
                Field('title_or_identifier', _("Title")),
                Field('title', _("Title"), not_null=True),
                Field('description', _("Description"), width=64,
                      descr=_("Brief description shown as a tooltip on links (such as menu items) "
                              "and in site map.")),
                ContentField('_content', _("Content"), compact=True, height=20, width=80,
                             attachment_storage=self._attachment_storage),
                ContentField('content'),
                Field('comment', _("Comment"), virtual=True, width=70, type=pd.String(),
                      descr=_("Describe briefly the changes you made.")),
                # Translators: "Module" is an independent reusable part of a computer program
                # (here a module of Wiking CMS).
                Field('modname', _("Module"), not_null=False,
                      enumerator=enum([_m.name() for _m in wiking.cfg.resolver.available_modules()
                                       if (issubclass(_m, Embeddable) and
                                           _m not in (EmbeddableCMSModule, CMSExtension))]),
                      selection_type=CHOICE, display=_modtitle, prefer_display=True,
                      descr=_("Select the extension module to embed into the page.  Leave blank "
                              "for an ordinary text page.")),
                # Translators: "Parent item" has the meaning of hierarchical position.  More precise
                # term might be "Superordinate item" but doesn't sound that nice in English.
                # The term "item" represents a page, but also a menu item.
                Field('parent', _("Parent item"), not_null=False,
                      codebook='PageStructure', selection_type=CHOICE,
                      runtime_filter=computer(lambda r, site: pd.EQ('site', pd.sval(site))),
                      descr=_("Select the superordinate item in page hierarchy.  Leave blank for "
                              "a top-level page.")),
                # Translators: Page configuration option followed by a selection
                # input field.  Determines the position in the sense of order in a
                # sequence.  What is first and what next.
                Field('ord', _("Position"), not_null=True, editable=ALWAYS,
                      enumerator=Pages.PagePositionEnumerator(), selection_type=CHOICE,
                      runtime_arguments=computer(lambda r, site, parent, page_id:
                                                 dict(site=site, parent=parent, page_id=page_id)),
                      computer=computer(Pages.PagePositionEnumerator().last_position),
                      display=lambda x: x.label,  # See PageStructure.page_position_selection().
                      descr=_("Select the position within the items of the same level.")),
                Field('menu_visibility', _("Visibility in menu"), not_null=True,
                      enumerator=Pages.MenuVisibility, selection_type=RADIO,
                      descr=_('When "%(always)s" is selected, unauthorized users see the menu '
                              'item, but still can not open the page.  When "%(authorized)s" '
                              'is selected, visibility is controlled by the "Access Rights" '
                              'settings below.  Note that when access rights are restricted, '
                              'the item will be hidden until the user logs in, which may be '
                              'confusing (the expected item is not there).',
                              always=dict(Pages.MenuVisibility.enumeration).get('always'),
                              authorized=dict(Pages.MenuVisibility.enumeration).get('authorized'))),
                Field('foldable', _("Foldable"), editable=computer(lambda r, menu_visibility:
                                                                   menu_visibility != 'never'),
                      descr=_("Check if you want the relevant menu item to be foldable (only makes "
                              "sense for pages, which have subordinate items in the menu).")),
                Field('tree_order', type=pd.TreeOrder()),
                Field('creator', _("Creator"), not_null=True,
                      codebook='Users', selection_type=CHOICE,
                      inline_referer='creator_login', inline_display='creator_name'),
                Field('creator_login'),
                Field('creator_name'),
                Field('created', _("Created"), default=now),
                # Translators: Configuration option determining whether the page is publicly
                # visible or not (passive form of publish).  The label may be followed by
                # a checkbox.
                Field('published', _("Published"), default=False,
                      # Translators: Item is a generic term to refer to a web page,
                      # publication, article or another kind of content.
                      descr=_("Check to make the item visible in production mode. "
                              "Otherwise it is only visible in preview mode. "
                              "Allows content development before publishing it. "
                              "Different language variants may be published "
                              "independently (switch language to control availability "
                              "in other languages). Unpublishing also applies to "
                              "all descendant items in the hierarchy. In other words "
                              "the item needs to be published itself as well as all "
                              "its parent items to be actually available.")),
                Field('published_since', _("Available since")),
                Field('parents_published'),
                Field('status', _("Status"), virtual=True, type=pd.String(),
                      computer=computer(self._status)),
                # Field('grouping', virtual=True,
                #      computer=computer(lambda r, tree_order: tree_order.split('.')[1])),
                # Translators: Label of a selector of a group allowed to access the page read only.
                Field('read_role_id', _("Read only access"), not_null=True,
                      codebook='ApplicationRoles', selection_type=CHOICE,
                      computer=self._parent_field_computer('read_role_id', Roles.ANYONE.id()),
                      editable=ALWAYS,
                      descr=_("Select the role allowed to view the page contents.")),
                # Translators: Label of a selector of a group allowed to edit the page.
                Field('write_role_id', _("Read/write access"), not_null=True,
                      codebook='ApplicationRoles', selection_type=CHOICE,
                      computer=self._parent_field_computer('write_role_id',
                                                           Roles.CONTENT_ADMIN.id()),
                      editable=ALWAYS,
                      descr=_("Select the role allowed to edit the page contents.")),
                Field('owner', _("Owner"), not_null=False,
                      codebook='Users', selection_type=CHOICE,
                      inline_referer='owner_login', inline_display='owner_name',
                      computer=self._parent_field_computer('owner'), editable=ALWAYS,
                      descr=_("The owner has full read/write access regardless of roles "
                              "settings above.")),
                Field('owner_login'),
                Field('owner_name'),
            )

        def _status(self, record, _content, content):
            if _content == content:
                return _("OK")
            else:
                return _("Changed")

        def _default_identifier(self, record, title):
            if title and record['identifier'].value() is None:
                # This only applies on new record insertion and not during further editation.
                return lcg.text_to_id(title)
            else:
                return record['identifier'].value()

        def _attachment_storage_uri(self, record):
            return '/' + record['identifier'].export() + '/attachments'

        def _attachment_storage(self, record):
            return Attachments.AttachmentStorage(record.req(),
                                                 record['page_id'].value(),
                                                 record['lang'].value(),
                                                 self._attachment_storage_uri(record))

        def _parent_field_computer(self, field_id, default=None):
            return computer(lambda r, parent:
                            self._parent_field_value(r, parent, field_id, default=default))

        def _parent_field_value(self, record, parent, field_id, default=None):
            if record.new():
                if parent:
                    return record.cb_value('parent', field_id).value()
                else:
                    return default
            else:
                return record[field_id].value()

        def row_style(self, record):
            if not record['published'].value() or not record['parents_published'].value():
                return pp.Style(foreground='#777')
            else:
                return None

        def check(self, record):
            parent = record['parent'].value()
            if parent is not None and parent == record['page_id'].value():
                return ('parent', _("A page can not be its own parent."))
        condition = pd.EQ('kind', pd.sval('page'))
        sorting = (('tree_order', ASC), ('identifier', ASC),)
        # grouping = 'grouping'
        # group_heading = 'title'
        layout = ()  # Defined by _layout() method.
        columns = ('title_or_identifier', 'modname', 'status',
                   'menu_visibility', 'read_role_id', 'write_role_id')
        cb = CodebookSpec(display='title_or_identifier', prefer_display=True)
        actions = (
            # Translators: Button label. Page configuration options.
            Action('options', _("Options"), icon='ellipsis-icon',
                   descr=_("Edit global options, such as visibility, "
                           "menu position and access rights.")),
            Action('commit', _("Commit"), icon='circle-up-icon',
                   descr=_("Publish the current concept in production mode."),
                   enabled=lambda r: (r['parents_published'].value() and r['published'].value() and
                                      r['_content'].value() != r['content'].value())),
            Action('revert', _("Revert"), icon='undo-icon',
                   descr=_("Replace the current concept with the production version."),
                   enabled=lambda r: (r['parents_published'].value() and r['published'].value() and
                                      r['_content'].value() != r['content'].value())),
            # Action('translate', _("Translate"),
            #      descr=_("Create the content by translating another language variant"),
            #       enabled=lambda r: r['_content'].value() is None),
            Action('new_page', _("New Page"), icon='create-icon',
                   descr=_("Create a new page")),
            # The action seems inadequate in row context menu and the help page
            # is out of date anyway.
            # Action('help', _("Help")),
        )
        # Translators: Noun. Such as e-mail attachments (here attachments for a webpage).
        bindings = (
            # We include Attachments twice under different identifiers.  The binding
            # 'attachments-management' is for the management form, where the URL
            # /<page-id>/attachments-management/<filename.ext> leads to a ShowForm
            # displaying attachment details and allowing further actions, while
            # /<page-id>/attachments/<filename.ext> leads to direct attachment download
            # and allows simply linking this URL from other pages.
            Binding('attachments-management', _("Attachments"), 'Attachments', 'page_id'),
            Binding('attachments', _("Attachments"), 'Attachments', 'page_id'),
            Binding('history', _("History"), 'PageHistory', 'page_key'),
        )

    _REFERER = 'identifier'
    _EXCEPTION_MATCHERS = (
        ('duplicate key (value )?violates unique constraint "cms_pages_pkey"',
         _("The page already exists in given language.")),
        ('duplicate key (value )?violates unique constraint "cms_pages_unique_tree_(?P<id>ord)er"',
         _("Duplicate menu order at this level of hierarchy.")),) + \
        SiteSpecificContentModule._EXCEPTION_MATCHERS
    _LIST_BY_LANGUAGE = True
    _INSERT_LABEL = _("New page")
    _UPDATE_LABEL = _("Edit Text")
    _UPDATE_DESCR = _("Edit title, description and content for the current language")
    _LIST_LABEL = _("List all pages")
    _INSERT_MSG = _("New page was successfully created.")
    _UPDATE_MSG = _("The page was successfully updated.")
    _SEPARATOR = re.compile(r'^====+\s*$', re.MULTILINE)
    _HONOUR_SPEC_TITLE = True
    _ROW_ACTIONS = True

    _cache_ids = ('default', 'module_uri', 'page_uri')

    def _check_page_access(self, req, record, readonly=False):
        """Return true if the current user has readonly/readwrite access to given page record.

        Note, this logic is duplicated at 'Publications._condition()', so any
        change here should be reflected there as well.

        """
        if not record:
            return False
        if not (record['published'].value() and record['parents_published'].value()
                or wiking.module.Application.preview_mode(req)):
            return False
        if req.check_roles(Roles.CONTENT_ADMIN):
            return True
        if req.check_roles(Roles.USER) and req.user().uid() == record['owner'].value():
            return True
        roles = wiking.module.Users.Roles()
        if req.check_roles(roles[record['write_role_id'].value()]):
            return True
        if readonly and req.check_roles(roles[record['read_role_id'].value()]):
            return True
        return False

    def _handle(self, req, action, **kwargs):
        """Setup specific environment when processing a request for a CMS page.

        Attaching the attributes 'page_record', 'page_read_access' and
        'page_write_access' to the request is a quick hack.  It allows us to
        quickly determine the current page within further request processing.
        As we also save the access rights of the current page, we can also
        quickly determine access to related subcontent, such as attachments or
        records of embedded modules.  Some modules may override the access
        attributes when we dive into content with specific access settings.
        For example the module 'Publications' will owerwrite the attributes
        'req.page_read_access' and 'req.page_write_access' according to the
        access settings of the current publication when we dive into a
        publication (the request leads to some content within it).  Thus the
        Attachments module will automatically respect theese attributes when
        accessing attachments of a publication.

        A cleaner approach would be to store these properties within the
        request forwarding information (see 'req.forward()') and having some
        nice API to access them, but for now this simple approach satisfies our
        needs.

        """
        # Check hasattr to avoid overwriting page_record in derived classes,
        # such as in Publications, which are processed inside pages.
        if not hasattr(req, 'page_record'):
            record = kwargs.get('record')
            req.page_record = record
            req.page_read_access = self._check_page_access(req, record, readonly=True)
            req.page_write_access = self._check_page_access(req, record)
        return super(Pages, self)._handle(req, action, **kwargs)

    def _authorization_error(self, req, record=None, **kwargs):
        if ((record
             and not (record['published'].value() and record['parents_published'].value())
             and wiking.module.Application.preview_mode_possible(req)
             and not wiking.module.Application.preview_mode(req))):
            raise wiking.AuthorizationError(_("The page is not visible in production mode. "
                                              "You need to switch to the preview mode "
                                              "to be able to access it."))
        return super(Pages, self)._authorization_error(req, record=record, **kwargs)

    def _authorized(self, req, action, record=None, **kwargs):
        if action in ('new_page', 'insert', 'list', 'options', 'commit', 'revert', 'delete'):
            return req.check_roles(Roles.CONTENT_ADMIN,)
        elif record and action in ('view', 'rss'):
            return self._check_page_access(req, record, readonly=True)
        elif record and action in ('update', 'commit', 'revert',):
            return self._check_page_access(req, record)
        else:
            return False  # raise NotFound or BadRequest?

    def _layout(self, req, action, record=None):
        if action in ('insert', 'options'):
            layout = [
                FieldSet(_("Basic Options"), ('identifier', 'modname', 'published')),
                FieldSet(_("Menu position"), ('parent', 'ord', 'menu_visibility', 'foldable')),
                FieldSet(_("Access Rights"), ('read_role_id', 'write_role_id', 'owner')),
            ]
            if action == 'insert':
                layout.insert(0, FieldSet(_("Page Text (for the current language)"),
                                          ('title', 'description', '_content')))
            return layout
        elif action == 'update':
            return ('title', 'description', '_content', 'comment',)
        elif action == 'delete':
            return ()

    def _handle_subpath(self, req, record):
        modname = record['modname'].value()
        if modname:
            binding = self._embed_binding(modname)
            if binding:
                if req.unresolved_path[0] == binding.id():
                    del req.unresolved_path[0]
                    if self._binding_enabled(req, record, binding):
                        return self._perform_binding_forward(req, record, binding)
                    else:
                        raise Forbidden()
            else:
                # This for modules, which are Embeddable, but not
                # EmbeddableCMSModule.
                mod = wiking.module(modname)
                if isinstance(mod, wiking.RequestHandler):
                    try:
                        return req.forward(mod)
                    except NotFound:
                        # Don't allow further processing if unresolved_path was already consumed.
                        if not req.unresolved_path:
                            raise
        return super(Pages, self)._handle_subpath(req, record)

    def _binding_visible(self, req, record, binding):
        if binding.id() == 'attachments':
            return False
        else:
            return super()._binding_visible(req, record, binding)

    def _current_base_uri(self, req, record=None):
        return '/'

    def _load_page_rows(self, key, transaction=None):
        identifier, preview_mode = key
        kwargs = dict(site=wiking.cfg.server_hostname)
        if not preview_mode:
            kwargs['published'] = True
            kwargs['parents_published'] = True
        if identifier is not None:
            kwargs['identifier'] = identifier
        return self._data.get_rows(sorting=self._sorting, **kwargs)

    def _resolve(self, req):
        if not req.unresolved_path:
            return None
        identifier = req.unresolved_path[0]
        # Recognize special path of RSS channel as '<identifier>.<lang>.rss'.
        if identifier.endswith('.rss') and len(identifier) > 7 and identifier[-7] == '.':
            row = self._data.get_row(site=wiking.cfg.server_hostname,
                                     identifier=identifier[:-7], lang=str(identifier[-6:-4]))
            if row:
                req.set_param('action', 'rss')
                del req.unresolved_path[0]
                return row
        # Resolve the unpublished language variants when the preview mode is on
        # or when the current user is authorized to switch.
        preview_mode = (wiking.module.Application.preview_mode(req)
                        or wiking.module.Application.preview_mode_possible(req))
        rows = self._get_value((identifier, preview_mode), loader=self._load_page_rows)
        if rows:
            if req.has_param(self._key):
                # If key is passed (on form submission), resolve by key
                # rather than by preferred language (the preferred language may
                # have changed while the form was displayed).
                key = req.param(self._key)
                keys = [r[self._key].export() for r in rows]
                if key in keys:
                    del req.unresolved_path[0]
                    return rows[keys.index(key)]
            variants = [str(r['lang'].value()) for r in rows]
            lang = req.preferred_language(variants)
            del req.unresolved_path[0]
            return rows[variants.index(lang)]
        else:
            raise NotFound()

    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid == 'parent':
            return None
        return super(Pages, self)._link_provider(req, uri, record, cid, **kwargs)

    def _prefill(self, req):
        return dict(super(Pages, self)._prefill(req),
                    lang=req.preferred_language(raise_error=False),
                    creator=req.user().uid())

    def _submit_buttons(self, req, action, record=None):
        if action == 'insert':
            return ((None, _("Save")),)
        elif action == 'update':
            if not record['published'].value() or not record['parents_published'].value():
                return ((None, _("Save as Concept")),)
            else:
                return ((None, _("Save as Concept")),
                        ('commit', _("Save as Production Version"), 'circle-up-icon'))
        else:
            return super(Pages, self)._submit_buttons(req, action, record=record)

    def _before_page_change(self, req, record):
        if req.has_param('commit') or record.new() or not (record['published'].value() and
                                                           record['parents_published'].value()):
            # When the page is not published, we commit the changes
            # automatically.  It makes no difference in preview mode and the page
            # is not visible in production mode anyway.  We also want the page to
            # appear in the expected state once it is published.
            # We also autocommit the content on insertion because when published
            # immediately, the user will expect it to be published in the current
            # state (and when not published immediately, the above applies).
            record['content'] = record['_content']
        if ((record.field_changed('published') and record['published'].value() and
             record['published_since'].value() is None)):
            # TODO: This should be done in DB to propagate publication through parent pages.
            record['published_since'] = pd.Value(record.type('published_since'), now())
        if record['creator'].value() is None:
            # Supply creator to a newly created language variant (where prefill
            # doesn't apply because it actually is an update, not insert).
            record['creator'] = pd.Value(record.type('creator'), req.user().uid())
        if record['created'].value() is None:
            record['created'] = pd.Value(record.type('created'), now())
        if record['title'].value() is None and record['published'].value():
            if record['modname'].value() is not None:
                # Supply the module's title automatically.
                mod = wiking.module(record['modname'].value())
                record['title'] = pd.Value(record.type('title'),
                                           req.localize(mod.title(), record['lang'].value()))
            else:
                raise wiking.DBException(_("Can't publish untitled page."))

    def _insert_transaction(self, req, record):
        return self._transaction()

    def _update_transaction(self, req, record):
        return self._transaction()

    def _insert(self, req, record, transaction):
        self._before_page_change(req, record)
        result = super(Pages, self)._insert(req, record, transaction)
        wiking.module.PageHistory.on_page_change(req, record, transaction=transaction)
        return result

    def _update(self, req, record, transaction):
        self._before_page_change(req, record)
        super(Pages, self)._update(req, record, transaction)
        wiking.module.PageHistory.on_page_change(req, record, transaction=transaction)

    def _insert_msg(self, req, record):
        if not record['published'].value():
            note = _("It is now only visible in preview mode. "
                     'Set as "Published" to appear in production mode.')
        elif not record['parents_published'].value():
            # Translators: "It" refers to a page, publication or another kind of content
            # mentioned in a previous sentence.  The formulation shoud work for all cases.
            note = _("It is now only visible in preview mode because of "
                     "unpublished parent items. Publish the unpublished "
                     "parent to make this item visible in production mode.")
        else:
            note = _("It is now visible in production mode.")
        return self._INSERT_MSG + ' ' + note

    def _update_msg(self, req, record):
        msg = self._UPDATE_MSG
        if record.field_changed('published'):
            # Translators: "It" refers to a page, publication or another kind of content
            # mentioned in a previous sentence.  The formulation shoud work for all cases.
            if record['published'].value():
                if record['parents_published'].value():
                    note = _("It will be visible in production mode from now on.")
                else:
                    note = _("It will remain only visible in preview mode for now "
                             "due to unpublished parent items, but will appear in "
                             "production mode as soon as all parents are published.")
            else:
                if record['parents_published'].value():
                    note = _("It will be only visible in preview mode from now on.")
                else:
                    note = _("It will not become visible in production mode even if "
                             "parents are published until you set it as published "
                             "explicitly.")

            msg += ' ' + note
        if ((record.field_changed('_content') and
             record['content'].value() != record['_content'].value())):
            msg += _("The content was modified, however the changes are only visible in "
                     "preview mode. Commit the changes to make them visible in production mode.")
        return msg

    def _set_preview_mode_if_necessary(self, req, record):
        if ((record['content'].value() != record['_content'].value()
             or not record['published'].value() or not record['parents_published'].value())):
            # Make sure uncommited changes are visible in the displayed page.
            wiking.module.Application.set_preview_mode(req, True)

    def _redirect_after_insert(self, req, record):
        req.message(self._insert_msg(req, record), req.SUCCESS)
        self._set_preview_mode_if_necessary(req, record)
        raise Redirect(self._current_record_uri(req, record))

    def _redirect_after_update(self, req, record):
        req.message(self._update_msg(req, record), req.SUCCESS)
        self._set_preview_mode_if_necessary(req, record)
        raise Redirect(req.uri())

    def _delete_form_content(self, req, form, record):
        preview_mode = wiking.module.Application.preview_mode(req)
        return [form] + self._page_content(req, record, preview=preview_mode)

    def _visible_in_menu(self, req, row):
        """Return True or False if page described by row is visible or not in the menu"""
        visibility = row['menu_visibility'].value()
        if visibility == 'always':
            return True
        elif visibility == 'authorized':
            return self._check_page_access(req, row, readonly=True)
        elif visibility == 'never':
            return False

    # Public methods

    def menu(self, req):
        children = {None: []}
        translations = {}
        application = wiking.module.Application
        available_languages = application.languages()
        preview_mode = application.preview_mode(req)

        def item(row):
            page_id = row['page_id'].value()
            identifier = str(row['identifier'].value())
            titles, descriptions = translations[page_id]
            modname = row['modname'].value()
            if modname is not None:
                from pytis.util import ResolverError
                try:
                    mod = wiking.module(modname)
                except ResolverError:
                    # We want the CMS to work even if the module was uninstalled or renamed.
                    submenu = []
                else:
                    submenu = list(mod.submenu(req))
            else:
                submenu = []
            submenu += [item(r) for r in children.get(page_id, ())]
            if preview_mode:
                variants = available_languages
            else:
                variants = list(titles.keys())
            return MenuItem('/' + identifier,
                            title=lcg.SelfTranslatableText(identifier, translations=titles),
                            descr=lcg.SelfTranslatableText('', translations=descriptions),
                            hidden=not self._visible_in_menu(req, row),
                            foldable=(True if submenu and row['parent'].value() is None
                                      else bool(row['foldable'].value())),
                            variants=variants,
                            submenu=submenu)
        rows = self._get_value((None, preview_mode), loader=self._load_page_rows)
        for row in rows:
            page_id = row['page_id'].value()
            if page_id not in translations:
                children.setdefault(row['parent'].value(), []).append(row)
                translations[page_id] = ({}, {})
            titles, descriptions = translations[page_id]
            lang = str(row['lang'].value())
            titles[lang] = row['title_or_identifier'].value()
            if row['description'].value() is not None:
                descriptions[lang] = row['description'].value()
        return [item(row) for row in children[None]] + \
               [MenuItem('_registration', _("Registration"), hidden=True),
                # Translators: Label for section with user manuals, help pages etc.
                MenuItem('_doc', _("Documentation"), hidden=True)]

    def empty(self, req):
        return len(self._data.get_rows(site=wiking.cfg.server_hostname)) == 0

    def module_uri(self, req, modname):
        return self._get_value(modname, cache_id='module_uri', loader=self._load_module_uri)

    def page_uri(self, req, page_id):
        return self._get_value(page_id, cache_id='page_uri', loader=self._load_page_uri)

    def _load_page_uri(self, page_id, transaction=None):
        row = self._data.get_row(page_id=page_id, site=wiking.cfg.server_hostname)
        if row:
            return '/' + row['identifier'].value()
        else:
            return None

    def _load_module_uri(self, modname, transaction=None):
        if modname == self.name():
            uri = '/'
        else:
            row = self._data.get_row(modname=modname, site=wiking.cfg.server_hostname)
            if row:
                uri = '/' + row['identifier'].value()
                binding = self._embed_binding(modname)
                if binding:
                    uri += '/' + binding.id()
            else:
                uri = None
        return uri

    def _page_content(self, req, record, preview=False):
        # Main content
        modname = record['modname'].value()
        if modname is not None:
            from pytis.util import ResolverError
            try:
                module = wiking.module(modname)
            except ResolverError:
                # Allow changing the module if it no longer exists.
                content = [wiking.Message((_("Unknown module: %s", modname)), kind='error')]
                wiking.module.Application.report_error(req, wiking.InternalServerError())
            else:
                content = module.embed(req)
        else:
            content = []
        if preview:
            text = record['_content'].value()
        else:
            text = record['content'].value()
        if text:
            text = unicodedata.normalize('NFC', text)
            if self._SEPARATOR.search(text):
                pre, post = self._SEPARATOR.split(text, maxsplit=2)
            else:
                pre, post = text, ''
            content = [text2content(req, pre)] + content + [text2content(req, post)]
        # Process page attachments
        storage = record.attachment_storage('_content')
        resources = storage.resources()
        # Create automatic image gallery if any attachments are marked as in gallery.
        gallery_images = [lcg.InlineImage(r) for r in resources
                          if isinstance(r, lcg.Image) and r.info()['in_gallery']]
        if gallery_images:
            content.append(lcg.Container(gallery_images, name='wiking-image-gallery'))
        # Create automatic attachment list if any attachments are marked as listed.
        listed_attachments = [(lcg.link(r, r.title() or r.filename()),
                               ' (' + format_byte_size(r.info()['byte_size']) + ') ',
                               lcg.coerce(r.descr() or '', formatted=True))
                              for r in resources if r.info()['listed']]
        if listed_attachments:
            # Translators: Section title. Attachments as in email attachments.
            content.append(lcg.Section(title=_("Attachments"),
                                       content=lcg.ul(listed_attachments),
                                       id='attachment-automatic-list',  # Prevent dupl. anchor.
                                       in_toc=False))
        if content or resources:
            return [lcg.Container(content, resources=resources)]
        else:
            return content

    def _page_actions_content(self, req, record):
        # Create an empty show form just for the action menu.
        actions = self._form_actions_argument(req)
        form = self._form(pw.ShowForm, req, record=record, layout=(), actions=actions)
        if any(a for a in actions(form, record) if a.name() != 'view'):
            return [form]
        else:
            return []

    # Action handlers.

    def action_view(self, req, record):
        preview_mode = wiking.module.Application.preview_mode(req)
        content = self._page_content(req, record, preview=preview_mode)
        if not content:
            # Redirect to the first visible subpage (if any) when the page
            # has no content.  This makes it possible to create menu items
            # which have no direct content, but only subitems.  The first
            # subitem is selected when such item is clicked.
            condition = pd.AND(pd.EQ('parent', record['page_id']),
                               pd.NE('menu_visibility', pd.sval('never')),
                               pd.EQ('published', pd.bval(True)),
                               pd.EQ('site', pd.sval(wiking.cfg.server_hostname)))
            for row in self._data.get_rows(condition=condition, sorting=self._sorting):
                if self._visible_in_menu(req, row):
                    if preview_mode:
                        req.message(_("This page has no content. "
                                      "Users will be redirected to the first visible "
                                      "subpage in production mode."), req.WARNING)
                        break
                    else:
                        raise Redirect('/' + row['identifier'].value())
        if req.page_write_access or self.name() != 'Pages':
            # The above condition is just to avoid unnecessary slowdown in the simplest case...
            actions = self._page_actions_content(req, record)
            if actions:
                name = ['cms-page-actions']
                if record['kind'].value() != 'page':
                    name.append('cms-%s-actions' % record['kind'].value())
                content.append(lcg.Container(actions, name=name))
        if req.page_write_access:
            content.extend(self._related_content(req, record))
        return self._document(req, content, record)

    def action_update(self, req, record, action='update'):
        application = wiking.module.Application
        if action == 'update' and not application.preview_mode(req) \
                and record['content'].value() != record['_content'].value():
            req.message(_("There are unpublished changes which are not visible "
                          "in production mode."), req.WARNING)
            application.set_preview_mode(req, True)
        return super(Pages, self).action_update(req, record, action=action)

    def action_rss(self, req, record):
        modname = record['modname'].value()
        if modname is not None:
            mod = wiking.module(modname)
            binding = self._embed_binding(modname)
            return mod.action_rss(req, relation=binding and (binding, record))
        else:
            raise NotFound()

    def action_options(self, req, record):
        return self.action_update(req, record, action='options')

    def action_translate(self, req, record):
        lang = req.param('src_lang')
        if not lang:
            if record['_content'].value() is not None:
                req.message(_("Content for this page already exists!"), req.ERROR)
                raise Redirect(self._current_record_uri(req, record))
            cond = pd.AND(pd.NE('_content', pd.Value(pd.String(), None)),
                          pd.NE('lang', record['lang']))
            langs = [str(row['lang'].value()) for row in
                     self._data.get_rows(page_id=record['page_id'].value(), condition=cond)]
            if not langs:
                req.message(_("Content for this page does not exist in any language."),
                            req.ERROR)
                raise Redirect(self._current_record_uri(req, record))
            d = pw.SelectionDialog('src_lang', _("Choose source language"),
                                   [(l, lcg.language_name(l) or l) for l in langs],
                                   action='translate',
                                   hidden=[(id, record[id].value()) for id in ('page_id', 'lang')])
            return self._document(req, d, record, subtitle=_("Translate"))
        else:
            row = self._data.get_row(page_id=record['page_id'].value(),
                                     lang=str(req.param('src_lang')))
            for k in ('_content', 'title'):
                req.set_param(k, row[k].value())
            return self.action_update(req, record)

    def action_commit(self, req, record):
        try:
            record.update(content=record['_content'].value())
        except pd.DBException as e:
            req.message(self._error_message(*self._analyze_exception(e)), req.ERROR)
        else:
            req.message(_("The changes were published."), req.SUCCESS)
        raise Redirect(self._current_record_uri(req, record))

    def action_revert(self, req, record):
        try:
            record.update(_content=record['content'].value())
        except pd.DBException as e:
            req.message(self._error_message(*self._analyze_exception(e)), req.ERROR)
        else:
            req.message(_("The content was reverted to its previous state."), req.SUCCESS)
        raise Redirect(self._current_record_uri(req, record))

    def action_new_page(self, req, record):
        raise Redirect(self._current_base_uri(req, record), action='insert',
                       parent=record['parent'].value(), ord=record['ord'].value())


class NavigablePages(Pages):
    """Pages which have a simple sequential navigation bar at the top and bottom."""

    class Navigation(lcg.Content):

        def __init__(self, position):
            self._position = position
            super(NavigablePages.Navigation, self).__init__()

        def _navigation_links(self, req, node):
            publication_id = '/%s/data/%s' % (req.page_record['identifier'].value(),
                                              req.publication_record['identifier'].value())
            top = [n for n in node.path() if n.id() == publication_id][0]

            def target(tnode):
                if tnode and tnode is not node and top in tnode.path():
                    return tnode
                else:
                    return None
            return (
                # Translators: Label of a link in sequential navigation.
                (target(node.prev()), 'arrow-left-icon', _("Previous Chapter")),
                # Translators: Label of a link in sequential navigation.
                (target(node.next()), 'arrow-right-icon', _("Next Chapter")),
                # Translators: Label of a link to the start page of a publication.
                (target(top), 'arrow-up-icon', _("Top")),
            )

        def export(self, context):
            g = context.generator()

            def ctrl(target, label, icon_cls):
                # Check that the target node is within the publications's children.
                cls = 'navigation-ctrl'
                if target:
                    uri = context.uri(target)
                    title = target.title()
                else:
                    # Translators: Label used instead of a link when the target
                    # does not exist.  For example sequential navigation may
                    # contain: "Previous: Introduction, Next: None".
                    uri = None
                    title = _("None")
                    cls += ' dead'
                icon = g.span('', cls='icon ' + icon_cls)
                if icon_cls == 'arrow-right-icon':
                    label = label + icon
                else:
                    label = icon + label
                return g.a(label, href=uri, title=label + ': ' + title, cls=cls)
            return g.div(lcg.concat([ctrl(target, label, cls) for target, cls, label
                                     in self._navigation_links(context.req(), context.node())],
                                    separator=' | '),
                         cls='page-navigation ' + self._position)

    def _inner_page_content(self, req, record, preview=False):
        return super(NavigablePages, self)._page_content(req, record, preview=preview)

    def _page_content(self, req, record, preview=False):
        return ([self.Navigation('top')] +
                self._inner_page_content(req, record, preview=preview) +
                [self.Navigation('bottom')])


class BrailleExporter(wiking.Module):

    _OMIT_FOOTER = False

    @classmethod
    def braille_presentation(cls):
        if hasattr(lcg, 'braille_presentation'):
            presentation = lcg.braille_presentation()
            try:
                local_presentation = lcg.braille_presentation('presentation-braille-local.py')
            except IOError:
                pass
            else:
                for o in dir(local_presentation):
                    if o[0] in string.ascii_lowercase and hasattr(presentation, o):
                        setattr(presentation, o, getattr(local_presentation, o))
        else:
            presentation = None
        return presentation

    @classmethod
    def braille_available(cls):
        return cls.braille_presentation() is not None

    @classmethod
    def braille_option_fields(cls, virtual=False):
        presentation = cls.braille_presentation()
        return (
            Field('printer', _("Printer"), virtual=virtual, type=pd.String(),
                  enumerator=enum(presentation and presentation.printers.keys() or ()),
                  selection_type=CHOICE,
                  default=presentation and presentation.default_printer or None, not_null=False),
            Field('page_width', _("Characters per line"), width=3, virtual=virtual,
                  type=pd.Integer(), default=33),
            Field('page_height', _("Page lines"), width=3, virtual=virtual,
                  type=pd.Integer(), default=28),
            Field('inner_margin', _("Inner margin"), width=3, virtual=virtual,
                  type=pd.Integer(), default=1),
            Field('outer_margin', _("Outer margin (v2: Left margin)"), width=3, virtual=virtual,
                  type=pd.Integer(), default=0),
            Field('top_margin', _("Top margin"), width=3, virtual=virtual,
                  type=pd.Integer(), default=0),
            Field('bottom_margin', _("Bottom margin"), width=3, virtual=virtual,
                  type=pd.Integer(), default=0),
        )
    BRAILLE_EXPORT_OPTIONS_FIELDSET = FieldSet(
        _("Braille Export Options"),
        (HGroup(
            ('printer', 'page_width', 'page_height',),
            FieldSet(_("Margins"), ('inner_margin', 'outer_margin', 'top_margin', 'bottom_margin')),
        ),),
    )

    def _export_braille(self, req, publication):
        presentation = self.braille_presentation()
        printer = req.param('printer')
        if printer:
            presentation.default_printer = printer
        for param, default in (('page_width', 33),
                               ('page_height', 28),
                               ('inner_margin', 1),
                               ('outer_margin', 0),
                               ('top_margin', 0),
                               ('bottom_margin', 0)):
            value = req.param(param)
            if value:
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    raise wiking.BadRequest("Invalid value of braille export parameter '%s': %s" %
                                            (param, value))
            else:
                value = default
            setattr(presentation, param, lcg.UFont(value))
        if self._OMIT_FOOTER:
            presentation.left_page_footer = None
        presentation.right_page_footer = None
        exporter = lcg.BrailleExporter(translations=wiking.cfg.translation_path)
        context = exporter.context(publication, req.preferred_language(),
                                   presentation=lcg.PresentationSet(((presentation,
                                                                      lcg.TopLevelMatcher(),),)))
        result = exporter.export(context, recursive=True)
        return result, context.messages()


class PDFExporter(wiking.Module):

    @classmethod
    def pdf_option_fields(cls, virtual=False):
        return (
            Field('zoom', _("Zoom"), virtual=virtual, type=pd.Float(), default=1),
        )
    PDF_EXPORT_OPTIONS_FIELDSET = FieldSet(
        _("PDF Export Options"),
        ('zoom',),
    )

    def _export_pdf(self, req, record, publication):
        zoom = req.param('zoom')
        try:
            zoom = float(zoom)
        except (TypeError, ValueError):
            zoom = 1
        if zoom < 0.1:
            zoom = 0.1
        elif zoom > 10:
            zoom = 10
        page_id = record['page_id'].value()

        class PDFExporter(lcg.pdf.PDFExporter):

            def _get_resource_path(self, context, resource):
                return wiking.module.Attachments.retrieve(req, page_id, resource.filename(),
                                                          path_only=True)
        exporter = PDFExporter(translations=wiking.cfg.translation_path)
        presentation = lcg.Presentation()
        presentation.font_size = zoom
        context = exporter.context(publication, req.preferred_language(),
                                   presentation=lcg.PresentationSet(((presentation,
                                                                      lcg.TopLevelMatcher(),),)))
        result = exporter.export(context, recursive=True)
        return result, context.messages()


class CmsPageExcerpts(EmbeddableCMSModule, BrailleExporter):

    _OMIT_FOOTER = True

    class Spec(wiking.Specification):
        title = _("Excerpts")
        table = 'cms_page_excerpts'

        def fields(self):
            return (Field('id', _("Id")),
                    Field('title', _("Title")),
                    Field('page_id', _("Page"), not_null=True,
                          codebook='PageStructure', selection_type=CHOICE),
                    Field('lang'),
                    ContentField('content', _("Content")),
                    )
        columns = ('title', 'page_id',)

    def _authorized(self, req, action, record=None, **kwargs):
        if action == 'list' or record and action in ('view', 'delete', 'export_braille'):
            return req.page_read_access
        else:
            return False

    def _layout(self, req, action, record=None):
        return (lambda record: self._excerpt_content(req, record),)

    def _excerpt_content(self, req, record):
        form = wiking.InputForm(
            req, dict(
                fields=self.braille_option_fields(),
                layout=self.BRAILLE_EXPORT_OPTIONS_FIELDSET,
            ),
            name='ExcerptExportForm',
            action='export_braille',
            submit_buttons=((None, _("Export"), 'gear-icon'),),
            show_reset_button=False,
            show_footer=False,
        )
        return lcg.Container((text2content(req, record['content'].value()),
                              lcg.CollapsiblePane(_("Export to Braille"), form)))

    def _redirect_after_delete_uri(self, req, record, **kwargs):
        return self._binding_parent_uri(req), kwargs

    def store_excerpt(self, req, page_id, lang, title, content, transaction=None):
        row = pd.Row((('page_id', page_id), ('lang', lang),
                      ('title', title), ('content', content),))
        return self._data.insert(row, transaction=transaction)

    def action_export_braille(self, req, record):
        resource_provider = lcg.ResourceProvider(dirs=wiking.cfg.resource_path)
        node = lcg.ContentNode('excerpt', title=record['title'].value(),
                               content=text2content(req, record['content'].value()),
                               resource_provider=resource_provider)
        try:
            data, messages = self._export_braille(req, node)
        except lcg.BrailleError as e:
            req.message(e.message(), req.ERROR)
            raise Redirect(self._current_record_uri(req, record))
        else:
            return wiking.Response(data, content_type='application/octet-stream',
                                   filename='%s.brl' % record['title'].value())


class Publications(NavigablePages, EmbeddableCMSModule, BrailleExporter, PDFExporter):
    """CMS module to manage electronic publications.

    A publication is created as a hierarchy of CMS pages.  The top level page
    represents the publication, subordinary pages are its chapters.  This
    module may be added to any CMS page (it is an embeddable CMS module) and it
    will consist of a listing of available publications in alphabetical
    order.  Entering a particular publication will add its hierarchy to the CMS
    menu.

    """

    class Spec(Pages.Spec):
        title = _("Publications")
        table = 'cms_v_publications'

        def fields(self):
            override = (
                Field('kind', default='publication'),
                Field('description', _("Subtitle")),
                Field('parent',
                      computer=computer(lambda r: r.req().page_record['page_id'].value())),
                # Avoid default ord=1 to work around slow insertion!
                Field('ord', enumerator=None, default=None, computer=None),
                Field('menu_visibility', default='never'),
                Field('read_role_id',
                      descr=_("Select the role allowed to view the publication.")),
                Field('write_role_id',
                      descr=_("Select the role allowed to edit the publication.")),
            )
            extra = (
                Field('author', _("Author"), width=40, height=3, not_null=True,
                      descr=_("Full name(s) of the creator(s) of the publication or "
                              "the original work, if the publication is a derived work. "
                              "One name per line.")),
                Field('illustrator', _("Illustrations"), width=40, height=3,
                      descr=_("Full name(s) of the author(s) of illustrations used in the "
                              "publication. One name per line.")),
                Field('contributor', _("Contributors"), width=40, height=3,
                      descr=_("Creators of the publication with a less significant role "
                              "than the author(s). One name per line.")),
                Field('original_isbn', _("Original ISBN"), width=40,
                      descr=_("ISBN identifier of the original work if the publication is "
                              "a digitized book or another kind of derived work.")),
                Field('isbn', _("ISBN"), width=40,
                      descr=_("ISBN identifier of this publication if it has one assigned.")),
                Field('uuid', _("UUID"), width=40,
                      descr=_("Universally unique identifier of this publication. "
                              "Used when ISBN is not defined."),
                      computer=computer(self._uuid)),
                Field('adapted_by', _("Adapted by"), width=40, height=3,
                      descr=_("Name(s) of person(s) or organization(s), who created this "
                              "digital publication.  These are typically not the authors "
                              "of the content itself, but authors of its digital version. "
                              "One name per line.")),
                Field('adapted_for', _("Adapted for"), width=40,
                      descr=_("Name of the organization or project, for which this adaptation "
                              "has been done.  This field is for a digitized adaptation "
                              "an analogy of the Publisher field for the original work.")),
                Field('cover_image', _("Cover Image"), not_null=False,
                      codebook='Attachments', selection_type=CHOICE, value_column='attachment_id',
                      inline_referer='cover_image_filename',
                      runtime_filter=computer(self._attachment_filter), display='filename',
                      # There are no atttachments to select on insert. TODO: allow uploading one?
                      visible=computer(lambda r: not r.new()),
                      descr=_("Insert the image as an attachment and select it "
                              "from the list here.")),
                Field('cover_image_filename'),
                Field('publisher', _("Publisher"), width=30,
                      descr=_("Name of the organization which published the "
                              "original work.")),
                Field('published_year', _("Year Published"), width=4,
                      descr=_("Year when the original work was published.")),
                Field('edition', _("Edition"), width=3,
                      descr=_("Numeric order of the original work's edition.")),
                Field('copyright_notice', _("Copyright Notice"), width=78, height=4,
                      compact=True, computer=computer(self._copyright_notice),
                      editable=ALWAYS),
                Field('notes', _("Notes"), width=78, height=4, compact=True,
                      descr=_("Any other additional information about the "
                              "publication, such as names of translators, "
                              "reviewers etc.")),
                Field('pubinfo', _("Publisher"), virtual=True, type=pd.String(),
                      computer=computer(self._pubinfo)),
                Field('download_role_id', _("Download access"),
                      codebook='ApplicationRoles', selection_type=CHOICE,
                      not_null=False,  # Doesn't work: type=pd.String(not_null=False),
                      descr=_("Select the role allowed to download the publication for offline "
                              "use in one of the available download formats. Users with "
                              "read/write access are always allowed to download the publication "
                              "(because they create the downloadable versions). When empty, "
                              "download is only allowed to users with read/write access and "
                              "no one else. Users can not download without at least a read only "
                              "access to the publication, so they actually need to be members "
                              "of both roles, the download access role as well as the role set "
                              'for "Read only access".')),
            )
            return self._inherited_fields(Publications.Spec, override=override) + extra

        def _preview_mode(self, record):
            return wiking.module.Application.preview_mode(record.req())

        def _attachment_filter(self, record, page_id, lang):
            return pd.AND(pd.EQ('page_id', pd.ival(page_id)),
                          pd.EQ('lang', pd.sval(lang)),
                          pd.WM('mime_type', pd.WMValue(pd.String(), 'image/*')))

        def _attachment_storage_uri(self, record):
            return '/%s/data/%s/attachments' % (record.req().page_record['identifier'].value(),
                                                record['identifier'].value())

        def _uuid(self, record, isbn):
            if isbn is None:
                import uuid
                return str(uuid.uuid1())
            else:
                return None

        def _copyright_notice(self, record, lang):
            notice = record['copyright_notice'].value()
            if record.new() and notice is None:
                text = wiking.cms.texts.default_copyright_notice
                notice = wiking.module.Texts.localized_text(record.req(), text, lang=lang)
            return notice

        def _pubinfo(self, record, publisher, published_year, edition):
            if publisher:
                info = publisher
                if published_year:
                    info += ' %d' % (published_year,)
                if edition:
                    info += ' (' + _("%d. edition", edition) + ')'
                return info
            else:
                return None

        condition = pd.AND(pd.EQ('kind', pd.sval('publication')),
                           pd.NE('title', pd.sval(None)))
        columns = ('title', 'author', 'publisher', 'published')
        sorting = ('title', pd.ASCENDENT),
        bindings = Pages.Spec.bindings + (
            Binding('chapters', _("Chapters"), 'PublicationChapters', 'parent'),
            Binding('exports', _("Exported Versions"), 'PublicationExports', 'page_key'),
        )
        actions = Pages.Spec.actions + (
            Action('new_chapter', _("New Chapter"), icon='create-icon',
                   descr=_("Create a new chapter in this publication.")),
        )

    _LIST_BY_LANGUAGE = False
    _INSERT_LABEL = _("New Publication")
    _UPDATE_LABEL = _("Title Page Text")
    _UPDATE_DESCR = _("Edit the text displayed on the title page.")
    _EMBED_BINDING_COLUMN = 'parent'
    _INSERT_MSG = _("New publication was successfully created.")
    _UPDATE_MSG = _("The publication was successfully updated.")

    EPUB_EXPORT_OPTIONS_FIELDSET = FieldSet(
        _("EPUB Export Options"),
        ('allow_interactivity',),
    )

    @classmethod
    def epub_option_fields(cls, virtual=False):
        return (
            Field('allow_interactivity', _("Allow interactivity"), virtual=virtual,
                  type=pd.Boolean(),
                  descr=_("Interactive features (exercises) currently don't work "
                          "in iBooks, so it is safer to leave this option unchecked. "
                          "The exercises will remain in the publication, but they "
                          "will not support interaction.")),
        )

    def _handle(self, req, action, **kwargs):
        if not hasattr(req, 'publication_record'):
            record = kwargs.get('record')
            req.publication_record = kwargs.get('record')
            if record:
                # Overwrite the following variables when we dive into a publication.
                # This will make Attachments and other nested modules respect
                # the rights of the current publication instead of the page
                # where the publication belongs.
                req.page_read_access = self._check_page_access(req, record, readonly=True)
                req.page_write_access = self._check_page_access(req, record)
        return super(Publications, self)._handle(req, action, **kwargs)

    def _layout(self, req, action, record=None):
        if action in ('insert', 'options'):
            layout = [
                FieldSet(_("Basic Options"),
                         ('title', 'description', 'lang', 'identifier',
                          'cover_image', 'published')),
                FieldSet(_("Bibliographic Information"),
                         ('author', 'contributor', 'illustrator',
                          'publisher', 'published_year', 'edition',
                          'original_isbn', 'isbn', 'adapted_by', 'adapted_for',
                          'copyright_notice', 'notes')),
                FieldSet(_("Access Rights"),
                         ('read_role_id', 'download_role_id', 'write_role_id', 'owner')),
            ]
            if action == 'insert':
                layout.insert(2, FieldSet(_("Title Page Text"), ('_content',)))
            return layout
        elif action == 'update':
            return ('_content', 'comment')
        elif action == 'delete':
            return ()

    def _authorized(self, req, action, record=None, **kwargs):
        if action in ('insert',):
            return req.page_write_access
        elif record and action in ('view', 'rss'):
            return self._check_page_access(req, record, readonly=True)
        elif record and action in ('update', 'options', 'new_chapter',
                                   'export_publication', 'commit', 'revert', 'delete'):
            return self._check_page_access(req, record)
        else:
            return False  # raise NotFound or BadRequest?

    def _condition(self, req):
        uid = req.user() and req.user().uid()
        conditions = [
            super(Publications, self)._condition(req),
            # Beware, this condition actually duplicates the logic in _check_page_access().
            pd.OR(pd.EQ('owner', pd.ival(uid)),
                  *[pd.FunctionCondition('cms_f_role_member', pd.ival(uid), role) for role in
                    ('read_role_id', 'write_role_id', pd.sval(Roles.CONTENT_ADMIN.id()))])
        ]
        if not wiking.module.Application.preview_mode(req):
            conditions.append(pd.EQ('published', pd.bval(True)))
        return pd.AND(*conditions)

    def _columns(self, req):
        columns = super(Publications, self)._columns(req)
        if not wiking.module.Application.preview_mode(req):
            columns = [c for c in columns if c != 'published']
        return columns

    def _current_base_uri(self, req, record=None):
        # Use PytisModule._current_base_uri (skip Pages._current_base_uri).
        return super(Pages, self)._current_base_uri(req, record=record)

    def _redirect_after_delete_uri(self, req, record, **kwargs):
        return '/' + req.page_record['identifier'].value(), kwargs

    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid == 'lang':
            return None
        return super(Publications, self)._link_provider(req, uri, record, cid, **kwargs)

    def _binding_visible(self, req, record, binding):
        return (binding.id() != 'chapters' and
                super(Publications, self)._binding_visible(req, record, binding))

    def _publication_export_form(self, req, record):
        if not self._check_page_access(req, record):
            return lcg.Content()

        def script(context, element, form):
            g = context.generator()
            context.resource('wiking-cms.%s.po' % context.lang())
            context.resource('wiking-cms.js')
            return g.script(g.js_call('new wiking.cms.PublicationExportForm', form.form_id()))
        form = wiking.InputForm(
            req, dict(
                fields=(
                    Field('format', _("Format"), not_null=True,
                          enumerator=PublicationExports.Formats,
                          runtime_filter=computer(lambda r: (lambda x: x != 'braille'
                                                             or self.braille_available()))),
                ) + (self.braille_option_fields() +
                     self.epub_option_fields() +
                     self.pdf_option_fields()),
                layout=(
                    'format',
                    self.BRAILLE_EXPORT_OPTIONS_FIELDSET,
                    self.EPUB_EXPORT_OPTIONS_FIELDSET,
                    self.PDF_EXPORT_OPTIONS_FIELDSET,
                    FieldSet(
                        # Translators: "Export" in the sense of generating an output
                        # presentation of a document an the "log" here is a sequence
                        # of messages recorded during the export.
                        _("Export Progress Log"),
                        (lambda r: lcg.HtmlContent(
                            lambda c, e: c.generator().div('', cls='export-progress-log')),),
                    ),
                ),
            ),
            name='PublicationExportForm',
            action='export_publication',
            submit_buttons=(('test', _("Export"), 'gear-icon'),
                            (None, _("Download"), 'circle-down-icon'),),
            show_reset_button=False,
            show_footer=False,
        )
        return lcg.CollapsiblePane(
            _("Current Version Testing Export"),
            (form, lcg.HtmlContent(script, form))
        )

    def _page_content(self, req, record, preview=False):
        def cover_image(context, element):
            if record['cover_image'].value():
                g = context.generator()
                filename_x = record.cb_value('cover_image', 'filename')
                if filename_x is None:
                    return ''
                filename = filename_x.value()
                storage = record.attachment_storage('_content')
                image = storage.resource(filename)
                if image.size():
                    width, height = image.size()
                else:
                    width, height = None, None
                return g.div(g.img(src=image.uri(), alt=image.descr(), width=width, height=height),
                             cls='publication-cover-image')
            else:
                return ''
        return ([self.Navigation('top'),
                 lcg.HtmlContent(cover_image),
                 self._publication_info(req, record)] +
                self._inner_page_content(req, record, preview=preview) +
                [lcg.Section(_("Table of Contents"), lcg.NodeIndex(), in_toc=False),
                 wiking.module.PublicationExports.exported_versions_list(req),
                 self.Navigation('bottom')])

    def _page_actions_content(self, req, record):
        return ([self._publication_export_form(req, record)] +
                super(Publications, self)._page_actions_content(req, record))

    def _publication_info(self, req, record, online=True):
        def format(fid):
            if isinstance(record.type(fid), pd.DateTime):
                return pw.localizable_export(record[fid])
            if isinstance(record.type(fid), pd.Boolean):
                return record[fid].value() and _("Yes") or _("No")
            else:
                value = record.display(fid) or record[fid].export()
                if not isinstance(value, lcg.Localizable):
                    value = '; '.join(record[fid].export().splitlines())
                return value

        def label(fid):
            if fid == 'original_isbn' and record['isbn'].value() is None:
                fid = 'isbn'
            return self._view.field(fid).label()

        def fields(field_ids):
            return [(label(fid) + ':', format(fid))
                    for fid in field_ids if record[fid].value() is not None]

        def watermark(value, name):
            # Use anchor to get <span id="watermark-..."> in HTML output.  This marks the values
            # for later substitution in PublicationExports.action_download().
            return lcg.Anchor('watermark-' + name, value)
        basic_fields = fields(('title', 'description', 'author', 'contributor',
                               'illustrator', 'pubinfo', 'original_isbn', 'lang'))
        extra_fields = fields(('adapted_by', 'adapted_for', 'isbn',))
        if record['isbn'].value() is None:
            extra_fields.extend(fields(('uuid',)))
        if online:
            if record['published'].value():
                extra_fields.extend(fields(('published_since',)))
            else:
                extra_fields.extend(fields(('created', 'published',)))
        else:
            timestamp = now().strftime('%Y-%m-%d %H:%M:%S')
            extra_fields.append((_("Created") + ':',
                                 lcg.LocalizableDateTime(timestamp, utc=True)))
        if record['original_isbn'].value() is None:
            basic_fields.extend(extra_fields)
            extra_fields = ()
        content = [lcg.fieldset(basic_fields)]
        if record['copyright_notice'].value():
            content.append(lcg.p(record['copyright_notice'].value()))
        if extra_fields:
            content.extend((
                lcg.strong(_("Information about this adaptation of the work:")),
                lcg.fieldset(extra_fields)
            ))
        if online and record['notes'].value():
            content.append(lcg.p(lcg.strong(_("Notes") + ':'), ' ', record['notes'].value()))
        # Checking 'format' request param is a quick hack - we currently only support
        # watermarking in EPUB export...
        if not online and req.param('format') == 'epub':
            date = lcg.LocalizableDateTime(now().strftime('%Y-%m-%d %H:%M:%S'), utc=True)
            content.extend((
                lcg.strong(_("Authorization for this copy:")),
                lcg.fieldset(((_("Authorized Person") + ':', watermark(req.user().name(), 'name')),
                              (_("E-mail") + ':', watermark(req.user().email(), 'email')),
                              (_("Date") + ':', watermark(date, 'date'))))
            ))
        return lcg.Container(content)

    def _child_rows(self, req, record, preview=False):
        children = wiking.module.PublicationChapters.child_rows(req,
                                                                record['tree_order'].value(),
                                                                record['lang'].value(),
                                                                preview=preview)
        children[record['parent'].value()] = [record.row()]
        return children

    def _publication(self, req, record, preview=False, toc=False):
        children = self._child_rows(req, record, preview=preview)
        resource_provider = lcg.ResourceProvider(dirs=wiking.cfg.resource_path)
        resources = []

        def node(row, root=False):
            # TODO: Don't ignore content processing error here!
            content = self._inner_page_content(req, self._record(req, row), preview=preview)
            cover_image = None
            if root:
                filename = row['cover_image_filename'].value()
                resources.extend(lcg.Container(content).resources())
                if filename:
                    cover_image = find(filename, resources, key=lambda r: r.filename())
                content.insert(0, self._publication_info(req, record, online=False))
                if toc:
                    content.append(lcg.Section(_("Table of Contents"), lcg.NodeIndex(),
                                               in_toc=False))
                metadata = lcg.Metadata(authors=row['author'].export().splitlines(),
                                        contributors=(row['contributor'].export().splitlines() +
                                                      row['adapted_by'].export().splitlines()),
                                        original_isbn=row['original_isbn'].value(),
                                        isbn=row['isbn'].value(),
                                        uuid=row['uuid'].value(),
                                        publisher=row['publisher'].value(),
                                        published=row['published_year'].export(),)
            else:
                content = lcg.Container(content, resources=resources)
                metadata = None
            return lcg.ContentNode(row['identifier'].value(),
                                   title=row['title'].value(),
                                   content=content,
                                   cover_image=cover_image,
                                   resource_provider=resource_provider,
                                   children=[node(r) for r in
                                             children.get(row['page_id'].value(), ())],
                                   metadata=metadata)
        return node(record.row(), root=True)

    def _export_epub(self, req, record, publication):
        page_id = record['page_id'].value()

        class EpubExporter(lcg.EpubExporter):

            def _get_resource_data(self, context, resource):
                data = wiking.module.Attachments.retrieve(req, page_id, resource.filename())
                if not data:
                    r = wiking.module.Resources.resource(resource.filename())
                    if r:
                        data = r.get()
                if data:
                    return data
                else:
                    raise Exception("Unable to retrieve resource %s." % resource.filename())
        exporter = EpubExporter(translations=wiking.cfg.translation_path)
        context = exporter.context(publication, req.preferred_language(),
                                   allow_interactivity=bool(req.param('allow_interactivity')))
        result = exporter.export(context)
        return result, context.messages()

    def export_publication(self, req, record, export_format, preview=False):
        publication = self._publication(req, record, preview=preview,
                                        # EPUB has automatic navigation so only Braille needs a TOC
                                        toc=export_format == 'braille')
        if export_format == 'epub':
            return self._export_epub(req, record, publication)
        elif export_format == 'braille':
            return self._export_braille(req, publication)
        elif export_format == 'pdf':
            return self._export_pdf(req, record, publication)

    def submenu(self, req):
        # TODO: This partially duplicates Pages.menu() - refactor?
        if not hasattr(req, 'publication_record') or req.publication_record is None:
            return []
        record = req.publication_record

        children = self._child_rows(req, record,
                                    preview=wiking.module.Application.preview_mode(req))
        base_uri = '/%s/data/%s' % (req.page_record['identifier'].value(),
                                    record['identifier'].value())

        def item(row):
            if row['page_id'].value() == record['page_id'].value():
                uri = base_uri
            else:
                uri = base_uri + '/chapters/' + row['identifier'].value()
            return MenuItem(uri,
                            title=row['title'].value(),
                            descr=row['description'].value(),
                            foldable=True,
                            submenu=[item(r) for r in children.get(row['page_id'].value(), ())])
        return [item(row) for row in children[record['parent'].value()]]

    def action_new_chapter(self, req, record):
        raise Redirect(req.uri() + '/chapters', action='insert')

    def action_export_publication(self, req, record):
        preview = wiking.module.Application.preview_mode(req)
        export_format = req.param('format', 'epub')
        data, messages = self.export_publication(req, record, export_format, preview=preview)
        if req.param('submit') == 'test':
            kinds = [x[0] for x in messages]
            summary = lcg.concat(_.ngettext("%d error", "%d errors", kinds.count(lcg.ERROR)),
                                 _.ngettext("%d warning", "%d warnings", kinds.count(lcg.WARNING)),
                                 format_byte_size(len(data)),
                                 separator=', ')
            return wiking.Response(json.dumps({'messages': [(kind, req.localize(msg))
                                                            for kind, msg in messages],
                                               'summary': req.localize(summary)}),
                                   content_type='application/json')
        else:
            if export_format == 'epub':
                content_type = 'application/epub+zip'
                ext = 'epub'
            elif export_format == 'braille':
                content_type = 'application/octet-stream'
                ext = 'brl'
            elif export_format == 'pdf':
                content_type = 'application/pdf'
                ext = 'pdf'
            return wiking.Response(data, content_type=content_type,
                                   filename='%s.%s' % (record['identifier'].value(), ext))


class PublicationChapters(NavigablePages):
    """Publication chapters are regular CMS pages """
    class Spec(Pages.Spec):

        def fields(self):
            override = (
                Field('kind', default='chapter'),
                Field('parent', not_null=True, editable=ALWAYS,
                      runtime_filter=computer(self._parent_filter),
                      computer=computer(lambda r: r.req().publication_record['page_id'].value()),
                      descr=_("Select the superordinate chapter in hierarchy.")),
                Field('published', default=True),
            )
            extra = (
                Field('excerpt_title', _("Excerpt title"), virtual=True,
                      type=pd.String(not_null=True)),
                ContentField('excerpt_content', _("Excerpt"), compact=True,
                             height=20, width=80, type=pd.String(), virtual=True,
                             attachment_storage=self._attachment_storage),
            )
            return self._inherited_fields(PublicationChapters.Spec, override=override) + extra

        def _default_identifier(self, record, title):
            identifier = super(PublicationChapters.Spec, self)._default_identifier(record, title)
            if title and record['identifier'].value() is None:
                identifier = '%s-%s' % (record['parent'].export(), identifier)
            return identifier

        def _parent_filter(self, record, site):
            publication = record.req().publication_record
            return pd.AND(pd.EQ('site', pd.sval(site)),
                          pd.OR(pd.EQ('page_id', publication['page_id']),
                                pd.WM('tree_order',
                                      pd.WMValue(pd.String(),
                                                 '%s.*' % publication['tree_order'].value())))
                          )

        def _attachment_storage(self, record):
            req = record.req()
            return Attachments.AttachmentStorage(req,
                                                 req.publication_record['page_id'].value(),
                                                 record['lang'].value(),
                                                 '/%s/data/%s/attachments' %
                                                 (req.page_record['identifier'].value(),
                                                  req.publication_record['identifier'].value()))
        bindings = (
            Binding('attachments', _("Attachments"), 'Attachments',
                    condition=(lambda r:
                               pd.EQ('page_id', pd.ival(r.req().publication_record['page_id']
                                                        .value()))),
                    prefill=lambda r: dict(page_id=r.req().publication_record['page_id'].value())),
        ) + tuple([_b for _b in Pages.Spec.bindings if _b.id() != 'attachments']) + (
            Binding('excerpts', _("Excerpts"), 'CmsPageExcerpts', 'page_id'),
        )
        condition = pd.EQ('kind', pd.sval('chapter'))
        columns = ('title', 'status')
        sorting = ('ord', pd.ASCENDENT),
        actions = NavigablePages.Spec.actions + (
            Action('excerpt', _("Store Excerpt")),
        )

    _INSERT_LABEL = _("New Chapter")
    _INSERT_MSG = _("New chapter was successfully created.")
    _UPDATE_MSG = _("The chapter was successfully updated.")

    def _authorized(self, req, action, record=None, **kwargs):
        if action in ('view',):
            return req.page_read_access
        elif action in ('insert', 'update', 'options', 'commit', 'revert', 'delete', 'excerpt',):
            return req.page_write_access
        else:
            return False  # raise NotFound or BadRequest?

    def _layout(self, req, action, record=None):
        if action == 'insert':
            return ('title', 'description', '_content', 'parent', 'ord', 'published')
        elif action == 'options':
            return ('parent', 'ord', 'published')
        elif action == 'excerpt':
            return ('excerpt_title', '_content', 'excerpt_content',)
        else:
            return super(PublicationChapters, self)._layout(req, action, record=record)

    def _submit_buttons(self, req, action, record=None):
        if action == 'excerpt':
            return ((None, _("Store")),)
        else:
            return super(PublicationChapters, self)._submit_buttons(req, action, record=record)

    def _update(self, req, record, transaction):
        if req.param('action') == 'excerpt':
            lang = record['lang']
            if lang.value() is not None:
                lang = pd.sval(req.preferred_language())
            wiking.module.CmsPageExcerpts.store_excerpt(req, record['page_id'], lang,
                                                        record['excerpt_title'],
                                                        record['excerpt_content'])
        else:
            super(PublicationChapters, self)._update(req, record, transaction)

    def _current_base_uri(self, req, record=None):
        # Use PytisModule._current_base_uri (skip Pages._current_base_uri).
        return super(Pages, self)._current_base_uri(req, record=record)

    def child_rows(self, req, tree_order, lang, preview=False):
        children = {}
        conditions = [
            pd.WM('tree_order', pd.WMValue(pd.String(), '%s.*' % tree_order)),
            pd.EQ('lang', pd.sval(lang)),
            pd.EQ('site', pd.sval(wiking.cfg.server_hostname)),
        ]
        if not preview:
            conditions.extend((
                pd.EQ('published', pd.bval(True)),
                pd.EQ('parents_published', pd.bval(True)),
            ))
        for row in self._data.get_rows(condition=pd.AND(*conditions),
                                       sorting=(('tree_order', pd.ASCENDENT),)):
            children.setdefault(row['parent'].value(), []).append(row)
        return children

    def action_excerpt(self, req, record):
        return self.action_update(req, record, action='excerpt')


class PublicationExports(ContentManagementModule):
    """e-Publication exported versions."""
    class Formats(pp.Enumeration):
        enumeration = (
            # ('html', _("HTML")),
            ('epub', _("EPUB")),
            ('braille', _("Braille")),
            ('pdf', _("PDF")),
        )
        default = 'epub'
        selection_type = RADIO
        orientation = pp.Orientation.HORIZONTAL

    class Spec(Specification):
        title = _("Exported Publication Versions")
        table = wiking.dbdefs.cms_v_publication_exports

        def fields(self):
            override = (
                Field('page_key', codebook='Publications', selection_type=CHOICE),
                Field('format', _("Format"), enumerator=PublicationExports.Formats),
                Field('version', _("Version"),
                      type=pd.RegexString(maxlen=64, regex=r'^[0-9a-zA-Z\.\-]+$'),
                      descr=_("Version number and optional variant identifiers.  The whole string "
                              "is used as a part of the output file name, so it should only "
                              "contain digits, letters, dashes and periods.  Version number may "
                              "consist of major and minor version numbers, such as 2.4, where 2 "
                              "is the major version and 4 is the minor version.  Major version "
                              "typically changes on significant changes while minor version "
                              "changes on fixes and less significant changes.  Variant identifier "
                              "may be used for example to distinguish exported variants for "
                              "different purposes, such as various braille formats and sizes. "
                              "Example version string may be '2.4-evernote' to denote the target "
                              "Braille printer.  The final file name will be "
                              "'publication-identifier-2.4-evernote.brl' in this case. "
                              "Use creatively to distinguish between different exported versions "
                              "but take care decide for one versioning scheme and use it "
                              "consistently throughout your publications.")),
                Field('timestamp', _("Created"), default=now),
                Field('public', _("Public"), default=True,
                      descr=_("If checked, this export will be available to anyone having access "
                              "to the publication, otherwise only editors (with read/write "
                              "access) will see it.")),
                Field('bytesize', _("Size"), formatter=format_byte_size),
                Field('notes', _("Notes"), width=80,
                      descr=_("Short text describing this exported version and/or variant. "
                              "Leave empty if there is nothing important to note.")),
            )
            return (self._inherited_fields(PublicationExports.Spec, override=override) +
                    BrailleExporter.braille_option_fields(virtual=True) +
                    Publications.epub_option_fields(virtual=True) +
                    Publications.pdf_option_fields(virtual=True))
        layout = ('format', 'version', 'timestamp', 'bytesize', 'public', 'notes')
        columns = ('format', 'version', 'timestamp', 'bytesize', 'public')
        actions = (
            Action('download', _("Download"), icon='circle-down-icon'),
        )

    # See note in Publications._publication_info() where these spans are created.
    _WATERMARK_SUBSTITUTION_REGEX = re.compile(r'<span id="watermark-([a-z]+)">([^<]*)</span>')
    _ROW_ACTIONS = True

    def _authorized(self, req, action, record=None, **kwargs):
        if action == 'download' and record['public'].value():
            return self._check_publication_download_access(req)
        if action in ('list', 'view', 'insert', 'update', 'delete', 'download'):
            return req.page_write_access
        else:
            return False

    def _check_publication_download_access(self, req):
        if req.page_write_access:
            return True
        else:
            role_id = req.publication_record['download_role_id'].value()
            if role_id:
                return req.check_roles(wiking.module.Users.Roles()[role_id])
            else:
                return False

    def _layout(self, req, action, record=None):
        if action == 'insert':
            return ('format',
                    Publications.BRAILLE_EXPORT_OPTIONS_FIELDSET,
                    Publications.EPUB_EXPORT_OPTIONS_FIELDSET,
                    Publications.PDF_EXPORT_OPTIONS_FIELDSET,
                    'version', 'public', 'notes')
        elif action == 'view':
            return (self.Spec.layout,
                    FieldSet(_("Export Progress Log"),
                             (lambda r: lcg.HtmlContent(self._render_export_messages, r),)))
        else:
            return super(PublicationExports, self)._layout(req, action, record=record)

    def _render_export_messages(self, context, element, record):
        # Note: This code partially duplicates the Javascript code in
        # wiking.cms.PublicationExportForm.on_test_result().  At least we
        # need to keep the html structure consistent because of the styles.
        g = context.generator()
        messages = json.loads(record['log'].value() or '[]')
        kinds = [x[0] for x in messages]
        labels = {lcg.WARNING: _("Warning"),
                  lcg.ERROR: _("Error")}
        return (
            g.div([g.div((g.span(labels[kind] + ':', cls='label') + ' '
                          if kind in labels else '') +
                         message,
                         cls=kind.lower() + '-msg')
                   for kind, message in messages],
                  cls='export-progress-log') +
            g.div(lcg.format('%s %s, %s',
                             g.span(_("Summary") + ':', cls='label'),
                             _.ngettext("%d error", "%d errors", kinds.count(lcg.ERROR)),
                             _.ngettext("%d warning", "%d warnings", kinds.count(lcg.WARNING))),
                  cls='export-progress-summary')
        )

    def _insert_form_content(self, req, form, record):
        def script(context, element):
            g = context.generator()
            context.resource('wiking-cms.%s.po' % context.lang())
            context.resource('wiking-cms.js')
            return g.script(g.js_call('new wiking.cms.PublicationExportForm', form.form_id()))
        return [form, lcg.HtmlContent(script)]

    def _file_path(self, req, record):
        fname = record['export_id'].export() + '.' + record['format'].export()
        return os.path.join(wiking.cms.cfg.storage, wiking.cfg.dbname, 'exports', fname)

    def _insert_transaction(self, req, record):
        return self._transaction()

    def _insert(self, req, record, transaction):
        publication_record = req.publication_record
        data, messages = wiking.module.Publications.export_publication(req, publication_record,
                                                                       record['format'].value())
        children = wiking.module.PublicationChapters.child_rows(
            req, publication_record['tree_order'].value(), publication_record['lang'].value(),
            preview=True)
        messages.extend([(lcg.WARNING, _("Unpublished chapter: %s", row['title'].value()))
                         for row in reduce(operator.add, children.values(), [])
                         if row['parents_published'].value() and not row['published'].value()])
        bytesize = len(data)
        for key, value in (('page_id', publication_record['page_id'].value()),
                           ('lang', publication_record['lang'].value()),
                           ('bytesize', bytesize),
                           ('log', json.dumps([(x, req.localize(msg)) for x, msg in messages]))):
            record[key] = pd.Value(record.type(key), value)
        super(PublicationExports, self)._insert(req, record, transaction)
        path = self._file_path(req, record)
        directory = os.path.split(path)[0]
        if not os.path.exists(directory):
            os.makedirs(directory, 0o700)
        log(OPERATIONAL, "Saving file:", (path, format_byte_size(bytesize)))
        f = open(path, 'wb')
        try:
            f.write(data)
        finally:
            f.close()

    def _redirect_after_insert(self, req, record):
        req.message(self._insert_msg(req, record), req.SUCCESS)
        raise Redirect(self._current_record_uri(req, record))

    def action_download(self, req, record):
        if req.cached_since(record['timestamp'].value()):
            raise wiking.NotModified()
        export_format = record['format'].value()
        identifier = req.publication_record['identifier'].value()
        filename_template = '%s-%s.%%s' % (identifier, record['version'].value())
        path = self._file_path(req, record)
        if export_format == 'epub':
            import zipfile
            titlepage = 'rsrc/%s.xhtml' % identifier
            src_zip = zipfile.ZipFile(path, mode='r')
            try:
                if self._WATERMARK_SUBSTITUTION_REGEX.search(src_zip.read(titlepage)):
                    date = lcg.LocalizableDateTime(now().strftime('%Y-%m-%d %H:%M:%S'), utc=True)
                    user = req.user()
                    # Visible watermark substitutions (the exported HTML must contain
                    # placeholders created in Publications._publication_info()).
                    substitutions = dict(name=' '.join((user.firstname(), user.surname())),
                                         email=user.email(),
                                         date=req.localize(date))
                    # Simple invisible watermark (relying on known LCG export constructs).
                    replacement = ('<div id="heading">',
                                   '<div id="heading" class="heading-%d">' % user.uid())
                    result = io.BytesIO()
                    dst_zip = zipfile.ZipFile(result, 'w')
                    try:
                        for item in src_zip.infolist():
                            data = src_zip.read(item.filename)
                            if item.filename == titlepage:
                                data = self._WATERMARK_SUBSTITUTION_REGEX.sub(
                                    lambda match: substitutions[match.group(1)],
                                    data,
                                )
                            if item.filename.endswith('.xhtml'):
                                data = data.replace(*replacement)
                            dst_zip.writestr(item, data)
                    finally:
                        dst_zip.close()
                    return wiking.Response(result.getvalue(), content_type='application/epub+zip',
                                           filename=filename_template % 'epub')
                else:
                    return wiking.serve_file(req, path, content_type='application/epub+zip',
                                             filename=filename_template % 'epub')
            finally:
                src_zip.close()
        elif export_format == 'braille':
            return wiking.serve_file(req, path, content_type='application/octet-stream',
                                     filename=filename_template % 'brl')
        elif export_format == 'pdf':
            raise wiking.AuthorizationError(_("PDF download not yet supported."))

    def exported_versions_list(self, req):
        def export(context, element, rows):
            g = context.generator()
            req = context.req()
            formats = dict(PublicationExports.Formats.enumeration)
            base_uri = req.uri() + '/exports/'
            return g.div((
                g.h2(_("Available Download Versions")),
                g.ul(*[g.li(g.a(_("%(format)s version %(version)s",
                                  format=formats[row['format'].value()],
                                  version=row['version'].value()),
                                href=req.make_uri(base_uri + row['export_id'].export(),
                                                  action='download')) + ' ' +
                            lcg.format("(%(bytesize)s, %(timestamp)s) %(notes)s",
                                       timestamp=pw.localizable_export(row['timestamp']),
                                       bytesize=format_byte_size(row['bytesize'].value()),
                                       notes=row['notes'].export()))
                       for row in rows]),
            ), cls='publication-exports')
        if self._check_publication_download_access(req):
            rows = self._data.get_rows(page_id=req.publication_record['page_id'].value(),
                                       public=True, sorting=(('timestamp', pd.DESCENDANT),))
            if rows:
                return lcg.HtmlContent(export, rows)
        return lcg.Content()


class PageHistory(ContentManagementModule):
    """History of page content changes."""
    class Spec(Specification):
        table = 'cms_v_page_history'

        def fields(self):
            return (
                Field('history_id'),
                Field('page_key', not_null=True, codebook='Pages', selection_type=CHOICE),
                Field('page_id'),
                Field('lang'),
                Field('uid', not_null=True, codebook='Users', selection_type=CHOICE,
                      inline_referer='login'),
                Field('login'),
                Field('user', _("Changed by"), computer=pp.CbComputer('uid', 'user_')),
                Field('timestamp', _("Date"), utc=True),
                Field('comment', _("Comment")),
                Field('content'),
                Field('inserted_lines', _("Inserted lines")),
                Field('changed_lines', _("Changed lines")),
                Field('deleted_lines', _("Deleted lines")),
                Field('changes', _("Inserted / Changed / Deleted Lines")),
                Field('diff_add', _("Inserted"), virtual=True,
                      computer=computer(lambda r: _("Green"))),
                Field('diff_chg', _("Changed"), virtual=True,
                      computer=computer(lambda r: _("Yellow"))),
                Field('diff_sub', _("Deleted"), virtual=True,
                      computer=computer(lambda r: _("Red"))),
            )
        sorting = (('timestamp', pd.DESCENDANT),)
        columns = ('timestamp', 'user', 'comment', 'changes')
        # actions = (
        #     Action('diff', _("Show differences against the current version")),
        #     )

    _ASYNC_LOAD = True

    def _authorized(self, req, action, **kwargs):
        if action in ('list', 'view'):
            return req.page_write_access
        else:
            return False

    def _document_title(self, req, record):
        if record:
            page_title = self._binding_forward(req).arg('title')
            dt = record['timestamp'].value().strftime('%Y-%m-%d %H:%M:%S')
            return page_title + ' :: ' + _("Changed on %s", lcg.LocalizableDateTime(dt, utc=True))
        else:
            return super(PageHistory, self)._document_title(req, record)

    def _layout(self, req, action, record=None):
        if action == 'view':
            return (
                ('comment',),
                HGroup(
                    FieldSet(_("Change Summary"),
                             ('inserted_lines', 'changed_lines', 'deleted_lines')),
                    FieldSet(_("Colors"), ('diff_add', 'diff_chg', 'diff_sub')),
                ),
                self._diff,
            )
        else:
            return super(PageHistory, self)._layout(req, action, record=record)

    def _diff(self, record):
        req = record.req()
        rows = self._rows(req, condition=pd.AND(pd.EQ('page_key', record['page_key']),
                                                pd.LT('history_id', record['history_id'])),
                          sorting=(('history_id', pd.DESCENDANT),), limit=1)
        if rows:
            row = rows[0]
            text1 = row['content'].value()
            text2 = record['content'].value() or ''
            if text1 == text2:
                content = lcg.p(_("No differences against previous version."))
            else:
                name1 = (_("Original version") +
                         lcg.format(" (%s %s)", row['user'].value(), row['timestamp'].export()))
                name2 = (_("Modified version") +
                         lcg.format(" (%s %s)", record['user'].value(),
                                    record['timestamp'].export()))
                diff = difflib.HtmlDiff(wrapcolumn=80)
                content = lcg.HtmlContent(diff.make_table(text1.splitlines(),
                                                          text2.splitlines(),
                                                          req.localize(name1),
                                                          req.localize(name2),
                                                          context=True,
                                                          numlines=3))
        else:
            content = lcg.p(_("Previous version empty (no differences available)."))
        return content

    def on_page_change(self, req, page, transaction):
        """Insert a new history item if the page text has changed."""
        original_text = page.original_row()['_content'].value() or ''
        new_text = page['_content'].value() or ''
        if page.new() or new_text != original_text:
            matcher = difflib.SequenceMatcher(lambda x: False,
                                              original_text.splitlines(), new_text.splitlines())
            inserted = changed = deleted = 0
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                a, b = i2 - i1, j2 - j1
                if tag == 'insert':
                    inserted += b
                elif tag == 'delete':
                    deleted += a
                elif tag == 'replace':
                    if a > b:
                        changed += b
                        inserted += b - a
                    else:
                        changed += a
                        deleted += a - b
            row = self._data.make_row(
                history_id=pytis.util.nextval('cms_page_history_history_id_seq')(),
                page_id=page['page_id'].value(),
                lang=page['lang'].value(),
                uid=req.user().uid(),
                timestamp=now(),
                comment=page['comment'].value() or page.new() and _("Initial version") or None,
                content=new_text,
                inserted_lines=inserted,
                changed_lines=changed,
                deleted_lines=deleted)
            result, success = self._data.insert(row, transaction=transaction)
            if not success:
                raise pd.DBException(result)


class Attachments(ContentManagementModule):
    """Attachments are external files (documents, images, media, ...) attached to CMS pages.

    Pytis supports storing binary data types directly in the database, however the current
    implementation is unfortunately too slow for web usage.  Thus we work around that making the
    field virtual, storing its value in a file and loading it back through a 'computer'.

    """

    class Spec(Specification):

        class _FakeFile(str):
            """The string value determines the file path, len() returns its size."""

            def __len__(self):
                try:
                    info = os.stat(self)
                except OSError:
                    return 0
                else:
                    return info.st_size

        # Translators: Section title. Attachments as in email attachments.
        title = _("Attachments")
        table = 'cms_v_page_attachments'

        def fields(self):
            return (
                Field('attachment_key',
                      computer=computer(lambda r, attachment_id, lang:
                                        attachment_id and '%d.%s' % (attachment_id, lang))),
                Field('attachment_id'),
                Field('page_id', _("Page"), not_null=True, editable=ALWAYS,
                      codebook='PageStructure', selection_type=CHOICE,
                      runtime_filter=computer(lambda r: pd.EQ('site',
                                                              pd.sval(wiking.cfg.server_hostname))),
                      descr=_("Select the page where you want to move this attachment.  "
                              "Don't forget to update all explicit links to "
                              "this attachment within page text(s).")),
                Field('lang', _("Language"), not_null=True, editable=ONCE,
                      codebook='Languages', selection_type=CHOICE, value_column='lang'),
                # Translators: Noun. File on disk. Computer terminology.
                Field('upload', _("File"), virtual=True, editable=ALWAYS,
                      type=pd.Binary(not_null=True, maxlen=wiking.cms.cfg.upload_limit),
                      descr=_("Upload a file from your local system.  The file name will be used "
                              "to refer to the attachment within the page content.  Please note "
                              "that the file will be served over the internet, so the filename "
                              "should not contain any special characters.  Letters, digits, "
                              "underscores, dashes and dots are safe.  "
                              "You risk problems with most other characters.")),
                Field('fake_file', _("File"), virtual=True,
                      # Hack: To avoid reading the file into memory in ShowForm,
                      # this field is represented as pytis.web.FileField thanks to
                      # the 'filename' specification.  The field is represented as
                      # "filename (size)" in the UI and _FakeFile reports its size
                      # as the size of the file.
                      computer=computer(lambda r, file_path: self._FakeFile(file_path)),
                      filename=lambda r: r['filename'].value()),
                Field('filename', _("Filename"),
                      computer=computer(lambda r, upload: upload and upload.filename() or None),
                      type=pd.RegexString(maxlen=64, not_null=True, regex=r'^[0-9a-zA-Z_\.-]*$')),
                Field('mime_type', _("MIME type"), width=22,
                      computer=computer(lambda r, upload: upload and upload.mime_type() or None)),
                Field('title', _("Title"), width=30, maxlen=64,
                      descr=_("The name of the attachment (e.g. the full name of the document). "
                              "If empty, the file name will be used instead.")),
                Field('description', _("Description"), height=3, width=60, maxlen=240,
                      descr=_("Optional description used for the listing of attachments "
                              "(see below).")),
                Field('created', _("Created"), editable=pp.Editable.NEVER, default=now),
                Field('last_modified', _("Last Modified"), editable=pp.Editable.NEVER, default=now,
                      computer=computer(self._last_modified)),
                Field('ext', virtual=True, computer=computer(self._ext)),
                # Translators: Size of a file, in number of bytes, kilobytes etc.
                Field('bytesize', _("Size"),
                      computer=computer(self._bytesize),
                      formatter=format_byte_size),
                Field('thumbnail', '', type=pd.Image(), computer=computer(self._thumbnail)),
                # Translators: Thumbnail is a small image preview in computer terminology.
                Field('thumbnail_size', _("Preview size"), not_null=False,
                      enumerator=enum(('small', 'medium', 'large')), default='medium',
                      display=self._thumbnail_size_display, prefer_display=True,
                      null_display=_("Full size (don't resize)"),
                      selection_type=RADIO,
                      descr=_("Only relevant for images.  When set, the image will not be "
                              "displayed in full size, but as a small clickable preview.")),
                # thumbnail_size is the desired maximal width (the corresponding
                # pixel width may change with configuration option
                # wiking.cms.cfg.image_thumbnail_sizes), while thumbnail_width and
                # thumbnail_height reflect the actual size of the thumbnail when it
                # is generated (they also reflect the image aspect ratio).
                Field('thumbnail_width', computer=computer(self._thumbnail_width)),
                Field('thumbnail_height', computer=computer(self._thumbnail_height)),
                Field('image', type=pd.Image(), computer=computer(self._resized_image)),
                Field('image_width', computer=computer(self._resized_image_width)),
                Field('image_height', computer=computer(self._resized_image_height)),
                Field('width', computer=computer(self._orig_width)),
                Field('height', computer=computer(self._orig_height)),
                Field('in_gallery', _("In Gallery"),
                      # editable=computer(lambda r, thumbnail_size: thumbnail_size is not None),
                      # The computer doesn't work (probably a PresentedRow issue?).
                      # computer=computer(lambda r, thumbnail_size: thumbnail_size is not None),
                      descr=_("Check if you want the image to appear in an image Gallery "
                              "below the page text.")),
                Field('listed', _("Listed"), default=False,
                      descr=_("Check if you want the item to appear in the listing of attachments "
                              "at the bottom of the page.")),
                # Field('author', _("Author"), width=30),
                # Field('location', _("Location"), width=50),
                # Field('exif_date', _("EXIF date")),
                Field('file_path', virtual=True, computer=computer(self._file_path)),
                Field('archive', _("Archive"), virtual=True,
                      type=pd.Binary(not_null=True, maxlen=1000 * wiking.cms.cfg.upload_limit),
                      descr=_("Upload multiple attachments at once "
                              "as a ZIP, TAR or TAR.GZ archive.")),
                Field('overwrite', _("Overwrite existing files"), virtual=True,
                      type=pd.Boolean(not_null=True),
                      descr=_("If checked, the existing attachments will be updated when "
                              "the archive contains files of the same name.")),
                Field('retype', _("Change file types"), virtual=True,
                      type=pd.Boolean(not_null=True),
                      editable=computer(lambda r, overwrite: overwrite),
                      descr=_("If checked, the files to overwrite will be matched by name "
                              "without extension instead of full file name.  This makes it "
                              "possible to change types of some files, such as replace "
                              "JPEGs by PNGs (file 'xy.png' replaces an existing file "
                              "'xy.jpg' because their names without extension match).")),
            )

        def _ext(self, record, filename):
            if filename is None:
                return ''
            else:
                ext = filename and os.path.splitext(filename)[1].lower()
                return len(ext) > 1 and ext[1:] or ext

        def _image(self, data):
            # Return PIL.Image instance if 'data' is an image or None if not.
            import PIL.Image
            if data is None:
                return None
            f = io.BytesIO(data)
            try:
                return PIL.Image.open(f)
            except IOError:
                return None

        def _resize(self, data, size):
            # Return PIL.Image resized to given size if 'data' is an image or None if not.
            image = self._image(data)
            if image:
                import PIL.Image
                img = image.copy()
                img.thumbnail(size, PIL.Image.LANCZOS)
                stream = io.BytesIO()
                img.save(stream, image.format)
                return stream.getvalue()
            else:
                return None

        def _resized_image(self, record, upload):
            return self._resize(upload, wiking.cms.cfg.image_screen_size)

        def _file_data(self, record):
            with open(record['file_path'].value(), 'rb') as f:
                return f.read()

        def _thumbnail(self, record, upload, thumbnail_size):
            if thumbnail_size == 'small':
                size = wiking.cms.cfg.image_thumbnail_sizes[0]
            elif thumbnail_size == 'medium':
                size = wiking.cms.cfg.image_thumbnail_sizes[1]
            elif thumbnail_size == 'large':
                size = wiking.cms.cfg.image_thumbnail_sizes[2]
            else:
                return None
            if upload:
                image = upload
            elif record['attachment_id'].value() is not None:
                image = self._file_data(record)
            else:
                image = None
            return self._resize(image, (size, size))

        def _thumbnail_width(self, record, thumbnail):
            return thumbnail.image().size[0] if thumbnail else None

        def _thumbnail_height(self, record, thumbnail):
            return thumbnail.image().size[1] if thumbnail else None

        def _resized_image_width(self, record, image):
            return image.image().size[0] if image else None

        def _resized_image_height(self, record, image):
            return image.image().size[1] if image else None

        def _orig_width(self, record, upload):
            image = self._image(upload)
            return image.size[0] if image else None

        def _orig_height(self, record, upload):
            image = self._image(upload)
            return image.size[1] if image else None

        def _file_path(self, record, attachment_id, ext):
            fname = str(attachment_id) + '.' + ext
            return os.path.join(wiking.cms.cfg.storage, wiking.cfg.dbname, 'attachments', fname)

        def _thumbnail_size_display(self, size):
            # Translators: Size label related to "Preview size" field (pronoun).
            labels = {'small': _("Small") + " (%dpx)" % wiking.cms.cfg.image_thumbnail_sizes[0],
                      'medium': _("Medium") + " (%dpx)" % wiking.cms.cfg.image_thumbnail_sizes[1],
                      'large': _("Large") + " (%dpx)" % wiking.cms.cfg.image_thumbnail_sizes[2]}
            return labels.get(size, size)

        def _last_modified(self, record, upload):
            if record.field_changed('upload'):
                return now()
            else:
                return record['last_modified'].value()

        def _bytesize(self, record, upload):
            if upload:
                return len(upload)
            else:
                return None

        columns = ('filename', 'title', 'bytesize', 'created', 'last_modified',
                   'in_gallery', 'listed', 'page_id')
        sorting = (('filename', ASC),)

        actions = (
            # Action('insert_image', _("New image"), descr=_("Insert a new image attachment"),
            #        context=pp.ActionContext.GLOBAL),
            # Translators: Button label
            Action('move', _("Move"), icon='circle-out-icon',
                   descr=_("Move the attachment to another page.")),
            Action('upload_archive', _("Upload Archive"), icon='circle-in-up-icon',
                   context=pp.ActionContext.GLOBAL,
                   descr=_("Upload multiple attachments at once as a ZIP, TAR or TAR.GZ archive.")),
        )

    class AttachmentStorage(pp.AttachmentStorage):

        def __init__(self, req, page_id, lang, base_uri):
            self._req = req
            self._page_id = page_id
            self._lang = lang
            self._base_uri = base_uri

        def _api_call(self, name, *args, **kwargs):
            method = getattr(wiking.module.Attachments, 'storage_api_' + name)
            return method(self._req, self._page_id, self._lang, *args, **kwargs)

        def _row_resource(self, row):
            if row['thumbnail_size'].value():
                thumbnail_size = (row['thumbnail_width'].value(), row['thumbnail_height'].value())
            else:
                thumbnail_size = None
            if row['image_width'].value() and row['image_height'].value():
                size = (row['image_width'].value(), row['image_height'].value())
            else:
                size = None
                log(OPERATIONAL, "{}: Unknown size: Run bin/update-thumbnails.py to fix that."
                    .format(row['filename'].value()))
            return self._resource(row['filename'].value(),
                                  title=row['title'].value(),
                                  descr=row['description'].value(),
                                  info=dict(mime_type=row['mime_type'].value(),
                                            byte_size=row['bytesize'].value(),
                                            listed=row['listed'].value(),
                                            in_gallery=row['in_gallery'].value(),
                                            thumbnail_size=row['thumbnail_size'].value()),
                                  size=size,
                                  has_thumbnail=thumbnail_size is not None,
                                  thumbnail_size=thumbnail_size)

        def _resource_uri(self, filename):
            return self._req.make_uri(self._base_uri + '/' + filename, action='download')

        def _image_uri(self, filename):
            return self._req.make_uri(self._base_uri + '/' + filename, action='image')

        def _thumbnail_uri(self, filename):
            return self._req.make_uri(self._base_uri + '/' + filename, action='thumbnail')

        def resource(self, filename):
            row = self._api_call('row', filename)
            if row:
                return self._row_resource(row)
            else:
                return None

        def resources(self):
            return [self._row_resource(row) for row in self._api_call('rows')]

        def insert(self, filename, data, values):
            return self._api_call('insert', filename, data, values)

        def update(self, filename, values):
            return self._api_call('update', filename, values)

        def retrieve(self, filename):
            # Currently unused by the web form attachment dialog.
            pass

    _INSERT_LABEL = _("New attachment")
    _REFERER = 'filename'
    _LIST_BY_LANGUAGE = True
    _SEQUENCE_FIELDS = (('attachment_id', 'cms_page_attachments_attachment_id_seq'),)
    _EXCEPTION_MATCHERS = (
        (r'duplicate key (value )?violates unique constraint "cms_page_attachments_filename_key"',
         ('upload', _("Attachment of the same file name already exists for this page."))),
        (r'value too long for type character varying\(64\)',
         ('upload', _("Attachment file name exceeds the maximal length 64 characters."))),
    )
    _ROW_ACTIONS = True
    _ASYNC_LOAD = True

    def _delayed_init(self):
        super(Attachments, self)._delayed_init()
        self._non_binary_columns = [c.id() for c in self._data.columns()
                                    if not isinstance(c.type(), pd.Binary)]

    def _default_action(self, req, record=None):
        if record and self._current_base_uri(req, record).endswith('/attachments'):
            # When accessing through /<page-id>/attachments/<filename.ext>, just download.
            return 'download'
        else:
            return super()._default_action(req, record=record)

    def _authorized(self, req, action, record=None, **kwargs):
        if action in ('image', 'download', 'thumbnail'):
            return req.page_read_access
        elif self._current_base_uri(req, record).endswith('/attachments-management'):
            # See Pages.Spec.bindings for diferences in access through /<page_id>/attachments/
            # and /<page_id>/attachments-management/
            if action in ('list', 'view', 'insert', 'upload_archive', 'update', 'delete', 'move'):
                return req.page_write_access
        return False

    def _cell_editable(self, req, record, cid):
        if cid in ('title', 'in_gallery', 'listed'):
            return self._authorized(req, 'update', record=record)
        else:
            return False

    def _layout(self, req, action, record=None):
        if action == 'move':
            return ('page_id',)
        elif action == 'upload_archive':
            return ('archive', 'overwrite', 'retype')
        else:
            if action in ('insert', 'update'):
                f = 'upload'
            else:
                f = 'fake_file'
            layout = [f, 'title', 'description', 'thumbnail_size', 'in_gallery', 'listed']
            if record and not record['mime_type'].value().startswith('image/'):
                layout.remove('thumbnail_size')
                layout.remove('in_gallery')
            return layout
        return super(Attachments, self)._layout(req, action, record=record)

    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid == 'fake_file':
            return self._link_provider(req, uri, record, None, action='download')
        return super(Attachments, self)._link_provider(req, uri, record, cid, **kwargs)

    def _image_provider(self, req, uri, record, cid):
        if cid == 'fake_file':
            if record['mime_type'].value().startswith('image/'):
                return self._link_provider(req, uri, record, None, action='thumbnail')
            else:
                return None
        return super(Attachments, self)._image_provider(req, uri, record, cid)

    def _tooltip_provider(self, req, uri, record, cid):
        if cid == 'filename':
            if record['mime_type'].value().startswith('image/'):
                return self._link_provider(req, uri, record, None, action='thumbnail')
            else:
                return None
        return super(Attachments, self)._tooltip_provider(req, uri, record, cid)

    def _binding_column(self, req):
        column, value = super(Attachments, self)._binding_column(req)
        if not column:
            # If the parent page is not the in binding column, it is in the
            # binding prefill, see PublicationChapters.Spec.bindings...
            fw = self._binding_forward(req)
            binding, record = fw.arg('binding'), fw.arg('record')
            column, value = 'page_id', binding.prefill()(record)['page_id']
        return column, value

    def _save_attachment_file(self, record):
        storage = wiking.cms.cfg.storage
        if not os.path.exists(storage) or not os.access(storage, os.W_OK):
            import getpass
            raise Exception("The configuration option 'storage' points to '%(storage)s', but this "
                            "directory does not exist or is not writable by user '%(user)s'." %
                            dict(storage=storage, user=getpass.getuser()))
        path = record['file_path'].value()
        directory = os.path.split(path)[0]
        if not os.path.exists(directory):
            os.makedirs(directory, 0o700)
        value = record['upload'].value()
        if value is not None:
            log(OPERATIONAL, "Saving file:", (path, format_byte_size(len(value))))
            with open(path, 'wb') as f:
                f.write(value)

    def _insert_transaction(self, req, record):
        return self._transaction()

    def _insert(self, req, record, transaction):
        super(Attachments, self)._insert(req, record, transaction)
        self._save_attachment_file(record)

    def _update_transaction(self, req, record):
        return self._transaction()

    def _update(self, req, record, transaction):
        super(Attachments, self)._update(req, record, transaction)
        self._save_attachment_file(record)

    def _delete_transaction(self, req, record):
        return self._transaction()

    def _delete(self, req, record, transaction):
        super(Attachments, self)._delete(req, record, transaction)
        path = record['file_path'].value()
        if os.path.exists(path):
            os.unlink(path)

    def _redirect_after_update_uri(self, req, record, **kwargs):
        if req.param('__invoked_from') == 'ShowForm':
            # The URI /page/attachments/x.jpg displays the image itself so we
            # need to add the explicit action, but not when invoked from list.
            kwargs['action'] = 'view'
        return super(Attachments, self)._redirect_after_update_uri(req, record, **kwargs)

    def storage_api_row(self, req, page_id, lang, filename):
        return self._data.get_row(columns=self._non_binary_columns,
                                  page_id=page_id, lang=lang, filename=filename)

    def storage_api_rows(self, req, page_id, lang):
        self._data.select(columns=self._non_binary_columns,
                          condition=pd.AND(pd.EQ('page_id', pd.ival(page_id)),
                                           pd.EQ('lang', pd.sval(lang))),
                          sort=self._sorting)
        while True:
            row = self._data.fetchone()
            if row is None:
                break
            yield row
        self._data.close()

    def storage_api_insert(self, req, page_id, lang, filename, data, values):
        prefill = dict(page_id=page_id, lang=lang, listed=False)
        record = self._record(req, None, new=True, prefill=prefill)
        error = record.validate('upload', data, filename=filename,
                                mime_type=values.pop('mime_type'))
        if error:
            return error.message()
        try:
            transaction = self._insert_transaction(req, record)
            self._in_transaction(transaction, self._insert, req, record, transaction)
        except pd.DBException as e:
            return self._error_message(*self._analyze_exception(e))
        else:
            return None

    def storage_api_update(self, req, page_id, lang, filename, values):
        row = self._data.get_row(page_id=page_id, lang=lang, filename=filename)
        if row:
            record = self._record(req, row)
            for key, value in values.items():
                record[key] = pd.Value(record.type(key), value)
            try:
                self._data.update(record.key(), record.rowdata())
            except pd.DBException as e:
                return self._error_message(*self._analyze_exception(e))
            else:
                return None
        else:
            return _("Attachment '%s' not found!", filename)

    def retrieve(self, req, page_id, filename, path_only=False):
        # Used by Publications._export_epub() and Publications._export_pdf().
        row = self._data.get_row(columns=self._non_binary_columns,
                                 page_id=page_id, filename=filename)
        if row:
            record = self._record(req, row)
            path = record['file_path'].value()
            if path_only:
                return path
            # log(OPR, "Loading file:", path)
            with open(path, 'rb') as f:
                return f.read()
        else:
            return None

    def action_move(self, req, record):
        return self.action_update(req, record, action='move')

    def action_download(self, req, record):
        if req.cached_since(record['last_modified'].value()):
            raise wiking.NotModified()
        return wiking.serve_file(req, record['file_path'].value(),  # lock=False,
                                 content_type=record['mime_type'].value())

    def action_thumbnail(self, req, record):
        return self.action_image(req, record, field='thumbnail')

    def action_image(self, req, record, field='image'):
        last_modified = record['last_modified'].value()
        if req.cached_since(last_modified):
            raise wiking.NotModified()
        value = record[field].value()
        if not value:
            raise NotFound()
        else:
            return Response(value, content_type='image/%s' % value.image().format.lower(),
                            last_modified=last_modified)

    def action_upload_archive(self, req):
        import shutil
        upload = req.param('archive')
        if not upload:
            return self.action_insert(req, action='upload_archive')
        elif not isinstance(upload, wiking.FileUpload):
            raise wiking.BadRequest()

        class Error(Exception):
            pass

        class Archive:
            pass

        class ZipArchive(Archive):

            def __init__(self, fileobj):
                import zipfile
                self._archive = zipfile.ZipFile(fileobj, mode='r')

            def items(self):
                return self._archive.infolist()

            def isfile(self, item):
                return not item.filename.endswith('/')  # Directory names end with a slash...

            def filename(self, item):
                return str(item.filename, "cp437")

            def open(self, item):
                return self._archive.open(item)

            def close(self):
                return self._archive.close()

        class TarArchive(Archive):

            def __init__(self, fileobj):
                import tarfile
                self._archive = tarfile.open(fileobj=upload.file(), mode='r')

            def items(self):
                return self._archive.getmembers()

            def isfile(self, item):
                return item.isfile()

            def filename(self, item):
                return item.name

            def open(self, item):
                return self._archive.extractfile(item)

            def close(self):
                return self._archive.close()
        overwrite = req.param('overwrite') == 'T'
        retype = req.param('retype') == 'T'
        files = []

        def insert_attachments(archive, prefill, transaction):
            page_id, lang = prefill['page_id'], prefill['lang']
            for item in archive.items():
                if not archive.isfile(item):
                    # Ignore special files such as symlinks (security!)
                    continue
                filename = re.split(r'[\\/]', archive.filename(item))[-1]
                mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                if overwrite:
                    if retype:
                        matcher = os.path.splitext(filename)[0] + '.*'
                        matcher_value = pd.WMValue(pd.String(), matcher)
                        rows = self._data.get_rows(columns=self._non_binary_columns,
                                                   page_id=page_id, lang=lang,
                                                   condition=pd.WM('filename', matcher_value),
                                                   transaction=transaction)
                        if not rows:
                            row = None
                        elif len(rows) == 1:
                            row = rows[0]
                        else:
                            raise Error(matcher, _("Multiple files match"),
                                        ', '.join(r['filename'].value() for r in rows))
                    else:
                        row = self._data.get_row(columns=self._non_binary_columns,
                                                 page_id=page_id, filename=filename,
                                                 transaction=transaction)
                else:
                    row = None
                if row:
                    record = self._record(req, row)
                    operation = self._update
                    orig_path = record['file_path'].value()
                else:
                    record = self._record(req, None, new=True, prefill=prefill)
                    operation = self._insert
                    orig_path = None
                data = archive.open(item)
                error = record.validate('upload', data, filename=filename, mime_type=mime_type)
                if error:
                    raise Error(filename, error.message())
                else:
                    new_path = record['file_path'].value()
                    if new_path == orig_path:
                        backup_path = orig_path + '.backup'
                        # Create a backup copy in case we want to revert the whole operation.
                        shutil.copyfile(orig_path, backup_path)
                    else:
                        backup_path = None
                    try:
                        operation(req, record, transaction=transaction)
                    except pd.DBException as e:
                        raise Error(filename, self._analyze_exception(e)[1])
                    else:
                        files.append((orig_path, new_path, backup_path))

        def failure(error):
            req.message(error, req.ERROR)
            req.set_param('submit', None)
            return self.action_insert(req, action='upload_archive')
        try:
            filename = upload.filename()
            lname = filename.lower()
            if lname.endswith(".zip"):
                archive = ZipArchive(upload.file())
            elif lname.endswith(".tar") or lname.endswith(".tar.gz") or lname.endswith(".tgz"):
                archive = TarArchive(upload.file())
            else:
                return failure(_("Unknown archive file type: %s", filename))
        except Exception as e:
            return failure(_("Unable to read archive: %s", str(e)))
        try:
            prefill = dict(self._prefill(req), listed=False)
            transaction = self._transaction()
            self._in_transaction(transaction, insert_attachments, archive, prefill, transaction)
        except Exception as e:
            for orig_path, new_path, backup_path in files:
                if new_path != orig_path and os.path.exists(new_path):
                    # On insert and on update when the new file has a different extension (retype).
                    os.unlink(new_path)
                if new_path == orig_path and os.path.exists(backup_path):
                    # On update when the new file has the same extension.
                    shutil.copyfile(backup_path, orig_path)
                    os.unlink(backup_path)
            if isinstance(e, Error):
                return failure(lcg.concat(e.args, separator=': '))
            raise
        else:
            inserted_files, updated_files = 0, 0
            for orig_path, new_path, backup_path in files:
                if orig_path is None:
                    inserted_files += 1
                else:
                    updated_files += 1
                    if backup_path and os.path.exists(backup_path):
                        os.unlink(backup_path)
                    if orig_path != new_path and os.path.exists(orig_path):
                        # TODO: This should probably be done in _save_attachment_file()
                        # because it may happen on single attachment update as well.
                        os.unlink(orig_path)
            msg = []
            if inserted_files:
                msg.append(_.ngettext("%d attachment successfully inserted",
                                      "%d attachments successfully inserted", inserted_files))
            if updated_files:
                msg.append(_.ngettext("%d attachment successfully updated",
                                      "%d attachments successfully updated", updated_files))
            req.message(lcg.concat(msg, separator=', ') + '.', req.SUCCESS)
        finally:
            archive.close()
        raise wiking.Redirect(req.uri())


class _News(ContentManagementModule, EmbeddableCMSModule, wiking.CachingPytisModule):
    """Common base class for News and Planner."""
    class Spec(Specification):

        def fields(self):
            return (
                Field('page_id', _("Page"), not_null=True, editable=ONCE,
                      codebook='PageStructure', selection_type=CHOICE,
                      runtime_filter=computer(lambda r:
                                              pd.EQ('site', pd.sval(wiking.cfg.server_hostname)))),
                Field('lang', _("Language"), not_null=True, editable=ONCE,
                      codebook='Languages', selection_type=CHOICE, value_column='lang'),
                Field('timestamp', _("Date"), default=now, nocopy=True),
                Field('title', _("Title"), column_label=_("Message"), width=32,
                      descr=_("The item brief summary.")),
                ContentField('content', _("Message"), height=6, width=80),
                Field('author', _("Author"), not_null=True,
                      codebook='Users', selection_type=CHOICE,
                      inline_referer='author_login', inline_display='author_name'),
                Field('author_name'),
                Field('author_login'),
                Field('date', _("Date"), virtual=True, computer=computer(self._date),
                      descr=_("Date of the news item creation.")),
                Field('date_title', virtual=True, computer=computer(self._date_title)),
            )

        def _date(self, record, timestamp):
            return pw.localizable_export(pd.dval(record['timestamp'].value().date()))

        def _date_title(self, record, date, title):
            if title:
                return date + ': ' + title
            else:
                return None

    _LIST_BY_LANGUAGE = True
    _EMBED_BINDING_COLUMN = 'page_id'
    _PANEL_FIELDS = ('date', 'title')
    _ROW_ACTIONS = True
    _RSS_DESCR_COLUMN = 'content'

    def _authorized(self, req, action, record=None, **kwargs):
        if action == 'list':
            return req.page_read_access
        elif action in ('insert', 'update', 'delete', 'copy'):
            return req.page_write_access
        else:
            return False

    def _prefill(self, req):
        return dict(super(_News, self)._prefill(req),
                    author=req.user().uid())

    def _record_uri(self, req, record, *args, **kwargs):
        page_uri = wiking.module.Pages.page_uri(req, record['page_id'].value())
        anchor = 'item-' + record[self._referer].export()
        return req.make_uri(page_uri, anchor)

    def _redirect_after_insert(self, req, record):
        req.message(self._insert_msg(req, record), req.SUCCESS)
        identifier = record.cb_value('page_id', 'identifier').value()
        raise Redirect('/' + identifier)

    def _rss_author(self, req, record):
        cbvalue = record.cb_value('author', 'email')
        return cbvalue and cbvalue.export()

    def _load_panel_rows(self, key, transaction=None, **kwargs):
        condition, lang, count = key
        return self._data.get_rows(condition=condition, lang=lang, limit=count,
                                   sorting=self.Spec.sorting)

    def _panel_rows(self, req, relation, lang, count):
        key = (self._panel_condition(req, relation), lang, count)
        # return self._load_panel_rows(key)
        return self._get_value(key, loader=self._load_panel_rows)


class News(_News):

    class Filters(pp.Enumeration):
        enumeration = (
            ('recent', _("Recent news")),
            ('archive', _("Archive of older news")),
        )
        selection_type = CHOICE

    class Spec(_News.Spec):
        # Translators: Section title and menu item
        title = _("News")
        # Translators: Help string describing more precisely the meaning of the "News" section.
        help = _("Publish site news.")
        table = 'cms_v_news'

        def fields(self):
            extra = (
                Field('news_id', editable=NEVER),
                Field('days_displayed', _("Displayed days"), default=30,
                      descr=_("Number of days the item stays displayed in news.")),
            )
            return extra + self._inherited_fields(News.Spec)
        sorting = (('timestamp', DESC),)
        columns = ('title', 'timestamp', 'author')
        # TODO: timestamp can not be editable because editation confuses time zone!
        layout = ('days_displayed', 'title', 'content')
        list_layout = pp.ListLayout('title', meta=('timestamp', 'author', 'news_id'),
                                    content=lambda r: text2content(r.req(), r['content'].value()),
                                    anchor="item-%s", popup_actions=True)

        def query_fields(self):
            return (Field('filter', _("Show"), enumerator=News.Filters,
                          null_display=_("All items"), not_null=False, default='recent'),)

        def condition_provider(self, query_fields={}, **kwargs):
            f = query_fields['filter'].value()
            recent = pd.FunctionCondition('cms_recent_timestamp', 'timestamp', 'days_displayed')
            if f == 'recent':
                condition = recent
            elif f == 'archive':
                condition = pd.NOT(recent)
            else:
                condition = None
            return condition

    # Translators: Button label for creating a new message in "News".
    _INSERT_LABEL = _("New message")
    _RSS_TITLE_COLUMN = 'title'
    _RSS_DATE_COLUMN = 'timestamp'

    def _panel_condition(self, req, relation):
        return pd.AND(super(News, self)._panel_condition(req, relation),
                      pd.FunctionCondition('cms_recent_timestamp', 'timestamp', 'days_displayed'))


class Planner(_News):

    class Spec(_News.Spec):
        # Translators: Section heading and menu item
        title = _("Planner")
        help = _("Announce future events by date in a calendar-like listing.")
        table = 'cms_v_planner'

        def fields(self):
            override = (
                Field('title', column_label=_("Event"), descr=_("The event brief summary.")),
            )
            sample_date = datetime.datetime.today() + datetime.timedelta(weeks=1)
            extra = (
                Field('planner_id', editable=NEVER),
                Field('start_date', _("Date"), width=10,
                      descr=_("The date when the planned event begins. Enter the date "
                              "including year.  Example: %(date)s",
                              date=lcg.LocalizableDateTime(sample_date.date().isoformat()))),
                Field('end_date', _("End date"), width=10,
                      descr=_("The date when the event ends if it is not the same as the "
                              "start date (for events which last several days).")),
            )
            return extra + self._inherited_fields(Planner.Spec, override=override)
        sorting = (('start_date', ASC),)
        columns = ('title', 'date', 'author')
        layout = ('start_date', 'end_date', 'title', 'content')
        list_layout = pp.ListLayout('date_title', meta=('author', 'timestamp'),
                                    content=lambda r: text2content(r.req(), r['content'].value()),
                                    anchor="item-%s")

        def _date(self, record, start_date, end_date):
            date = lcg.LocalizableDateTime(start_date.isoformat(), show_weekday=True)
            if end_date:
                date += ' - ' + lcg.LocalizableDateTime(end_date.isoformat(), show_weekday=True)
            return date

        def check(self, record):
            start_date, end_date = record['start_date'].value(), record['end_date'].value()
            if start_date < pd.Date.datetime():
                return ('start_date', _("Date in the past"))
            if end_date and end_date <= start_date:
                return ('end_date', _("End date precedes start date"))
    # Translators: Button label for creating a new event in "Planner".
    _INSERT_LABEL = _("New event")
    _RSS_TITLE_COLUMN = 'date_title'
    _RSS_DATE_COLUMN = None

    def _condition(self, req):
        scondition = super(Planner, self)._condition(req)
        today = pd.Date.datetime()
        condition = pd.OR(pd.GE('start_date', pd.dval(today)), pd.GE('end_date', pd.dval(today)))
        if scondition:
            return pd.AND(scondition, condition)
        else:
            return condition

    def _panel_condition(self, req, relation):
        return pd.AND(super(Planner, self)._panel_condition(req, relation),
                      self._condition(req))


class Newsletters(EmbeddableCMSModule):
    """E-mail newsletters with subscription."""
    class Spec(Specification):
        title = _("E-mail Newsletters")
        table = wiking.dbdefs.cms_newsletters

        def fields(self):
            override = (
                Field('page_id', codebook='PageStructure', selection_type=CHOICE),
                Field('title', _("Title")),
                Field('lang', _("Language"), editable=ONCE,
                      codebook='Languages', selection_type=CHOICE, value_column='lang'),
                Field('description', _("Description"), width=80, height=5,
                      descr=_("Description of the newsletter purpose and estimated "
                              "target audience.")),
                Field('image', _("Image"), type=pd.Image()),
                Field('image_width', computer=computer(self._image_width)),
                Field('image_height', computer=computer(self._image_height)),
                Field('sender', _("Sender")),
                Field('address', _("Address"), height=4, width=50),
                Field('read_role_id', _("Read only access"), default=Roles.ANYONE.id(),
                      codebook='ApplicationRoles', selection_type=CHOICE,
                      descr=_("Select the role allowed to read the newsletter online and "
                              "subscribe for e-mail distribution.")),
                # Translators: Label of a selector of a group allowed to edit the page.
                Field('write_role_id', _("Read/write access"), default=Roles.CONTENT_ADMIN.id(),
                      codebook='ApplicationRoles', selection_type=CHOICE,
                      descr=_("Select the role allowed create and send the newsletter editions.")),
                # Template substitution colors.
                Field('text_color', _("Text"), type=pd.Color(), default='#000000'),
                Field('link_color', _("Links"), type=pd.Color(), default='#000000'),
                Field('heading_color', _("Headings"), type=pd.Color(), default='#000000'),
                Field('bg_color', _("Background"), type=pd.Color(), default='#FFFFFF'),
                Field('top_text_color', _("Text"), type=pd.Color(), default='#FFFFFF'),
                Field('top_link_color', _("Links"), type=pd.Color(), default='#FFFFFF'),
                Field('top_bg_color', _("Background"), type=pd.Color(), default='#000000'),
                Field('footer_text_color', _("Text"), type=pd.Color(), default='#000000'),
                Field('footer_link_color', _("Links"), type=pd.Color(), default='#000000'),
                Field('footer_bg_color', _("Background"), type=pd.Color(), default='#D8E0F0'),
            )
            return self._inherited_fields(Newsletters.Spec, override=override)

        def _image_width(self, record, image):
            return image.image().size[0] if image else None

        def _image_height(self, record, image):
            return image.image().size[1] if image else None

        layout = ()  # Defined dynamically in _layout().
        columns = ('title', 'lang', 'read_role_id', 'write_role_id')
        bindings = (
            wiking.Binding('editions', _("Editions"), 'NewsletterEditions', 'newsletter_id',
                           form=pw.ItemizedView),
            Binding('subscribers', _("Subscribers"), 'NewsletterSubscription', 'newsletter_id',
                    enabled=lambda r: r.req().newsletter_write_access),
        )
        actions = (
            Action('colors', _("Colors")),
            Action('subscribe', _("Subscribe")),
            Action('unsubscribe', _("Unsubscribe")),
        )

    _EMBED_BINDING_COLUMN = 'page_id'

    def _authorized(self, req, action, record=None, **kwargs):
        roles = wiking.module.Users.Roles()
        if record:
            req.newsletter_read_access = req.check_roles(roles[record['read_role_id'].value()])
            req.newsletter_write_access = req.check_roles(roles[record['write_role_id'].value()])
        # TODO: Isn't it posible to hack around this by URI manipulation?
        if action == 'list':
            return req.page_read_access
        elif action == 'insert':
            return req.page_write_access
        elif action in ('view', 'image'):
            return req.newsletter_read_access
        elif action in ('subscribe', 'unsubscribe'):
            return req.newsletter_read_access and not req.newsletter_write_access
        elif action in ('update', 'delete', 'colors'):
            return req.newsletter_write_access
        else:
            return False

    def _layout(self, req, action, record=None):
        if action == 'colors':
            layout = ('text_color', 'link_color', 'heading_color', 'bg_color',
                      FieldSet(_("Top Bar"),
                               ('top_bg_color', 'top_text_color', 'top_link_color')),
                      FieldSet(_("Footer"),
                               ('footer_bg_color', 'footer_text_color', 'footer_link_color')))
        elif action in ('insert', 'update'):
            layout = ('title', 'lang', 'description', 'image', 'sender', 'address',
                      'read_role_id', 'write_role_id')
        else:
            def image(context, element):
                g = context.generator()
                uri = req.make_uri(self._current_record_uri(req, record), action='image')
                return g.img(src=uri)
            layout = (lambda r: lcg.Container((lcg.HtmlContent(image),
                                               lcg.p(r['description'].export()))),)
        return layout

    def _prefill(self, req):
        return dict(super(Newsletters, self)._prefill(req),
                    lang=req.preferred_language())

    def _image_provider(self, req, uri, record, cid):
        if cid == 'image':
            return self._link_provider(req, uri, record, None, action='image')
        return super(Newsletters, self)._image_provider(req, uri, record, cid)

    def action_colors(self, req, record):
        return self.action_update(req, record, action='colors')

    def action_subscribe(self, req, record):
        return wiking.module.NewsletterSubscription.subscribe(req, record)

    def action_unsubscribe(self, req, record):
        return wiking.module.NewsletterSubscription.unsubscribe(req, record)

    def action_image(self, req, record):
        # if req.cached_since(last_modified):
        #     raise wiking.NotModified()
        value = record['image'].value()
        return Response(value, content_type='image/%s' % value.image().format.lower())
        # last_modified=last_modified)


class NewsletterSubscription(CMSModule):
    """E-mail newsletters with subscription."""
    class Spec(Specification):
        table = wiking.dbdefs.cms_v_newsletter_subscription

        def fields(self):
            override = (
                Field('newsletter_id', codebook='Newsletters', selection_type=CHOICE),
                Field('uid', _("User"), codebook='Users', selection_type=CHOICE,
                      inline_referer='user_login', inline_display='user_name'),
                Field('email', _("E-mail"), type=pd.Email()),
                Field('timestamp', _("Since"), editable=pp.Editable.NEVER, default=now),
            )
            return self._inherited_fields(NewsletterSubscription.Spec, override=override)
        layout = ('email',)
        columns = ('email', 'uid', 'timestamp')

    def _authorized(self, req, action, record=None, **kwargs):
        # TODO: Isn't it posible to hack around this by URI manipulation?
        if action in ('view', 'list', 'insert', 'delete'):
            return req.newsletter_write_access
        else:
            return False

    def _subscription_form(self, req, action, newsletter_title):
        if action in ('subscribe', 'insert'):
            submit = _("Subscribe")
            title = _("Subscribe to %s", newsletter_title)
        else:
            submit = _("Unsubscribe")
            title = _("Unsubscribe from %s", newsletter_title)
        form = wiking.InputForm(req, dict(fields=(Field('email', _("E-mail"),),)),
                                name='NewsletterSubscription',
                                action=action,
                                submit_buttons=((None, submit),),
                                show_reset_button=False,
                                show_cancel_button=True,
                                show_footer=False)
        return wiking.Document(title, form)

    def action_insert(self, req):
        fw = self._binding_forward(req)
        return self.subscribe(req, fw.arg('record'), action='insert')

    def subscribe(self, req, newsletter_record, action='subscribe'):
        if req.param('_cancel'):
            raise Redirect(req.uri())
        values = dict(newsletter_id=newsletter_record['newsletter_id'].value(), timestamp=now())
        email = req.param('email')
        if email:
            values['email'] = email
            values['code'] = wiking.generate_random_string(16)
            success = _("The e-mail address %s has been subscribed successfully.", email)
        elif action == 'subscribe' and req.user():
            values['uid'] = req.user().uid()
            success = _("You have been subscribed successfully.")
        else:
            return self._subscription_form(req, action, newsletter_record['title'].value())
        try:
            self._data.insert(self._data.make_row(**values))
        except pd.DBException as e:
            req.message(self._error_message(*self._analyze_exception(e)), req.ERROR)
        else:
            req.message(success, req.SUCCESS)
        raise Redirect(req.uri())

    def unsubscribe(self, req, newsletter_record):
        if req.param('_cancel'):
            raise Redirect(req.uri())
        email = req.param('email')
        values = dict(newsletter_id=newsletter_record['newsletter_id'].value())
        if email:
            values['email'] = email
            success = _("The e-mail address %s has been unsubscribed successfully.", email)
            failure = _("The e-mail address %s is not subscribed.", email)
        elif req.user():
            values['uid'] = req.user().uid()
            success = _("You have been unsubscribed successfully.")
            failure = _("You are not subscribed.")
        else:
            return self._subscription_form(req, 'unsubscribe', newsletter_record['title'].value())
        row = self._data.get_row(**values)
        if not row:
            req.message(_("Cannot unsubscribe: %s.", failure), req.ERROR)
            raise Redirect(req.uri())
        if email:
            code = req.param('code')
            if not code:
                subject = _("Unsubscribe from %s", newsletter_record['title'].value())
                text = _("Use the following link to confirm your unsubscription "
                         "from %(newsletter)s at %(server_hostname)s:\n\n"
                         "%(uri)s\n\n",
                         newsletter=newsletter_record['title'].value(),
                         server_hostname=wiking.cfg.server_hostname,
                         uri=req.make_uri(req.server_uri() + req.uri(), action='unsubscribe',
                                          email=email, code=row['code'].value()))
                err = wiking.send_mail(email, subject, text, lang=req.preferred_language())
                if err:
                    req.message(_("Failed sending e-mail:") + ' ' + err, req.ERROR)
                    req.message(_("Please, try repeating your request later or "
                                  "contact the administrator if the problem persists."))
                else:
                    req.message(_("Unsubscription confirmation has been sent to %s. "
                                  "Please, check your mail and click on the link to "
                                  "finish unsubscription.", email))
                raise Redirect(req.uri())
            elif code != row['code'].value():
                req.message(_("Invalid unsubscription code."), req.ERROR)
                raise Redirect(req.uri())
        try:
            self._data.delete(row['subscription_id'])
        except pd.DBException as e:
            req.message(self._error_message(*self._analyze_exception(e)), req.ERROR)
        else:
            req.message(success, req.SUCCESS)
        raise Redirect(req.uri())

    def subscribers(self, newsletter_id):
        return [(r['email'].value(), r['code'].value())
                for r in self._data.get_rows(newsletter_id=newsletter_id)]


class NewsletterEditions(CMSModule):
    """E-mail newsletters with subscription."""
    class Spec(Specification):
        table = wiking.dbdefs.cms_newsletter_editions

        def fields(self):
            override = (
                Field('newsletter_id', codebook='Newsletters', selection_type=CHOICE),
                Field('creator', _("Creator"), codebook='Users', selection_type=CHOICE),
                Field('created', _("Created"), editable=pp.Editable.NEVER, default=now,
                      visible=computer(lambda r: r.req().newsletter_write_access)),
                Field('sent', _("Sent"), editable=pp.Editable.NEVER),
                Field('access_code',),
            )
            extra = (
                Field('title', type=pd.String(), virtual=True, computer=computer(self._title)),
            )
            return self._inherited_fields(NewsletterEditions.Spec, override=override) + extra

        def _title(self, record, created, sent):
            if sent:
                return lcg.LocalizableDateTime(sent.strftime('%Y-%m-%d %H:%M'), utc=True)
            else:
                return _("Unpublished edition from %s",
                         lcg.LocalizableDateTime(created.strftime('%Y-%m-%d %H:%M'), utc=True))
        layout = (
            lambda r: lcg.HtmlContent(
                lambda context, element:
                context.generator().img(src='%s/../..?action=image' % context.req().uri()),
            ),
        )
        columns = ('title',)
        bindings = (
            Binding('posts', _("Posts"), 'NewsletterPosts', 'edition_id'),
        )
        actions = (
            Action('preview', _("Preview")),
            Action('send', _("Send")),
            Action('test', _("Test")),
        )

    _LIST_LABEL = _("Overview of Editions")
    _TITLE_COLUMN = 'title'
    _POST_TEMPLATE_MATCHER = re.compile(r'<!-- POST START -->(.*)<!-- POST END -->',
                                        re.DOTALL | re.MULTILINE)
    _IMAGE_TEMPLATE_MATCHER = re.compile(r'<!-- IMAGE (?P<align>LEFT|RIGHT) START -->'
                                         r'(.*)<!-- IMAGE (?P=align) END -->',
                                         re.DOTALL | re.MULTILINE)

    def _authorized(self, req, action, record=None, **kwargs):
        if action == 'list':
            return req.newsletter_read_access
        elif action == 'view':
            return (req.newsletter_write_access or
                    req.newsletter_read_access and record['sent'].value() is not None)
        elif action in ('insert', 'update', 'delete', 'send', 'test', 'preview'):
            return req.newsletter_write_access
        else:
            return False

    def _condition(self, req):
        condition = super(NewsletterEditions, self)._condition(req)
        if not req.newsletter_write_access:
            condition = pd.AND(condition, pd.NE('sent', pd.dtval(None)))
        return condition

    def _prefill(self, req):
        return dict(super(NewsletterEditions, self)._prefill(req),
                    creator=req.user().uid())

    def _newsletter_html(self, req, record):
        newsletter_id = record['newsletter_id'].value()
        newsletter_row = record['newsletter_id'].type().enumerator().row(newsletter_id)
        lang = newsletter_row['lang'].value()
        template_resource = wiking.module.Resources.resource('newsletter-template.html')
        template = template_resource.get()
        match = self._POST_TEMPLATE_MATCHER.search(template)
        if not match:
            req.message(_("%s: Post template not found!", template_resource.src_file()),
                        req.ERROR)
            raise wiking.Redirect(req.uri())
        post_template = match.group(1)
        template = template.replace(match.group(0), '%(posts)s')
        image_templates = {}

        def subst(match):
            align = match.group('align').lower()
            image_templates[align] = match.group(2)
            return '%%(image_%s)s' % align

        post_template = self._IMAGE_TEMPLATE_MATCHER.sub(subst, post_template)
        if 'left' not in image_templates or 'right' not in image_templates:
            req.message(_("%s: Image template sections not found!",
                          template_resource.src_file()), req.ERROR)
            raise wiking.Redirect(req.uri())
        server_uri = req.server_uri()

        def abs_uri(uri):
            return server_uri + uri

        newsletter_uri = abs_uri(self._binding_parent_uri(req))
        edition_uri = abs_uri(self._current_record_uri(req, record))
        colors = dict([(k, newsletter_row[k].export())
                       for k in newsletter_row.keys() if k.endswith('_color')])

        def post(row, post_template, image_templates, edition_uri):
            content = lcg.format_text(row['content'].value().strip()).replace(
                '<a ', ('<a style="color: %(link_color)s; text-decoration: none; '
                        'font-weight: bold;"' % colors)
            )
            values = dict(colors,
                          title=row['title'].value().strip(),
                          content=content,
                          image_left='',
                          image_right='')
            if row['image'].value():
                align = row['image_position'].value()
                values['image_' + align] = image_templates[align] % dict(
                    post_image_uri=req.make_uri(edition_uri + '/posts/' + row['post_id'].export(),
                                                action='image'),
                    post_image_width=row['image_width'].export(),
                    post_image_height=row['image_height'].export(),
                )
            return post_template % values
        posts = [post(r, post_template, image_templates, edition_uri)
                 for r in wiking.module.NewsletterPosts.posts(record['edition_id'].value())]

        def translate(x):
            return req.translate(x, lang=lang)

        try:
            return template % dict(
                title=newsletter_row['title'].export(),
                sender=newsletter_row['sender'].export(),
                edition_uri=edition_uri + '?action=preview',
                resources_uri=abs_uri(req.module_uri('Resources')),
                server_uri=server_uri,
                unsubscribe_uri=newsletter_uri + ('?action=unsubscribe;email=%(email)s;'
                                                  'code=%(code)s'),
                image_uri=newsletter_uri + '?action=image',
                like_uri=req.make_uri('https://www.facebook.com/sharer/sharer.php', u=edition_uri),
                tweet_uri=req.make_uri('https://twitter.com/share',
                                       text=newsletter_row['title'].export(),
                                       url=edition_uri),
                share_uri=req.make_uri('mailto:',
                                       subject=newsletter_row['title'].export(),
                                       body=edition_uri),
                like_msg=translate(_("Like")),
                tweet_msg=translate(_("Tweet")),
                share_msg=translate(_("Share")),
                thank_you_msg=translate(_("Thank you for your attention.")),
                not_interested_msg=translate(_("Not interested in this newsletter anymore:")),
                unsubscribe_msg=translate(_("Unsubscribe")),
                web_version_msg=translate(_("Web version")),
                address=''.join([r + '<br/>'
                                 for r in newsletter_row['address'].export().splitlines()]),
                posts='\n'.join(posts),
                # Resize the image to fit 640px wide template maintaining the aspect ratio.
                image_height=(newsletter_row['image_height'].value() *
                              (640 / float(newsletter_row['image_width'].value()))),
                **colors
            )
        except KeyError as e:
            req.message(_("%s: Invalid template variable: %s" % (template_resource.src_file(), e)),
                        req.ERROR)
            raise wiking.Redirect(req.uri())

    def _newsletter_text(self, html):
        import textwrap

        def link2text(m):
            url = m.group(1).strip()
            label = m.group(2).strip()
            if url and label and url != label:
                return '%s: %s' % (label, url)
            else:
                return label
        text = re.sub(r'<!--.*?-->', '', html.replace('&nbsp;', ' '), flags=re.DOTALL)
        text = re.sub(r'<a href="([^"]+)"[^>]*>(.*?)</a>', link2text, text,
                      flags=re.MULTILINE | re.DOTALL)
        text = re.sub(r'<.*?>', '', text, flags=re.MULTILINE | re.DOTALL)
        return '\n\n'.join([textwrap.fill(paragraph.strip().strip('|').strip(),
                                          78, replace_whitespace=True)
                            for paragraph in re.split(r'\n\s*', text, flags=re.MULTILINE)])

    def _send_newsletter(self, req, record, addresses):
        newsletter_id = record['newsletter_id'].value()
        newsletter_row = record['newsletter_id'].type().enumerator().row(newsletter_id)
        title = newsletter_row['title'].value()
        lang = newsletter_row['lang'].value()
        html = self._newsletter_html(req, record)
        n, errors = 0, 0
        #  Preserve % signs in HTML template (only keyword substitutions are meant to be used).
        html = re.sub(r'%(?!\([a-z]+\)s)', '%%', html)
        text = self._newsletter_text(html)
        for email, code in addresses:
            subst = dict([(k, urllib.parse.quote(v)) for k, v in (('email', email),
                                                                  ('code', code))])
            err = wiking.send_mail(email, title, html=html % subst, text=text % subst, lang=lang)
            if err:
                errors += 1
                log(OPERATIONAL, "Error sending newsletter to %s: %s" % (email, err))
            else:
                n += 1
        try:
            record.update(sent=now())
        except pd.DBException as e:
            req.message(self._error_message(*self._analyze_exception(e)), req.ERROR)
        req.message(_("The newsletter has been sent to %d recipients.", n), req.SUCCESS)
        if errors:
            req.message(_("Sending to %d recipients failed. "
                          "Details can be found in servers error log.", errors), req.ERROR)

    def action_preview(self, req, record):
        html = self._newsletter_html(req, record)
        return wiking.Response(html)

    def action_send(self, req, record):
        newsletter_id = record['newsletter_id'].value()
        addresses = wiking.module.NewsletterSubscription.subscribers(newsletter_id)
        self._send_newsletter(req, record, addresses)
        raise Redirect(req.uri())

    def action_test(self, req, record):
        if req.param('_cancel'):
            raise Redirect(req.uri())
        form = wiking.InputForm(req, dict(
            fields=(Field('addresses', _("Addresses"), width=60, height=4, type=pd.String(),
                          computer=computer(lambda r: r.req().user().email()), editable=ALWAYS,
                          descr=_("Type in e-mail addresses separated by colons, "
                                  "spaces or new lines. The newsletter will be sent "
                                  "to given addresses only, not to regular subscribers")),),),
            name='NewsletterTest',
            action='test',
            submit_buttons=((None, _("Send")),),
            show_reset_button=False,
            show_cancel_button=True,
            show_footer=False,
        )
        if req.param('submit') and form.validate(req):
            addresses = re.split(r'(?:\s*,\s*|\s+)', form.row()['addresses'].value(),
                                 re.MULTILINE)
            self._send_newsletter(req, record, [(a, '') for a in addresses])
            raise Redirect(req.uri())
        else:
            return wiking.Document(_("Test Send to Given Addresses"), form)


class NewsletterPosts(CMSModule):
    """E-mail newsletters with subscription."""
    class ImagePositions(pp.Enumeration):
        enumeration = (
            ('left', _("Left")),
            ('right', _("Right")),
        )
        default = 'left'
        selection_type = CHOICE

    class Spec(Specification):
        table = wiking.dbdefs.cms_newsletter_posts

        def fields(self):
            override = (
                Field('edition_id', codebook='NewsletterEditions', selection_type=CHOICE),
                Field('title', _("Title"), width=70),
                Field('ord', _("Order"), width=5, computer=computer(self._last_order),
                      editable=ALWAYS,
                      descr=_("Number denoting the order of the post on the page."),),
                Field('content', _("Content"), width=80, height=6, compact=True),
                Field('image', _("Image"), type=pd.Image()),
                Field('image_position', _("Image Position"),
                      enumerator=NewsletterPosts.ImagePositions),
                Field('image_width', computer=computer(self._image_width)),
                Field('image_height', computer=computer(self._image_height)),
            )
            return self._inherited_fields(NewsletterPosts.Spec, override=override)

        def _last_order(self, record, edition_id):
            return wiking.module.NewsletterPosts.last(edition_id)

        def _image_width(self, record, image):
            return image.image().size[0] if image else None

        def _image_height(self, record, image):
            return image.image().size[1] if image else None
        layout = ('title', 'ord', 'image', 'image_position', 'content')
        columns = ('title',)
        sorting = (('ord', ASC),)

        def list_layout(self):
            def clearing(context, element):
                g = context.generator()
                return g.div('')

            def image(context, element, record):
                if record['image_width'].value() is None:  # Test width, big values are excluded...
                    return ''
                g = context.generator()
                style = ('margin-%s: 16px;' %
                         ('left' if record['image_position'].value() == 'right' else 'right',))
                return g.img(src='%s/posts/%s?action=image' % (context.req().uri(),
                                                               record['post_id'].value()),
                             align=record['image_position'].value(),
                             width=record['image_width'].value(),
                             height=record['image_height'].value(),
                             style=style,
                             alt='')
            return pp.ListLayout('title',
                                 content=(lambda r: lcg.HtmlContent(image, r),
                                          'content',
                                          lambda r: lcg.HtmlContent(clearing),
                                          ))

    _ROW_ACTIONS = True

    def _authorized(self, req, action, **kwargs):
        if action in ('view', 'list', 'image'):
            return req.newsletter_read_access
        elif action in ('insert', 'update', 'delete'):
            return req.newsletter_write_access
        else:
            return False

    def _image_provider(self, req, uri, record, cid):
        if cid == 'image':
            return self._link_provider(req, uri, record, None, action='image')
        return super(NewsletterPosts, self)._image_provider(req, uri, record, cid)

    def last(self, edition_id):
        ords = [r['ord'].value() for r in self._data.get_rows(edition_id=edition_id)]
        if ords:
            return sorted(ords)[-1] + 1
        else:
            return 1

    def posts(self, edition_id):
        return self._data.get_rows(edition_id=edition_id)

    def action_image(self, req, record):
        # if req.cached_since(last_modified):
        #     raise wiking.NotModified()
        value = record['image'].value()
        return Response(value, content_type='image/%s' % value.image().format.lower())
        # last_modified=last_modified)


class Discussions(ContentManagementModule, EmbeddableCMSModule):

    class Spec(Specification):
        # Translators: Name of the extension module for simple forum-like discussions.
        title = _("Discussions")
        # Translators: Help string describing more precisely the meaning of the "News" section.
        help = _("Allow logged in users to post messages as in a simple forum.")
        table = 'cms_discussions'

        def fields(self):
            return (
                Field('comment_id', editable=NEVER),
                Field('page_id', not_null=True, editable=ONCE,
                      codebook='PageStructure', selection_type=CHOICE,
                      runtime_filter=computer(lambda r:
                                              pd.EQ('site', pd.sval(wiking.cfg.server_hostname)))),
                Field('lang', not_null=True, editable=ONCE,
                      codebook='Languages', selection_type=CHOICE, value_column='lang'),
                Field('in_reply_to'),
                Field('tree_order', type=pd.TreeOrder()),
                Field('timestamp', default=now),
                Field('author', not_null=True, codebook='Users', selection_type=CHOICE),
                # Translators: Field label for posting a message to the discussion.
                Field('text', _("Your comment"), height=6, width=80, compact=True,),
            )
        sorting = (('tree_order', ASC),)
        layout = ('text',)

        def list_layout(self):
            import textwrap

            def reply_info(context, element, record):
                if record.req().check_roles(Roles.USER):
                    g = context.generator()
                    text = textwrap.fill(record['text'].value(), 60, replace_whitespace=False)
                    quoted = '\n'.join(['> ' + line for line in text.splitlines()]) + '\n\n'
                    # This hidden 'div.discussion-reply' is a placeholder and
                    # information needed for the Javascript 'Discussion' class
                    # instantiated below the form in the method related().
                    return g.div((g.span(record['comment_id'].export(), cls='id'),
                                  g.span(urllib.parse.quote(quoted.encode('utf-8')), cls='quoted'),
                                  ), cls='discussion-reply', style='display: none')
                else:
                    return ''
            return pp.ListLayout(lcg.TranslatableText("%(timestamp)s, %(author)s:"),
                                 content=('text', lambda r: lcg.HtmlContent(reply_info, r)),
                                 anchor='comment-%s')

    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid is None:
            return None
        return super(Discussions, self)._link_provider(req, uri, record, cid, **kwargs)

    def _actions(self, req, record):
        # Disable the New Record button under the list as we have the insertion
        # form just below.
        return [a for a in super(Discussions, self)._actions(req, record) if a.id() != 'insert']

    def _authorized(self, req, action, record=None):
        if action in ('list', 'insert', 'reply'):
            return req.page_read_access
        else:
            return False

    def _redirect_after_insert(self, req, record):
        req.message(_("Your comment was posted to the discussion."), req.SUCCESS)
        raise Redirect(self._binding_parent_uri(req))

    def _prefill(self, req):
        return dict(super(Discussions, self)._prefill(req),
                    timestamp=now(),
                    author=req.user().uid(),
                    page_id=req.page_record['page_id'].value(),
                    lang=req.page_record['lang'].value())

    def action_reply(self, req, record):
        prefill = dict(self._prefill(req),
                       in_reply_to=record['comment_id'].value(),
                       text=req.param('text'))
        record = self._record(req, None, new=True, prefill=prefill)
        try:
            transaction = self._insert_transaction(req, record)
            self._in_transaction(transaction, self._insert, req, record, transaction)
        except pd.DBException as e:
            req.message(self._error_message(*self._analyze_exception(e)), req.ERROR)
            raise Redirect(self._binding_parent_uri(req))
        else:
            return self._redirect_after_insert(req, record)

    def _list_form_content(self, req, form, uri=None):
        content = super(Discussions, self)._list_form_content(req, form, uri=uri)
        if uri is not None:
            def render(context, element):
                # Add JavaScript initialization below the list.
                context.resource('discussion.css')
                if req.check_roles(Roles.USER):
                    g = context.generator()
                    context.resource('discussion.js')
                    return g.script(g.js_call('new Discussion', form.form_id(), uri, 'text'))
                else:
                    return ''
            content.append(lcg.HtmlContent(render))
            if req.check_roles(Roles.USER):
                # Embed insertion form directly below the message list.
                content.append(self._form(pw.EditForm, req, action='insert', show_reset_button=False))
            else:
                # Translators: The square brackets mark a link.  Please leave the brackets and the
                # link target '?command=login' untouched and traslate 'log in' to fit into the
                # sentence.  The user only sees it as 'You need to log in before ...'.
                msg = _("Note: You need to [?command=login log in] before you can post messages.")
                content.append(wiking.Message(req.localize(msg), formatted=True))
            # Wrap in a named container to allow css styling.
            content = [lcg.Container(content, name='discussion-list')]
        return content


class SiteMap(wiking.Module, Embeddable, wiking.RequestHandler):
    """Extend page content by including a hierarchical listing of the main menu

    This module can be embedded in CMS page content as well as mapped directly
    as a request handler.

    """
    # Translators: Section heading and menu item. Computer terminology idiom.
    _TITLE = _("Site Map")

    def embed(self, req):
        return [lcg.RootIndex()]

    def handle(self, req):
        return wiking.Document(self._TITLE, self.embed(req))


class ContactForm(wiking.Module, Embeddable):
    _TITLE = _("Contact Form")
    _FIELDS = (
        Field('name', _("Your Name"), width=20, not_null=True),
        Field('company', _("Company or Organization"), width=20),
        Field('email', _("Your e-mail address"), type=pd.Email(), width=20, not_null=True),
        Field('phone', _("Your phone number"), width=20),
        Field('message', _("Your Message"), width=67, height=10,
              compact=True, not_null=True),
    )

    def _check_email(self, record):
        if not record.req().param('_pytis_form_update_request'):
            ok, error = wiking.validate_email_address(record['email'].value())
            if not ok:
                return ('email', error)

    def embed(self, req):
        if req.param('contact_form_submission') == 'success':
            return (lcg.p(lcg.strong(_("Thank you for contacting us!")),
                          id='contact-form-response'),
                    lcg.p(_("We will process your enquiry at the nearest occasion."),
                          id='contact-form-response-text'))
        form = pytis.web.VirtualForm(req, wiking.cfg.resolver, dict(fields=self._FIELDS,
                                                                    check=(self._check_email,)),
                                     submit_buttons=(('submit', _("Submit")),),
                                     show_reset_button=False)
        if form.is_ajax_request(req):
            return wiking.ajax_response(req, form)
        if req.param('submit') and form.validate(req):
            record = form.row()
            text = lcg.concat([lcg.format("%s: %s\n", label, record[field].export())
                               for field, label in (('name', _("Name")),
                                                    ('company', _("Company")),
                                                    ('email', _("E-mail")),
                                                    ('phone', _("Phone")),)],
                              "\n", record['message'].value())
            address = wiking.cfg.webmaster_address
            error = wiking.send_mail(address, sender=wiking.cfg.default_sender_address,
                                     subject=_("Contact Form Enquiry from %s",
                                               req.server_uri() + req.uri()),
                                     text=text, lang=req.preferred_language())
            if error:
                req.message(_("Error sending your enquiry!"), req.ERROR)
                # Our attempt may fail, but the user has a different SMTP server...
                req.message(_("Please, try sending the form later. "
                              "If the problem persists, contact %s." % address))
                log(OPERATIONAL, "Error sending mail to %s:" % address, error)
            else:
                # Protect against multiple submissions by POST/Redirect/GET.
                raise wiking.Redirect(req.uri(), contact_form_submission='success')
        return [form]


class Resources(wiking.Resources):
    """Serve resource files.

    The Wiking base Resources class is extended to retrieve the stylesheet
    contents from the database driven 'StyleSheets' module (in addition to
    serving the default styles installed on the filesystem).

    """

    def _theme(self, req):
        try:
            theme_id = int(req.param('preview_theme'))
            cfg_mtime = datetime.datetime.utcnow()
        except (TypeError, ValueError):
            theme_id = wiking.module.Config.theme_id()
            cfg_mtime = wiking.module.Config.cached_table_timestamp(utc=True)
        if theme_id is None:
            theme = wiking.cfg.theme
            theme_mtime = self._DEFAULT_THEME_MTIME
        else:
            theme = wiking.module.Themes.theme(theme_id)
            theme_mtime = wiking.module.Themes.cached_table_timestamp(utc=True)
        if theme_mtime and cfg_mtime:
            mtime = max(theme_mtime, cfg_mtime)
        else:
            mtime = None
        return theme, mtime

    def _handle_resource(self, req, filename):
        content = wiking.module.StyleSheets.stylesheet(req, filename)
        if content:
            mtime = wiking.module.StyleSheets.cached_table_timestamp(utc=True)
            return wiking.Response(content, content_type='text/css', last_modified=mtime)
        else:
            return super(Resources, self)._handle_resource(req, filename)


class StyleSheets(SiteSpecificContentModule, StyleManagementModule,
                  wiking.CachingPytisModule):
    """Manage available Cascading Style Sheets through a Pytis data object."""
    class Scopes(pp.Enumeration):
        enumeration = (
            # Translators: This and the next label define the available values
            # of a stylesheet's scope (applicability to diferent parts of a
            # website).  Each stylesheet may be applicable to the management
            # interface (the area where only administrators are allowed), pages
            # (everything outside the management interface) or both ("Global"
            # scope).
            ('website', _("Website")),
            ('wmi', _("Management interface")),
        )

    class Spec(Specification):
        # Translators: Section heading and menu item. Meaning the visual appearance. Computer
        # terminology.
        title = _("Style sheets")
        table = wiking.dbdefs.cms_stylesheets
        # Translators: Help string. Cascading Style Sheet (CSS) is computer terminology idiom.
        help = _("Manage available Cascading Style Sheets.")

        def _customize_fields(self, fields):
            field = fields.modify
            field('filename', label=_("File Name"), width=16)
            field('description', label=_("Description"), width=50)
            field('active', label=_("Active"), default=True)
            # Translators: Scope of applicability of a stylesheet on different website parts.
            field('scope', label=_("Scope"), enumerator=StyleSheets.Scopes,
                  selection_type=RADIO,
                  # Translators: Global scope (applies to all parts of the website).
                  null_display=_("Global"), not_null=False,
                  # Translators: Description of scope options.  Make sure you
                  # use the same terms as in the options themselves, which are
                  # defined a few items above.
                  descr=_("Determines where this style sheet is applicable. "
                          'The "Management interface" is the area for CMS administration, '
                          '"Website" means the regular pages outside the management interface '
                          'and "Global" means both.'))
            field('ord', label=_("Order"), width=5,
                  # Translators: Precedence meaning position in a sequence of importance or
                  # priority.
                  descr=_("Number denoting the style sheet precedence."))
            field('content', label=_("Content"), height=20, width=80)

        layout = ('filename', 'active', 'scope', 'ord', 'description', 'content')
        columns = ('filename', 'active', 'scope', 'ord', 'description')
        sorting = (('ord', ASC),)
    _REFERER = 'filename'

    _cache_ids = ('default', 'single',)

    def stylesheets(self, req):
        return self._get_value((None, req.wmi))

    def stylesheet(self, req, filename):
        return self._get_value((filename, None), cache_id='single')

    def _load_value(self, key, transaction=None):
        filename, wmi = key
        if filename is None:
            scopes = (None, wmi and 'wmi' or 'website')
            return [lcg.Stylesheet(row['filename'].value())
                    for row in self._data.get_rows(site=wiking.cfg.server_hostname,
                                                   active=True,
                                                   condition=pd.OR(*[pd.EQ('scope', pd.sval(s))
                                                                     for s in scopes]),
                                                   sorting=self._sorting)]
        else:
            row = self._data.get_row(filename=filename, active=True,
                                     site=wiking.cfg.server_hostname)
            if row:
                return row['content'].value()
            else:
                return None


class Text(Structure):
    """Representation of a predefined text.

    Each predefined text consists of the following attributes:

      label -- unique identifier of the text, string
      description -- human description of the text, presented to application
        administrators managing the texts
      text -- the text itself, as a translatable string in LCG formatting
      text_format -- One of 'pytis.presentation.TextFormat' constants.  The
        default value None denotes that the format depends on the current
        setting of 'wiking.cfg.content_editor'.  Otherwise the format of given
        text is explititly set and the text will be treated as such.  This
        option is useful for application defined texts, which may for some
        reason prefer a certain format and don't want to handle the text
        differently depending on 'wiking.cfg.content_editor' setting.  The
        management interface will respect this setting when editing the text
        value.

    """
    _attributes = (Attribute('label', str),
                   Attribute('description', str),
                   Attribute('text', str),
                   Attribute('text_format', str),)

    @classmethod
    def _module_class(class_):
        return Texts

    def __init__(self, label, description, text, text_format=None):
        assert text_format is None or text_format in pytis.util.public_attr_values(pp.TextFormat)
        Structure.__init__(self, label=label, description=description, text=text,
                           text_format=text_format)
        self._module_class().register_text(self)


class CommonTexts(SettingsManagementModule):
    """Management of predefined texts editable by administrators.

    Predefined texts may be used for various purposes in applications,
    typically to display some application specific information.  Application
    developer must define all the predefined texts to be used in the
    application, in the form of 'Text' instances.  Application administrators
    may change the texts in CMS, but they can't delete them nor to insert new
    texts (except for translations of defined texts).

    So that the module can find the texts, they must be registered using
    'register_text' method.  This usually happens in constructors of text
    definition classes (such as 'Text').

    This is a base class for text retrieval modules, its subclasses may define
    access to various kinds of texts.

    Wiking modules can access the texts by using the 'text()' method.  See also
    'TextReferrer' class.

    Note the predefined (default) text values get localized automatically.
    When the text is customized through the management interface, the
    customized value only applies for the language in which it is customized,
    so don't forget to customize all language variants where appropriate.

    """
    class Spec(Specification):
        # This must be a private attribute, otherwise Pytis handles it in a special way
        _texts = {}

        def fields(self):
            return (
                Field('text_id'),
                Field('label'),
                Field('lang'),
                Field('description'),
                Field('descr', _("Purpose"), width=64, virtual=True,
                      computer=computer(self._description)),
                # The first field is used implicitly for texts with no text_format
                # defined and its type is controlled by the current value of
                # 'wiking.cms.cfg.content_editor'.  The other fields below
                # are used for texts with a specific text_format value.
                ContentField('content', _("Text"), width=80, height=10),
                ContentField('plain_content', _("Text"), dbcolumn='content',
                             text_format=pp.TextFormat.PLAIN, width=80, height=10),
                ContentField('lcg_content', _("Text"), dbcolumn='content',
                             text_format=pp.TextFormat.LCG, width=80, height=10),
                ContentField('html_content', _("Text"), dbcolumn='content',
                             text_format=pp.TextFormat.HTML, width=80, height=10),
            )

        sorting = (('label', ASC,),)

        def _description(self, row, label, description):
            if description:
                descr = description
            else:
                try:
                    descr = self._texts[label].description()
                except KeyError:
                    # May happen only for obsolete texts in the database
                    descr = ''
            return descr

    _LIST_BY_LANGUAGE = True
    _REFERER = 'label'
    _DELETE_PROMPT = _("This text is no longer in use by the application."
                       " Do you want to remove it?")

    @classmethod
    def register_text(class_, text):
        """Register 'text' into the texts.

        This method is intended to be called only from the constructor of
        compatible text definition classes, such as 'Text'.  The 'text'
        argument must be an instance of such a class.

        All texts to be used must be registered in their corresponding
        management classes, otherwise they are unknown to them.

        """
        texts = class_.Spec._texts
        label = text.label()
        if label not in texts:
            texts[label] = text

    def _authorized(self, req, action, record=None, **kwargs):
        if action == 'insert':
            return False
        elif action == 'delete':
            # Allow deletion of texts which don't exist in the application anymore.
            return record['label'].value() not in self.Spec._texts
        else:
            return super(CommonTexts, self)._authorized(req, action, record=record, **kwargs)

    def _delayed_init(self):
        super(CommonTexts, self)._delayed_init()
        self._register_texts()

    def _register_texts(self):
        pass

    def _layout(self, req, action, record=None):
        try:
            text = self.Spec._texts[record['label'].value()]
        except KeyError:
            if action == 'delete':
                text_format = None  # Avoid redirection loop.
            else:
                raise Redirect(self._current_record_uri(req, record), action='delete',
                               __invoked_from='ListView')
        else:
            text_format = text.text_format()
        if text_format == pp.TextFormat.PLAIN:
            content_field = 'plain_content'
        elif text_format == pp.TextFormat.LCG:
            content_field = 'lcg_content'
        elif text_format == pp.TextFormat.HTML:
            content_field = 'html_content'
        elif text_format is None:
            content_field = 'content'
        else:
            raise Exception('Unsupported text format: %s' % text_format)
        return (content_field,)

    def _update(self, req, record, transaction):
        # Use the value of the layout column for update.
        row = pd.Row([(fid.replace('plain_', '').replace('html_', ''), record[fid])
                      for fid in self._layout(req, 'update', record=record)])
        self._data.update(record.key(), row, transaction=transaction)

    def _select_language(self, req, lang):
        if lang is None:
            lang = req.preferred_language()
            if lang is None:
                lang = 'en'
        return lang

    def _localized_text(self, req, localizable_text, lang, args):
        result = req.localize(localizable_text, lang=lang)
        if args:
            result = result % self._localized_args(req, lang, args)
        return result

    def _localized_args(self, req, lang, args):
        return dict([(k, req.localize(v, lang)) for k, v in args.items()])

    def _auto_filled_fields(self, req):
        return ()

    def _record(self, req, row, new=False, prefill=None):
        record = super(CommonTexts, self)._record(req, row, new=new, prefill=prefill)
        values_to_update = {}
        for field_id, function in self._auto_filled_fields(req):
            if not record[field_id].value():
                values_to_update[field_id] = function(req, record, field_id)
        if values_to_update:
            record.update(**values_to_update)
        return record


class Texts(CommonTexts, wiking.CachingPytisModule):
    """Management of simple texts.

    The texts are LCG structured texts and they are language dependent.  Each
    of the texts is identified by a 'Text' instance with unique identifier (its
    'label' attribute).  See 'Text' class for more details.

    """
    class TextStates(pp.Enumeration):
        enumeration = (
            ('unknown', _("Unknown text")),
            ('default', _("Default")),
            ('custom', _("Edited")),
        )
        selection_type = CHOICE

    class Spec(CommonTexts.Spec):
        table = 'cms_v_system_texts'
        title = _("System Texts")
        help = _("Edit miscellaneous system texts.")

        def fields(self):
            extra = (
                Field('site'),
                Field('title', label=_("Title"), virtual=True,
                      computer=computer(lambda r, label, descr: descr or label)),
                Field('state', label=_("State"), virtual=True, computer=computer(self._state),
                      enumerator=Texts.TextStates),
            )
            return self._inherited_fields(Texts.Spec) + extra
        columns = ('title', 'state',)

        def _state(self, record, label, content):
            if label not in self._texts:
                return 'unknown'
            elif content is None:
                return 'default'
            else:
                return 'custom'

        def row_style(self, record):
            state = record['state'].value()
            if state == 'unknown':
                return pp.Style(foreground='#f00')
            elif state == 'custom':
                return pp.Style(bold=True)
            else:
                return None

    _DB_FUNCTIONS = dict(CommonTexts._DB_FUNCTIONS,
                         cms_add_text_label=(('label', pd.String()), ('site', pd.String())))
    _ROW_EXPANSION = True
    _ASYNC_ROW_EXPANSION = True

    def _refered_row_values(self, req, value):
        return dict(super(Texts, self)._refered_row_values(req, value),
                    site=wiking.cfg.server_hostname)

    def _condition(self, req):
        return pd.AND(super(Texts, self)._condition(req),
                      pd.EQ('site', pd.sval(wiking.cfg.server_hostname)))

    def _prefill(self, req):
        return dict(super(Texts, self)._prefill(req), site=wiking.cfg.server_hostname)

    def _auto_filled_fields(self, req):
        def content(req, record, field_id):
            label = record['label'].value()
            if label is None:
                return ''
            lang = record['lang'].value()
            try:
                text = self.Spec._texts[label]
                return req.localize(text.text(), lang)
            except KeyError:
                return ''
        return (('content', content,),)

    def _register_texts(self):
        for identifier, text in self.Spec._texts.items():
            if isinstance(text, Text):
                site = wiking.cfg.server_hostname
                self._call_db_function('cms_add_text_label', text.label(), site)

    def _load_value(self, key, transaction=None):
        label, site = key
        translations = [(row['lang'].value(), row['content'].value(),)
                        for row in self._data.get_rows(label=label, site=site)
                        if row['content'].value() is not None]
        return dict(translations)

    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid is None and not kwargs:
            return self._link_provider(req, uri, record, None, action='update',
                                       __invoked_from='ListView')
        return super(Texts, self)._link_provider(req, uri, record, cid, **kwargs)

    def _expand_row(self, req, record, form):
        try:
            text = self.Spec._texts[record['label'].value()]
        except KeyError:
            return lcg.container(lcg.container('', name='error-icon'),
                                 lcg.p(_("The text '%s' exists in the database, but "
                                         "is not defined by the application.",
                                         record['label'].value())),
                                 lcg.p(_("This may be an old text which is not used anymore. "
                                         "You can remove it if this is the case.")),
                                 name='cms-text-not-found')
        content = self.parsed_text(req, text)
        if not content or isinstance(content, lcg.Container) and not content.content():
            return lcg.em(_("empty value"), name='cms-text-empty-value')
        return content

    def text(self, text):
        """Return text corresponding to 'text' as 'lcg.TranslatableText' instance.

        Arguments:

          text -- 'Text' instance identifying the text

        Returns a 'lcg.TranslatableText' instance which in each particular
        language translates into the site specific text defined in the database
        or to the application defined default text when no site specific text
        is defined.

        """
        assert isinstance(text, Text)
        translations = self._get_value((text.label(), wiking.cfg.server_hostname))
        return lcg.SelfTranslatableText(text.text() or '', translations=translations)

    def localized_text(self, req, text, lang=None, args=None):
        """Return the localized text corresponding to 'text' as a string.

        Arguments:

          req -- wiking request
          text -- 'Text' instance identifying the text
          lang -- two-character string identifying the language of the text
          args -- dictionary of formatting arguments for the text; if
            non-empty, the text is processed by the '%' operator and all '%'
            occurences within it must be properly escaped; if 'False', no
            formatting is performed

        If the language is not specified explicitly, language of the request is
        used.  If there is no language set in request, 'en' is assumed.  If no
        site specific text for the given language is defined in the database,
        the application defined default text is used.

        """
        lang = self._select_language(req, lang)
        return self._localized_text(req, self.text(text), lang, args)

    def parsed_text(self, req, text, lang=None, args=None):
        """Return 'lcg.Content' corresponding to given 'Text' instance.

        This method is similar to 'text()' but instead of returning the source
        text, it returns the corresponding 'lcg.Content' instance produced by
        processing the source text.  If the given text doesn't exist, 'None' is
        returned.

        """
        lang = self._select_language(req, lang)
        localizable_text = self.text(text)
        localized_text = self._localized_text(req, localizable_text, lang, args)
        # If the text comes from the database, use text2content
        # to respect the current setting of 'config.content_editor',
        # but if it is the default text defined by the application,
        # always parse it as structured text.
        if lang in localizable_text._translations:
            return text2content(req, localized_text)
        else:
            return lcg.Container(_parser.parse(localized_text))


class EmailText(Structure):
    """Representation of a predefined e-mail.

    Each predefined e-mail consists of the following attributes:

      label -- unique identifier of the e-mail, string
      description -- human description of the e-mail, presented to application
        administrators managing the e-mails
      subject -- subject of the mail, as a translatable plain text string
      text -- body of the mail, as a translatable plain text string
      cc -- comma separated recipient e-mail addresses, as a string

    Note the predefined e-mail texts get automatically localized.

    """
    _attributes = (Attribute('label', str),
                   Attribute('description', str),
                   Attribute('text', str),
                   Attribute('subject', str),
                   Attribute('cc', str, default=''),
                   Attribute('text_format', str),)

    @classmethod
    def _module_class(class_):
        return Emails

    def __init__(self, label, description, subject, text, **kwargs):
        Structure.__init__(self, label=label, description=description, subject=subject, text=text,
                           **kwargs)
        self._module_class().register_text(self)


class Emails(CommonTexts):
    """Management of predefined e-mails.

    This class provides the following special features:

    - E-mails may contain more data such as subjects or CC lists.

    - Application administrator can add his own e-mail texts.

    Standard predefined e-mails and custom ones are distinguished by an
    underscore prefix prepended to custom e-mail labels.

    """
    _DB_FUNCTIONS = dict(CommonTexts._DB_FUNCTIONS,
                         cms_add_email_label=(('label', pd.String()),))

    class LabelType(pytis.data.String):

        def _validate(self, obj, **kwargs):
            if isinstance(obj, str) and not obj.startswith('_'):
                obj = '_' + obj
            return pytis.data.String._validate(self, obj, **kwargs)

    class Spec(CommonTexts.Spec):

        table = 'cms_v_emails'
        title = _("E-mails")
        help = _("Edit e-mail texts.")

        def fields(self):
            override = (
                Field('label', type=Emails.LabelType(maxlen=64), editable=ONCE),
            )
            extra = (
                Field('subject', _("Subject")),
                Field('cc', _("Additional recipients"),
                      descr=_("Comma separated list of e-mail addresses.")),
            )
            return self._inherited_fields(Emails.Spec, override=override) + extra

        columns = ('label', 'descr',)
        sorting = (('label', ASC,),)
        layout = ('label', 'descr', 'subject', 'cc', 'content',)

    def _register_texts(self):
        for identifier, text in self.Spec._texts.items():
            if isinstance(text, EmailText):
                self._call_db_function('cms_add_email_label', text.label())

    def _actions(self, req, record):
        actions = super(Emails, self)._actions(req, record)
        if record is not None and not record['label'].value().startswith('_'):
            actions = [a for a in actions if a.id() != 'delete']
        return actions

    def _auto_filled_fields(self, req):
        def content(req, record, field_id):
            label = record['label'].value()
            if label is None:
                return ''
            lang = record['lang'].value()
            email = self.Spec._texts[label]
            if field_id == 'content':
                text = email.text()
            elif field_id == 'subject':
                text = email.subject()
            else:
                return ''
            return req.localize(text, lang)
        return (('content', content,),
                ('subject', content,),)

    def email_args(self, req, text, lang=None, args=None):
        """Return dictionary of some 'wiking.send_mail' arguments for 'text'.

        The dictionary contains 'subject', 'text', 'cc' and 'lang' keys with
        corresponding values.

        Arguments:

          req -- wiking request
          text -- 'EmailText' instance identifying the text
          lang -- two-character string identifying the language of the text
          args -- dictionary of formatting arguments for the text; if
            non-empty, the text is processed by the '%' operator and all '%'
            occurences within it must be properly escaped

        If the language is not specied explicitly, language of the request is
        used.  If there is no language set in request, 'en' is assumed.  If the
        text is not available for the selected language in the database, the
        method looks for the predefined text in the application and gettext
        mechanism is used for its translation.

        """
        assert isinstance(text, EmailText)
        lang = self._select_language(req, lang)
        text_id = text.label() + ':' + lang
        row = self._data.get_row(text_id=text_id)
        send_mail_args = dict(lang=lang, subject='', text='', cc=())
        if row is not None:
            send_mail_args['subject'] = row['subject'].value() or req.localize(text.subject(), lang)
            send_mail_args['text'] = row['content'].value() or req.localize(text.text(), lang)
            cc_string = row['cc'].value() or text.cc()
            if cc_string:
                send_mail_args['cc'] = [address.strip() for address in cc_string.split(',')]
        if args:
            for key in ('subject', 'text',):
                send_mail_args[key] = send_mail_args[key] % self._localized_args(req, lang, args)
        return send_mail_args


class TextReferrer:
    """Convenience class for modules using 'Texts' and 'Emails' modules.

    It defines convenience methods for text retrieval.

    The class is intended to be inherited as an additional class into Wiking
    modules using multiple inheritance.

    """

    def _text(self, req, text, lang=None, args=None):
        """Return text corresponding to 'text'.

        Arguments:

          req -- wiking request
          text -- 'Text' instance identifying the text
          lang -- two-character string identifying the language of the text
          args -- dictionary of formatting arguments for the text; if
            non-empty, the text is processed by the '%' operator and all '%'
            occurences within it must be properly escaped

        Looking texts for a particular language is performed according the
        rules documented in 'Texts.localized_text()'.

        """
        return wiking.module.Texts.localized_text(req, text, lang=lang, args=args)

    def _parsed_text(self, req, text, args=None, lang='en'):
        """Return parsed text corresponding to 'text'.

        This method is the same as '_text()' but instead of returning LCG
        structured text string, it returns its parsed form, as an 'lcg.Content'
        instance.  If the given text doesn't exist, 'None' is returned.

        """
        return wiking.module.Texts.parsed_text(req, text, lang=lang, args=args)

    def _email_args(self, *args, **kwargs):
        """The same as 'Emails.email_args'"""
        return wiking.module.Emails.email_args(*args, **kwargs)

    def _send_mail(self, req, text, recipients, lang=None, args=None, **kwargs):
        """Send e-mail identified by 'text' to 'recipients'.

        Arguments:

          req -- wiking request
          text -- 'EmailText' instance identifying the predefined e-mail
          recipients -- sequence of e-mail recipients, it can contain three
            kinds of elements: 1. string containing '@' representing an e-mail
            address, 2. 'Role' instance representing a user role,
            3. 'None' representing all registered users including disabled
            users
          lang -- two-character string identifying the preferred language of
            the text
          args -- dictionary of formatting arguments for the text; if
            non-empty, the text is processed by the '%' operator and all '%'
            occurences within it must be properly escaped
          kwargs -- other arguments to be passed to 'send_mail'

        """
        lang_args = {}

        def lang_email_args(lang):
            email_args = lang_args.get(lang)
            if email_args is None:
                email_args = self._email_args(req, text, lang=lang, args=args)
                email_args['cc'] = list(email_args['cc']) + list(kwargs.get('cc', []))
                for k, v in kwargs.items():
                    if k not in email_args:
                        email_args[k] = v
                lang_args[lang] = email_args
            return email_args
        addr = []
        for r in recipients:
            if r is None or isinstance(r, wiking.Role):
                users = self._module.find_users(role=r)
                for u in users:
                    wiking.send_mail(u.email(), **lang_email_args(u.lang()))
            else:
                addr.append(r)
        if addr:
            wiking.send_mail(addr, **lang_email_args(lang))


class EmailSpool(MailManagementModule):
    """Storage and archive for bulk e-mails sent to application users.
    """
    class Spec(Specification):

        table = 'cms_email_spool'
        # Translators: Section title and menu item. Sending emails to multiple recipients.
        title = _("Bulk E-mails")

        def fields(self):
            return (
                Field('id', editable=NEVER),
                Field('sender_address', _("Sender address"),
                      default=wiking.cfg.default_sender_address,
                      descr=_("E-mail address of the sender.")),
                # Translators: List of recipients of an email message
                Field('role_id', _("Recipients"), not_null=False,
                      # Translators: All users are intended recipients of an email message
                      codebook='UserGroups', selection_type=CHOICE, null_display=_("All users")),
                Field('subject', _("Subject")),
                ContentField('content', _("Text"), width=80, height=10),
                Field('date', _("Date"), default=now, editable=NEVER),
                Field('pid', editable=NEVER),
                Field('finished', editable=NEVER),
                Field('state', _("State"), type=pytis.data.String(), editable=NEVER,
                      virtual=True, computer=computer(self._state_computer)),
            )

        def _state_computer(self, row, pid, finished):
            if finished:
                # Translators: State of processing of an email message (e.g. Pending, Sending, Sent)
                state = _("Sent")
            elif pid:
                # Translators: State of processing of an email message (e.g. Pending, Sending, Sent)
                state = _("Sending")
            else:
                # Translators: State of processing of an email message (e.g. Pending, Sending, Sent)
                state = _("Pending")
            return state

        columns = ('id', 'subject', 'date', 'state',)
        sorting = (('date', DESC,),)
        layout = ('role_id', 'sender_address', 'subject', 'content', 'date', 'state',)

    _TITLE_TEMPLATE = _('%(subject)s')
    # Translators: Button label meaning save this email text for later repeated usage
    _COPY_LABEL = _("Use as a Template")
    # Translators: Description of button for creating a template of an email
    _COPY_DESCR = _("Edit this mail for repeated use")

    def _authorized(self, req, action, **kwargs):
        if action == 'update':
            return False
        if action == 'copy':
            return req.check_roles(*self._ADMIN_ROLES)
        else:
            return super(EmailSpool, self)._authorized(req, action, **kwargs)

    def _layout(self, req, action, **kwargs):
        if 'action' == 'insert':
            return ('role_id', 'sender_address', 'subject', 'content',)
        else:
            return super(EmailSpool, self)._layout(req, action, **kwargs)
