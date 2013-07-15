# -*- coding: utf-8 -*-
# Copyright (C) 2006-2013 Brailcom, o.p.s.
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

"""Definition of Wiking CMS modules.

The actual contents served by CMS modules, as well as its structure and application configuration,
is stored in database and can be managed using a web browser.

"""

import lcg
import pytis.data as pd
import pytis.presentation as pp
import pytis.web as pw
import wiking
from wiking import Binding, FieldSet, Forbidden, MenuItem, NotFound, PanelItem, \
    Redirect, Response, Role, Specification, Theme, make_uri
import wiking.cms

import collections
import datetime
import os
import re
import sys
import time
import difflib

from pytis.util import OPERATIONAL, Attribute, Structure, format_byte_size, log
import pytis.data
from pytis.presentation import computer, CodebookSpec, \
    Field, ColumnLayout, Action

CHOICE = pp.SelectionType.CHOICE
ALPHANUMERIC = pp.TextFilter.ALPHANUMERIC
LOWER = pp.PostProcess.LOWER
ONCE = pp.Editable.ONCE
NEVER = pp.Editable.NEVER
ALWAYS = pp.Editable.ALWAYS
ASC = pd.ASCENDENT
DESC = pd.DESCENDANT
now = pytis.data.DateTime.datetime
enum = lambda seq: pd.FixedEnumerator(seq)

_ = lcg.TranslatableTextFactory('wiking-cms')

