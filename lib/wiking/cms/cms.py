# -*- coding: utf-8 -*-
# Copyright (C) 2006, 2007, 2008 Brailcom, o.p.s.
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

from wiking.cms import *

import cStringIO
import os
import re
import subprocess
import tempfile

import mx.DateTime
from mx.DateTime import today, TimeDelta

import pytis.data
from pytis.presentation import computer, Computer, CbComputer, Fields, HGroup, CodebookSpec, \
     FieldSpec as Field
from lcg import log as debug

CHOICE = pp.SelectionType.CHOICE
ALPHANUMERIC = pp.TextFilter.ALPHANUMERIC
LOWER = pp.PostProcess.LOWER
ONCE = pp.Editable.ONCE
NEVER = pp.Editable.NEVER
ALWAYS = pp.Editable.ALWAYS
ASC = pd.ASCENDENT
DESC = pd.DESCENDANT
now = pytis.data.DateTime.current_gmtime
enum = lambda seq: pd.FixedEnumerator(seq)

_ = lcg.TranslatableTextFactory('wiking-cms')

_STRUCTURED_TEXT_DESCR = \
    _("The content should be formatted as LCG structured text. See the %(manual)s.",
      manual=('<a target="help" href="/_doc/lcg/structured-text">' + \
              _("formatting manual") + "</a>"))

def _modcls(name):
    try:
        return cfg.resolver.wiking_module_cls(name)
    except:
        None

def _modtitle(name, default=None):
    """Return a localizable module title by module name."""
    if name is None:
        title = ''
    else:
        cls = _modcls(name)
        if cls:
            title = cls.title()
        else:
            title = default or concat(name,' (',_("unknown"),')')
    return title

def _modules():
    return cfg.resolver.available_modules()
    

class WikingManagementInterface(Module, RequestHandler):
    """Wiking Management Interface.

    This module handles the WMI requestes by redirecting the request to the selected module.  The
    module name is part of the request URI.

    """
    SECTION_USERS = 'users'
    SECTION_STYLE = 'style'
    SECTION_SETUP = 'setup'
    SECTION_CERTIFICATES = 'certificates'
    
    _SECTIONS = ((SECTION_STYLE,   _("Look &amp; Feel"),
                  _("Customize the appearance of your site.")),
                 (SECTION_USERS,   _("User Management"),
                  _("Manage registered users and their privileges.")),
                 #(SECTION_CERTIFICATES, _("Certificate Management"),
                 # _("Manage trusted certificates of your site.")),
                 (SECTION_SETUP,   _("Setup"),
                  _("Edit global properties of your web site.")),
                 )
    
    def _wmi_modules(self, modules, section):
        return [m for m in modules if hasattr(m, 'WMI_SECTION') and 
                getattr(m, 'WMI_SECTION') == section]
    
    def _wmi_order(self, module):
        if hasattr(module, 'WMI_ORDER'):
            return getattr(module, 'WMI_ORDER')
        else:
            return None
    
    def _handle(self, req):
        req.wmi = True # Switch to WMI only after successful authorization.
        if not req.unresolved_path:
            return req.redirect('/'+req.path[0]+'/Pages')
        try:
            module = self._module(req.unresolved_path[0])
        except AttributeError:
            for section, title, descr in self._SECTIONS:
                if req.unresolved_path[0] == section:
                    modules = self._wmi_modules(_modules(), section)
                    if modules:
                        modules.sort(lambda a, b: cmp(self._wmi_order(a), self._wmi_order(b)))
                        return req.redirect('/'+req.path[0]+'/'+modules[0].name())
            raise NotFound(req)
        else:
            del req.unresolved_path[0]
            return req.forward(module)

    def menu(self, req):
        modules = _modules()
        variants = self._application.languages()
        return [MenuItem(req.path[0] + '/Pages', _("Content"),
                         descr=_("Manage available pages and their content."),
                         variants=variants)] + \
               [MenuItem(req.path[0] + '/' + section, title, descr=descr, variants=variants,
                         submenu=[MenuItem(req.path[0] + '/' + m.name(), m.title(),
                                           descr=m.descr(), order=self._wmi_order(m),
                                           variants=variants)
                                  for m in self._wmi_modules(modules, section)])
                for section, title, descr in self._SECTIONS] + \
               [MenuItem('__site_menu__', '', hidden=True, variants=variants,
                         submenu=self._module('Pages').menu(req))]

def _certificate_mail_info(record):
    text = _("To generate the request, you can use the OpenSSL package "
             "and the attached OpenSSL configuration file.\n"
             "In such a case use the following command to generate the certificate "
             "request, assuming your private key is stored in a file named `key.pem':")
    text += ("\n\n"
             "  openssl req -utf8 -new -key key.pem -out request.pem -config openssl.cnf\n\n")
    text += ("If you don't have a private key, you can generate one together with the "
             "certificate request using the following command:\n\n"
             "  openssl req -utf8 -newkey rsa:2048 -keyout key.pem -out request.pem"
             " -config openssl.cnf\n\n")
    attachment = "openssl.cnf"
    user_name = '%s %s' % (record['firstname'].value(), record['surname'].value(),)
    user_email = record['email'].value()
    attachment_stream = cStringIO.StringIO(str (
                '''[ req ]
distinguished_name  = req_distinguished_name
attributes          = req_attributes
x509_extensions     = v3_ca
prompt              = no
string_mask         = utf8only
[ req_distinguished_name ]
CN                  = %s
emailAddress       = %s
[ req_attributes ]
[ usr_cert ]
[ v3_req ]
basicConstraints   = CA:FALSE
nsCertType        = client
keyUsage           = keyEncipherment
[ v3_ca ]

[ crl_ext ]
''' % (user_name, user_email,)))
    return text, attachment, attachment_stream
    
class Registration(Module, ActionHandler):
    """User registration and account management.

    This module is statically mapped by Wiking CMS to the reserved `_registration' URI to always
    provide an interface for new user registration, password reminder, password change and other
    user account related operations.
    
    All these operations are in fact provided by the 'Users' module.  The 'Users' module, however,
    may not be reachable from outside unless used as an extension module for an existing page.  If
    that's not the case, the 'Registration' module provides the needed operations (by proxying the
    requests to the 'Users' module).
    
    """
    class ReminderForm(lcg.Content):
        def export(self, exporter):
            g = exporter.generator()
            controls = (
                g.label(_("Enter your login name or e-mail address")+':', id='login'),
                g.field(name='login', value='', id='login', tabindex=0, size=14),
                g.submit(_("Submit"), cls='submit'),)
            return g.form(controls, method='POST', cls='password-reminder-form') #+ \
                   #g.p(_(""))
    
    def _default_action(self, req, **kwargs):
        return 'view'

    def action_view(self, req):
        if req.user():
            return self._module('Users').action_view(req, req.user().data())
        elif req.param('command') == 'logout':
            return Document(_("Good Bye"), lcg.p(_("You have been logged out.")))
        else:
            raise AuthenticationError()
    RIGHTS_view = (Roles.ANYONE,)
    
    def action_insert(self, req):
        if not cfg.appl.allow_registration:
            raise Forbidden()
        if req.param('form_name') == 'CertificateRequest':
            certificate_request_module = self._module('CertificateRequest')
            record, errors, layout = certificate_request_module.action_insert_perform(req)
            if errors:
                result = certificate_request_module.action_insert_document(req, layout, errors,
                                                                           record)
            else:
                result = self.action_confirm(req)
        else:
            result = self._module('Users').action_insert(req)
        return result
    RIGHTS_insert = (Roles.ANYONE,)
    
    def action_remind(self, req):
        certificate_authentication = cfg.certificate_authentication
        req_user = req.user()
        if req_user is not None:
            title = req_user.name() + " :: " + _("Certificate renewal")
        elif certificate_authentication:
            title = _("Password reminder and certificate change")
        else:
            title = _("Password reminder")
        if req.param('login') or req_user:
            users = self._module('Users')
            record = users.find_user(req, req.param('login') or req_user.login())
            if record:
                if req_user is not None:
                    text = ""
                else:
                    text = concat(
                        _("A password reminder request has been made at %(server_uri)s.",
                          server_uri=req.server_uri()), '',
                        separator='\n')
                attachments = []
                uid = record['uid'].value()
                login = record['login'].value()
                password = record['password'].value()
                if req_user is not None:
                    pass
                elif password:
                    text = concat(
                        text,
                        _("Your credentials are:"),
                        '   '+_("Login name") +': '+ login,
                        '   '+_("Password") +': '+ record['password'].value(), '',
                        _("We strongly recommend you change your password at nearest occassion, "
                          "since it has been exposed to an unsecure channel."),
                        separator='\n')
                else:
                    text = concat(
                        text,
                        _("No password authentication for your account"))
                text += "\n"
                if certificate_authentication:
                    code = users.set_registration_code(uid)
                    attachments = ()
                    cert_text, attachment, attachment_stream = _certificate_mail_info(record)
                    attachments += (MailAttachment(attachment, stream=attachment_stream),)
                    uri = req.server_uri() + make_uri(self._base_uri(req), action='certload',
                                                      uid=uid, regcode=code, reset=1)
                    text = concat (
                        text,
                        _("Visit %(uri)s to upload your certificate request.", uri=uri),
                        cert_text,
                        separator='\n') + "\n"
                elif req_user is None:
                    # TODO: Raise RequestError?
                    return Document(title, lcg.p(_("Invalid request.")))
                err = send_mail(record['email'].value(), title, text, lang=req.prefered_language(),
                                attachments=attachments)
                if err:
                    req.message(_("Failed sending e-mail notification:") +' '+ err, type=req.ERROR)
                    msg = _("Please try repeating your request later or contact the administrator!")
                else:
                    msg = _("E-mail information has been sent to your email address.")
                content = lcg.p(msg)
            else:
                req.message(_("No user account for your query."), type=req.ERROR)
                content = self.ReminderForm()
        else:
            content = self.ReminderForm()
        return Document(title, content)
    RIGHTS_remind = (Roles.ANYONE,)

    def action_update(self, req):
        return self._module('Users').action_update(req, req.user().data())
    RIGHTS_update = (Roles.USER,)
    
    def action_passwd(self, req):
        return self._module('Users').action_passwd(req, req.user().data())
    RIGHTS_passwd = (Roles.USER,)
    
    def action_confirm(self, req):
        return self._module('Users').action_confirm(req)
    RIGHTS_confirm = (Roles.ANYONE,)

    def action_certload(self, req):
        users = self._module('Users')
        record, error = users.check_registration_code(req)
        if error:
            raise AuthorizationError()
        result = self._module('CertificateRequest').action_insert(req)
        if req.param('submit'):
            users.delete_registration_code(req)
        return result
    RIGHTS_certload = (Roles.ANYONE,)

    def action_certrequest(self, req):
        return self.action_remind(req)
    RIGHTS_certrequest = (Roles.ANYONE,)


class CMSModule(PytisModule, RssModule, Panelizable):
    "Base class for all CMS modules."""
    RIGHTS_view = (Roles.ANYONE,)
    RIGHTS_list = (Roles.ANYONE,)
    RIGHTS_rss  = (Roles.ANYONE,)
    RIGHTS_subpath = (Roles.ANYONE,)
    RIGHTS_insert    = (Roles.ADMIN,)
    RIGHTS_update    = (Roles.ADMIN,)
    RIGHTS_delete    = (Roles.ADMIN,)
    RIGHTS_publish   = (Roles.ADMIN,)
    RIGHTS_unpublish = (Roles.ADMIN,)

    def _base_uri(self, req):
        if req.wmi:
            uri = req.uri_prefix() + '/_wmi/'+ self.name()
        else:
            uri = super(CMSModule, self)._base_uri(req)
        return uri

    def _embed_binding(self, modname):
        cls = _modcls(modname)
        if cls and issubclass(cls, EmbeddableCMSModule):
            binding = cls.binding()
        else:
            binding = None
        return binding

    def _form(self, form, req, *args, **kwargs):
        help = None
        if req.wmi and form == pw.ListView:
            form = pw.BrowseForm
            # HACK: Disable help for related forms (binding side forms).
            if not kwargs.has_key('uri'): 
                help = self._view.help()
        result = super(CMSModule, self)._form(form, req, *args, **kwargs)
        if help:
            result = lcg.Container((lcg.p(help), result))
        return result

    
class Embeddable(object):
    """Mix-in class for modules which may be embedded into page content.

    Wiking CMS allows setting an extension module for each page in its global options.  The list of
    available modules always consists of all available modules derived from this class.  The
    derived classes must implement the 'embed()' method to produce content, which is then embedded
    into the page content together with the page text.  This content normally appears below the
    page text, but if the page text contains the delimitter consisting of four or more equation
    signs on a separate line, the embedded content will be placed within the text in the place of
    this delimetter.

    Except for the actual embedded content, the derived classes may also define menu items to be
    automatically added into the main menu.  See the method 'submenu()'.

    """
    
    def embed(self, req):
        """Return a list of content instances extending the page content.

        The returned value can also be an integer to indicate that the request has already been
        served (with the resulting status code).
        
        """
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
        return Binding(cls.title(), cls.name(), cls._EMBED_BINDING_COLUMN,
                       condition=cls._embed_binding_condition, id='data')

    def embed(self, req):
        content = [self.related(req, self.binding(), req.page, req.uri())]
        lang = req.page['lang'].value()
        if not req.wmi and lang:
            rss_info = self._rss_info(req, lang)
            if rss_info:
                content.append(rss_info)
        return content


class CMSExtension(Module, Embeddable, RequestHandler):
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
                self._module(item.modname).set_parent(self)
                init(item.submenu)
        init(self._MENU)
    
    def embed(self, req):
        uri = self.submenu(req)[0].id()
        return req.redirect(uri)

    def submenu(self, req):
        def menu_item(item):
            module = self._module(item.modname)
            identifier = self.submodule_uri(req, item.modname)[1:]
            submenu = [menu_item(i) for i in item.submenu] + module.submenu(req)
            return MenuItem(identifier, module.title(), descr=module.descr(),
                            submenu=submenu, **item.kwargs)
        return [menu_item(item) for item in self._MENU
                if item.enabled is None or item.enabled(req)]

    def handle(self, req):
        try:
            modname = self._mapping[req.unresolved_path[0]]
        except KeyError:
            raise NotFound
        del req.unresolved_path[0]
        return req.forward(self._module(modname))

    def submodule_uri(self, req, modname):
        return self._base_uri(req) +'/'+ self._rmapping[modname]
    

class CMSExtensionModule(CMSModule):
    """CMS module to be used within a 'CMSExtension'."""
    _HONOUR_SPEC_TITLE = True

    def set_parent(self, parent):
        self._parent = parent
    
    def submenu(self, req):
        return []
        
    def _base_uri(self, req):
        try:
            parent = self._parent
        except AttributeError:
            return None
        return parent.submodule_uri(req, self.name())

    
class Session(PytisModule, wiking.Session):
    """Implement Wiking session management by storing session ids in database.

    This module is required by the 'CookieAuthentication' Wiking module.
    
    """
    class Spec(Specification):
        fields = [Field(_id) for _id in ('session_id', 'login', 'key', 'expire')]

    def init(self, user):
        # Delete all expired records first...
        self._data.delete_many(pd.AND(pd.EQ('login', pd.Value(pd.String(), user.login())),
                                      pd.LT('expire', pd.Value(pd.DateTime(),
                                                               mx.DateTime.now().gmtime()))))
        session_key = self._new_session_key()
        row = self._data.make_row(login=user.login(), key=session_key, expire=self._expiration())
        self._data.insert(row)
        return session_key
        
    def check(self, req, user, key):
        row = self._data.get_row(login=user.login(), key=key)
        if row and not self._expired(row['expire'].value()):
            self._record(req, row).update(expire=self._expiration())
            return True
        else:
            return False

    def close(self, req, user, key):
        row = self._data.get_row(login=user.login(), key=key)
        if row:
            self._delete(self._record(req, row))
            

class Config(CMSModule):
    """Site specific configuration provider.

    This implementation stores the configuration variables as one row in a
    Pytis data object to allow their modification through WMI.

    """
    class Spec(Specification):
        class _Field(Field):
            def __init__(self, name, label=None, descr=None, transform_default=None, **kwargs):
                if hasattr(cfg, name):
                    option = cfg.option(name)
                elif hasattr(cfg.appl, name):
                    option = cfg.appl.option(name)
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
                        if isinstance(option, cfg.BooleanOption):
                            transform_default = lambda x: x and _("enabled") or _("disabled")
                        else:
                            transform_default = lambda x: x is None and _("undefined") or repr(x)
                    descr += ' '+ _("The default value is %s.", transform_default(default))
                self._cfg_option = option
                self._cfg_default_value = default
                Field.__init__(self, name, label, descr=descr, **kwargs)
            def configure(self, value):
                option = self._cfg_option
                if option is not None:
                    if value is None:
                        value = self._cfg_default_value
                    option.set_value(value)
                
        title = _("Basic Configuration")
        help = _("Edit site configuration.")
        fields = (
            _Field('config_id'),
            _Field('theme_id', codebook='Themes'),
            _Field('site_title', width=24),
            _Field('site_subtitle', width=50),
            _Field('webmaster_address',
                   descr=_("This address is used as public contact address for your site. "
                           "It is displayed at the bottom of each page, in error messages, RSS "
                           "feeds and so on.  Please make sure that this address is valid "
                           "(e-mail sent to it is delivered to a responsible person).")),
            _Field('default_sender_address',
                   descr=_("E-mail messages sent by the system, such as automatic notifications, "
                           "password reminders, bug-reports etc. will use this sender address. "
                           "Please make sure that this address is valid, since users may reply "
                           "to such messages if they encounter problems.")),
            _Field('allow_login_panel'),
            _Field('allow_registration'),
            _Field('force_https_login'),
            _Field('upload_limit',
                   transform_default=lambda n: repr(n) +' ('+ pp.format_byte_size(n)+')'),
            )
        layout = ('site_title', 'site_subtitle', 'webmaster_address', 'default_sender_address',
                  'allow_login_panel', 'allow_registration', 'force_https_login', 'upload_limit')
    _TITLE_TEMPLATE = _("Basic Configuration")
    WMI_SECTION = WikingManagementInterface.SECTION_SETUP
    WMI_ORDER = 100

    def _resolve(self, req):
        # We always work with just one record.
        return self._data.get_row(config_id=0)
    
    def _default_action(self, req, **kwargs):
        return 'update'
        
    def _redirect_after_update(self, req, record):
        self._configure(record.row())
        req.set_param('submit', None) # Avoid recursion.
        return self.action_update(req, record, msg=self._update_msg(record))
    
    def _configure(self, row):
        for f in self._view.fields():
            f.configure(row[f.id()].value())
    
    def configure(self, req):
        # Called by the application prior to handling any request.
        row = self._data.get_row(config_id=0)
        self._configure(row)
        theme_id = row['theme_id'].value()
        if theme_id is None:
            if isinstance(cfg.theme, Themes.Theme):
                cfg.theme = Theme()
        elif not isinstance(cfg.theme, Themes.Theme) or cfg.theme.theme_id() != theme_id:
            cfg.theme = self._module('Themes').theme(theme_id)

    def set_theme(self, req, theme_id):
        row = self._data.get_row(config_id=0)
        record = self._record(req, row)
        try:
            record.update(theme_id=theme_id)
        except pd.DBException, e:
            return self._error_message(*self._analyze_exception(e))
    

class PageTitles(CMSModule):
    """Simplified version of the 'Pages' module for 'Mapping' enumerator.

    This module is needed to prevent recursive enumerator definition in 'Mapping'.
    
    """
    class Spec(Specification):
        table = 'pages'
        fields = [Field(_f) for _f in ('page_id', 'mapping_id', 'lang', 'title')]

        
class Mapping(CMSModule):
    """Provide a set of available URIs -- page identifiers bound to particular pages.

    This mapping contains unique record for each page identifier.  Pages define the content for
    each mapping identifier in one particular languages.  This module is needed for the reference
    integrity specification in 'Pages', 'Attachments' and other modules, where records are related
    to (language independent) mapping items.
    
    """
    class Spec(Specification):
        fields = (Field('mapping_id', enumerator='PageTitles'),
                  Field('identifier'),
                  Field('modname'),
                  Field('private'),
                  Field('tree_order'),
                  )
        sorting = (('tree_order', ASC), ('identifier', ASC),)
        def _translate(self, row):
            enumerator = row['mapping_id'].type().enumerator()
            condition = pd.AND(pd.EQ('mapping_id', row['mapping_id']),
                               pd.NE('title', pd.Value(pd.String(), None)))
            indent = '   ' * (len(row['tree_order'].value().split('.')) - 2)
            translations = dict([(r['lang'].value().lower(), indent + r['title'].value())
                                 for r in enumerator.rows(condition=condition)])
            return lcg.SelfTranslatableText(indent + row['identifier'].value(),
                                            translations=translations)
        def cb(self):
            return pp.CodebookSpec(display=self._translate, prefer_display=True)


class Panels(CMSModule, Publishable):
    """Provide a set of side panels.

    The panels are stored in a Pytis data object to allow their management through WMI.

    """
    class Spec(Specification):
        title = _("Panels")
        help = _(u"Manage panels – the small windows shown by the side of "
                 "every page.")
        fields = (
            Field('panel_id', width=5, editable=NEVER),
            Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                  selection_type=CHOICE, value_column='lang'),
            Field('ptitle', _("Title"), width=30,
                  descr=_(u"Panel title – you may leave the field blank to "
                          "use the menu title of the selected module.")),
            Field('mtitle'),
            Field('title', _("Title"), virtual=True, width=30, 
                  computer=computer(lambda r, ptitle, mtitle, modname:
                                    ptitle or mtitle or _modtitle(modname))),
            Field('ord', _("Order"), width=5,
                  descr=_("Number denoting the order of the panel on the page.")),
            Field('mapping_id', _("List items"), width=5, not_null=False, codebook='Mapping',
                  descr=_("The items of the extension module used by the selected page will be "
                          "shown by the panel.  Leave blank for a text content panel.")),
            Field('identifier', editable=NEVER),
            Field('modname'),
            Field('private'),
            Field('modtitle', _("Module"), virtual=True,
                  computer=computer(lambda r, modname: _modtitle(modname))),
            Field('size', _("Items count"), width=5,
                  descr=_("Number of items from the selected module, which "
                          "will be shown by the panel.")),
            Field('content', _("Content"), height=10, width=80,
                  descr=_("Additional text content displayed on the panel.")+\
                  ' '+_STRUCTURED_TEXT_DESCR),
            Field('published', _("Published"), default=True,
                  descr=_("Controls whether the panel is actually displayed."),
                  ),
            )
        sorting = (('ord', ASC),)
        columns = ('title', 'ord', 'modtitle', 'size', 'published', 'content')
        layout = ('ptitle', 'ord', 'mapping_id', 'size', 'content', 'published')
    _LIST_BY_LANGUAGE = True
    WMI_SECTION = WikingManagementInterface.SECTION_SETUP
    WMI_ORDER = 500

    def panels(self, req, lang):
        panels = []
        parser = lcg.Parser()
        for row in self._data.get_rows(lang=lang, published=True, sorting=self._sorting):
            if row['private'].value() is True and not Roles.check(req, (Roles.USER,)):
                continue
            panel_id = row['identifier'].value() or str(row['panel_id'].value())
            title = row['ptitle'].value() or row['mtitle'].value() or \
                    _modtitle(row['modname'].value())
            content = ()
            modname = row['modname'].value()
            if modname:
                module = self._module(modname)
                binding = self._embed_binding(modname)
                content = tuple(module.panelize(req, lang, row['size'].value(),
                                                relation=binding and (binding, row)))
            if row['content'].value():
                content += tuple(parser.parse(row['content'].value()))
            panels.append(Panel(panel_id, title, lcg.SectionContainer(content, toc_depth=0)))
        return panels
                
                
class Languages(CMSModule):
    """List all languages available for given site.

    This implementation stores the list of available languages in a Pytis data
    object to allow their modification through WMI.

    """
    class Spec(Specification):
        title = _("Languages")
        help = _("Manage available languages.")
        fields = (
            Field('lang_id'),
            Field('lang', _("Code"), width=2, column_width=6,
                  filter=ALPHANUMERIC, post_process=LOWER, fixed=True),
            Field('name', _("Name"), virtual=True,
                  computer=computer(lambda r, lang: lcg.language_name(lang))),
            )
        sorting = (('lang', ASC),)
        cb = CodebookSpec(display=lcg.language_name, prefer_display=True)
        layout = ('lang',)
        columns = ('lang', 'name')
    _REFERER = 'lang'
    _TITLE_TEMPLATE = _('%(name)s')
    WMI_SECTION = WikingManagementInterface.SECTION_SETUP
    WMI_ORDER = 200

    def languages(self):
        return [str(r['lang'].value()) for r in self._data.get_rows()]

    