class ContentField(Field):
    def __init__(self, name, label=None, descr=None, **kwargs):
        editor = wiking.cms.cfg.content_editor
        if editor == 'plain':
            msg = _("The content should be formatted as LCG structured text. "
                    "See the %(manual)s.",
                    manual=lcg.format('<a target="help" href="%s">%s</a>',
                                      '/_doc/lcg/structured-text',
                                      _("formatting manual")))
            if descr:
                descr += ' ' + msg
            else:
                descr = msg
            text_format = pp.TextFormat.LCG
        elif editor == 'html':
            text_format = pp.TextFormat.HTML
        else:
            raise Exception("Invalid value of 'wiking.cms.cfg.content_editor': %s" % editor)
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
        except Exception as e:
            content = lcg.Container((lcg.p(_("Error processing document content:")),
                                     lcg.PreformattedText("%s: %s" % (e.__class__.__name__, e))),
                                    name='wiking-content-processing-error')
            wiking.module.Application.send_bug_report(req, sys.exc_info())
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
        except:
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
         ['Users', 'ApplicationRoles', 'SessionLog', 'EmailSpool', 'CryptoNames']),
        # Translators: Heading and menu title. Computer idiom meaning configuration of appearance
        # (colors, sizes, positions, graphical presentation...).
        ('style', _("Look &amp; Feel"),
         _("Customize the appearance of your site."),
         ['StyleSheets', 'Themes']),
        # Translators: Heading and menu title for configuration.
        ('setup', _("Setup"),
         _("Edit global properties of your web site."),
         ['Config', 'Languages', 'Countries', 'Texts', 'Emails']),
    )
    
    def _handle(self, req):
        req.wmi = True # Switch to WMI only after successful authorization!
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
        variants = wiking.module('Application').languages()
        return [MenuItem('/_wmi/' + section, title, descr=descr, variants=variants,
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
    REGISTERED = Role('registered', _("Successfuly registered user"))
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
    USER_ADMIN = Role('user_admin', _("User administrator"))
    """User administrator."""
    # Translators: Name of a predefined user group.
    CRYPTO_ADMIN = Role('crypto_admin', _("Crypto administrator"))
    """Crypto stuff administrator."""
    # Translators: Name of a predefined user group.
    CONTENT_ADMIN = Role('content_admin', _("Content administrator"))
    """Content administrator."""
    # Translators: Name of a predefined user group.
    SETTINGS_ADMIN = Role('settings_admin', _("Settings administrator"))
    """Settings administrator."""
    # Translators: Name of a predefined user group.
    MAIL_ADMIN = Role('mail_admin', _("Mail administrator"))
    """Bulk mailing user and administrator."""
    # Translators: Name of a predefined user group.
    STYLE_ADMIN = Role('style_admin', _("Style administrator"))
    """Administrator of stylesheets, color themes and other web design related settings."""
    # Translators: Name of a predefined user group.
    ADMIN = Role('admin', _("Administrator"))
    """Administrator containing all administration roles.
    This is a container role, including all the C{*_ADMIN} roles defined here.
    Applications may include their own administration roles into this role by
    adding corresponding entries to the database table C{role_sets}.
    """
    
    def __getitem__(self, role_id):
        try:
            return super(Roles, self).__getitem__(role_id)
        except KeyError:
            role = wiking.module('ApplicationRoles').get_role(role_id)
            if role is None:
                raise KeyError(role_id)
            return role
    
    def all_roles(self):
        standard_roles = super(Roles, self).all_roles()
        user_defined_roles = wiking.module('ApplicationRoles').user_defined_roles()
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
            # This needs to be first in order to maintain backwards
            # compatibility with existing RIGHTS_* specifications.  When
            # RIGHTS_* are removed everywhere, calling super class should
            # become the last resort.
            return super(CMSModule, self)._authorized(req, action, **kwargs)
        elif action in ('view', 'list', 'rss', 'print_field'):
            return True
        elif action in ('insert', 'update', 'delete'):
            return req.check_roles(Roles.ADMIN)
        else:
            # Actions 'export' and 'copy' denied by default.  Enable explicitly when needed.
            return False

    def _embed_binding(self, modname):
        """Helper method to get a binding instance if given module is EmbeddableCMSModule."""
        try:
            cls = wiking.cfg.resolver.wiking_module_cls(modname)
        except:
            cls = None
        if cls and issubclass(cls, EmbeddableCMSModule):
            binding = cls.binding()
        else:
            binding = None
        return binding

    def _list_form_content(self, req, form, uri=None):
        # Add short module help text above the list form in WMI.
        content = []
        if req.wmi:
            help = self._view.help()
            if help:
                content = [lcg.p(help)]
        return content + super(CMSModule, self)._list_form_content(req, form, uri=uri)

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
            raise wiking.DecryptionError(unavailable_names.pop())

    def _generate_crypto_cookie(self):
        return wiking.module('Session').session_key()

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

    def panelize(self, req, lang, count, relation=None):
        count = count or self._PANEL_DEFAULT_COUNT
        fields = [self._view.field(id)
                  for id in self._PANEL_FIELDS or self._view.columns()]
        record = self._record(req, None)
        items = []
        for row in self._rows(req, condition=self._panel_condition(req, relation),
                              lang=lang, limit=count):
            record.set_row(row)
            item = PanelItem([(f.id(), record[f.id()].export(),
                               f.id() == self._title_column and
                               self._record_uri(req, record)) or None
                              for f in fields])
            items.append(item)
        if items:
            return items
        else:
            # Translators: Record as in `database record'.
            return (lcg.TextContent(_("No records.")),)


class _ManagementModule(CMSModule):
    _ADMIN_ROLES = ()
    def _authorized(self, req, action, **kwargs):
        if action in ('insert', 'update', 'delete'):
            return req.check_roles(*self._ADMIN_ROLES)
        else:
            return super(_ManagementModule, self)._authorized(req, action, **kwargs)

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
    
    
class Embeddable(object):
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
    class MenuItem(object):
        """Specification of a menu item bound to a submodule of an extension."""
        def __init__(self, modname, id=None, submenu=(), enabled=None, **kwargs):
            """Arguments:

               modname -- string name of the submodule derived from 'CMSExtensionModule'
               
               id -- item identifier as a string.  The default value is determined by transforming
                 'modname' to lower case using dashes to separate camel case words.  This
                 identifier is used as part of the URI of the item.
               enabled -- function of one argument (the request object) determining whether the
                 item is enabled (visible) in given context.  Note, that the URI of a disabled item
                 remains valid, so you still need to restrict access to the module by defining
                 access rights or any other means appropriate for the reason of unavalability of
                 the item.  This option only controls the presence of the item in the menu.  If
                 None (default), the item is always visible.
               submenu -- sequence of subordinate 'CMSExtension.MenuItem' instances.

            All other keyword arguments will be passed to 'MenuItem' constructor when converting
            the menu definition into a Wiking menu.

            """
            if __debug__:
                assert isinstance(modname, (str, unicode)), modname
                assert enabled is None or isinstance(enabled, collections.Callable), enabled
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
            submenu = [menu_item(i) for i in item.submenu] + submodule.submenu(req)
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

    
class CMSExtensionMenuModule(object):
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


class Config(SettingsManagementModule):
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
                            transform_default = lambda x: x and _("enabled") or _("disabled")
                        else:
                            transform_default = lambda x: x is None and _("undefined") or repr(x)
                    descr += ' ' + _("The default value is %s.", transform_default(default))
                self._cfg_option = option
                self._cfg_default_value = default
                Field.__init__(self, name, label, descr=descr, **kwargs)
            def configure(self, value):
                option = self._cfg_option
                if option is not None:
                    if value is None:
                        value = self._cfg_default_value
                    option.set_value(value)
                
        # Translators: Website heading and menu item
        title = _("Basic Configuration")
        help = _("Edit site configuration.")
        table = 'cms_config'
        def fields(self):
            F = self._Field
            return (
                F('site'),
                F('theme_id', codebook='Themes'),
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
                F('allow_login_panel'),
                F('allow_registration'),
                F('force_https_login'),
                F('upload_limit',
                  transform_default=lambda n: repr(n) + ' (' + format_byte_size(n) + ')'),
            )
        layout = ('site_title', 'site_subtitle', 'webmaster_address', 'default_sender_address',
                  'allow_login_panel', 'allow_registration', 'force_https_login', 'upload_limit')
    _TITLE_TEMPLATE = _("Basic Configuration")

    def _resolve(self, req):
        # We always work with just one record.
        return self._data.get_row(site=wiking.cfg.server_hostname)
    
    def _default_action(self, req, **kwargs):
        return 'update'
        
    def _redirect_after_update(self, req, record):
        req.message(self._update_msg(req, record))
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
        # This dummy read of wiking.cms.cfg.allow_registration is here to
        # force reading wiking.cms.cfg before updating it.  Not doing so may
        # lead to owerwriting the updated values by the default values from the
        # confuiguration file after its change, because config file
        # modification is detected only after an attempt to read a value.  This
        # is not a perfect solution - better would be to recognize the
        # precedence of configuration value sources directly within the
        # Configuration class.
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
        for f in self._view.fields():
            f.configure(row[f.id()].value())
        try:
            theme_id = int(req.param('preview_theme'))
        except (TypeError, ValueError):
            theme_id = row['theme_id'].value()
        if theme_id is None:
            if isinstance(wiking.cfg.theme, Themes.Theme):
                wiking.cfg.theme = Theme()
        elif (not isinstance(wiking.cfg.theme, Themes.Theme) or
              wiking.cfg.theme.theme_id() != theme_id):
            wiking.cfg.theme = wiking.module('Themes').theme(theme_id)

    def set_theme(self, req, theme_id):
        row = self._data.get_row(site=wiking.cfg.server_hostname)
        record = self._record(req, row)
        try:
            record.update(theme_id=theme_id)
        except pd.DBException as e:
            return self._error_message(*self._analyze_exception(e))

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
        fields = (Field('page_id', enumerator='PageTitles'),
                  Field('site'),
                  Field('kind'),
                  Field('identifier'),
                  Field('modname'),
                  Field('parent'),
                  Field('ord'),
                  Field('menu_visibility'),
                  Field('tree_order'),
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
    
    
class Panels(SiteSpecificContentModule):
    """Manage a set of side panels.

    The panels are stored in a Pytis data object to allow their management through WMI.

    """
    class Spec(Specification):
        # Translators: Panels are small windows containing different things (such as recent news,
        # application specific controls, sponsorship reference etc.) displayed by the side of a
        # webpage.  To avoid confusion, we should avoid terms such as "windows", "frames"
        # etc. which all have their specific meaning in computer terminology.
        title = _("Panels")
        help = _(u"Manage panels – the small windows shown by the side of "
                 "every page.")
        table = 'cms_v_panels'
        def fields(self):
            return (
                Field('panel_id', width=5, editable=NEVER),
                Field('site'),
                Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                      selection_type=CHOICE, value_column='lang'),
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
                Field('page_id', _("List items"), width=5, not_null=False, codebook='PageStructure',
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
                # Translators: Yes/no option whether the item is publically
                # visible. Followed by a checkbox.
                Field('published', _("Published"), default=True,
                      descr=_("Controls whether the panel is actually displayed.")),
            )
        sorting = (('ord', ASC),)
        columns = ('title', 'identifier', 'ord', 'modtitle', 'size', 'published', 'content')
        layout = ('title', 'identifier', 'ord', 'page_id', 'size', 'content', 'published')
        actions = (
            Action('publish', _("Publish"),
                   enabled=lambda r: not r['published'].value(),
                   descr=_("Make the panel visible in production mode")),
            Action('unpublish', _("Unpublish"),
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
        hidden_fields.append(('_manage_cms_panels', '1'))
        return hidden_fields

    def _delete_confirmation_actions(self, req, record, action):
        return (Action('delete', self._DELETE_LABEL, _manage_cms_panels='1',
                       panel_id=record['panel_id'].export(), submit=1),)
        
    def panels(self, req, lang):
        panels = []
        #TODO: tady uvidim prirazenou stranku, navigable
        roles = wiking.module('Users').Roles()
        if wiking.module('Application').preview_mode(req):
            restriction = {}
        else:
            restriction = {'published': True}
        for row in self._data.get_rows(site=wiking.cfg.server_hostname, lang=lang,
                                       sorting=self._sorting, **restriction):
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
                    if isinstance(enabled, collections.Callable):
                        enabled = enabled(record)
                    return enabled
                items = [lcg.PopupMenuItem(action.title(),
                                           tooltip=action.descr(),
                                           enabled=is_enabled(action),
                                           uri=req.make_uri('/', _manage_cms_panels='1',
                                                            action=action.id(),
                                                            panel_id=row['panel_id'].export()))
                         for action in self._form_actions(req, record, None)]
                titlebar_content = lcg.PopupMenuCtrl(items, tooltip=_("Popup the menu of actions "
                                                                      "for this panel"),
                                                     active_area_selector='h3')
            else:
                titlebar_content = None
            panels.append(wiking.Panel(panel_id, title, content,
                                       titlebar_content=titlebar_content, channel=channel))
            
        return panels

    def action_publish(self, req, record, publish=True):
        try:
            record.update(published=publish)
        except pd.DBException as e:
            req.message(self._error_message(*self._analyze_exception(e)), type=req.ERROR)
        else:
            if publish:
                msg = _("The panel was published.")
            else:
                msg = _("The panel was unpublished.")
            req.message(msg)
        raise Redirect(req.uri())

    def action_unpublish(self, req, record):
        return self.action_publish(req, record, publish=False)

    
class Languages(SettingsManagementModule):
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
    _language_list = None
    _language_list_time = None
    
    def languages(self):
        if ((self._language_list_time is None or
             time.time() - self._language_list_time > 30)):
            Languages._language_list = [str(r['lang'].value()) for r in self._data.get_rows()]
            Languages._language_list_time = time.time()
        return self._language_list


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
    _language_list = None
    _language_list_time = None

    
class Themes(StyleManagementModule):
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
            return (isinstance(wiking.cfg.theme, Themes.Theme) and
                    wiking.cfg.theme.theme_id() == theme_id)
        def _title(self, row, name, active):
            return name + (active and ' (' + _("active") + ')' or '')
        def _preview(self, record):
            # TODO: It would be better to have a special theme demo page, which
            # would display all themable constructs.
            # TODO: Disable user interaction within the iframe.
            req = record.req()
            # We can't rely on redirection here as it would not pass the
            # preview_theme argument.
            menu = [item for item in wiking.module('Pages').menu(req) if not item.hidden()]
            if menu:
                uri = menu[0].id()
            else:
                uri = '/_wmi/Users'
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
            Action('activate', _("Activate"), descr=_("Activate this color theme"),
                   enabled=lambda r: not r['active'].value()),
            # Translators: Button label
            Action('activate', _("Activate default"), context=pp.ActionContext.GLOBAL,
                   descr=_("Activate the default color theme"),
                   enabled=lambda r: isinstance(wiking.cfg.theme, Themes.Theme)),
        )
        
    _ROW_ACTIONS = True

    class Theme(Theme):
        def __init__(self, row):
            self._theme_id = row['theme_id'].value()
            colors = [(c.id(), row[c.id()].value())
                      for c in self.COLORS if row[c.id()].value() is not None]
            super(Themes.Theme, self).__init__(colors=dict(colors))
        def theme_id(self):
            return self._theme_id

    def _authorized(self, req, action, **kwargs):
        if action in ('copy', 'activate'):
            return req.check_roles(*self._ADMIN_ROLES)
        else:
            return super(Themes, self)._authorized(req, action, **kwargs)
        
    def theme(self, theme_id):
        row = self._data.get_row(theme_id=theme_id)
        return self.Theme(row)
        
    def action_activate(self, req, record=None):
        if record:
            theme_id = record['theme_id'].value()
            name = record['name'].value()
            wiking.cfg.theme = self.Theme(record.row())
        else:
            theme_id = None
            name = _("Default")
            wiking.cfg.theme = Theme()
        err = wiking.module('Config').set_theme(req, theme_id)
        if err is None:
            req.message(_("The color theme \"%s\" has been activated.", name))
        else:
            req.message(err, type=req.ERROR)
        req.set_param('search', theme_id)
        raise Redirect(self._current_base_uri(req, record))
    

# ==============================================================================
# The modules below handle the actual content.
# The modules above are system modules used internally by Wiking.
# ==============================================================================

class Pages(SiteSpecificContentModule):
    """Define available pages and their content and allow their management.

    This module implements the key CMS functionality.  Pages, their hierarchy, content and other
    properties are managed throug a Pytis data object.
    
    """
    class PagePositionEnumerator(pytis.data.Enumerator):
        def values(self, **kwargs):
            return wiking.module('PageStructure').page_position_selection(**kwargs)
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
        help = _("Manage available pages and their content.")
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
                      descr=_("The identifier may be used to refer to this page from outside "
                              "and also from other pages. "
                              "A valid identifier can only contain letters, digits, "
                              "dashes and underscores.  It must start with a letter.")),
                Field('lang', _("Language"), editable=ONCE, codebook='Languages',
                      value_column='lang'),
                Field('title_or_identifier', _("Title")),
                Field('title', _("Title"), not_null=True),
                Field('description', _("Description"), width=64,
                      descr=_("Brief description shown as a tooltip on links (such as menu items) "
                              "and in site map.")),
                ContentField('_content', _("Content"), compact=True, height=20, width=80,
                             attachment_storage=self._attachment_storage),
                ContentField('content'),
                Field('comment', _("Comment"), virtual=True, width=70,
                      descr=_("Describe briefly the changes you made.")),
                # Translators: "Module" is an independent reusable part of a computer program
                # (here a module of Wiking CMS).
                Field('modname', _("Module"), display=_modtitle, prefer_display=True,
                      not_null=False,
                      enumerator=enum([_m.name() for _m in wiking.cfg.resolver.available_modules()
                                       if issubclass(_m, Embeddable)
                                       and _m not in (EmbeddableCMSModule, CMSExtension)]),
                      descr=_("Select the extension module to embed into the page.  Leave blank "
                              "for an ordinary text page.")),
                # Translators: "Parent item" has the meaning of hierarchical position.  More precise
                # term might be "Superordinate item" but doesn't sound that nice in English.
                # The term "item" represents a page, but also a menu item.
                Field('parent', _("Parent item"), codebook='PageStructure', not_null=False,
                      runtime_filter=computer(lambda r, site: pd.EQ('site', pd.sval(site))),
                      descr=_("Select the superordinate item in page hierarchy.  Leave blank for "
                              "a top-level page.")),
                # Translators: Page configuration option followed by a selection
                # input field.  Determines the position in the sense of order in a
                # sequence.  What is first and what next.
                Field('ord', _("Position"),
                      enumerator=Pages.PagePositionEnumerator(), editable=ALWAYS,
                      runtime_arguments=computer(lambda r, site, parent, page_id:
                                                 dict(site=site, parent=parent, page_id=page_id)),
                      computer=computer(Pages.PagePositionEnumerator().last_position),
                      display=lambda x: x.label, # See PageStructure.page_position_selection().
                      descr=_("Select the position within the items of the same level.")),
                Field('menu_visibility', _("Visibility in menu"),
                      enumerator=Pages.MenuVisibility, selection_type=pp.SelectionType.RADIO,
                      descr=_('When "%(always)s" is selected, unauthorized users see the menu '
                              'item, but still can not open the page.  When "%(authorized)s" '
                              'is selected, visibility is controlled by the "Access Rights" '
                              'settings below.  Note, that when access rights are restricted, '
                              'the item will be hidden until the user logs in, which may be '
                              'confusing (the expected item is not there).',
                              always=dict(Pages.MenuVisibility.enumeration).get('always'),
                              authorized=dict(Pages.MenuVisibility.enumeration).get('authorized'))),
                Field('foldable', _("Foldable"), editable=computer(lambda r, menu_visibility:
                                                                   menu_visibility != 'never'),
                      descr=_("Check if you want the relevant menu item to be foldable (only makes "
                              "sense for pages, which have subordinary items in the menu).")),
                Field('tree_order', type=pd.TreeOrder()),
                Field('creator', _("Creator"), codebook='Users'),
                Field('created', _("Created"), default=now),
                Field('published_since', _("Published since")),
                # Translators: Configuration option determining whether the page is published or not
                # (passive form of publish).  The label may be followed by a checkbox.
                Field('published', _("Published"), default=False,
                      descr=_("Allows you to control the availability of this page in each of the "
                              "supported languages (switch language to control the availability in "
                              "other languages)")),
                Field('status', _("Status"), virtual=True, computer=computer(self._status)),
                #Field('grouping', virtual=True,
                #      computer=computer(lambda r, tree_order: tree_order.split('.')[1])),
                # Translators: Label of a selector of a group allowed to access the page read only.
                Field('read_role_id', _("Read only access"), codebook='ApplicationRoles',
                      default=Roles.ANYONE.id(),
                      descr=_("Select the role allowed to view the page contents.")),
                # Translators: Label of a selector of a group allowed to edit the page.
                Field('write_role_id', _("Read/write access"), codebook='ApplicationRoles',
                      default=Roles.CONTENT_ADMIN.id(),
                      descr=_("Select the role allowed to edit the page contents.")),
            )
        def _status(self, record, published, _content, content):
            if not published:
                return _("Not published")
            elif _content == content:
                return _("Ok")
            else:
                return _("Changed")
        def _default_identifier(self, record, title):
            import unicodedata
            if title and record['identifier'].value() is None:
                # This only applies on new record insertion and not during further editation.
                without_accents = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore')
                return re.sub(r'[^a-z0-9-]', '', without_accents.lower().replace(' ', '-'))
            else:
                return record['identifier'].value()
        def _attachment_storage_uri(self, record):
            return '/' + record['identifier'].export() + '/attachments'
        def _attachment_storage(self, record):
            return Attachments.AttachmentStorage(record.req(),
                                                 record['page_id'].value(),
                                                 record['lang'].value(),
                                                 self._attachment_storage_uri(record))
        def row_style(self, record):
            return not record['published'].value() and pp.Style(foreground='#777') or None
        def check(self, record):
            parent = record['parent'].value()
            if parent is not None and parent == record['page_id'].value():
                return ('parent', _("A page can not be its own parent."))
        condition = pd.EQ('kind', pd.sval('page'))
        sorting = (('tree_order', ASC), ('identifier', ASC),)
        #grouping = 'grouping'
        #group_heading = 'title'
        layout = ()
        columns = ('title_or_identifier', 'identifier', 'modname', 'status',
                   'menu_visibility', 'read_role_id', 'write_role_id')
        cb = CodebookSpec(display='title_or_identifier', prefer_display=True)
        actions = (
            # Translators: Button label. Page configuration options.
            Action('options', _("Options"),
                   descr=_("Edit global (language independent) page options and menu position")),
            Action('commit', _("Publish"), descr=_("Publish the page in its current state"),
                   enabled=lambda r: (r['_content'].value() != r['content'].value()
                                      or not r['published'].value())),
            Action('unpublish', _("Unpublish"),
                   descr=_("Make the page invisible in production mode"),
                   enabled=lambda r: r['published'].value()),
            Action('revert', _("Revert"),
                   descr=_("Revert the unpublished changes in page text "
                           "to the last published state"),
                   enabled=lambda r: r['_content'].value() != r['content'].value()),
            #Action('translate', _("Translate"),
            #      descr=_("Create the content by translating another language variant"),
            #       enabled=lambda r: r['_content'].value() is None),
            Action('new_page', _("New Page"), descr=_("Create a new page")),
            # The action seems inadequate in row context menu and the help page
            # is out of date anyway.
            #Action('help', _("Help")),
        )
        # Translators: Noun. Such as e-mail attachments (here attachments for a webpage).
        bindings = (Binding('attachments', _("Attachments"), 'Attachments', 'page_id'),
                    Binding('history', _("History"), 'PageHistory', 'page_key'),)

    _REFERER = 'identifier'
    _EXCEPTION_MATCHERS = (
        ('duplicate key (value )?violates unique constraint "cms_pages_pkey"',
         _("The page already exists in given language.")),
        ('duplicate key (value )?violates unique constraint "cms_pages_unique_tree_(?P<id>ord)er"',
         _("Duplicate menu order at this level of hierarchy.")),) + \
        SiteSpecificContentModule._EXCEPTION_MATCHERS
    _LIST_BY_LANGUAGE = True
    _LAYOUT = {'insert':
               (FieldSet(_("Page Text (for the current language)"),
                         ('title', 'description', '_content')),
                FieldSet(_("Global Options (for all languages)"),
                         ('identifier', 'modname',
                          FieldSet(_("Menu position"), ('parent', 'ord', 'menu_visibility',
                                                        'foldable')),
                          FieldSet(_("Access Rights"), ('read_role_id', 'write_role_id',)),
                          ))),
               'update': ('title', 'description', '_content', 'comment'),
               'delete': (),
               'options':
               (FieldSet(_("Basic Options"), ('identifier', 'modname',)),
                FieldSet(_("Menu position"), ('parent', 'menu_visibility', 'ord', 'foldable')),
                FieldSet(_("Access Rights"), ('read_role_id', 'write_role_id')),
                )
               }
    _SUBMIT_BUTTONS_ = ((_("Save as concept"), None), (_("Save and publish"), 'commit'))
    _SUBMIT_BUTTONS = {'update': _SUBMIT_BUTTONS_,
                       'insert': _SUBMIT_BUTTONS_}
    _INSERT_LABEL = _("New page")
    _UPDATE_LABEL = _("Edit Text")
    _UPDATE_DESCR = _("Edit title, description and content for the current language")
    _LIST_LABEL = _("List all pages")
    _SEPARATOR = re.compile('^====+\s*$', re.MULTILINE)
    _HONOUR_SPEC_TITLE = True
    _ROW_ACTIONS = True

    def __init__(self, *args, **kwargs):
        super(Pages, self).__init__(*args, **kwargs)
        
    def _handle(self, req, action, **kwargs):
        # TODO: This is a hack to find out the parent page and access rights in
        # the embedded modules.
        if not hasattr(req, 'page_record'):
            record = kwargs.get('record')
            req.page_record = record
            req.page_read_access = self._authorized(req, 'view', record=record)
            req.page_write_access = self._authorized(req, 'update', record=record)
        return super(Pages, self)._handle(req, action, **kwargs)
        
    def _authorized(self, req, action, record=None, **kwargs):
        if action in ('new_page', 'insert', 'list', 'options', 'publish', 'unpublish',
                      'delete', 'translate'):
            roles = (Roles.CONTENT_ADMIN,)
        else:
            roles_module = wiking.module('Users').Roles()
            if record and action in ('view', 'rss'):
                roles = (roles_module[record['read_role_id'].value()],
                         roles_module[record['write_role_id'].value()],
                         Roles.CONTENT_ADMIN,)
            elif record and action in ('update', 'commit', 'revert', 'attachments'):
                roles = (roles_module[record['write_role_id'].value()],
                         Roles.CONTENT_ADMIN,)
            else:
                roles = () # raise NotFound or BadRequest?
        return req.check_roles(*roles)
        
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

    def _current_base_uri(self, req, record=None):
        return '/'

    def _resolve(self, req):
        if wiking.module('Application').preview_mode(req):
            restriction = {}
        else:
            restriction = {'published': True}
        if not req.unresolved_path:
            return None
        identifier = req.unresolved_path[0]
        # Recognize special path of RSS channel as '<identifier>.<lang>.rss'.
        if identifier.endswith('.rss'):
            req.set_param('action', 'rss')
            identifier = identifier[:-4]
            if len(identifier) > 3 and identifier[-3] == '.' and identifier[-2:].isalpha():
                lang = str(identifier[-2:])
                row = self._data.get_row(site=wiking.cfg.server_hostname,
                                         identifier=identifier[:-3], lang=lang, **restriction)
                if row:
                    del req.unresolved_path[0]
                    return row
        rows = self._data.get_rows(site=wiking.cfg.server_hostname,
                                   identifier=identifier, **restriction)
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
        elif self._data.get_rows(identifier=identifier, site=wiking.cfg.server_hostname):
            if req.check_roles(Roles.CONTENT_ADMIN) and restriction:
                req.message(_("The page exists but is not published. "
                              "You need to switch to the Preview mode to be able to access it."),
                            type=req.WARNING)
            raise Forbidden()
        else:
            raise NotFound()

    def _prefill(self, req):
        return dict(super(Pages, self)._prefill(req),
                    lang=req.preferred_language(raise_error=False),
                    creator=req.user().uid())

    def _validate(self, req, record, layout):
        errors = super(Pages, self)._validate(req, record, layout)
        if not errors and req.has_param('commit'):
            record['content'] = record['_content']
            record['published'] = pd.bval(True)
            if ((not record.original_row()['published'].value() and
                 record['published_since'].value() is None)):
                record['published_since'] = pd.Value(record.type('published_since'), now())
        if record['creator'].value() is None:
            # Supply creator to a newly created language variant (where prefill
            # doesn't apply because it actually is an update, not insert).
            record['creator'] = pd.Value(record.type('creator'), req.user().uid())
        if record['created'].value() is None:
            record['created'] = pd.Value(record.type('created'), now())
        return errors
    
    def _insert_transaction(self, req, record):
        return self._transaction()
    
    def _update_transaction(self, req, record):
        return self._transaction()
    
    def _insert(self, req, record, transaction):
        result = super(Pages, self)._insert(req, record, transaction)
        wiking.module('PageHistory').on_page_change(req, record, transaction=transaction)
        return result
        
    def _update(self, req, record, transaction):
        result = super(Pages, self)._update(req, record, transaction)
        wiking.module('PageHistory').on_page_change(req, record, transaction=transaction)
        return result

    def _insert_msg(self, req, record):
        if record['published'].value():
            return _("New page was successfully created and published.")
        else:
            return _("New page was successfully created, but was not published yet. "
                     "Publish it when you are done.")
        
    def _update_msg(self, req, record):
        if record['content'].value() == record['_content'].value():
            return super(Pages, self)._update_msg(req, record)
        else:
            return _("Page content was modified, however the changes remain unpublished. "
                     "Don't forget to publish the changes when you are done.")

    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid == 'parent':
            return None
        return super(Pages, self)._link_provider(req, uri, record, cid, **kwargs)

    def _redirect_after_insert(self, req, record):
        req.message(self._insert_msg(req, record))
        if not req.has_param('commit'):
            wiking.module('Application').set_preview_mode(req, True)
        raise Redirect(self._current_record_uri(req, record))
        
    def _redirect_after_update(self, req, record):
        req.message(self._update_msg(req, record))
        if not req.has_param('commit'):
            wiking.module('Application').set_preview_mode(req, True)
        raise Redirect(req.uri())
        
    def _delete_form_content(self, req, form, record):
        return [form] + self._page_content(req, record)

    def _visible_in_menu(self, req, row):
        """Return True or False if page described by row is visible or not in the menu"""
        visibility = row['menu_visibility'].value()
        if visibility == 'always':
            return True
        elif visibility == 'authorized':
            roles = wiking.module('Users').Roles()
            return req.check_roles(roles[row['read_role_id'].value()],
                                   roles[row['write_role_id'].value()])
        elif visibility == 'never':
            return False

    # Public methods
    
    def menu(self, req):
        children = {None: []}
        translations = {}
        application = wiking.module('Application')
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
                variants = titles.keys()
            return MenuItem('/' + identifier,
                            title=lcg.SelfTranslatableText(identifier, translations=titles),
                            descr=lcg.SelfTranslatableText('', translations=descriptions),
                            hidden=not self._visible_in_menu(req, row),
                            foldable=bool(row['foldable'].value()),
                            variants=variants,
                            submenu=submenu)
        if preview_mode:
            restriction = {}
        else:
            restriction = {'published': True}
        for row in self._data.get_rows(site=wiking.cfg.server_hostname,
                                       sorting=self._sorting, **restriction):
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

    def _page_content(self, req, record):
        # Main content
        modname = record['modname'].value()
        if modname is not None:
            content = wiking.module(modname).embed(req)
        else:
            content = []
        if wiking.module('Application').preview_mode(req):
            text = record['_content'].value()
        else:
            text = record['content'].value()
        if text:
            if self._SEPARATOR.search(text):
                pre, post = self._SEPARATOR.split(text, maxsplit=2)
            else:
                pre, post = text, u''
            content = [text2content(req, pre)] + content + [text2content(req, post)]
        # Process page attachments
        storage = record.attachment_storage('_content')
        resources = storage.resources()
        # Create automatic image gallery if any attachments are marked as in gallery.
        gallery_images = [r for r in resources if r.info()['in_gallery']]
        if gallery_images:
            content.append(Attachments.ImageGallery(gallery_images))
        # Create automatic attachment list if any attachments are marked as listed.
        listed_attachments = [(lcg.link(r.uri(), r.title() or r.filename()),
                               ' (' + r.info()['byte_size'] + ') ',
                               lcg.coerce(r.descr() or '', formatted=True))
                              for r in resources if r.info()['listed']]
        if listed_attachments:
            # Translators: Section title. Attachments as in email attachments.
            content.append(lcg.Section(title=_("Attachments"), content=lcg.ul(listed_attachments),
                                       anchor='attachment-automatic-list')) # Prevent dupl. anchor.
        # Load Lightbox if there are any images with thumbnails within the attachments.
        if any(isinstance(r, lcg.Image) and r.thumbnail() for r in resources):
            resources.extend((lcg.Script('prototype.js'),
                              lcg.Script('effects.js'),
                              lcg.Script('builder.js'),
                              lcg.Script('lightbox.js'),
                              lcg.Stylesheet('lightbox.css')))
        if content and resources:
            return [lcg.Container(content, resources=resources)]
        else:
            return content

    # Action handlers.
        
    def action_view(self, req, record):
        content = self._page_content(req, record)
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
                    if wiking.module('Application').preview_mode(req):
                        req.message(_("This page has no content. "
                                      "Users will be redirected to the first visible "
                                      "subpage in production mode.", type=req.WARNING))
                        break
                    else:
                        raise Redirect('/' + row['identifier'].value())
        if req.check_roles(Roles.CONTENT_ADMIN):
            # Append an empty show form just for the action menu.
            form = self._form(pw.ShowForm, req, record=record, layout=(),
                              actions=self._form_actions_argument(req))
            content.extend([lcg.Container(form, id='cms-page-actions')] +
                           self._related_content(req, record))
        return self._document(req, content, record)

    def action_update(self, req, record, action='update'):
        application = wiking.module('Application')
        if action == 'update' and not application.preview_mode(req) \
                and record['content'].value() != record['_content'].value():
            req.message(_("The page has unpublished changes (not visible in production mode)."),
                        type=req.WARNING)
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
                req.message(_("Content for this page already exists!"), type=req.ERROR)
                raise Redirect(self._current_record_uri(req, record))
            cond = pd.AND(pd.NE('_content', pd.Value(pd.String(), None)),
                          pd.NE('lang', record['lang']))
            langs = [str(row['lang'].value()) for row in
                     self._data.get_rows(page_id=record['page_id'].value(), condition=cond)]
            if not langs:
                req.message(_("Content for this page does not exist in any language."),
                            type=req.ERROR)
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
        values = dict(content=record['_content'].value(), published=True)
        if not record['published'].value() and record['published_since'].value() is None:
            values['published_since'] = now()
        if record['title'].value() is None:
            if record['modname'].value() is not None:
                # Supply the module's title automatically.
                mod = wiking.module(record['modname'].value())
                values['title'] = req.localize(mod.title(), record['lang'].value())
            else:
                req.message(_("Can't publish untitled page."), type=req.ERROR)
                raise Redirect(self._current_record_uri(req, record))
        try:
            record.update(**values)
        except pd.DBException as e:
            req.message(self._error_message(*self._analyze_exception(e)), type=req.ERROR)
        else:
            req.message(_("The changes were published."))
        raise Redirect(self._current_record_uri(req, record))

    def action_revert(self, req, record):
        try:
            record.update(_content=record['content'].value())
        except pd.DBException as e:
            req.message(self._error_message(*self._analyze_exception(e)), type=req.ERROR)
        else:
            req.message(_("The page contents was reverted to its previous state."))
        raise Redirect(self._current_record_uri(req, record))
    
    def action_unpublish(self, req, record):
        try:
            record.update(published=False)
        except pd.DBException as e:
            req.message(self._error_message(*self._analyze_exception(e)), type=req.ERROR)
        else:
            req.message(_("The page was unpublished. "
                          "It will not be visible in production mode anymore."))
        wiking.module('Application').set_preview_mode(req, True)
        raise Redirect(self._current_record_uri(req, record))

    def action_new_page(self, req, record):
        raise Redirect(self._current_base_uri(req, record), action='insert',
                       parent=record['parent'].value(), ord=record['ord'].value())

    #def action_help(self, req, record):
    #    raise Redirect('/_doc/wiking/cms/pages')


class NavigablePages(Pages):
    """Pages which have a simple sequential navigation bar at the top and bottom."""

    class Navigation(lcg.Content):

        def __init__(self, position):
            self._position = position
            super(NavigablePages.Navigation, self).__init__()
            
        def export(self, context):
            g = context.generator()
            req = context.req()
            node = context.node()
            publication_id = '/%s/data/%s' % (req.page_record['identifier'].value(),
                                              req.publication_record['identifier'].value())
            publication = [n for n in node.path() if n.id() == publication_id][0]
            def ctrl(target, cls, label):
                # Check that the target node is within the publications's children.
                if target and publication in target.path():
                    uri = context.uri(target)
                    title = target.title()
                else:
                    # Translators: Label used instead of a link when the target
                    # does not exist.  For example sequential navigation may
                    # contain: "Previous: Introduction, Next: None".
                    uri = None
                    title = _("None")
                    cls += ' dead'
                return g.a(label, href=uri, title=label + ': ' + title,
                           cls='navigation-ctrl ' + cls)
            # Translators: Label of a link in sequential navigation.
            return g.div((ctrl(node.prev(), 'prev', _('Previous Chapter')), ' | ',
                          ctrl(node.next(), 'next', _('Next Chapter'))),
                         cls='page-navigation ' + self._position)

    def _inner_page_content(self, req, record):
        return super(NavigablePages, self)._page_content(req, record)

    def _page_content(self, req, record):
        return ([self.Navigation('top')] +
                self._inner_page_content(req, record) +
                [self.Navigation('bottom')])


class Publications(NavigablePages, EmbeddableCMSModule):
    """e-Publications management as a CMS module.

    e-Publication (e-Book) is created as a hierarchy of CMS pages.  The top
    level page represents the publication, subordinary pages are its chapters.
    This module may be added to any CMS page (it is an embeddable CMS module)
    and it will consist of a listing of available e-Publications in
    alphabetical order.  Entering a particular publication will add its
    hierarchy to the CMS menu.
    
    """
    
    class Spec(Pages.Spec):
        title = _("e-Publications")
        table = 'cms_v_publications'
        def fields(self):
            override = (
                Field('kind', default='publication'),
                Field('_content', _("Title Page")),
                Field('description', _("Subtitle")),
                Field('creator', _("Digitalized by")),
                Field('published_since', _("Available since")),
                Field('parent',
                      computer=computer(lambda r: r.req().page_record['page_id'].value())),
                Field('menu_visibility', default='never'),
                Field('status', visible=computer(self._preview_mode)),
                #Field('read_role_id', visible=computer(self._is_admin)),
                #Field('write_role_id', visible=computer(self._is_admin)),
            )
            extra = (
                Field('author', _("Author"), width=60, not_null=True,
                      descr=_("Author's full name or a comma separated list of full names.")),
                Field('isbn', _("ISBN"), width=20,
                      descr=_("ISBN of the original book if the publication is "
                              "a digitalized book.")),
                Field('cover_image', _("Cover Image"), not_null=False,
                      codebook='Attachments', value_column='attachment_id',
                      runtime_filter=computer(self._attachment_filter), display='filename',
                      descr=_("Insert the image as an attachment and select it "
                              "from the list here.")),
                Field('illustrator', _("Illustrator"), width=50,
                      descr=_("Full name or a comma separated list of full names.")),
                Field('publisher', _("Publisher"), width=30,
                      descr=_("Name of the organization which published the original work.")),
                Field('published_year', _("Year Published"), width=4,
                      descr=_("Year when the original work was published.")),
                Field('edition', _("Edition"), width=3,
                      descr=_("Numeric order of the original work's edition.")),
                Field('notes', _("Notes"), width=60, height=4,
                      descr=_("Any other additional information about the publication, "
                              "such as names of translators, reviewers etc.")),
                Field('pubinfo', _("Published<publisher>"), virtual=True,
                      computer=computer(self._pubinfo)),
            )
            return self._inherited_fields(Publications.Spec, override=override) + extra
        def _preview_mode(self, record):
            return wiking.module('Application').preview_mode(record.req())
        #def _is_admin(self, record):
        #    return record.req().check_roles(Roles.CONTENT_ADMIN)
        def _attachment_filter(self, record, page_id, lang):
            return pd.AND(pd.EQ('page_id', pd.ival(page_id)),
                          pd.EQ('lang', pd.sval(lang)),
                          pd.WM('mime_type', pd.WMValue(pd.String(), 'image/*')))
        def _attachment_storage_uri(self, record):
            return '/%s/data/%s/attachments' % (record.req().page_record['identifier'].value(),
                                                record['identifier'].value())
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
        layout = ('title', 'description', 'lang', 'identifier', 'cover_image',
                  FieldSet(_("Bibliographic information"),
                           ('author', 'illustrator', 'isbn',
                            'publisher', 'published_year', 'edition', 'notes')),
                  '_content',
                  FieldSet(_("Access Rights"),
                           ('read_role_id', 'write_role_id',)),
                  )
        columns = ('title', 'author', 'publisher', 'status')
        sorting = ('title', pd.ASCENDENT),
        bindings = (
            Binding('chapters', _("Chapters"), 'PublicationChapters', 'parent'),
        ) + Pages.Spec.bindings
        actions = Pages.Spec.actions + (
            Action('new_chapter', _("New Chapter"),
                   descr=_("Create a new chapter in this publication.")),
            Action('export_epub', _("Export to EPUB"),
                   descr=_("Export the publication to EPUB format")),
            Action('export_braille', _("Export to Braille"),
                   descr=_("Export the publication to Braille")),
        )
    
    _LIST_BY_LANGUAGE = False
    _INSERT_LABEL = _("New e-Publication")
    _UPDATE_LABEL = _("Edit")
    _EMBED_BINDING_COLUMN = 'parent'
    _LAYOUT = {}

    def _authorized(self, req, action, **kwargs):
        if action in ('new_page', 'list', 'options'):
            return False
        elif action == 'new_chapter':
            return req.page_write_access
        elif action in ('export_epub', 'export_braille'):
            return req.page_read_access
        else:
            return super(Publications, self)._authorized(req, action, **kwargs)
    
    def _condition(self, req):
        condition = super(Publications, self)._condition(req)
        if not wiking.module('Application').preview_mode(req):
            condition = pd.AND(condition, pd.EQ('published', pd.bval(True)))
        return condition

    def _insert_msg(self, req, record):
        if record['published'].value():
            return _("New e-Publication was successfully created and published.")
        else:
            return _("New e-Publication was successfully created, but was not published yet. "
                     "Publish it when you are done.")

    def _current_base_uri(self, req, record=None):
        # Use PytisModule._current_base_uri (skip Pages._current_base_uri).
        return super(Pages, self)._current_base_uri(req, record=record)
    
    def _redirect_after_delete_uri(self, req, record, **kwargs):
        return '/' + req.page_record['identifier'].value(), kwargs
        
    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid == 'lang':
            return None
        return super(Publications, self)._link_provider(req, uri, record, cid, **kwargs)

    def _handle(self, req, action, **kwargs):
        req.publication_record = kwargs.get('record')
        return super(Publications, self)._handle(req, action, **kwargs)

    def _binding_visible(self, req, record, binding):
        return (binding.id() != 'chapters' and
                super(Publications, self)._binding_visible(req, record, binding))
        
    def _inner_page_content(self, req, record):
        def cover_image(element, context):
            if record['cover_image'].value():
                g = context.generator()
                filename = record.cb_value('cover_image', 'filename').value()
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
        return ([wiking.HtmlRenderer(cover_image),
                 self._form(pw.ShowForm, req, record=record, actions=(),
                            layout=[fid for fid in ('description', 'author', 'illustrator',
                                                    'isbn', 'pubinfo', 'lang',
                                                    'creator', 'published_since', 'notes')
                                    if record[fid].value() is not None])] +
                super(Publications, self)._inner_page_content(req, record) +
                [lcg.NodeIndex(title=_("Table of Contents"))])

    def _child_rows(self, req, record):
        children = wiking.module('PublicationChapters').child_rows(req,
                                                                   record['tree_order'].value(),
                                                                   record['lang'].value())
        children[record['parent'].value()] = [record.row()]
        return children

    def _publication(self, req, record):
        children = self._child_rows(req, record)
        def node(row):
            return lcg.ContentNode(row['identifier'].value(),
                                   title=row['title'].value(),
                                   # Call the super class _inner_page_content to
                                   # avoid a table of contents in every node.
                                   content=super(Publications, self).
                                   _inner_page_content(req, self._record(req, row)),
                                   children=[node(r) for r in
                                             children.get(row['page_id'].value(), ())])
        return node(record.row())
        
    def submenu(self, req):
        # TODO: This partially duplicates Pages.menu() - refactor?
        if not hasattr(req, 'publication_record') or req.publication_record is None:
            return []
        record = req.publication_record
        children = self._child_rows(req, record)
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

    def action_export_epub(self, req, record):
        class EpubExporter(lcg.EpubExporter):
            def _get_resource_data(self, context, resource):
                if resource.src_file():
                    return resource.get()
                else:
                    # TODO: Retrieve the attachment.
                    return None
        node = self._publication(req, record)
        exporter = EpubExporter(translations=wiking.cfg.translation_path)
        context = exporter.context(node, req.preferred_language())
        result = exporter.export(context)
        return wiking.Response(result, content_type='application/epub+zip',
                               filename='%s.epub' % record['identifier'].value())
    
    def action_export_braille(self, req, record):
        page_width = int(req.param('braille_page_width') or '0')
        page_height = int(req.param('braille_page_height') or '0')
        inner_margin = int(req.param('braille_inner_margin') or '0')
        outer_margin = int(req.param('braille_outer_margin') or '0')
        top_margin = int(req.param('braille_top_margin') or '0')
        bottom_margin = int(req.param('braille_bottom_margin') or '0')
        printer = req.param('braille_printer')
        try:
            presentation = lcg.braille_presentation('presentation-braille-local.py')
        except IOError:
            presentation = lcg.braille_presentation()
        if page_width and page_height:
            node = self._publication(req, record)
            exporter = lcg.BrailleExporter(translations=wiking.cfg.translation_path)
            presentation.page_width = lcg.UFont(page_width)
            presentation.page_height = lcg.UFont(page_height)
            presentation.inner_margin = lcg.UFont(inner_margin)
            presentation.outer_margin = lcg.UFont(outer_margin)
            presentation.top_margin = lcg.UFont(top_margin)
            presentation.bottom_margin = lcg.UFont(bottom_margin)
            presentation.default_printer = printer
            presentation_set = lcg.PresentationSet(((presentation, lcg.TopLevelMatcher(),),))
            context = exporter.context(node, req.preferred_language(),
                                       presentation=presentation_set)
            try:
                result = exporter.export(context, recursive=True)
            except lcg.BrailleError, e:
                req.message(e.message(), type=req.ERROR)
                raise Redirect(self._current_record_uri(req, record))
            return wiking.Response(result, content_type='text/plain',
                                   filename='%s.txt' % record['identifier'].value())
        else:
            if not page_width:
                page_width = presentation.page_width.size()
            if not page_height:
                page_height = presentation.page_height.size()
            if inner_margin is None:
                inner_margin = presentation.inner_margin.size()
            if outer_margin is None:
                outer_margin = presentation.outer_margin.size()
            if top_margin is None:
                top_margin = presentation.top_margin.size()
            if bottom_margin is None:
                bottom_margin = presentation.bottom_margin.size()
            if printer is None:
                printer = presentation.default_printer
            class Form(lcg.Content):
                def __init__(self, uri, page_width, page_height, inner_margin, outer_margin,
                             top_margin, bottom_margin, printer):
                    self._uri = uri
                    self._page_width = page_width
                    self._page_height = page_height
                    self._inner_margin = inner_margin
                    self._outer_margin = outer_margin
                    self._top_margin = top_margin
                    self._bottom_margin = bottom_margin
                    self._printer = printer
                    super(Form, self).__init__()
                def export(self, context):
                    g = context.generator()
                    def braille_field(label, id_, value):
                        return (g.label(label, id_),
                                g.field(value=str(value), name=id_, size=3, id=id_),
                                g.br(),)
                    buttons = g.submit(_("Export"))
                    available_printers = [(p, p) for p in presentation.printers.keys()]
                    form_elements = ((g.label(_("Printer:"), 'braille_printer'),
                                      g.select('braille_printer', available_printers,
                                               selected=self._printer),
                                      g.br(),) +
                                     braille_field(_("Page width:"), 'braille_page_width',
                                                   self._page_width) +
                                     braille_field(_("Page height:"), 'braille_page_height',
                                                   self._page_height) +
                                     braille_field(_("Inner margin:"), 'braille_inner_margin',
                                                   self._inner_margin) +
                                     braille_field(_("Outer margin:"), 'braille_outer_margin',
                                                   self._outer_margin) +
                                     braille_field(_("Top margin:"), 'braille_top_margin',
                                                   self._top_margin) +
                                     braille_field(_("Bottom margin:"), 'braille_bottom_margin',
                                                   self._bottom_margin) +
                                     (buttons,))
                    return g.form(form_elements +
                                  (g.hidden('action', 'export_braille'),),
                                  action=g.uri(self._uri))
            return Form(req.uri(), page_width, page_height, inner_margin, outer_margin,
                        top_margin, bottom_margin, printer)
            
                    
class PublicationChapters(NavigablePages):
    """e-Publication chapters are regular CMS pages """
    class Spec(Pages.Spec):
        def fields(self):
            override = (
                Field('kind', default='chapter'),
                Field('parent', runtime_filter=computer(self._parent_filter)),
            )
            return self._inherited_fields(PublicationChapters.Spec, override=override)
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
        def _attachment_storage_uri(self, record):
            return '/%s/data/%s/chapters/%s/attachments' % \
                (record.req().page_record['identifier'].value(),
                 record.req().publication_record['identifier'].value(),
                 record['identifier'].value())
        condition = pd.EQ('kind', pd.sval('chapter'))
        columns = ('title', 'status')
        sorting = ('ord', pd.ASCENDENT),
    _INSERT_LABEL = _("New Chapter")
    _LAYOUT = dict(Pages._LAYOUT,
                   insert=('title', 'description', '_content', 'parent', 'ord'),
                   options=('parent', 'ord'),
                   )
    def _authorized(self, req, action, **kwargs):
        if action in ('new_page', 'list'):
            return False
        else:
            return super(PublicationChapters, self)._authorized(req, action, **kwargs)

    def _current_base_uri(self, req, record=None):
        # Use PytisModule._current_base_uri (skip Pages._current_base_uri).
        return super(Pages, self)._current_base_uri(req, record=record)

    def child_rows(self, req, tree_order, lang):
        children = {}
        if wiking.module('Application').preview_mode(req):
            restriction = {}
        else:
            restriction = {'published': True}
        for row in self._data.get_rows(site=wiking.cfg.server_hostname,
                                       condition=pd.WM('tree_order',
                                                       pd.WMValue(pd.String(),
                                                                  '%s.*' % tree_order)),
                                       lang=lang,
                                       sorting=(('tree_order', pd.ASCENDENT),),
                                       **restriction):
            children.setdefault(row['parent'].value(), []).append(row)
        return children


class PageHistory(ContentManagementModule):
    """History of page content changes."""
    class Spec(Specification):
        table = 'cms_v_page_history'
        def fields(self):
            return (
                Field('history_id'),
                Field('page_key', codebook='Pages'),
                Field('page_id'),
                Field('lang'),
                Field('uid', codebook='Users'),
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
        #actions = (
        #    Action('diff', _("Show differences against the current version")),
        #    )

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
            return (('comment',),
                    ColumnLayout(
                    FieldSet(_("Change Summary"), ('inserted_lines', 'changed_lines',
                                                   'deleted_lines')),
                    FieldSet(_("Colors"), ('diff_add', 'diff_chg', 'diff_sub')),
                    ),
                    self._diff)
        else:
            return super(PageHistory, self)._layout(req, action, record=record)

    def _diff(self, record):
        rows = self._rows(record.req(),
                          condition=pd.AND(pd.EQ('page_key', record['page_key']),
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
                content = lcg.HtmlContent(diff.make_table(text1.splitlines(), text2.splitlines(),
                                                          name1, name2, context=True, numlines=3))
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
        # Translators: Section title. Attachments as in email attachments.
        title = _("Attachments")
        help = _("Manage page attachments. Go to a page to create new attachments.")
        table = 'cms_v_page_attachments'
        def fields(self):
            return (
                Field('attachment_key',
                      computer=computer(lambda r, attachment_id, lang:
                                        attachment_id and '%d.%s' % (attachment_id, lang))),
                Field('attachment_id'),
                Field('page_id', _("Page"), codebook='PageStructure', editable=ALWAYS,
                      runtime_filter=computer(lambda r: pd.EQ('site',
                                                              pd.sval(wiking.cfg.server_hostname))),
                      descr=_("Select the page where you want to move this attachment.  "
                              "Don't forget to update all explicit links to "
                              "this attachment within page text(s).")),
                Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                      value_column='lang'),
                # Translators: Noun. File on disk. Computer terminology.
                Field('file', _("File"), virtual=True, editable=ALWAYS,
                      computer=computer(self._file),
                      type=pd.Binary(not_null=True, maxlen=wiking.cms.cfg.upload_limit),
                      descr=_("Upload a file from your local system.  The file name will be used "
                              "to refer to the attachment within the page content.  Please note, "
                              "that the file will be served over the internet, so the filename "
                              "should not contain any special characters.  Letters, digits, "
                              "underscores, dashes and dots are safe.  "
                              "You risk problems with most other characters.")),
                Field('filename', _("Filename"),
                      computer=computer(lambda r, file: file and file.filename()),
                      type=pd.RegexString(maxlen=64, not_null=True, regex='^[0-9a-zA-Z_\.-]*$')),
                Field('mime_type', _("Mime-type"), width=22,
                      computer=computer(lambda r, file: file and file.mime_type())),
                Field('title', _("Title"), width=30, maxlen=64,
                      descr=_("The name of the attachment (e.g. the full name of the document). "
                              "If empty, the file name will be used instead.")),
                Field('description', _("Description"), height=3, width=60, maxlen=240,
                      descr=_("Optional description used for the listing of attachments "
                              "(see below).")),
                Field('ext', virtual=True, computer=computer(self._ext)),
                # Translators: Size of a file, in number of bytes, kilobytes etc.
                Field('bytesize', _("Size"),
                      computer=computer(lambda r, file: file and pp.format_byte_size(len(file)))),
                Field('thumbnail', '', type=pd.Image(), computer=computer(self._thumbnail)),
                # Translators: Thumbnail is a small image preview in computer terminology.
                Field('thumbnail_size', _("Preview size"), not_null=False,
                      enumerator=enum(('small', 'medium', 'large')), default='medium',
                      display=self._thumbnail_size_display, prefer_display=True,
                      null_display=_("Full size (don't resize)"),
                      selection_type=pp.SelectionType.RADIO,
                      descr=_("Only relevant for images.  When set, the image will not be "
                              "displayed in full size, but as a small clickable preview.")),
                # thumbnail_size is the desired maximal width (the corresponding
                # pixel width may change with configuration option
                # wiking.cms.cfg.image_thumbnail_sizes), while thumbnail_width and
                # thumbnail_height reflect the actual size of the thumbnail when it
                # is generated (they also reflect the image aspect ratio).
                Field('thumbnail_width', computer=computer(self._thumbnail_width)),
                Field('thumbnail_height', computer=computer(self._thumbnail_height)),
                Field('image', type=pd.Image(), computer=computer(self._image)),
                Field('in_gallery', _("In Gallery"),
                      #editable=computer(lambda r, thumbnail_size: thumbnail_size is not None),
                      # The computer doesn't work (probably a PresentedRow issue?).
                      #computer=computer(lambda r, thumbnail_size: thumbnail_size is not None),
                      descr=_("Check if you want the image to appear in an image Gallery "
                              "below the page text.")),
                Field('listed', _("Listed"), default=True,
                      descr=_("Check if you want the item to appear in the listing of attachments "
                              "at the bottom of the page.")),
                #Field('author', _("Author"), width=30),
                #Field('location', _("Location"), width=50),
                #Field('exif_date', _("EXIF date"), type=wiking.DateTime()),
                Field('_filename', virtual=True, computer=computer(self._filename)),
            )
        def _ext(self, record, filename):
            if filename is None:
                return ''
            else:
                ext = filename and os.path.splitext(filename)[1].lower()
                return len(ext) > 1 and ext[1:] or ext
        def _file(self, record):
            value = record['file']
            result = value.value()
            if result is not None or record.new():
                return result
            else:
                #log(OPR, "Loading file:", record['_filename'].value())
                return value.type().Buffer(record['_filename'].value(),
                                           mime_type=str(record['mime_type'].value()),
                                           filename=unicode(record['filename'].value()))
        def _resize(self, file, size):
            # Compute the value by resizing the original image.
            import PIL.Image
            import cStringIO
            if file is None:
                return None
            f = cStringIO.StringIO(file.buffer())
            try:
                image = PIL.Image.open(f)
            except IOError:
                return None
            else:
                img = image.copy()
                img.thumbnail(size, PIL.Image.ANTIALIAS)
                stream = cStringIO.StringIO()
                img.save(stream, image.format)
                return pd.Image.Buffer(buffer(stream.getvalue()))
        def _image(self, record, file):
            return self._resize(file, wiking.cms.cfg.image_screen_size)
        def _thumbnail(self, record, file, thumbnail_size):
            if thumbnail_size is None:
                return None
            elif thumbnail_size == 'small':
                size = wiking.cms.cfg.image_thumbnail_sizes[0]
            elif thumbnail_size == 'medium':
                size = wiking.cms.cfg.image_thumbnail_sizes[1]
            else:
                size = wiking.cms.cfg.image_thumbnail_sizes[2]
            return self._resize(file, (size, size))
        def _thumbnail_width(self, record, thumbnail):
            if thumbnail:
                return thumbnail.image().size[0]
            else:
                return None
        def _thumbnail_height(self, record, thumbnail):
            if thumbnail:
                return thumbnail.image().size[1]
            else:
                return None
        def _filename(self, record, attachment_id, ext):
            fname = str(attachment_id) + '.' + ext
            return os.path.join(wiking.cms.cfg.storage, wiking.cfg.dbname, 'attachments', fname)
        def _thumbnail_size_display(self, size):
            # Translators: Size label related to "Preview size" field (pronoun).
            labels = {'small': _("Small") + " (%dpx)" % wiking.cms.cfg.image_thumbnail_sizes[0],
                      'medium': _("Medium") + " (%dpx)" % wiking.cms.cfg.image_thumbnail_sizes[1],
                      'large': _("Large") + " (%dpx)" % wiking.cms.cfg.image_thumbnail_sizes[2]}
            return labels.get(size, size)

        layout = ('file', 'title', 'description', 'thumbnail_size', 'in_gallery', 'listed')
        columns = ('filename', 'title', 'bytesize', 'mime_type', 'thumbnail_size', 'in_gallery',
                   'listed', 'page_id')
        sorting = (('filename', ASC),)
        actions = (
            #Action('insert_image', _("New image"), descr=_("Insert a new image attachment"),
            #       context=pp.ActionContext.GLOBAL),
            # Translators: Button label
            Action('move', _("Move"), descr=_("Move the attachment to another page.")),
        )

    class ImageGallery(lcg.Content):

        def __init__(self, images):
            self._images = images
            super(Attachments.ImageGallery, self).__init__()

        def _export_item(self, context, resource):
            g = context.generator()
            title = resource.title() or resource.filename()
            if resource.descr():
                title += ': ' + resource.descr()
            thumbnail = resource.thumbnail()
            if thumbnail:
                size = thumbnail.size()
                if size:
                    width, height = size
                else:
                    width, height = None, None
                img = g.img(thumbnail.uri(), width=width, height=height)
                return g.a(img, href=resource.uri(), rel='lightbox[gallery]', title=title)
            else:
                return g.img(resource.uri())

        def export(self, context):
            g = context.generator()
            content = [self._export_item(context, r) for r in self._images]
            return g.div(content, cls='wiking-image-gallery')

    class AttachmentStorage(pp.AttachmentStorage):

        def __init__(self, req, page_id, lang, base_uri):
            self._req = req
            self._page_id = page_id
            self._lang = lang
            self._base_uri = base_uri

        def _api_call(self, name, *args, **kwargs):
            method = getattr(wiking.module('Attachments'), 'storage_api_' + name)
            return method(self._req, self._page_id, self._lang, *args, **kwargs)

        def _row_resource(self, row):
            if row['thumbnail_size'].value():
                thumbnail_size = (row['thumbnail_width'].value(), row['thumbnail_height'].value())
            else:
                thumbnail_size = None
            return self._resource(row['filename'].value(),
                                  title=row['title'].value(),
                                  descr=row['description'].value(),
                                  info=dict(mime_type=row['mime_type'].value(),
                                            byte_size=row['bytesize'].export(),
                                            listed=row['listed'].value(),
                                            in_gallery=row['in_gallery'].value(),
                                            thumbnail_size=row['thumbnail_size'].value()),
                                  has_thumbnail=thumbnail_size is not None,
                                  thumbnail_size=thumbnail_size)

        def _resource_uri(self, filename):
            return self._req.make_uri(self._base_uri + '/' + filename)

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
    _LAYOUT = {'move': ('page_id',)}
    _LIST_BY_LANGUAGE = True
    _SEQUENCE_FIELDS = (('attachment_id', 'cms_page_attachments_attachment_id_seq'),)
    _EXCEPTION_MATCHERS = (
        ('duplicate key (value )?violates unique constraint "cms_page_attachments_filename_key"',
         ('file', _("Attachment of the same file name already exists for this page."))),
        ('value too long for type character varying\(64\)',
         ('file', _("Attachment file name exceeds the maximal length 64 characters."))),
    )
    _ROW_ACTIONS = True
    _ASYNC_LOAD = True

    def _authorized(self, req, action, **kwargs):
        if action in ('download', 'image', 'thumbnail'):
            return req.page_read_access
        elif action in ('list', 'view', 'insert', 'update', 'delete', 'move'):
            return req.page_write_access
        else:
            return False

    def _default_action(self, req, record=None):
        if record is None:
            return 'list'
        else:
            return 'download'

    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid is None and not kwargs:
            kwargs['action'] = 'view'
        elif cid == 'file':
            cid = None
            kwargs['action'] = 'download'
        return super(Attachments, self)._link_provider(req, uri, record, cid, **kwargs)

    def _image_provider(self, req, uri, record, cid, **kwargs):
        if cid == 'file':
            return self._link_provider(req, uri, record, None, action='thumbnail')
        return super(Attachments, self)._image_provider(req, uri, record, cid, **kwargs)

    def _save_files(self, record):
        directory = wiking.cms.cfg.storage
        if not os.path.exists(directory) or not os.access(directory, os.W_OK):
            import getpass
            raise Exception("The configuration option 'storage' points to '%(dir)s', but this "
                            "directory does not exist or is not writable by user '%(user)s'." %
                            dict(dir=directory, user=getpass.getuser()))
        fname = record['_filename'].value()
        dir = os.path.split(fname)[0]
        if not os.path.exists(dir):
            os.makedirs(dir, 0700)
        buf = record['file'].value()
        if buf is not None:
            log(OPERATIONAL, "Saving file:", (fname, pp.format_byte_size(len(buf))))
            buf.save(fname)

    def _insert_transaction(self, req, record):
        return self._transaction()

    def _insert(self, req, record, transaction):
        super(Attachments, self)._insert(req, record, transaction)
        self._save_files(record)

    def _update_transaction(self, req, record):
        return self._transaction()

    def _update(self, req, record, transaction):
        super(Attachments, self)._update(req, record, transaction)
        self._save_files(record)

    def _delete_transaction(self, req, record):
        return self._transaction()

    def _delete(self, req, record, transaction):
        super(Attachments, self)._delete(req, record, transaction)
        fname = record['_filename'].value()
        if os.path.exists(fname):
            os.unlink(fname)

    def _redirect_after_update_uri(self, req, record, **kwargs):
        if req.param('__invoked_from') == 'ShowForm':
            # The URI /page/attachments/x.jpg displays the image itself so we
            # need to add the explicit action, but not when invoked from list.
            kwargs['action'] = 'view'
        return super(Attachments, self)._redirect_after_update_uri(req, record, **kwargs)

    def storage_api_row(self, req, page_id, lang, filename):
        return self._data.get_row(page_id=page_id, lang=lang, filename=filename)

    def storage_api_rows(self, req, page_id, lang):
        self._data.select(condition=pd.AND(pd.EQ('page_id', pd.ival(page_id)),
                                           pd.EQ('lang', pd.sval(lang))))
        while True:
            row = self._data.fetchone()
            if row is None:
                break
            yield row
        self._data.close()

    def storage_api_insert(self, req, page_id, lang, filename, data, values):
        prefill = dict(page_id=page_id, lang=lang, listed=False)
        record = self._record(req, None, new=True, prefill=prefill)
        error = record.validate('file', data, filename=filename, mime_type=values.pop('mime_type'))
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
            try:
                self._data.update(row['attachment_key'], self._data.make_row(**values))
            except pd.DBException as e:
                return self._error_message(*self._analyze_exception(e))
            else:
                return None
        else:
            return _("Attachment '%s' not found!", filename)

    def action_move(self, req, record):
        return self.action_update(req, record, action='move')

    def action_download(self, req, record):
        return Response(record['file'].value().buffer(), content_type=record['mime_type'].value())

    def action_thumbnail(self, req, record):
        value = record['thumbnail'].value()
        if not value:
            raise NotFound()
        else:
            return Response(value.buffer(), content_type='image/%s' % value.image().format.lower())

    def action_image(self, req, record):
        value = record['image'].value()
        if not value:
            raise NotFound()
        else:
            return Response(value.buffer(), content_type='image/%s' % value.image().format.lower())


class _News(ContentManagementModule, EmbeddableCMSModule):
    """Common base class for News and Planner."""
    class Spec(Specification):
        def fields(self):
            return (
                Field('page_id', _("Page"), codebook='PageStructure', editable=ONCE,
                      runtime_filter=computer(lambda r:
                                              pd.EQ('site', pd.sval(wiking.cfg.server_hostname)))),
                Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                      selection_type=CHOICE, value_column='lang'),
                Field('timestamp', _("Date"), type=wiking.DateTime(not_null=True, utc=True),
                      default=now, nocopy=True),
                Field('title', _("Title"), column_label=_("Message"), width=32,
                      descr=_("The item brief summary.")),
                ContentField('content', _("Message"), height=6, width=80),
                Field('author', _("Author"), codebook='Users'),
                Field('date', _("Date"), virtual=True, computer=computer(self._date),
                      descr=_("Date of the news item creation.")),
                Field('date_title', virtual=True, computer=computer(self._date_title)),
            )
        def _date(self, record, timestamp):
            return record['timestamp'].export(show_time=False)
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
    _page_identifier_cache = wiking.BoundCache()

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
        def get():
            return record.cb_value('page_id', 'identifier').value()
        # BoundCache will cache only in the scope of one request.
        uri = '/' + self._page_identifier_cache.get(req, record['page_id'].value(), get)
        #if args or kwargs:
        #    uri += '/data/' + record[self._referer].export()
        #    return req.make_uri(uri, *args, **kwargs)
        anchor = 'item-' + record[self._referer].export()
        return make_uri(uri, anchor)

    def _redirect_after_insert(self, req, record):
        req.message(self._insert_msg(req, record))
        identifier = record.cb_value('page_id', 'identifier').value()
        raise Redirect('/' + identifier)

    def _rss_author(self, req, record):
        cbvalue = record.cb_value('author', 'email')
        return cbvalue and cbvalue.export()


class News(_News):
    class Spec(_News.Spec):
        # Translators: Section title and menu item
        title = _("News")
        # Translators: Help string describing more precisely the meaning of the "News" section.
        help = _("Publish site news.")
        table = 'cms_news'
        def fields(self):
            extra = (
                Field('news_id', editable=NEVER),
                Field('days_displayed', _("Displayed days"), default=30,
                      descr=_("Number of days the item stays displayed in news.")),
            )
            return extra + self._inherited_fields(News.Spec)
        sorting = (('timestamp', DESC),)
        columns = ('title', 'timestamp', 'author')
        layout = ('timestamp', 'days_displayed', 'title', 'content')
        list_layout = pp.ListLayout('title', meta=('timestamp', 'author'), content=('content',),
                                    anchor="item-%s", popup_actions=True)
        filter_sets = (pp.FilterSet('filter', _("Show"), default='recent', filters=(
            pp.Filter('recent', _("Recent news"),
                      pd.FunctionCondition('cms_recent_timestamp',
                                           'timestamp', 'days_displayed')),
            pp.Filter('archive', _("Archive of older news"),
                      pd.NOT(pd.FunctionCondition('cms_recent_timestamp',
                                                  'timestamp', 'days_displayed'))),
            pp.Filter('all', _("All items")))),)

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
        help = _("Announce future events by date in a callendar-like listing.")
        table = 'cms_planner'
        def fields(self):
            override = (
                Field('title', column_label=_("Event"), descr=_("The event brief summary.")),
            )
            sample_date = datetime.datetime.today() + datetime.timedelta(weeks=1)
            extra = (
                Field('planner_id', editable=NEVER),
                Field('start_date', _("Date"), width=10, type=wiking.Date(not_null=True),
                      descr=_("The date when the planned event begins. Enter the date "
                              "including year.  Example: %(date)s",
                              date=lcg.LocalizableDateTime(sample_date.date().isoformat()))),
                Field('end_date', _("End date"), width=10, type=wiking.Date(),
                      descr=_("The date when the event ends if it is not the same as the "
                              "start date (for events which last several days).")),
            )
            return extra + self._inherited_fields(Planner.Spec, override=override)
        sorting = (('start_date', ASC),)
        columns = ('title', 'date', 'author')
        layout = ('start_date', 'end_date', 'title', 'content')
        list_layout = pp.ListLayout('date_title', meta=('author', 'timestamp'), content='content',
                                    anchor="item-%s")
        def _date(self, record, start_date, end_date):
            date = record['start_date'].export(show_weekday=True)
            if end_date:
                date += ' - ' + record['end_date'].export(show_weekday=True)
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
        condition = pd.OR(pd.GE('start_date', pd.Value(pd.Date(), today)),
                          pd.GE('end_date', pd.Value(pd.Date(), today)))
        if scondition:
            return pd.AND(scondition, condition)
        else:
            return condition


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
                Field('page_id', codebook='PageStructure', editable=ONCE,
                      runtime_filter=computer(lambda r:
                                              pd.EQ('site', pd.sval(wiking.cfg.server_hostname)))),
                Field('lang', codebook='Languages', editable=ONCE,
                      selection_type=CHOICE, value_column='lang'),
                Field('in_reply_to'),
                Field('tree_order', type=pd.TreeOrder()),
                Field('timestamp', type=wiking.DateTime(not_null=True, utc=True), default=now),
                Field('author', codebook='Users'),
                # Translators: Field label for posting a message to the discussion.
                Field('text', _("Your comment"), height=6, width=80, compact=True,),
            )
        sorting = (('tree_order', ASC),)
        layout = ('text',)
        def list_layout(self):
            import textwrap
            import urllib
            def reply_info(element, context, record):
                if record.req().check_roles(Roles.USER):
                    g = context.generator()
                    text = textwrap.fill(record['text'].value(), 60, replace_whitespace=False)
                    quoted = '\n'.join(['> ' + line for line in text.splitlines()]) + '\n\n'
                    # This hidden 'div.discussion-reply' is a placeholder and
                    # information needed for the Javascript 'Discussion' class
                    # instantiated below the form in the method related().
                    return g.div((g.span(record['comment_id'].export(), cls='id'),
                                  g.span(urllib.quote(quoted.encode('utf-8')), cls='quoted'),
                                  ), cls='discussion-reply', style='display: none')
                else:
                    return ''
            return pp.ListLayout(lcg.TranslatableText("%(timestamp)s, %(author)s:"),
                                 content=('text', lambda r: wiking.HtmlRenderer(reply_info, r)),
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
        req.message(_("Your comment was posted to the discussion."))
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
            req.message(self._error_message(*self._analyze_exception(e)), type=req.ERROR)
            raise Redirect(self._binding_parent_uri(req))
        else:
            return self._redirect_after_insert(req, record)

    def _list_form_content(self, req, form, uri=None):
        content = super(Discussions, self)._list_form_content(req, form, uri=uri)
        if uri is not None:
            if req.check_roles(Roles.USER):
                # Add JavaScript initialization above the list.
                def render(element, context):
                    g = context.generator()
                    context.resource('effects.js')
                    context.resource('discussion.js')
                    return g.script(g.js_call('new Discussion', form.form_id(), uri, 'text'))
                content.append(wiking.HtmlRenderer(render))
                # We don't want to insert messages through a separate insert form,
                # so we embed one directly below the message list.
                content.append(self._form(pw.EditForm, req, reset=None, action='insert',
                                          handler=uri))
            else:
                # Translators: The square brackets mark a link.  Please leave the brackets and the
                # link target '?command=login' untouched and traslate 'log in' to fit into the
                # sentence.  The user only sees it as 'You need to log in before ...'.
                msg = _("Note: You need to [?command=login log in] before you can post messages.")
                content.append(lcg.Container((lcg.p(msg, formatted=True),), name='login-info'))
            # Wrap in a names container to allow css styling.
            content = [lcg.Container(content, name='discussions')]
        return content


class SiteMap(wiking.Module, Embeddable):
    """Extend page content by including a hierarchical listing of the main menu."""

    # Translators: Section heading and menu item. Computer terminology idiom.
    _TITLE = _("Site Map")

    def embed(self, req):
        return [lcg.RootIndex()]


class Resources(wiking.Resources):
    """Serve resource files.

    The Wiking base Resources class is extended to retrieve the stylesheet
    contents from the database driven 'StyleSheets' module (in addition to
    serving the default styles installed on the filesystem).

    """
    def _stylesheet(self, filename):
        return wiking.module('StyleSheets').stylesheet(filename)


class StyleSheets(SiteSpecificContentModule, StyleManagementModule):
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
    class MediaTypes(pp.Enumeration):
        enumeration = (('all', _("All types")),
                       # Translators: Braille as a type of media
                       ('braille', _("Braille")), # braille tactile feedback devices
                       #('embossed', _("Embossed") # for paged braille printers
                       # Translators: Handheld device. Small computer.
                       ('handheld', _("Handheld")),  # typically small screen, limited bandwidth
                       # Translators: Print as a type of media (print, speech...)
                       ('print', _("Print")), # paged material
                       #('projection', _(""))), # projected presentations, for example projectors
                       # Translators: Meaning computer screen
                       ('screen', _("Screen")), # color computer screens
                       # Translators: Speech as a type of media (print, speech...)
                       ('speech', _("Speech")), # for speech synthesizers
                       #('tty', _(""))), # media using a fixed-pitch character grid
                       #('tv', _(""))), # television-type devices
                       )

    class Spec(Specification):
        # Translators: Section heading and menu item. Meaning the visual appearance. Computer
        # terminology.
        title = _("Style sheets")
        table = 'cms_stylesheets'
        # Translators: Help string. Cascading Style Sheet (CSS) is computer terminology idiom.
        help = _("Manage available Cascading Style Sheets.")
        def fields(self):
            return (
                Field('stylesheet_id'),
                Field('site'),
                # Translators: Unique identifier of a stylesheet.
                Field('identifier', _("Identifier"), width=16),
                Field('description', _("Description"), width=50),
                Field('active', _("Active"), default=True),
                # Translators: Heading of a form field determining in
                # which media the page is displayed. E.g. web, print,
                # Braille, speech.
                Field('media', _("Media"), default='all', enumerator=StyleSheets.MediaTypes),
                # Translators: Scope of applicability of a stylesheet on different website parts.
                Field('scope', _("Scope"), enumerator=StyleSheets.Scopes,
                      selection_type=pp.SelectionType.RADIO,
                      # Translators: Global scope (applies to all parts of the website).
                      null_display=_("Global"), not_null=False,
                      # Translators: Description of scope options.  Make sure you
                      # use the same terms as in the options themselves, which are
                      # defined a few items above.
                      descr=_("Determines where this style sheet is applicable. "
                              'The "Management interface" is the area for CMS administration, '
                              '"Website" means the regular pages outside the management interface '
                              'and "Global" means both.')),
                Field('ord', _("Order"), width=5,
                      # Translators: Precedence meaning position in a sequence of importance or
                      # priority.
                      descr=_("Number denoting the style sheet precedence.")),
                Field('content', _("Content"), height=20, width=80),
            )
        layout = ('identifier', 'active', 'media', 'scope', 'ord', 'description', 'content')
        columns = ('identifier', 'active', 'media', 'scope', 'ord', 'description')
        sorting = (('ord', ASC),)
    _REFERER = 'identifier'

    def stylesheets(self, req):
        scopes = (None, req.wmi and 'wmi' or 'website')
        base_uri = req.module_uri('Resources')
        return [lcg.Stylesheet(row['identifier'].value(),
                               uri=base_uri + '/' + row['identifier'].value(),
                               media=row['media'].value())
                for row in self._data.get_rows(site=wiking.cfg.server_hostname,
                                               active=True,
                                               condition=pd.OR(*[pd.EQ('scope', pd.sval(s))
                                                                 for s in scopes]),
                                               sorting=self._sorting)]

    def stylesheet(self, name):
        row = self._data.get_row(identifier=name, active=True, site=wiking.cfg.server_hostname)
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
      text -- the text itself, as a translatable string or unicode in LCG
        formatting

    Note the predefined texts get automatically localized.

    """
    _attributes = (Attribute('label', str),
                   Attribute('description', basestring),
                   Attribute('text', basestring),)
    @classmethod
    def _module_class(class_):
        return Texts
    def __init__(self, label, description, text):
        Structure.__init__(self, label=label, description=description, text=text)
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

    """
    class Spec(Specification):
        # This must be a private attribute, otherwise Pytis handles it in a special way
        _texts = {}

        def fields(self):
            return (
                Field('text_id'),
                Field('label', _("Label"), width=32),
                Field('lang'),
                Field('description'),
                Field('descr', _("Purpose"), width=64, virtual=True,
                      computer=computer(self._description)),
                ContentField('content', _("Text"), width=80, height=10),
            )

        columns = ('label', 'descr',)
        sorting = (('label', ASC,),)
        layout = ('label', 'descr', 'content',)

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

    def _authorized(self, req, action, **kwargs):
        if action in ('insert', 'delete'):
            return False
        else:
            return super(CommonTexts, self)._authorized(req, action, **kwargs)

    def _delayed_init(self):
        super(CommonTexts, self)._delayed_init()
        self._register_texts()

    def _register_texts(self):
        pass

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

    def _select_language(self, req, lang):
        if lang is None:
            lang = req.preferred_language()
            if lang is None:
                lang = 'en'
        return lang

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


class Texts(CommonTexts):
    """Management of simple texts.

    The texts are LCG structured texts and they are language dependent.  Each
    of the texts is identified by a 'Text' instance with unique identifier (its
    'label' attribute).  See 'Text' class for more details.

    """
    class Spec(CommonTexts.Spec):
        table = 'cms_v_system_texts'
        title = _("System Texts")
        help = _("Edit miscellaneous system texts.")
        def fields(self):
            extra = (
                Field('site'),
            )
            return self._inherited_fields(Texts.Spec) + extra

    _DB_FUNCTIONS = dict(CommonTexts._DB_FUNCTIONS,
                         cms_add_text_label=(('label', pd.String()), ('site', pd.String())))

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
            text = self.Spec._texts[label]
            return req.localize(text.text(), lang)
        return (('content', content,),)

    def _register_texts(self):
        for identifier, text in self.Spec._texts.items():
            if isinstance(text, Text):
                site = wiking.cfg.server_hostname
                self._call_db_function('cms_add_text_label', text.label(), site)

    def text(self, req, text, lang=None, args=None):
        """Return text corresponding to 'text'.

        Arguments:

          req -- wiking request
          text -- 'Text' instance identifying the text
          lang -- two-character string identifying the language of the text
          args -- dictionary of formatting arguments for the text; if
            non-empty, the text is processed by the '%' operator and all '%'
            occurences within it must be properly escaped; if 'False', no
            formatting is performed

        If the language is not specied explicitly, language of the request is
        used.  If there is no language set in request, 'en' is assumed.  If the
        text is not available for the selected language in the database, the
        method looks for the predefined text in the application and gettext
        mechanism is used for its translation.

        """
        assert isinstance(text, Text)
        lang = self._select_language(req, lang)
        text_id = ':'.join((text.label(), wiking.cfg.server_hostname, lang))
        row = self._data.get_row(text_id=text_id)
        if row is None:
            retrieved_text = None
        else:
            retrieved_text = row['content'].value()
        if not retrieved_text:
            retrieved_text = req.localize(text.text(), lang=lang)
        if args:
            retrieved_text = retrieved_text % self._localized_args(req, lang, args)
        return retrieved_text

    def parsed_text(self, req, text, lang=None, args=None):
        """Return parsed text corresponding to 'text'.

        This method is the same as 'text()' but instead of returning LCG
        structured text, it returns its parsed form, as an 'lcg.Content'
        instance.  If the given text doesn't exist, 'None' is returned.

        """
        return text2content(req, self.text(req, text, lang=lang, args=args))


class EmailText(Structure):
    """Representation of a predefined e-mail.

    Each predefined e-mail consists of the following attributes:

      label -- unique identifier of the e-mail, string
      description -- human description of the e-mail, presented to application
        administrators managing the e-mails
      subject -- subject of the mail, as a translatable plain text string or unicode
      text -- body of the mail, as a translatable plain text string or unicode
      cc -- comma separated recipient e-mail addresses, as a string

    Note the predefined e-mail texts get automatically localized.

    """
    _attributes = (Attribute('label', str),
                   Attribute('description', basestring),
                   Attribute('text', basestring),
                   Attribute('subject', basestring),
                   Attribute('cc', str, default=''),)
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
            if isinstance(obj, basestring) and not obj.startswith('_'):
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


class TextReferrer(object):
    """Convenience class for modules using 'Texts' and 'Emails' modules.

    It defines convenience methods for text retrieval.

    The class is intended to be inherited as an additional class into Wiking
    modules using multiple inheritance.

    """
    def _text(self, req, text, lang=None, args=None, _method=Texts.text):
        """Return text corresponding to 'text'.

        Arguments:

          req -- wiking request
          text -- 'Text' instance identifying the text
          lang -- two-character string identifying the language of the text
          args -- dictionary of formatting arguments for the text; if
            non-empty, the text is processed by the '%' operator and all '%'
            occurences within it must be properly escaped

        Looking texts for a particular language is performed according the
        rules documented in 'Texts.text()'.

        """
        assert isinstance(text, Text)
        return _method(wiking.module('Texts'), req, text, lang=lang, args=args)

    def _parsed_text(self, req, text, args=None, lang='en'):
        """Return parsed text corresponding to 'text'.

        This method is the same as '_text()' but instead of returning LCG
        structured text string, it returns its parsed form, as an 'lcg.Content'
        instance.  If the given text doesn't exist, 'None' is returned.

        """
        assert isinstance(text, Text)
        return self._text(req, text, lang=lang, args=args, _method=Texts.parsed_text)

    def _email_args(self, *args, **kwargs):
        """The same as 'Emails.email_args'"""
        return wiking.module('Emails').email_args(*args, **kwargs)

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
                      codebook='UserGroups', null_display=_("All users")),
                Field('subject', _("Subject")),
                ContentField('content', _("Text"), width=80, height=10),
                Field('date', _("Date"), type=wiking.DateTime(), default=now, editable=NEVER),
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
    _LAYOUT = {'insert': ('role_id', 'sender_address', 'subject', 'content',)}
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