class Themes(CMSModule):
    class Spec(Specification):
        class _Field(Field):
            def __init__(self, id, label, descr=None):
                Field.__init__(self, id, label, descr=descr, type=pd.Color(),
                               dbcolumn=id.replace('-','_'))
        _FIELDS = (
            (_("Normal page colors"),
             (_Field('foreground', _("Text")),
              _Field('background', _("Background")),
              _Field('highlight-bg', _("Highlight background"),
                     descr=_("Background highlighting may be used for emphasizing the current "
                             "language, etc.")),
              _Field('link', _("Link")),
              _Field('link-visited', _("Visited link")),
              _Field('link-hover', _("Hover link"),
                     descr=_("Used for changing the link color when the user moves the mouse "
                             "pointer over it.")),
              _Field('border', _("Borders")))),
            (_("Heading colors"),
             (_Field('heading-fg', _("Text")),
              _Field('heading-bg', _("Background")),
              _Field('heading-line', _("Underline"),
                     descr=_("Heading colors are used for section headings, panel headings and "
                             "other heading-like elements.  Depending on stylesheets, some "
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
            (_("Misc."),
             (_Field('table-cell', _("Table cell")),
              _Field('table-cell2', _("Shaded table cell")),
              _Field('help', _("Form help text")),
              _Field('inactive-folder', _("Inactive folder")))),
            )
        title = _("Color Themes")
        help = _("Manage available color themes.")
        def fields(self):
            fields = [Field('theme_id'),
                      Field('name', _("Name")),
                      Field('active', _("Active"), virtual=True,
                            computer=computer(self._is_active))]
            for label, group in self._FIELDS:
                fields.extend(group)
            return fields
        def _is_active(self, row, theme_id):
            if isinstance(cfg.theme, Themes.Theme) and cfg.theme.theme_id() == theme_id:
                return _("Yes")
            else:
                return None
        def layout(self):
            return ('name',) + tuple([FieldSet(label, [f.id() for f in fields])
                                      for label, fields in self._FIELDS])
        columns = ('name', 'active')
        cb = CodebookSpec(display='name', prefer_display=True)
    WMI_SECTION = WikingManagementInterface.SECTION_STYLE
    WMI_ORDER = 100
    _ACTIONS = (Action(_("Activate"), 'activate', descr=_("Activate this color theme"),
                       enabled=lambda r: r['active'].value() is None, allow_referer=False),
                Action(_("Activate default"), 'activate', context=None,
                       descr=_("Activate the default color theme"),
                       enabled=lambda r: isinstance(cfg.theme, Themes.Theme)),)
    
    class Theme(Theme):
        def __init__(self, row):
            self._theme_id = row['theme_id'].value()
            colors = [(c.id(), row[c.id()].value())
                      for c in self.COLORS if row[c.id()].value() is not None]
            super(Themes.Theme, self).__init__(colors=dict(colors))
        def theme_id(self):
            return self._theme_id

    def theme(self, theme_id):
        row = self._data.get_row(theme_id=theme_id)
        return self.Theme(row)
        
    def action_activate(self, req, record=None):
        if record:
            theme_id = record['theme_id'].value()
            name = record['name'].value()
            cfg.theme = self.Theme(record.row())
        else:
            theme_id = None
            name = _("Default")
            cfg.theme = Theme()
        err = self._module('Config').set_theme(req, theme_id)
        if err is None:
            msg = _("The color theme \"%s\" has been activated.", name)
        else:
            msg = None
        req.set_param('search', theme_id)
        return self.action_list(req, msg=msg, err=err)
    RIGHTS_activate = (Roles.ADMIN,)
    

# ==============================================================================
# The modules below handle the actual content.  
# The modules above are system modules used internally by Wiking.
# ==============================================================================

class Pages(CMSModule):
    """Define available pages and their content and allow their management.

    This module implements the key CMS functionality.  Pages, their hierarchy, content and other
    properties are managed throug a Pytis data object.
    
    """
    class Spec(Specification):
        title = _("Pages")
        help = _("Manage available pages and their content.")
        def fields(self): return (
            Field('page_id'),
            Field('mapping_id'),
            Field('identifier', _("Identifier"), width=20, fixed=True, editable=ONCE,
                  type=pd.RegexString(maxlen=32, not_null=True, regex='^[a-zA-Z][0-9a-zA-Z_-]*$'),
                  descr=_("The identifier may be used to refer to this page from outside and also "
                          "from other pages. A valid identifier can only contain letters, digits, "
                          "dashes and underscores.  It must start with a letter.")),
            Field('lang', _("Language"), editable=ONCE, codebook='Languages', value_column='lang'),
            Field('title_or_identifier', _("Title")),
            Field('title', _("Title"), not_null=True),
            Field('description', _("Description"), width=64,
                  descr=_("Brief page description (shown as a tooltip and in site map).")),
            Field('_content', _("Content"), compact=True, height=20, width=80,
                  descr=_STRUCTURED_TEXT_DESCR), #type=pd.StructuredText()),
            Field('content'),
            Field('modname', _("Module"), display=_modtitle, prefer_display=True, not_null=False,
                  enumerator=enum([_m.name() for _m in _modules() if issubclass(_m, Embeddable) \
                                   and _m not in (EmbeddableCMSModule, CMSExtension)]),
                  descr=_("Select the extension module to embed into the page.  Leave blank for "
                          "an ordinary text page.")),
            Field('parent', _("Parent item"), codebook='Mapping', not_null=False,
                  descr=_("Select the superordinate item in page hierarchy.  Leave blank for "
                          "a top-level page.")),
            Field('published', _("Published"), default=False,
                  descr=_("Allows you to control the availability of this page in each of the "
                          "supported languages (switch language to control the availability in "
                          "other languages)")),
            Field('private', _("Private"), default=False,
                  descr=_("Make the item available only to logged-in users.")),
            Field('status', _("Status"), virtual=True, computer=computer(self._status)),
            Field('hidden', _("Hidden"),
                  descr=_("Check if you don't want this page to appear in the menu.")),
            Field('ord', _("Menu order"), width=6, editable=ALWAYS,
                  descr=_("Enter a number denoting the order of the page in the menu.  Leave "
                          "blank if you want to put the page automatically to the end.")),
            Field('tree_order', _("Tree level"), type=pd.TreeOrder()),
            #Field('group', virtual=True,
            #      computer=computer(lambda r, tree_order: tree_order.split('.')[1])),
            Field('owner', _("Owner"), codebook='Users', not_null=False,
                  descr=_("Set the ownership if you want a particular user to have full control "
                          "of the page even if his normal privileges are lower.")),
            )
        def _status(self, record, published, _content, content):
            if not published:
                return _("Not published")
            elif _content == content:
                return _("Ok")
            else:
                return _("Changed")
        def row_style(self, record):
            return not record['published'].value() and pp.Style(foreground='#777') or None
        sorting = (('tree_order', ASC), ('identifier', ASC),)
        #grouping = 'group'
        #group_heading = 'title'
        layout = (FieldSet(_("Page Text (for the current language)"),
                           ('title', 'description', 'status', '_content')),
                  FieldSet(_("Global Options (for all languages)"),
                           (('identifier', 'parent',),
                            ('hidden', 'ord'),
                            ('private', 'owner')),
                           horizontal=True))
        columns = ('title_or_identifier', 'identifier', 'modname', 'status', 'hidden', 'ord',
                   'private', 'owner')
        cb = CodebookSpec(display='title_or_identifier', prefer_display=True)
        bindings = (Binding(_("Attachments"), 'Attachments', 'mapping_id', id='attachments'),)

    _REFERER = 'identifier'
    _EXCEPTION_MATCHERS = (
        ('duplicate key (value )?violates unique constraint "_pages_mapping_id_key"',
         _("The page already exists in given language.")),
        ('duplicate key (value )?violates unique constraint "_mapping_unique_tree_(?P<id>ord)er"',
         _("Duplicate menu order at this level of hierarchy.")),) + \
         CMSModule._EXCEPTION_MATCHERS
    _LIST_BY_LANGUAGE = True
    _OWNER_COLUMN = 'owner'
    _SUPPLY_OWNER = False
    _LAYOUT = {'insert': (FieldSet(_("Page Text (for the current language)"),
                                   ('title', 'description', '_content')),
                          FieldSet(_("Global Options (for all languages)"),
                                   ('identifier', 'modname', 'parent', 'hidden', 'ord',
                                    'private', 'owner'),
                                   horizontal=True)),
               'update': ('title', 'description', '_content'),
               'options': ('identifier', 'modname', 'parent', 'hidden', 'ord', 'private', 'owner'),
               }
    _SUBMIT_BUTTONS_ = ((_("Save"), None), (_("Save and publish"), 'commit'))
    _SUBMIT_BUTTONS = {'update': _SUBMIT_BUTTONS_,
                       'insert': _SUBMIT_BUTTONS_}
    _INSERT_LABEL = _("New page")
    _UPDATE_LABEL = _("Edit Text")
    _UPDATE_DESCR = _("Edit title, description and content for the current language")
    _ACTIONS = (
        Action(_("Options"), 'options',
               descr=_("Edit global (language independent) page options and menu position")),
        Action(_("Publish"), 'commit', descr=_("Publish the page in its current state"),
               enabled=lambda r: (r['_content'].value() != r['content'].value() \
                                  or not r['published'].value())),
        Action(_("Unpublish"), 'unpublish', descr=_("Make the page invisible from outside"),
               enabled=lambda r: r['published'].value()),
        Action(_("Revert"), 'revert',  descr=_("Revert last modifications"),
               enabled=lambda r: r['_content'].value() != r['content'].value()),
        Action(_("Preview"), 'preview', descr=_("Display the page in its current state"),
               ), #enabled=lambda r: r['_content'].value() is not None),
        Action(_("Attachments"), 'attachments', descr=_("Manage this page's attachments")),
        #Action(_("Translate"), 'translate',
        #      descr=_("Create the content by translating another language variant"),
        #       enabled=lambda r: r['_content'].value() is None),
        )
    _SEPARATOR = re.compile('^====+\s*$', re.MULTILINE)
    RIGHTS_insert = (Roles.AUTHOR,)
    RIGHTS_update = (Roles.AUTHOR, Roles.OWNER)

    def _handle(self, req, action, **kwargs):
        # TODO: This is quite a hack.  It is used to find out the parent page in the embedded
        # module, but a better solution would be desirable.
        req.page = kwargs.get('record')
        return super(Pages, self)._handle(req, action, **kwargs)
        
    def _resolve(self, req):
        if req.wmi:
            return super(Pages, self)._resolve(req)
        if req.has_param(self._key):
            row = self._get_row_by_key(req, req.param(self._key))
            if req.unresolved_path:
                del req.unresolved_path[0]
            return row
        identifier = req.unresolved_path[0]
        variants = self._data.get_rows(identifier=identifier, published=True)
        if variants:
            for lang in req.prefered_languages():
                for row in variants:
                    if row['lang'].value() == lang:
                        del req.unresolved_path[0]
                        return row
            raise NotAcceptable([str(r['lang'].value()) for r in variants])
        elif self._data.get_rows(identifier=identifier):
            raise Forbidden()
        else:
            raise NotFound()

    def _bindings(self, req, record):
        bindings = super(Pages, self)._bindings(req, record)
        binding = self._embed_binding(record['modname'].value())
        if binding:
            bindings.insert(0, binding)
        return bindings

    def _validate(self, req, record, layout=None):
        result = super(Pages, self)._validate(req, record, layout=layout)
        if result is None and req.has_param('commit'):
            if not (Roles.check(req, self.RIGHTS_commit) or self.check_owner(req.user(), record)):
                return [(None, _("You don't have sufficient privilegs for this action.") +' '+ \
                         _("Save the page without publishing and ask the administrator to publish "
                           "your changes."))]
            record['content'] = record['_content']
            record['published'] = pytis.data.Value(pytis.data.Boolean(), True)
        return result

    def _update_msg(self, record):
        if record['content'].value() == record['_content'].value():
            return super(Pages, self)._update_msg(record)
        else:
            return _("Page content was modified, however the changes remain unpublished. Don't "
                     "forget to publish the changes when you are done.")

    def _insert_msg(self, record):
        if record['published'].value():
            return _("New page was successfully created and published.")
        else:
            return _("New page was successfully created, but was not published yet. "
                     "Publish it when you are done.")
        
    def _mapped_uri(self):
        return '/'
        
    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid == 'parent':
            return None
        return super(Pages, self)._link_provider(req, uri, record, cid, **kwargs)

    def _redirect_after_insert(self, req, record):
        return self.action_view(req, record, msg=self._insert_msg(record))
        
    def _redirect_after_update(self, req, record):
        if not req.wmi:
            return self.action_preview(req, record, msg=self._update_msg(record))
        else:
            return super(Pages, self)._redirect_after_update(req, record)

    def _actions(self, req, record):
        actions = super(Pages, self)._actions(req, record)
        if record is not None:
            if req.wmi and req.param('action') == 'preview':
                actions = (Action(_("Back"), 'view'),)
            if req.wmi:
                exclude = ('attachments',)
            else:
                # TODO: Unpublish doesn't work outside WMI.
                exclude = ('unpublish', 'preview', 'delete', 'list')
            actions = tuple([a for a in actions if a.name() not in exclude])
        return actions

    # Public methods
    
    def content_management_panel(self, req, record):
        # Currently unused!
        menu = self._action_menu(req, record, title=None, cls=None)
        if not menu:
            return None
        #links = (#(_("List all pages"), '/?action=list'),
        #         ('/_doc/pages', _("Help"),      _("Show on-line help")),
        #         ('/_wmi',       _("Enter WMI"), _("Enter the Wiking Management Interface")))
        #content = lcg.ul(((_("Current page:"), menu),
        #                  (_(""), lcg.ul([lcg.link(target, label, descr=descr)
        #                                  for target, label, descr in links]))))
        #return Panel('content-management-panel', _("Content management"), content)

    def menu(self, req):
        children = {None: []}
        translations = {}
        def mkitem(row):
            mapping_id, identifier = row['mapping_id'].value(), str(row['identifier'].value())
            titles, descriptions = translations[mapping_id]
            if row['modname'].value():
                try:
                    module = self._module(row['modname'].value())
                except AttributeError:
                    # We want the CMS to work even if the module was uninstalled or renamed. 
                    submenu = []
                else:
                    submenu = list(module.submenu(req))
            else:
                submenu = []
            return MenuItem(identifier,
                            lcg.SelfTranslatableText(identifier, translations=titles),
                            descr=lcg.SelfTranslatableText('', translations=descriptions),
                            hidden=row['hidden'].value(), variants=titles.keys(),
                            submenu=submenu + [mkitem(r) for r in children.get(mapping_id, ())])
        for row in self._data.get_rows(sorting=self._sorting, published=True):
            mapping_id = row['mapping_id'].value()
            if not translations.has_key(mapping_id):
                parent = row['parent'].value()
                if not children.has_key(parent):
                    children[parent] = []
                children[parent].append(row)
                translations[mapping_id] = ({}, {})
            titles, descriptions = translations[mapping_id]
            lang = str(row['lang'].value())
            titles[lang] = row['title_or_identifier'].value()
            if row['description'].value() is not None:
                descriptions[lang] = row['description'].value()
        return [mkitem(row) for row in children[None]] + \
               [MenuItem('_registration', _("Registration"), hidden=True),
                MenuItem('_doc', _("Wiking Documentation"), hidden=True)]
    
    def module_uri(self, modname):
        row = self._data.get_row(modname=modname) #, published=True)
        if row:
            uri = '/'+ row['identifier'].value()
            binding = self._embed_binding(row['modname'].value())
            if binding:
                uri += '/'+ binding.id()
        else:
            uri = None
        return uri

    # Action handlers.
        
    def action_view(self, req, record, err=None, msg=None, preview=False):
        if req.wmi and not preview:
            return super(Pages, self).action_view(req, record, err=err, msg=msg)
        # Main content
        if preview:
            text = record['_content'].value()
        else:
            text = record['content'].value()
        module = record['modname'].value() and self._module(record['modname'].value())
        if module:
            content = module.embed(req)
            if isinstance(content, int):
                # The request has already been served by the embedded module. 
                return content
        else:
            content = []
        if text:
            if self._SEPARATOR.search(text):
                pre, post = self._SEPARATOR.split(text, maxsplit=2)
            else:
                pre, post = text, ''
            parser = lcg.Parser()
            sections = parser.parse(pre) + content + parser.parse(post)
            content = [lcg.SectionContainer(sections, toc_depth=0)]
        # Attachment list
        amod = self._module('Attachments')
        attachments = amod.attachments(record['mapping_id'].value(), record['lang'].value(),
                                       '/'+ record['identifier'].export() + '/attachments')
        items = [(lcg.link(make_uri(a.uri), a.title),
                  ' ('+ a.bytesize +') ', lcg.WikiText(a.descr or ''))
                 for a in attachments if a.listed]
        if items:
            content.append(lcg.Section(title=_("Attachments"), content=lcg.ul(items),
                                       anchor='attachment-automatic-list')) # Prevent dupl. anchor.
        if not content and record['parent'].value() is None:
            rows = self._data.get_rows(parent=record['mapping_id'].value(), condition=\
                                       pd.AND(pd.EQ('hidden', pd.Value(pd.Boolean(), False)),
                                              pd.EQ('published', pd.Value(pd.Boolean(), True))),
                                       sorting=self._sorting)
            if rows:
                return req.redirect('/'+rows[0]['identifier'].value())
        # Action menu
        content.append(self._action_menu(req, record, help='/_doc/pages', cls='actions separate'))
        resources = [a.resource() for a in attachments]
        return self._document(req, content, record, resources=resources, err=err, msg=msg)

    def action_subpath(self, req, record):
        modname = record['modname'].value()
        if modname is not None:
            binding = self._embed_binding(modname)
            # Modules with bindings are handled in the parent class method.
            if not binding:
                module = self._module(modname)
                try:
                    return req.forward(module)
                except NotFound:
                    if not req.unresolved_path:
                        # Don't allow further processing if unresolved_path was already consumed. 
                        raise
        return super(Pages, self).action_subpath(req, record)

    def action_rss(self, req, record):
        modname = record['modname'].value()
        if modname is not None:
            module = self._module(modname)
            binding = self._embed_binding(modname)
            return module.action_rss(req, relation=binding and (binding, record))
        else:
            raise NotFound()
        
    def action_list(self, req, record=None, **kwargs):
        if record is not None:
            # Simulate the list action for the embedded module.
            return self.action_view(req, record, **kwargs)
        else:
            return super(Pages, self).action_list(req, **kwargs)
        
    def action_attachments(self, req, record, err=None, msg=None):
        binding = self._view.bindings()[0]
        content = self._module('Attachments').related(req, binding, record,
                                                      uri=self._current_record_uri(req, record))
        return self._document(req, content, record, subtitle=_("Attachments"), err=err, msg=msg)
    RIGHTS_attachments = (Roles.AUTHOR, Roles.OWNER)
        
    def action_preview(self, req, record, **kwargs):
        return self.action_view(req, record, preview=True, **kwargs)
    RIGHTS_preview = (Roles.AUTHOR, Roles.OWNER)

    def action_options(self, req, record):
        return self.action_update(req, record, action='options')
    RIGHTS_options = (Roles.AUTHOR, Roles.OWNER)
    
    def action_translate(self, req, record):
        lang = req.param('src_lang')
        if not lang:
            if record['_content'].value() is not None:
                e = _("Content for this page already exists!")
                return self.action_view(req, record, err=e)
            cond = pd.AND(pd.NE('_content', pd.Value(pd.String(), None)),
                          pd.NE('lang', record['lang']))
            langs = [(str(row['lang'].value()), lcg.language_name(row['lang'].value())) for row in 
                     self._data.get_rows(mapping_id=record['mapping_id'].value(), condition=cond)]
            if not langs:
                e = _("Content for this page does not exist in any language.")
                return self.action_view(req, record, err=e)
            d = pw.SelectionDialog('src_lang', _("Choose source language"), langs,
                                   action='translate', hidden=\
                                   [(id, record[id].value()) for id in ('mapping_id', 'lang')])
            return self._document(req, d, record, subtitle=_("Translate"))
        else:
            row = self._data.get_row(mapping_id=record['mapping_id'].value(),
                                     lang=str(req.param('src_lang')))
            for k in ('_content','title'):
                req.set_param(k, row[k].value())
            return self.action_update(req, record)
    RIGHTS_translate = (Roles.AUTHOR, Roles.OWNER)

    def action_commit(self, req, record):
        values = dict(content=record['_content'].value(), published=True)
        if record['title'].value() is None:
            if record['modname'].value() is not None:
                # Supply the module's title automatically.
                module = self._module(record['modname'].value())
                tr = translator(record['lang'].value())
                values['title'] = tr.translate(module.title())
            else:
                return self.action_view(req, record, err=_("Can't publish untitled page."))
        try:
            record.update(**values)
        except pd.DBException, e:
            kwargs = dict(err=self._error_message(*self._analyze_exception(e)))
        else:
            kwargs = dict(msg=_("The changes were published."))
        return self.action_view(req, record, **kwargs)
    RIGHTS_commit = (Roles.AUTHOR, Roles.OWNER)

    def action_revert(self, req, record):
        try:
            record.update(_content=record['content'].value())
        except pd.DBException, e:
            kwargs = dict(err=self._error_message(*self._analyze_exception(e)))
        else:
            kwargs = dict(msg=_("The page contents was reverted to its previous state."))
        return self.action_view(req, record, **kwargs)
    RIGHTS_revert = (Roles.ADMIN, Roles.OWNER)
    
    def action_unpublish(self, req, record):
        try:
            record.update(published=False)
        except pd.DBException, e:
            kwargs = dict(err=self._error_message(*self._analyze_exception(e)))
        else:
            kwargs = dict(msg=_("The page was unpublished."))
        return self.action_view(req, record, **kwargs)
    RIGHTS_unpublish = (Roles.ADMIN, Roles.OWNER)

    
class Attachments(CMSModule):
    """Attachments are external files (documents, images, media, ...) attached to CMS pages.

    Pytis supports storing binary data types directly in the database, however the current
    implementation is unfortunately too slow for web usage.  Thus we work around that making the
    field virtual, storing its value in a file and loading it back through a 'computer'.

    """
    
    class Spec(Specification):
        title = _("Attachments")
        help = _("Manage page attachments. Go to a page to create new attachments.")
        def fields(self): return (
            Field('attachment_variant_id',
                  computer=computer(lambda r, attachment_id, lang:
                                    attachment_id and '%d.%s' % (attachment_id, lang))),
            Field('attachment_id'),
            Field('mapping_id', _("Page"), codebook='Mapping', editable=ALWAYS,
                  descr=_("Select the page where you want to move this attachment.  Don't forget "
                          "to update all explicit links to this attachment within page text(s).")),
            Field('lang', _("Language"), codebook='Languages', editable=ONCE, value_column='lang'),
            Field('file', _("File"), virtual=True, editable=ALWAYS, computer=computer(self._file),
                  type=pd.Binary(not_null=True, maxlen=cfg.appl.upload_limit),
                  descr=_("Upload a file from your local system.  The file name will be used "
                          "to refer to the attachment within the page content.  Please note, "
                          "that the file will be served over the internet, so the filename should "
                          "not contain any special characters.  Letters, digits, underscores, "
                          "dashes and dots are safe.  You risk problems with most other "
                          "characters.")),
            Field('filename', _("Filename"),
                  computer=computer(lambda r, file: file and file.filename()),
                  type=pd.RegexString(maxlen=64, not_null=True, regex='^[0-9a-zA-Z_\.-]*$')),
            Field('mime_type', _("Mime-type"), width=22,
                  computer=computer(lambda r, file: file and file.type())),
            Field('title', _("Title"), width=30, maxlen=64,
                  descr=_("The name of the attachment (e.g. the full name of the document). "
                          "If empty, the file name will be used instead.")),
            Field('description', _("Description"), height=3, width=60, maxlen=240,
                  descr=_("Optional description used for the listing of attachments (see below).")),
            Field('ext', virtual=True, computer=computer(self._ext)),
            Field('bytesize', _("Size"),
                  computer=computer(lambda r, file: file and pp.format_byte_size(len(file)))),
            Field('listed', _("Listed"), default=True,
                  descr=_("Check if you want the item to appear in the listing of attachments at "
                          "the bottom of the page.")),
            Field('is_image'),
            Field('_filename', virtual=True,
                  computer=self._filename_computer()),
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
                                           type=str(record['mime_type'].value()),
                                           filename=str(record['filename'].value()))
        def _filename_computer(self, append=''):
            """Return a computer computing filename for storing the file."""
            def func(record, attachment_id, ext):
                fname = str(attachment_id) + append + '.' + ext
                return os.path.join(cfg.storage, cfg.dbname, self.table, fname)
            return computer(func)
        def redirect(self, record):
            return record['is_image'].value() and 'Images' or None
        layout = ('file', 'title', 'description', 'listed')
        columns = ('filename', 'title', 'bytesize', 'mime_type', 'listed', 'mapping_id')
        sorting = (('filename', ASC),)

    class Attachment(object):
        def __init__(self, row, uri):
            self.filename = filename = row['filename'].export()
            self.uri = uri +'/'+ filename
            self.title = row['title'].export() or filename
            self.descr = row['description'].value()
            self.bytesize = row['bytesize'].export()
            self.listed = row['listed'].value()
            self.mime_type = row['mime_type'].value()
        def resource(self):
            """Create and return 'lcg.Resource' instance using given 'lcg.ResourceProvider'."""
            if self.mime_type.startswith('image/'):
                cls = lcg.Image
            else:
                cls = lcg.Resource
            return cls(self.filename, uri=self.uri, title=self.title, descr=self.descr)
        
    _ACTIONS = (
        #Action(_("New image"), 'insert_image', descr=_("Insert a new image attachment"),
        #       context=None),
        Action(_("Move"), 'move', descr=_("Move the attachment to another page.")),
        )
    _STORED_FIELDS = (('file', '_filename'),) # Define which fields are stored as files.
    _INSERT_LABEL = _("New attachment")
    _REFERER = 'filename'
    _LAYOUT = {'move': ('mapping_id',)}
    _LIST_BY_LANGUAGE = True
    _SEQUENCE_FIELDS = (('attachment_id', '_attachments_attachment_id_seq'),)
    _EXCEPTION_MATCHERS = (
        ('duplicate key (value )?violates unique constraint "_attachments_mapping_id_key"',
         ('file', _("Attachment of the same file name already exists for this page."))),)
    RIGHTS_view   = (Roles.AUTHOR, Roles.OWNER)
    RIGHTS_insert = (Roles.AUTHOR, Roles.OWNER)
    RIGHTS_update = (Roles.AUTHOR, Roles.OWNER)
    RIGHTS_delete = (Roles.AUTHOR, Roles.OWNER)

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
        #if cid == 'thumbnail':
        #    cid = None
        #    kwargs['action'] = 'image'
        return super(Attachments, self)._link_provider(req, uri, record, cid, **kwargs)

    #def _image_provider(self, req, uri, record, cid, **kwargs):
        #if cid in('file', 'filename') and record['width'].value():
        #    return self._link_provider(req, uri, record, None, action='thumbnail')
        #return super(Attachments, self)._image_provider(req, uri, record, cid, **kwargs)

    def _actions(self, req, record):
        actions = super(Attachments, self)._actions(req, record)
        if record is None and not req.wmi:
            actions += (Action(_("Back"), 'list', context=None, descr=_("Display the page")),)
        return actions

    def _binding_parent_redirect(self, req, uri, **kwargs):
        if not req.wmi and (req.param('action') != 'list' or req.param('module') == 'Attachments'):
            # We normally want to redirect to the 'attachments' action in all cases (outside WMI),
            # but we want the default page action (view) when the _("Back") button defined above is
            # used.
            kwargs['action'] = 'attachments'
        return super(Attachments, self)._binding_parent_redirect(req, uri, **kwargs)

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
            if buf is not None:
                log(OPR, "Saving file:", (fname, pp.format_byte_size(len(buf))))
                buf.save(fname)
        
    def _insert(self, record):
        super(Attachments, self)._insert(record)
        try:
            self._save_files(record)
        except:
            # TODO: Rollback the transaction instead of deleting the record.
            self._delete(record)
            raise
        
    def _update(self, record):
        super(Attachments, self)._update(record)
        self._save_files(record)
        
    def _delete(self, record):
        super(Attachments, self)._delete(record)
        for id, filename_id in self._STORED_FIELDS:
            fname = record[filename_id].value()
            if os.path.exists(fname):
                os.unlink(fname)

    def attachments(self, mapping_id, lang, uri):
        return [self.Attachment(record, uri) for record in
                self._data.get_rows(mapping_id=mapping_id, lang=lang)]
    
    def action_move(self, req, record):
        return self.action_update(req, record, action='move')
    RIGHTS_move = (Roles.AUTHOR,)

    def action_download(self, req, record, **kwargs):
        return (str(record['mime_type'].value()), record['file'].value().buffer())
    RIGHTS_download = (Roles.ANYONE)

    def action_insert_image(self, req):
        req.set_param('action', 'insert')
        return self._module('Images').action_insert(req)
    RIGHTS_insert_image  = (Roles.AUTHOR, Roles.OWNER)


class Images(Attachments):
    class Spec(Attachments.Spec):
        table = 'attachments'
        def fields(self):
            fields = pp.Fields(super(Images.Spec, self).fields())
            overridden = (
                #Field(inherit=fields['mime_type'], check=),
                Field(inherit=fields['title'], 
                      descr=_("Image title.  If empty, the file name will be used instead.")),
                Field(inherit=fields['description'], maxlen=512,
                      descr=_("Optional image description.")),
                Field(inherit=fields['listed'], label=_("In galery"),
                      descr=_("Check if you want the image to appear an automatically generated "
                              "galery.")),
                Field(inherit=fields['is_image'], default=True),
                )
            extra = (
                Field('image', virtual=True, editable=ALWAYS, computer=computer(self._image),
                      type=pd.Image(maxsize=(3000, 3000))),
                #Field('resized', virtual=True, editable=ALWAYS, type=pd.Image(),
                #      computer=self._resize_computer('resized', '_resized_filename', (800, 800))),
                #Field('thumbnail', virtual=True, type=pd.Image(),
                #      computer=self._resize_computer('thumbnail', '_thumbnail_filename', (130, 130))),
                Field('author', _("Author"), width=30),
                Field('location', _("Location"), width=50),
                Field('width', _("Width"),
                      computer=computer(lambda r, image: image and image.size[0])),
                Field('height', _("Height"), 
                      computer=computer(lambda r, image: image and image.size[1])),
                #Field('size', _("Pixel size"), virtual=True,
                #      computer=computer(lambda r, width, height:
                #                        width is not None and '%dx%d' % (width, height))),
                #Field('exif_date', _("EXIF date"), type=DateTime()),
                #Field('exif'),
                Field('_thumbnail_filename', virtual=True,
                      computer=self._filename_computer('-thumbnail')),
                Field('_resized_filename', virtual=True,
                      computer=self._filename_computer('-resized')),
                )
            return tuple(fields.fields(override=overridden)) + extra
        def _image(self, record):
            # Use lazy get to prevent running the computer (to find out, whether a new file was
            # uploaded and prevent loading the previously saved file in that case).
            file = record.get('file', lazy=True).value()
            if file is not None and file.path() is None:
                log(OPR, "Loading image:", len(file))
                import PIL.Image 
                stream = cStringIO.StringIO(file.buffer())
                try:
                    image = PIL.Image.open(stream)
                except IOError:
                    return None
                else:
                    return image
            return None
        def _resize_computer(self, cid, filename, size):
            """Return a computer loading field value from file."""
            def func(record):
                value = record[cid]
                result = value.value()
                if result is not None:
                    return result
                else:
                    img = copy.copy(record['image'].value())
                    if img:
                        # Recompute the value by resizing the original image.
                        from PIL.Image import ANTIALIAS
                        log(OPR, "Resizing image:", (img.size, size))
                        img.thumbnail(size, ANTIALIAS)
                        stream = cStringIO.StringIO()
                        img.save(stream, img.format)
                        return pd.Image.Buffer(buffer(stream.getvalue()))
                    elif not record.new():
                        #log(OPR, "Loading file:", record[filename].value())
                        return value.type().Buffer(record[filename].value(),
                                                   type=str(record['mime_type'].value()))
                return result
            return computer(func)
        layout = ('file', 'title', 'description', 'author', 'location', 'listed')
            
    _STORED_FIELDS = (('file', '_filename'),
                      ('resized', '_resized_filename'),
                      ('thumbnail', '_thumbnail_filename')
                      )
    _INSERT_LABEL = _("New attachment")

    def _binding_forward(self, req):
        # HACK: This module is always accessed through redirect in Attachments, but the parent
        # method does not take that into account.
        for fw in reversed(req.forwards()):
            if fw.arg('binding') is not None:
                if fw.module().name() == 'Attachments':
                    return fw
                else:
                    return None
        return None
    
    #def action_resized(self, req, record):
    #    return (str(record['mime_type'].value()), record['resized'].value().buffer())
    #RIGHTS_resized = (Roles.ANYONE,)
    
    #def action_thumbnail(self, req, record):
    #    return (str(record['mime_type'].value()), record['thumbnail'].value().buffer())
    #RIGHTS_thumbnail = (Roles.ANYONE,)

    
class News(EmbeddableCMSModule):
    class Spec(Specification):
        title = _("News")
        help = _("Publish site news.")
        def fields(self): return (
            Field('news_id', editable=NEVER),
            Field('mapping_id', _("Page"), codebook='Mapping', editable=ONCE),
            Field('lang', _("Language"), codebook='Languages', editable=ONCE,
                  selection_type=CHOICE, value_column='lang'),
            Field('timestamp', _("Date"), width=19,
                  type=DateTime(not_null=True), default=now),
            Field('date', _("Date"), virtual=True,
                  computer=Computer(self._date, depends=('timestamp',)),
                  descr=_("Date of the news item creation.")),
            Field('title', _("Title"), column_label=_("Message"), width=32,
                  descr=_("The item brief summary.")),
            Field('content', _("Message"), height=6, width=80, descr=_STRUCTURED_TEXT_DESCR + ' ' + \
                  _("It is, however, recommened to use the simplest possible formatting, since "
                    "the item may be also published through an RSS channel, which does not "
                    "support formatting.")),
            Field('author', _("Author"), codebook='Users'),
            Field('date_title', virtual=True,
                  computer=Computer(self._date_title, depends=('date', 'title'))))
        sorting = (('timestamp', DESC),)
        columns = ('title', 'timestamp', 'author')
        layout = ('timestamp', 'title', 'content')
        list_layout = pp.ListLayout('title', meta=('timestamp', 'author'),  content='content',
                                    anchor="item-%s")
        def _date(self, record):
            return record['timestamp'].export(show_time=False)
        def _date_title(self, record):
            if record['title'].value():
                return record['date'].export() +': '+ record['title'].value()
        
    _LIST_BY_LANGUAGE = True
    _OWNER_COLUMN = 'author'
    _EMBED_BINDING_COLUMN = 'mapping_id'
    _PANEL_FIELDS = ('date', 'title')
    _INSERT_LABEL = _("New message")
    _RSS_TITLE_COLUMN = 'title'
    _RSS_DESCR_COLUMN = 'content'
    _RSS_DATE_COLUMN = 'timestamp'
    _RSS_AUTHOR_COLUMN = ('author', 'email')
    RIGHTS_insert = (Roles.CONTRIBUTOR,)
    RIGHTS_update = (Roles.ADMIN, Roles.OWNER)
    RIGHTS_delete = (Roles.ADMIN,)
    _mapping_identifier_cache = BoundCache()
    
    def _record_uri(self, req, record, *args, **kwargs):
        def get():
            return record.cb_value('mapping_id', 'identifier').value()
        # BoundCache will cache only in the scope of one request.
        uri = '/'+ self._mapping_identifier_cache.get(req, record['mapping_id'].value(), get)
        #if args or kwargs:
        #    uri += '/data/' + record[self._referer].export()
        #    return make_uri(uri, *args, **kwargs)
        anchor = 'item-'+ record[self._referer].export()
        return make_uri(uri, anchor)
            
    def _redirect_after_insert(self, req, record):
        if req.wmi:
            return super(News, self)._redirect_after_insert(req, record)
        else:
            return self._module('Pages').action_view(req, req.page, msg=self._insert_msg(record))
        

class Planner(News):
    class Spec(News.Spec):
        title = _("Planner")
        help = _("Announce future events by date in a callendar-like listing.")
        def fields(self): return [
            Field('planner_id', editable=NEVER),
            Field('start_date', _("Date"), width=10,
                  type=Date(not_null=True, constraints=(self._check_date,)),
                  descr=_("The date when the planned event begins. Enter the date including year. "
                          "Example: %(date)s", date=lcg.LocalizableDateTime((now()+7).date))),
            Field('end_date', _("End date"), width=10, type=Date(),
                  descr=_("The date when the event ends if it is not the same as the start date "
                          "(for events which last several days).")),
            Field('date', _("Date"), virtual=True, computer=computer(self._date)),
            Field('title', _("Title"), column_label=_("Event"), width=32,
                  descr=_("The event brief summary.")),
            ] + [f for f in super(Planner.Spec, self).fields() 
                 if f.id() not in ('news_id', 'date', 'title')]
        sorting = (('start_date', ASC),)
        columns = ('title', 'date', 'author')
        layout = ('start_date', 'end_date', 'title', 'content')
        list_layout = pp.ListLayout('date_title', meta=('author', 'timestamp'), content='content',
                                    anchor="item-%s")
        def _check_date(self, date):
            if date < today():
                return _("Date in the past")
        def _date(self, record, start_date, end_date):
            date = record['start_date'].export(show_weekday=True)
            if end_date:
                date += ' - ' + record['end_date'].export(show_weekday=True)
            return date
        def check(self, record):
            end = record['end_date'].value()
            if end and end <= record['start_date'].value():
                return ('end_date', _("End date precedes start date"))
    _RSS_TITLE_COLUMN = 'date_title'
    _RSS_DATE_COLUMN = None
    def _condition(self, req, **kwargs):
        scondition = super(Planner, self)._condition(req, **kwargs)
        condition = pd.OR(pd.GE('start_date', pd.Value(pd.Date(), today())),
                          pd.GE('end_date', pd.Value(pd.Date(), today())))
        if scondition:
            return pd.AND(scondition, condition)
        else:
            return condition


class SiteMap(Module, Embeddable):
    """Extend page content by including a hierarchical listing of the main menu."""

    _TITLE = _("Site Map")
    
    def embed(self, req):
        return [lcg.RootIndex()]


class Stylesheets(Stylesheets):
    """Serve the available stylesheets.

    The Wiking base stylesheet class is extended to retrieve the stylesheet contents from the
    database driven 'Styles' module (in addition to serving the default styles installed on the
    filesystem).

    """
    def _stylesheet(self, name):
        try:
            content = self._module('Styles').stylesheet(name)
        except MaintananceModeError:
            content = None
        if content:
            return content
        else:
            return super(Stylesheets, self)._stylesheet(name)

   
class Styles(CMSModule):
    """Manage available Cascading Stylesheets through a Pytis data object."""
    class Spec(Specification):
        title = _("Stylesheets")
        table = 'stylesheets'
        help = _("Manage available Cascading Stylesheets.")
        fields = (
            Field('stylesheet_id'),
            Field('identifier',  _("Identifier"), width=16),
            Field('active',      _("Active")),
            Field('description', _("Description"), width=50),
            Field('content',     _("Content"), height=20, width=80),
            )
        layout = ('identifier', 'active', 'description', 'content')
        columns = ('identifier', 'active', 'description')
    _REFERER = 'identifier'
    WMI_SECTION = WikingManagementInterface.SECTION_STYLE
    WMI_ORDER = 200

    def stylesheets(self):
        return [r['identifier'].value() for r in self._data.get_rows(active=True)]
        
    def stylesheet(self, name):
        row = self._data.get_row(identifier=name, active=True)
        if row:
            return row['content'].value()
        else:
            return None


class Users(CMSModule):
    """Manage user accounts through a Pytis data object.

    This module is used by the Wiking CMS application to retrieve the login
    information.
    
    """

    class Spec(Specification):
        title = _("Users")
        help = _("Manage registered users and their privileges.")
        _ROLES = (('none', _("Account disabled"), ()),
                  ('user', _("User"),         (Roles.USER,)),
                  ('cont', _("Contributor"),  (Roles.USER, Roles.CONTRIBUTOR)),
                  ('auth', _("Author"),       (Roles.USER, Roles.CONTRIBUTOR, Roles.AUTHOR)),
                  ('admn', _("Administrator"), (Roles.USER, Roles.CONTRIBUTOR, Roles.AUTHOR,
                                                Roles.ADMIN)))
        _ROLE_DICT = dict([(_code, (_title, _roles)) for _code, _title, _roles in _ROLES])

        def _fullname(self, record, firstname, surname, login):
            if firstname and surname:
                return firstname + " " + surname
            else:
                return firstname or surname or login
        def _registration_expiry(self, record):
            if not cfg.login_is_email:
                return None
            expiry_days = cfg.registration_expiry_days
            return mx.DateTime.now().gmtime() + mx.DateTime.TimeDelta(hours=expiry_days*24)
        def _registration_code(self, record):
            if not cfg.login_is_email:
                return None
            return self._generate_registration_code()
        @staticmethod
        def _generate_registration_code():
            import random
            import string
            random.seed()
            return string.join(['%d' % (random.randint(0, 9),) for i in range(16)], '')            
        def fields(self):
            md5_passwords = (cfg.password_storage == 'md5')
            return (
            Field('uid', width=8, editable=NEVER),
            Field('login', _("Login name"), width=16, editable=ONCE,
                  type=pd.RegexString(maxlen=16, not_null=True, regex='^[a-zA-Z][0-9a-zA-Z_\.-]*$'),
                  computer=(cfg.login_is_email and computer(lambda r, email: email) or None),
                  descr=_("A valid login name can only contain letters, digits, underscores, "
                          "dashes and dots and must start with a letter.")),
            Field('password', _("Password"), width=16,
                  type=pd.Password(minlen=4, maxlen=32,
                                   not_null=(not cfg.certificate_authentication),
                                   md5=md5_passwords),
                  descr=_("Please, write the password into each of the two fields to eliminate "
                          "typos.")),
            Field('old_password', _(u"Old password"), virtual=True, width=16,
                  type=pd.Password(verify=False, not_null=True, md5=md5_passwords),
                  descr=_(u"Verify your identity by entering your original (current) password.")),
            Field('new_password', _("New password"), virtual=True, width=16,
                  type=pd.Password(not_null=True),
                  descr=_("Please, write the password into each of the two fields to eliminate "
                          "typos.")),
            Field('fullname', _("Full Name"), virtual=True, editable=NEVER,
                  computer=computer(self._fullname)),
            Field('user', _("User"), dbcolumn='user_',
                  computer=computer(lambda r, nickname, fullname: nickname or fullname)),
            Field('firstname', _("First name")),
            Field('surname', _("Surname")),
            Field('nickname', _("Displayed name"),
                  descr=_("Leave blank if you want to be referred by your full name or enter an "
                          "alternate name, such as nickname or monogram.")),
            Field('email', _("E-mail"), width=36, constraints=(self._check_email,)),
            Field('phone', _("Phone")),
            Field('address', _("Address"), width=20, height=3),
            Field('uri', _("URI"), width=36),
            Field('since', _("Registered since"), type=DateTime(show_time=False), default=now),
            Field('role', _("Role"), display=self._rolename, prefer_display=True, default='none',
                  enumerator=enum([code for code, title, roles in self._ROLES]),
                  style=lambda r: r['role'].value() == 'none' and pp.Style(foreground='#a20') \
                        or None,
                  descr=_("Select one of the predefined roles to grant the user "
                          "the corresponding privileges.")),
            Field('lang'),
            Field('regexpire', computer=Computer(self._registration_expiry, depends=())),
            Field('regcode', computer=Computer(self._registration_code, depends=())),
            Field('certauth', _("Certificate authentication"), type=pd.Boolean(),
                  descr=_("Check this field to authenticate by a certificate rather than by "
                          "a password."), ),
            Field('organization', _("Organization"), editable=ONCE,
                  descr=_(("If you are a member of an organization registered in the application "
                           "write the name of the organization here. "
                           "Otherwise leave the field empty."))),
            Field('organization_id', _("Organization"), codebook='Organizations', not_null=False),
            Field('certfile', _("Certificat request file"), virtual=True, editable=ALWAYS,
                  type=pytis.data.Binary(not_null=True, maxlen=10000),
                  descr=_("Upload a PEM file containing the certificate")),
            )
        def check(self, record):
            if cfg.certificate_authentication:
                if not record['password'].value() and not record['certauth'].value():
                    return 'password', _("No password given")
        def _check_email(self, email):
            result = wiking.validate_email_address(email)
            if not result[0]:
                return _("Invalid e-mail address: %s", result[1])
        def _rolename(self, code):
            return self._ROLE_DICT[code][0]
        @classmethod
        def _roles(cls, row):
            return cls._ROLE_DICT[row['role'].value()][1]
        columns = ('fullname', 'nickname', 'email', 'role', 'since')
        sorting = (('surname', ASC), ('firstname', ASC))
        layout = (FieldSet(_("Personal data"), ('firstname', 'surname', 'nickname')),
                  FieldSet(_("Contact information"), ('email', 'phone', 'address', 'uri')))
        cb = CodebookSpec(display='user', prefer_display=True)
        conditions = (
            pp.Condition(_("All users"), None),
            pp.Condition(_("Active users"),
                         pd.AND(pd.NE('role', pd.Value(pd.String(), 'none')),
                                pd.EQ('regexpire', pd.Value(pd.DateTime(), None))),
                         id='active'),
            pp.Condition(_("Inactive users (including unconfirmed registration requests)"),
                         pd.AND(pd.EQ('role', pd.Value(pd.String(), 'none')),
                                pd.EQ('regexpire', pd.Value(pd.DateTime(), None))),
                         id='inactive'),
            pp.Condition(_("Invalid registration requests (pending e-mail approval)"),
                         pd.NE('regexpire', pd.Value(pd.DateTime(), None)),
                         id='unconfirmed'),
            )
        default_filter = 'active'

    _REFERER = 'login'
    _PANEL_FIELDS = ('fullname',)
    _ALLOW_TABLE_LAYOUT_IN_FORMS = False
    _OWNER_COLUMN = 'uid'
    _SUPPLY_OWNER = False
    _LAYOUT = {} # to be initialized in the constructor and/or redefined in a subclass
    _INSERT_LABEL = _("New user")
    _UPDATE_LABEL = _("Edit profile")
    _UPDATE_DESCR = _("Modify user's record")
    def _default_actions_first(self, req, record):
        actions = super(Users, self)._default_actions_first(req, record) + ( 
            Action(_("Access rights"), 'rights', descr=_("Change access rights")),)
        if req.user():
            authentication_method = req.user().authentication_method()
            if authentication_method == 'password':
                actions += (Action(_("Change password"), 'passwd',
                                   descr=_("Change user's password")),)
            elif authentication_method == 'certificate':
                actions += (Action(_("Change certificate"), 'newcert',
                                   descr=_("Generate new certificate"),
                                   uid=req.user().uid()),)
        return actions
    RIGHTS_insert = (Roles.ANYONE,)
    RIGHTS_update = (Roles.ADMIN, Roles.OWNER)
    RIGHTS_delete = (Roles.ADMIN,) #, Roles.OWNER)
    WMI_SECTION = WikingManagementInterface.SECTION_USERS
    WMI_ORDER = 100

    @staticmethod
    def _embed_binding_condition(row):
        return pd.NE('role', pd.Value(pd.String(), 'none'))

    def __init__(self, *args, **kwargs):
        super(Users, self).__init__(*args, **kwargs)
        if not self._LAYOUT:
            self._LAYOUT = {
                'insert': (FieldSet(_("Personal data"), ('firstname', 'surname', 'nickname',)),
                           FieldSet(_("Contact information"),
                                    (((not cfg.login_is_email) and ('email',) or ()) +
                                     ('phone', 'address', 'uri',))),
                           FieldSet(_("Login information"),
                                    ((cfg.login_is_email and ('email',) or ('login',)) +
                                     ('password',) +
                                     (cfg.certificate_authentication and ('certauth',) or ())))),
                'view':   (FieldSet(_("Personal data"), ('firstname', 'surname', 'nickname',)),
                           FieldSet(_("Contact information"), ('email', 'phone', 'address','uri')),
                           FieldSet(_("Access rights"), ('role',))),
                'rights': ('role',),
                'passwd': ((cfg.login_is_email and 'email' or 'login'),
                           'old_password', 'new_password',)}

    def _send_admin_confirmation_mail(self, req, record):
        self._module('Users').send_admin_approval_mail(req, record)

    def _certificate_confirmation(self, req, record, email=None):
        uid = record['uid'].value()
        certificate_row = self._module('UserCertificates').authentication_certificate(uid)
        if certificate_row is not None:
            certificate = certificate_row['certificate'].value()
            text = _("Here is your certificate to authenticate to the application")
            try:
                language = record['lang'].value()
            except KeyError:
                language = req.prefered_language()
            if email is None:
                email = record['email'].value()
            send_mail(email,
                      _("Your certificate for %s", req.server_hostname()),
                      text,
                      lang=language,
                      attachments=(MailAttachment('cert.pem',
                                                  stream=cStringIO.StringIO(str(certificate))),))
        return certificate_row
        
    def _confirmation_success(self, req, record):
        self._send_admin_confirmation_mail(req, record)
        content = lcg.p(_("Registration completed successfuly. "
                          "Your account now awaits administrator's approval."))
        if cfg.certificate_authentication and self._certificate_confirmation(req, record):
            content = lcg.Container((content, lcg.p(_("The signed certificate has been sent to "
                                                      "you by e-mail."))))
        return Document(_("Registration confirmed"), content)
    
    def _confirmation_failure(self, req, error_message):
        if req.param('action') == 'certload':
            title = _("Certificate renewal failure")
        else:
            title = _("Registration confirmation failed")
        return Document(title, lcg.p(error_message))
    
    def action_confirm(self, req):
        record, error_message = self._authorize_registration(req)
        if error_message is None:
            result = self._confirmation_success(req, record)
        else:
            result = self._confirmation_failure(req, error_message)
        return result
    RIGHTS_confirm = (Roles.ANYONE,)
    
    # TODO: Pravděpodobně zapomenuto při copy & paste.  Zrušit.
    def action_certload(self, req):
        record, error_message = self._authorize_registration(req)
        if error_message is None:
            result = self._confirmation_success(req, record)
        else:
            result = self._confirmation_failure(req, error_message)
        return result
    RIGHTS_certload = (Roles.ANYONE,)

    # TODO: Nutno zrušit a předělat to, kvůli čemu to tu bylo.
    def action_insert(self, req, record=None):
        if req.param('form_name') == 'CertificateRequest':
            result = self.action_newcert(req, record)
        else:
            result = super(Users, self).action_insert(req)
        return result
    
    def action_newcert(self, req, record):
        certificate_request_module = self._module('CertificateRequest')
        if req.param('submit'):
            record, errors, layout = certificate_request_module.action_insert_perform(req)
            if errors:
                result = certificate_request_module.action_insert_document(req, layout, errors,
                                                                           record)
            else:
                email = req.user().email()
                self._certificate_confirmation(req, record, email=email)
                result = Document(_("Certificate updated"), lcg.p(_("New certificate installed.")))
        else:
            result = certificate_request_module.action_insert(req)
        return result
    RIGHTS_newcert = (Roles.OWNER,)
    
    def _validate(self, req, record, layout=None):
        if record.new():
            record['lang'] = pd.Value(record['lang'].type(), req.prefered_language())
        if layout and 'old_password' in layout.order():
            errors = []
            current_password_value = record['password'].value()
            #if not Roles.check(req, (Roles.ADMIN,)): Too dangerous?
            old_password = req.param('old_password')
            if not old_password:
                errors.append(('old_password', _(u"Enter your current password.")))
            else:
                error = record.validate('old_password', old_password, verify=old_password)
                if error or record['old_password'].value() != current_password_value:
                    errors.append(('old_password', _(u"Invalid password.")))
            new_password = req.param('new_password')
            if not new_password:
                errors.append(('new_password', _(u"Enter the new password.")))
            else:
                error = record.validate('password', new_password[0], verify=new_password[1])
                if error:
                    errors.append(('new_password', error.message(),))
                elif record['password'].value() == current_password_value:
                    errors.append(('new_password',
                                   _(u"The new password is the same as the old one.")))
            if errors:
                return errors
        return super(Users, self)._validate(req, record, layout=layout)
        
    def _base_uri(self, req):
        if req.path[0] == '_registration':
            return '_registration'
        return super(Users, self)._base_uri(req)

    def _insert_subtitle(self, req):
        if req.path[0] == '_registration':
            return None
        return super(Users, self)._insert_subtitle(req)
        
    def _actions(self, req, record):
        actions = list(super(Users, self)._actions(req, record))
        if req.path[0] == '_registration':
            actions = [a for a in actions if a.name() != 'list']
        if record and record['role'].value() == 'none':
            actions.insert(0, Action(_("Enable"), 'enable', descr=_("Enable this account")))
        return actions

    def _registration_success_content(self, req, record):
        content = lcg.p(_("Registration completed successfuly. "
                          "Your account now awaits administrator's approval."))
        return content

    def _make_registration_email(self, req, record):
        msg, err = None, None
        base_uri = self._application.module_uri('Registration') or '/_wmi/'+ self.name()
        server_hostname = req.server_hostname()
        certificate_authentication = (cfg.certificate_authentication and req.param('certauth'))
        if certificate_authentication:
            action = 'certload'
        else:
            action = 'confirm'
        uri = req.server_uri() + make_uri(base_uri, action=action, uid=record['uid'].value(),
                                          regcode=record['regcode'].value())
        text = _("You have been successfully registered at %(server_hostname)s. "
                 "To complete your registration visit the URL %(uri)s and follow "
                 "the instructions there.\n",
                 server_hostname=server_hostname,
                 uri=uri)
        attachments = ()
        if certificate_authentication:
            cert_text, attachment, attachment_stream = _certificate_mail_info(record)
            text += _("\nYou will be asked to upload your certificate request.\n")
            text += cert_text
            attachments += (MailAttachment(attachment, stream=attachment_stream),)
        return text, attachments

    def _redirect_after_insert(self, req, record):
        content = lcg.p('')
        if cfg.login_is_email:
            text, attachments = self._make_registration_email(req, record)
            user_email = record['email'].value()
            err = send_mail(user_email, _("Your registration at %s" % (req.server_hostname(),)), text,
                            lang=record['lang'].value(), attachments=attachments)
            if err:
                self._data.delete(record['uid'])
                err = _("Failed sending e-mail notification:") +' '+ err + '\n' + _("Registration cancelled.")
            else:
                msg = _("E-mail was sent to you with instructions how to complete the registration process.")
        else:
            content = self._registration_success_content(req, record)
            msg, err = self.send_admin_approval_mail(req, record)
        return self._document(req, content, subtitle=None, msg=msg, err=err)

    def send_admin_approval_mail(self, req, record):
        msg, err = None, None
        addr = cfg.webmaster_address
        if addr:
            base_uri = self._application.module_uri(self.name()) or '/_wmi/'+ self.name()
            text = _("New user %(fullname)s registered at %(server_hostname)s. "
                     "Please approve the account: %(uri)s",
                     fullname=record['fullname'].value(), server_hostname=req.server_hostname(),
                     uri=req.server_uri() + base_uri +'/'+ record['login'].value()) + "\n"
            # TODO: The admin email is translated to users language.  It would be more approppriate
            # to subscribe admin messages from admin accounts and set the language for each admin.
            err = send_mail(addr, _("New user registration:") +' '+ record['fullname'].value(),
                            text, lang=record['lang'].value())
            if err:
                err = _("Failed sending e-mail notification:") +' '+ err
            else:
                msg = _("E-mail notification has been sent to server administrator.")
        return msg, err

    def _redirect_after_update(self, req, record):
        if record.original_row()['role'].value() == 'none' and record['role'].value() != 'none':
            msg = _("The account was enabled.")
            text = _("Your account at %(uri)s has been enabled. "
                     "Please log in with username '%(login)s' and your password.",
                     uri=req.server_uri(), login=record['login'].value()) + "\n"
            err = send_mail(record['email'].value(), _("Your account has been enabled."),
                            text, lang=record['lang'].value())
            if err:
                err = _("Failed sending e-mail notification:") +' '+ err
            else:
                msg += ' '+_("E-mail notification has been sent to:") +' '+ record['email'].value()
            return self.action_view(req, record, msg=msg, err=err)
        else:
            return super(Users, self)._redirect_after_update(req, record)
    
    def action_enable(self, req, record):
        req.set_param('submit', '1')
        req.set_param('role', 'user')
        return self.action_update(req, record, action='rights')
    RIGHTS_enable = (Roles.ADMIN,)
    
    def action_rights(self, req, record):
        # TODO: Enable table layout for this form.
        return self.action_update(req, record, action='rights')
    RIGHTS_rights = (Roles.ADMIN,)
    
    def action_passwd(self, req, record):
        return self.action_update(req, record, action='passwd')
    RIGHTS_passwd = (Roles.ADMIN, Roles.OWNER)

    def user(self, req, login):
        row = self._data.get_row(login=login)
        if row:
            record = self._record(req, row)
            base_uri = self._application.module_uri(self.name())
            if base_uri:
                uri = base_uri +'/'+ login
            else:
                uri = self._application.module_uri('Registration')
            organization_id_value = record['organization_id']
            organization_id = organization_id_value.value()
            if organization_id:
                organizations = self._module('Organizations')
                organization_record = organizations.record(req, organization_id_value)
                organization = organization_record['name'].value()
            else:
                organization = None
            return User(login, name=record['user'].value(), uid=record['uid'].value(),
                        uri=uri, email=record['email'].value(), data=record,
                        roles=self.Spec._roles(record),
                        organization_id=organization_id, organization=organization)
        else:
            return None

    def find_user(self, req, query):
        """Return the user record for given uid, login or email address (for password reminder).
        """
        if isinstance(query, int):
            row = self._data.get_row(uid=query)
        elif query.find('@') == -1:
            row = self._data.get_row(login=query)
        else:
            row = self._data.get_row(email=query)
        if row:
            return self._record(req, row)
        else:
            return None

    def role_users(self, req, role):
        """Return list of user records of the users having 'role'.

        Arguments:

          req -- web request instance
          role -- role identifier as defined in 'Roles' or its successor, string

        """
        assert isinstance(role, str)
        role_codes = [code for code, title, roles in self.Spec._ROLES if role in roles]
        String = pd.String()
        condition = pd.OR(*[pd.EQ('role', pd.Value(String, code)) for code in role_codes])
        data = self._data
        data.select(condition=condition)
        result_rows = []
        while True:
            row = data.fetchone()
            if row is None:
                break
            result_rows.append(row)
        data.close()
        return result_rows
        
    def check_registration_code(self, req):
        """Check whether given request contains valid login and registration code.

        Return pair (RECORD, MESSAGE) where RECORD is a 'Record' corresponding
        to the user id given in the request (if the record is available) and
        MESSAGE is either 'None' in case the login and registration code are
        valid, or a unicode describing the error.

        """
        uid = req.param('uid')
        registration_code = req.param('regcode')
        if not uid:
            return None, _("Missing form parameters")
        # This doesn't prevent double registration confirmation, but how to
        # avoid it?
        row = self._data.get_row(uid=uid)
        if row is None:
            record is None
        else:
            record = self._record(req, row)
        if record is None or (not record['regexpire'].value() and record['role'] == 'none'):
            # Let's be careful not to depict whether given login name is registered
            return None, _("Invalid login or user registration already confirmed")
        else:
            code = record['regcode'].value()
            if not code or code != registration_code:
                return record, _("Invalid access code")
        return record, None

    def set_registration_code(self, uid):
        """Generate and set new registration code for given user 'uid'.

        Return the generated code.

        This method can be used in registration or in password and certificate
        reminders.
        
        """
        code = self.Spec._generate_registration_code()
        code_value = pytis.data.String().validate(code)[0]
        uid_value = pytis.data.Integer().validate(str(uid))[0]
        row = pytis.data.Row((('regcode', code_value,),))
        new_row, result = self._data.update(uid_value, row)
        if not result:
            raise Exception(_("Database operation failed"))
        return code

    def delete_registration_code(self, req):
        """Remove registration code for user identified by 'req'."""
        uid = req.param('uid')
        uid_value = pytis.data.Integer().validate(str(uid))[0]
        code_value = pytis.data.String().validate('')[0]
        row = pytis.data.Row((('regcode', code_value,),))
        new_row, result = self._data.update(uid_value, row)
        if not result:
            raise Exception(_("Database operation failed"))
        
    def _authorize_registration(self, req):
        """Make user registration defined by 'Request' 'req' valid.

        Additionally perform all related actions such as sending an e-mail
        notification to the administrator.
        
        """
        record, error = self.check_registration_code(req)
        if error:
            return record, error
        record.update(regexpire=None)
        return record, None

    
class ActiveUsers(Users, EmbeddableCMSModule):
    """User listing to be embedded into page content.

    This extension module may be used to make the list of active users publically available on the
    website.  Standard page options can be used to make the list completely public or private (only
    available to logged in users).

    """
    class Spec(Users.Spec):
        table = 'users'
        title = _("Active users")
        help = _("Listing of all active user accounts.")
        condition = pd.AND(pd.NE('role', pd.Value(pd.String(), 'none')),
                           pd.EQ('regexpire', pd.Value(pd.DateTime(), None)))
        conditions = ()
        default_filter = None
    _INSERT_LABEL = lcg.TranslatableText("New user registration", _domain='wiking')
    WMI_SECTION = None
    WMI_ORDER = None


class Organizations(CMSModule):
    """Codebook of organization users can belong to.

    This module/table may play important role in determining user actions as it
    can define common users groups sharing the same data.

    """
    class Spec(Specification):
        
        title = _("Organizations")
        help = _("Manage institutions and other organizations.")

        def fields(self): return (
            Field('organization_id', width=8, editable=NEVER),
            Field('name', _("Name"), width=32),
            Field('vatid', _("VAT id")),
            Field('email', _("E-mail"), width=36, constraints=(self._check_email,)),
            Field('phone', _("Phone")),
            Field('address', _("Address"), width=20, height=3),
            Field('notes', _("Notes"), width=20, height=3),
            )
        def _check_email(self, email):
            result = wiking.validate_email_address(email)
            if not result[0]:
                return _("Invalid e-mail address: %s", result[1])
        cb = CodebookSpec(display='name', prefer_display=True)

        columns = ('name', 'vatid',)
        sorting = (('name', ASC,),)
        layout = ('name', 'vatid', 'email', 'phone', 'address', 'notes',)
    
    RIGHTS_insert = (Roles.ADMIN,)
    RIGHTS_update = (Roles.ADMIN,)
    RIGHTS_delete = (Roles.ADMIN,)

    WMI_SECTION = WikingManagementInterface.SECTION_USERS
    WMI_ORDER = 500

    _TITLE_COLUMN = 'name'


class TextLabels(PytisModule):
    """Internal module for managing identifiers of the texts accessed through the 'Text' module.
    """
    
    class Spec(Specification):
        
        _ID_COLUMN = 'label'

        table = 'text_labels'
        
        def fields(self): return (
            Field(self._ID_COLUMN),
            )

    def register_label(self, label):
        """Register text identified by 'label'.

        This ensures 'label' is present in the database and thus it can be
        accessed and managed in CMS.

        Arguments:

          label -- text identifier as a string

        """
        data = self._data
        if not data.get_row(label=label):
            label_value = pytis.data.Value(pytis.data.String(), label)
            row = pytis.data.Row((('label', label_value,),))
            data.insert(row)

    
class Texts(CMSModule):
    """Storage of various texts editable by administrators.

    The texts are LCG structured texts.  These texts are language dependent.

    Each of the texts is identified by a unique identifier.  To avoid naming
    conflicts between various Wiking extensions the identifiers are of the form
    NAMESPACE.ID where NAMESPACE is an identifier of the extension name space
    and ID is the particular text id within the name space.  It is recommended
    to limit both NAMESPACE and ID characters to English letters, digits and
    dashes.

    Particular texts are defined by applications through the 'register_text'
    method.  Unregistered texts cannot be used and accessed.  Administrators
    may change registered texts in CMS, but they can't delete them nor to
    insert new texts (except for translations of existing texts).

    Wiking modules can access the texts by using the 'text' method.

    """

    class Spec(Specification):

        _texts = {}

        # This must be a private method, otherwise Wiking handles it in a special way
        @classmethod
        def _register_text(class_, label, description, module):
            texts = class_._texts
            if not texts.has_key(label):
                texts[label] = description
                module._module('TextLabels').register_label(label)
        
        _ID_COLUMN = 'text_id'

        table = 'texts'
        title = _("System Texts")
        help = _("Edit miscellaneous system texts.")
        
        def fields(self): return (
            Field(self._ID_COLUMN, editable=NEVER),
            Field('label', _("Label"), width=32, editable=NEVER),
            Field('lang', editable=NEVER),
            Field('descr', _("Purpose"), type=pytis.data.String(), width=64, editable=NEVER, virtual=True,
                  computer=Computer(self._description, depends=('label',))),
            Field('content', _("Text"), width=80, height=10,
                  descr=_("Edit the given text as needed, in accordance with structured text rules.")),
            )
        
        columns = ('text_id', 'descr',)
        sorting = (('text_id', ASC,),)
        layout = ('text_id', 'descr', 'content',)

        def _description(self, record):
            return self._texts.get(record['label'].value(), "")
            
    _LIST_BY_LANGUAGE = True
    RIGHTS_insert = ()
    RIGHTS_update = (Roles.ADMIN,)
    RIGHTS_delete = ()
    WMI_SECTION = WikingManagementInterface.SECTION_SETUP
    WMI_ORDER = 900

    def _text_identifier(self, namespace, label, lang=None):
        identifier = '%s.%s' % (namespace, label,)
        if lang is not None:
            identifier = '%s@%s' % (identifier, lang,)
        return identifier
    
    def text(self, namespace, label, lang='en'):
        """Return text identified by 'namespace' and 'label'.

        If there is no such text, return 'None'.

        Arguments:

          namespace -- string identifying Wiking extension name space
          label -- string identifying the text within the name space
          lang -- two-character string identifying the language of the text

        If there is no text available for the given 'lang', the same text is
        search for language 'en'.  If no text is available even for 'en'
        language, 'None' is returned.
          
        """
        assert isinstance(namespace, str)
        assert isinstance(label, str)
        assert isinstance(lang, str)
        identifier = self._text_identifier(namespace, label, lang=lang)
        row = self._data.get_row(text_id=identifier)
        if row is None and lang != 'en':
            identifier = self._text_identifier(namespace, label, lang='en')
            row = self._data.get_row(text_id=identifier)
        if row is None:
            return None
        text = row['content'].value()
        return text

    def parsed_text(self, namespace, label, lang='en'):
        """Return parsed text identified by 'namespace' and 'label'.

        This method is the same as 'text' but instead of returning LCG
        structured text, it returns its parsed form, as a sequence of
        'lcg.Content' instances.  If the given text doesn't exist, an empty
        sequence is returned.
        
        """
        text = self.text(namespace, label, lang=lang)
        if text:
            sections = lcg.Parser().parse(text)
        else:
            sections = ()
        return sections

    def register_text(self, namespace, label, description):
        """Register text with given 'label'.

        All texts must be registered using this module method before their
        first use.

        Arguments:

          namespace -- string identifying Wiking extension name space
          label -- identifier of the text as a string
          description -- human description of the purpose of the text as a
            string or unicode
          
        """
        assert isinstance(namespace, str)
        assert isinstance(label, str)
        assert isinstance(description, basestring)
        identifier = self._text_identifier(namespace, label)
        self.Spec._register_text(identifier, description, self)


class TextReferrer(object):
    """Class of modules using 'Text' module.

    This class simplifies registration and retrieval of texts stored in 'Text'
    module.  It is intended to be inherited as an additional class into Wiking
    modules using multiple inheritance.

    In order to perform automatic registration, you must do the following:

      - Define text namespace in '_TEXTS_NAMESPACE' attribute, as a string.

      - Define texts to register in '_TEXTS' attribute.  It is a tuple
        containing entries of the form (LABEL, DESCRIPTION,) where LABEL is a
        string label of the text (without the name space identifier) and
        DESCRIPTION is a unicode describing the purpose of the text.

    Additionaly the class defines convenience methods 'text' and 'parsed_text'
    to simplify retrieving registered texts.

    """
    
    _TEXTS_NAMESPACE = ''
    _TEXTS = ()

    def __init__(self, *args, **kwargs):
        super(TextReferrer, self).__init__(*args, **kwargs)
        self._register_texts()

    def _register_texts(self):
        # Check text specification
        assert isinstance(self._TEXTS_NAMESPACE, str)
        assert self._TEXTS_NAMESPACE, "Name space of registered texts may not be empty"
        assert isinstance(self._TEXTS, tuple)
        if __debug__:
            for definition in self._TEXTS:
                assert isinstance(definition, tuple)
                try:
                    label, description = definition
                except ValueError:
                    raise AssertionError("Invalid _TEXTS entry", definition)
                assert isinstance(label, str), ("Invalid text label in _TEXTS", label,)
                assert isinstance(description, basestring), ("Invalid text description in _TEXTS", description,)
        # Perform registration
        text_module = self._module('Texts')
        namespace = self._TEXTS_NAMESPACE
        for label, description in self._TEXTS:
            text_module.register_text(namespace, label, description)

    def text(self, label, lang='en', _method=Texts.text):
        """Return text identified by 'label'.

        If there is no such text, return 'None'.

        Arguments:

          label -- string identifying the text within the name space defined in
            the class
          lang -- two-character string identifying the language of the text

        Looking texts for a particular language is performed according the
        rules documented in 'Text.text'.
          
        """
        assert label in [t[0] for t in self._TEXTS], ("Unregistered text referred", label,)
        assert isinstance(lang, str)
        return _method(self._module('Texts'), self._TEXTS_NAMESPACE, label, lang=lang)

    def parsed_text(self, label, lang='en'):
        """Return parsed text identified by 'label'.

        This method is the same as 'text' but instead of returning LCG
        structured text, it returns its parsed form, as a sequence of
        'lcg.Content' instances.  If the given text doesn't exist, an empty
        sequence is returned.
        
        """
        return self.text(label, lang=lang, _method=Texts.parsed_text)

        
class Certificates(CMSModule):
    """Base class of classes handling various kinds of certificates."""

    class UniType(pytis.data.Type):
        """Universal type able to contain any value.

        This is just a utility type for internal use within 'Certificates'
        class, without implementing any of the 'Type' methods.

        """

    class Spec(Specification):

        def __init__(self, *args, **kwargs):
            Specification.__init__(self, *args, **kwargs)
            self._ca_x509 = None

        _ID_COLUMN = 'certificates_id'
        
        def fields(self): return (
            Field(self._ID_COLUMN, width=8, editable=NEVER),
            Field('file', _("PEM file"), virtual=True, editable=ALWAYS,
                  type=pytis.data.Binary(not_null=True, maxlen=10000),
                  descr=_("Upload a PEM file containing the certificate")),
            Field('certificate', _("Certificate"), width=60, height=20, editable=NEVER,
                  computer=Computer(self._certificate_computer, depends=('file',))),
            Field('x509', _("X509 structure"), virtual=True, editable=NEVER, type=Certificates.UniType(),
                  computer=Computer(self._x509_computer, depends=('certificate',))),
            Field('serial_number', _("Serial number"), editable=NEVER,
                  computer=self._make_x509_computer(self._serial_number_computer)),
            Field('text', _("Certificate"), width=60, height=20, editable=NEVER,
                  computer=self._make_x509_computer(self._text_computer)),
            Field('issuer', _("Certification Authority"), width=32, editable=NEVER,
                  computer=self._make_x509_computer(self._issuer_computer)),
            Field('valid_from', _("Valid from"), editable=NEVER,
                  computer=self._make_x509_computer(self._valid_from_computer)),
            Field('valid_until', _("Valid until"), editable=NEVER,
                  computer=self._make_x509_computer(self._valid_until_computer)),
            Field('trusted', _("Trusted"), default=False,
                  descr=_("When this is checked, certificates signed by this root certificate are considered valid.")),
            )
        
        columns = ('issuer', 'valid_from', 'valid_until', 'trusted',)
        sorting = (('issuer', ASC,), ('valid_until', ASC,))
        layout = ('trusted', 'issuer', 'valid_from', 'valid_until', 'text',)

        def _certificate_computation(self, buffer):
            return str(buffer)
        def _certificate_computer(self, record):
            file_value = record['file'].value()
            if file_value is None: # new record form
                return None
            certificate = self._certificate_computation(file_value.buffer())
            return certificate
        def _x509_computer(self, record):
            import gnutls.crypto
            if self._ca_x509 is None:
                self._ca_x509 = gnutls.crypto.X509Certificate(open(cfg.ca_certificate_file).read())
            certificate = record['certificate'].value()
            if certificate is None: # new record form
                return None
            try:
                x509 = gnutls.crypto.X509Certificate(certificate)
            except Exception, e:
                raise Exception(_("Invalid certificate"), e)
            if not x509.has_issuer(x509) and not x509.has_issuer(self._ca_x509):
                x509 = None
            return x509
        def _make_x509_computer(self, function):
            def func(record):
                x509 = record['x509'].value()
                if x509 is None:
                    return None
                return function(x509)
            return Computer(func, depends=('x509',))
        def _serial_number_computer(self, x509):
            number = int(x509.serial_number)
            if not isinstance(number, int): # it may be long
                raise Exception(_("Unprocessable serial number"))
            return number
        def _issuer_computer(self, x509):
            return unicode(x509.issuer)
        def _valid_from_computer(self, x509):
            return self._convert_x509_timestamp(x509.activation_time)
        def _valid_until_computer(self, x509):
            return self._convert_x509_timestamp(x509.expiration_time)
        def _text_computer(self, x509):
            return ('Subject: %s\nIssuer: %s\nSerial number: %s\nVersion: %s\nValid from: %s\nValid until: %s\n' %
                    (x509.subject, x509.issuer, x509.serial_number, x509.version, time.ctime(x509.activation_time), time.ctime(x509.expiration_time),))
        def _convert_x509_timestamp(self, timestamp):
            time_tuple = time.gmtime(timestamp)
            mx_time = mx.DateTime.DateTime(*time_tuple[:6])
            return mx_time
            
        def check(self, record):
            x509 = record['x509'].value()
            if x509 is None:
                return ('file', _("The certificate is not valid"),)
                
    RIGHTS_view = (Roles.ADMIN,)
    RIGHTS_list = (Roles.ADMIN,)
    RIGHTS_rss  = (Roles.ADMIN,)
    RIGHTS_insert = (Roles.ADMIN,)
    RIGHTS_update = (Roles.ADMIN,)
    RIGHTS_delete = (Roles.ADMIN,)
        
    _LAYOUT = {'insert': ('file',)}

class CACertificates(Certificates):
    """Management of root certificates."""
    
    class Spec(Certificates.Spec):
        
        _ID_COLUMN = 'cacertificates_id'

        table = 'cacertificates'
        title = _("CA Certificates")
        help = _("Manage trusted root certificates.")
        
        def check(self, record):
            error = Certificates.Spec.check(self, record)
            if error is not None:
                return error
            x509 = record['x509'].value()
            if x509.check_ca() != 1:
                return ('file', _("This is not a CA certificate."))
        
    _LAYOUT = {'insert': ('file',)}
    
    WMI_SECTION = WikingManagementInterface.SECTION_CERTIFICATES
    WMI_ORDER = 100

class UserCertificates(Certificates):
    """Management of user certificates, especially for the purpose of authentication."""

    class Spec(Certificates.Spec):
        
        title = _("User Certificates")
        help = _("Manage user and other kinds of certificates.")
        table = 'certificates'
        
        _PURPOSE_AUTHENTICATION = 1

        def fields(self):
            fields = Certificates.Spec.fields(self)
            fields = fields + (Field('subject', _("Subject"), virtual=True, editable=NEVER, type=Certificates.UniType(),
                                     computer=self._make_x509_computer(self._subject_computer)),
                               Field('common_name', _("Name"), editable=NEVER,
                                     computer=Computer(self._common_name_computer, depends=('subject',))),
                               Field('email', _("E-mail"), editable=NEVER,
                                     computer=Computer(self._email_computer, depends=('subject',))),
                               Field('uid', not_null=True),
                               Field('purpose', not_null=True),
                               )
            return fields

        _OWNER_COLUMN = 'uid'
        columns = ('common_name', 'valid_from', 'valid_until', 'trusted',)
        layout = ('trusted', 'common_name', 'email', 'issuer', 'valid_from', 'valid_until', 'text',)

        def _subject_computer(self, x509):
            return x509.subject
        def _common_name_computer(self, record):
            subject = record['subject'].value()
            if subject is None:
                return ''
            return subject.common_name
        def _email_computer(self, record):
            subject = record['subject'].value()
            if subject is None:
                return ''
            return subject.email
            
    WMI_SECTION = WikingManagementInterface.SECTION_CERTIFICATES
    WMI_ORDER = 200

    def authentication_certificate(self, uid):
        """Return authentication certificate row of the given user.

        The return value is the corresponding 'pytis.data.Row' instance.  If
        the user doesn't have authentication certificate assigned, return
        'None'.

        This method considers only authentication certificates.  Certificates
        present for other purposes are ignored.

        Arguments:

          uid -- user id as an integer

        """
        data = self._data
        uid_value = pd.Value(data.find_column('uid').type(), uid)
        purpose_value = pd.Value(data.find_column('purpose').type(), self.Spec._PURPOSE_AUTHENTICATION)
        self._data.select(pd.AND(pd.EQ('uid', uid_value), pd.EQ('purpose', purpose_value)))
        row = self._data.fetchone()
        self._data.close()
        return row

    def certificate_user(self, req, certificate):
        """Return user corresponding to 'certificate' and request 'req'.

        If there is no such user, return 'None'.

        The method assumes the certificate has already been verified by site CA
        certificate, so no verification is performed.

        Arguments:

          req -- 'Request' instance to provide for construction of the user object
          certificate -- PEM encoded certificate verified against the site's CA
            certificate, a string
        
        """
        user = None
        import gnutls.crypto
        x509 = gnutls.crypto.X509Certificate(certificate)
        serial_number = int(x509.serial_number)
        row = self._data.get_row(serial_number=serial_number)
        if row is not None:
            uid = row['uid'].value()
            user_module = self._module('Users')
            user_record = user_module.find_user(req, uid)
            user = user_module.user(req, user_record['login'].value())
        return user

class CertificateRequest(UserCertificates):

    class Spec(UserCertificates.Spec):

        # This is a *public* method.  But it has to begin with underscore
        # otherwise it would be handled in a special way by Wiking, causing
        # failure.
        def _set_dbconnection(self, dbconnection):
            self._serial_number_counter = pd.DBCounterDefault('certificate_serial_number', dbconnection)
            
        def fields(self):
            fields = pp.Fields(UserCertificates.Spec.fields(self))
            overridden = [Field(inherit=fields['file'], descr=_("Upload a PEM file containing the certificate request")),
                          Field(inherit=fields['purpose'], default=self._PURPOSE_AUTHENTICATION)]
            # We add some fields to propagate last form values to the new request
            extra = [Field('regcode', type=pytis.data.String(), virtual=True)]
            return fields.fields(override=overridden) + extra            

        def _certificate_computation(self, buffer):
            serial_number = self._serial_number_counter.next()
            working_dir = os.path.join(cfg.storage, 'certificate-%d' % (serial_number,))
            request_file = os.path.join(working_dir, 'request')
            certificate_file = os.path.join(working_dir, 'certificate.pem')
            log_file = os.path.join(working_dir, 'log')
            template_file = os.path.join(working_dir, 'certtool.cfg')
            os.mkdir(working_dir)
            try:
                stdout = open(log_file, 'w')
                open(request_file, 'w').write(str(buffer))
                open(template_file, 'w').write('serial = %s\nexpiration_days = %s\ntls_www_client\n' %
                                               (serial_number, cfg.certificate_expiration_days,))
                return_code = subprocess.call(('/usr/bin/certtool', '--generate-certificate',
                                               '--load-request', request_file,
                                               '--outfile', certificate_file,
                                               '--load-ca-certificate', cfg.ca_certificate_file, '--load-ca-privkey', cfg.ca_key_file,
                                               '--template', template_file,),
                                              stdout=stdout, stderr=stdout)
                if return_code != 0:
                    raise Exception(_("Certificate request could not be processed"), open(log_file).read())
                certificate = open(certificate_file).read()
            finally:
                for file_name in os.listdir(working_dir):
                    os.remove(os.path.join(working_dir, file_name))
                os.rmdir(working_dir)
            return certificate
    
    def _spec(self, resolver):
        spec = super(CertificateRequest, self)._spec(resolver)
        spec._set_dbconnection(self._dbconnection)
        return spec

    def _layout(self, req, action, record=None):
        # This is necessary to propagate `uid' given in the form to the actual
        # data row
        if action == 'insert' and req.param('submit'):
            result = pp.GroupSpec(('uid', 'file',), orientation=pp.Orientation.VERTICAL)
        else:
            result = super(CertificateRequest, self)._layout(req, action, record)
        return result

    def _document_title(self, req, record):
        return _("Certificate upload")
