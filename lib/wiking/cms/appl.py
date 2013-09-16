# -*- coding: utf-8 -*-
# Copyright (C) 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013 Brailcom, o.p.s.
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

"""Wiking Content Management System application definition.

The CMS application is defined as an implementation of Wiking Application Interface.

"""

import lcg
import wiking
from wiking.cms import CMSExtension, CMSExtensionModule, CookieAuthentication, Roles, Users, \
    text2content

_ = lcg.TranslatableTextFactory('wiking-cms')

class Application(CookieAuthentication, wiking.Application):
    
    _MAPPING = {'_doc': 'Documentation',
                '_wmi': 'WikingManagementInterface',
                '_resources': 'Resources',
                '_registration': 'Registration',
                'favicon.ico': 'SiteIcon',
                'robots.txt': 'Robots'}

    _PREVIEW_MODE_COOKIE = 'wiking_cms_preview_mode'
    _PREVIEW_MODE_PARAM = '_wiking_cms_preview_mode'
    
    class WMILink(lcg.Content):
        # Used in login panel or bottom bar.
        def export(self, context):
            g = context.generator()
            if not context.req().wmi:
                uri, label, title = ('/_wmi/', _("Manage this site"),
                                     _("Enter the Wiking Management Interface"))
            else:
                uri, label, title = ('/', _("Leave the Management Interface"), None)
            return g.a(label, href=uri, title=title, accesskey="9", id='wmi-link')
    class PreviewModeCtrl(lcg.Content):
        def export(self, context):
            g = context.generator()
            req = context.req()
            if req.wmi:
                return ""
            else:
                name = Application._PREVIEW_MODE_PARAM
                # Translators: There are two modes of operation in the CMS
                # management.  The "Production mode" displays only the content
                # publically visible to the website visitors.  "Preview mode",
                # on the other hand, displays also the content which is not
                # published yet.  This content is only visible to the
                # administrators until it is published.  Please make sure you
                # translate these two modes consistently acros all their
                # occurences.
                values = (('0', _("Production mode")),
                          # Translators: See "Production mode"
                          ('1', _("Preview mode")))
                current_value = wiking.module('Application').preview_mode(req) and '1' or '0'
                return g.form([g.radio(id=name + '_' + value, name=name, value=value,
                                       checked=(current_value == value),
                                       onchange='this.form.submit();') +
                               g.label(label, name + '_' + value) + g.br()
                               for value, label in values],
                              action=req.uri(), method='GET')

    def preview_mode(self, req):
        """Query the current state of preview mode.

        Returns True if the application is currently in a
        preview mode and False when in production mode (the oposite of preview
        mode).

        These modes determine which content is displayed.  Preview mode is for
        site administrators (also unpublished content is displayed), production
        mode is for visitors (only published content is displayed).  Switching
        may be used by adimnistrators to check the differences.

        """
        if req.check_roles(Roles.CONTENT_ADMIN) or req.__dict__.get('page_write_access'):
            return req.cookie(self._PREVIEW_MODE_COOKIE) == '1'
        else:
            return False

    def set_preview_mode(self, req, value):
        """Change the current state of preview mode.

        The current mode is changed according to given 'value' -- switched to
        preview mode when 'value' is True or switched to production mode when
        value is False.

        """
        if self.preview_mode(req) != value:
            if value:
                message = _("Switching to preview mode")
            else:
                message = _("Switching to production mode")
            req.message(message, type=req.WARNING)
            req.set_cookie(self._PREVIEW_MODE_COOKIE, value and '1' or '0')

    def initialize(self, req):
        config_file = wiking.cfg.user_config_file
        if config_file:
            wiking.cms.cfg.user_config_file = config_file
        
    def handle(self, req):
        req.wmi = False # Will be set to True by `WikingManagementInterface' if needed.
        preview_mode_param = req.param(self._PREVIEW_MODE_PARAM)
        if preview_mode_param is not None:
            req.set_cookie(self._PREVIEW_MODE_COOKIE, preview_mode_param == '1' and '1' or None)
        wiking.module('CachedTables').reload_info(req)
        wiking.module('Config').configure(req)
        if req.unresolved_path:
            try:
                modname = self._MAPPING[req.unresolved_path[0]]
            except KeyError:
                modname = 'Pages'
            else:
                # Consume the unresolved path if it was in static mapping or
                # leave it for further resolution when passing to Pages.
                del req.unresolved_path[0]
        elif req.param('action'):
            if req.param('_manage_cms_panels') == '1':
                modname = 'Panels'
            else:
                modname = 'Pages'
        else:
            try:
                return super(Application, self).handle(req)
            except wiking.Forbidden:
                # The parent method raises Forbidden when there are no menu items to redirect to.
                if req.check_roles(Roles.CONTENT_ADMIN):
                    # Give the administrator some hints on a fresh install.
                    if wiking.module('Pages').empty(req):
                        raise wiking.Abort(_("Welcome to Wiking CMS"),
                                           lcg.Container((lcg.p("There are currently no pages."),
                                                          lcg.p(lcg.link("/?action=insert",
                                                                         _("Create a new page"))))))
                    elif not self.preview_mode(req):
                        req.message(_("There are no published pages. "
                                      "You need to switch to the Preview mode "
                                      "to be able to access the unpublished pages."),
                                    type=req.WARNING)
                raise
        return req.forward(wiking.module(modname))

    def module_uri(self, req, modname):
        """Return the base URI of given Wiking module (relative to server root).

        This method implements the interface defined by
        'wiking.Application.module_uri()' specifically for the Wiking CMS
        application.


        The method bahaves as follows:

          1. Static mapping as defined by the parent class (see
             'wiking.application._MAPPING') is searched first.  If the module
             is found there, the corresponding path is returned.
          2. If the above fails, the module is searched within CMS pages as
             their extension module.  If the module is found as an extension
             module of a particular page, the path to that page (including the
             subpath to the module) is returned.  Beware that if the same
             module had been used as an extension module for more than one
             page, there would be no way to distinguish which page to use to
             form the path and thus None is returned in such cases.
          3. If the above fails and the module is derived from
             'CMSExtensionModule', its parent module is searched according to
             2. and if found, the corresponding path plus the path to the
             submodule is returned.
          4. If the above fails and the module is accessible through the Wikimg
             Management Interface, the WMI uri is returned.
          5. If all the above fails, None is returned.  Particularly, this
             happens for modules, which are not directly associated with any
             page, which may also be the case for modules accessible through
             bindings to other modules.

         The mapping used in step 1. is called static, because it is a
         hardcoded assignment of URIs of modules needed for Wiking CMS to run
         (such as 'Documentation', 'Resources', etc).  The user is not able to
         change this mapping.  The convention is, that URIs in the static
         mapping in Wiking CMS start with an underscore to prevent conflicts
         with user defined URIs (identifiers) of CMS pages (which are dynamic
         from this perspective — the user may change them).

         Examples (calling through 'wiking.Request.module_uri()'):

           req.module_uri('Documentation')

         Returns '/_doc'.

           req.module_uri('Planner')

         Returns '/_wmi/Planner' in WMI or '/planner' outside WMI if the module
         'Planner' is used in a page with an identifier 'planner' or None if
         the module 'Planner' is not used in any CMS page or if it is used more
         than once.  The identifier, of course, may be any string the user
         decides to use, not just 'planner'.

           req.module_uri('BugComments')

         Returns '/_wmi/BugComments' in WMI or '/bts/bug-comments' outside WMI
         if the module 'WikingBTS' is used in a page with an identifier 'bts'
         ('BugComments' is a submodule of 'WikingBTS' with a static subpath
         'bug-comments').

        """
        # Try the static mapping first.
        uri = super(Application, self).module_uri(req, modname)
        if uri is None:
            # Try if the module is directly embedded in a page.
            uri = wiking.module('Pages').module_uri(req, modname)
            if uri is None:
                # If not embeded directly, try if it is a submodule of an embedded module.
                mod = wiking.module(modname)
                if isinstance(mod, CMSExtensionModule):
                    parent = mod.parent()
                    if parent is None:
                        # Hack: Instantiate all CMSExtension modules to get
                        # the parent, as parentship is initialized on
                        # CMSExtension module for all its child
                        # CMSExtensionModule submodules.
                        for modname_, modcls in wiking.cfg.resolver.walk(CMSExtension):
                            wiking.module(modname_)
                        parent = mod.parent() # It's hopefully not None now...
                    if parent is not None:
                        uri = parent.submodule_uri(req, modname)
                if uri is None:
                    uri = wiking.module('WikingManagementInterface').module_uri(req, modname)
        return uri

    def site_title(self, req):
        if req.wmi:
            return _("Wiking Management Interface")
        else:
            return wiking.cfg.site_title

    def site_subtitle(self, req):
        if req.wmi:
            return None
        else:
            return wiking.cfg.site_subtitle

    def menu(self, req):
        modname = req.wmi and 'WikingManagementInterface' or 'Pages'
        return wiking.module(modname).menu(req)

    def panels(self, req, lang):
        if wiking.cms.cfg.allow_login_panel:
            panels = [wiking.LoginPanel()]
        else:
            panels = []
        return panels + wiking.module('Panels').panels(req, lang)

    def languages(self):
        return wiking.module('Languages').languages()

    def stylesheets(self, req):
        return wiking.module('StyleSheets').stylesheets(req)

    def _auth_user(self, req, login):
        user = wiking.module('Users').user(req, login)
        if user is None and wiking.cms.cfg.allow_registration:
            # It is possible, that the user doesn't exist in the
            # application specific users table, but exists in the base
            # table of wiking CMS (the user was registered for some other
            # application sharing the same database).  Here we test if
            # that's the case and handle the situation in the _auth_hook()
            # below.
            user = wiking.module('wiking.cms.Users').user(req, login)
            if user and user.state() == Users.AccountState.NEW:
                user = None
        return user

    def _auth_hook(self, req, user):
        if not wiking.module('Users').user(req, user.login()):
            # See _auth_user() for comments.
            regcode = wiking.module('wiking.cms.Users').regenerate_registration_code(user)
            raise wiking.Redirect(self.module_uri(req, 'Registration'),
                                  action='reinsert', login=user.login(), regcode=regcode)

    def _auth_check_password(self, user, password):
        record = user.data()
        password_storage = wiking.cms.cfg.password_storage
        if password_storage == 'plain':
            pass
        elif password_storage == 'md5':
            if isinstance(password, unicode):
                password = password.encode('utf-8')
            try:
                from hashlib import md5
            except ImportError:
                from md5 import md5
            password = md5(password).hexdigest()
        else:
            raise Exception("Invalid password storage option", password_storage)
        return password == record['password'].value()

    def _logout_hook(self, req, user):
        super(Application, self)._logout_hook(req, user)
        if user is None:
            return
        wiking.module('CryptoKeys').clear_crypto_passwords(req, user)

    def contained_roles(self, req, role):
        role_sets = wiking.module('RoleSets')
        if isinstance(role, (list, tuple, set,)): # role is actually role ids
            role_ids = role_sets.included_role_ids_by_role_ids(role, instances=True)
        else:
            role_ids = role_sets.included_role_ids(role, instances=True)
        return role_ids

    def registration_uri(self, req):
        if wiking.cms.cfg.allow_registration:
            return req.make_uri(req.module_uri('Registration'), action='insert')
        return None

    def password_reminder_uri(self, req):
        return req.make_uri(req.module_uri('Registration'), action='remind')

    def login_panel_content(self, req):
        content = []
        if req.check_roles(Roles.CONTENT_ADMIN) or req.__dict__.get('page_write_access'):
            content.append(self.PreviewModeCtrl())
        if wiking.module('WikingManagementInterface').authorized(req):
            content.append(self.WMILink())
        return content or None

    def login_is_email(self, req):
        return wiking.cms.cfg.login_is_email

    def right_panels_bottom_content(self, req):
        if req.check_roles(Roles.CONTENT_ADMIN):
            def content(renderer, context):
                g = context.generator()
                return g.form((g.submit(_("New Panel")),
                               g.hidden('action', 'insert'),
                               g.hidden('_manage_cms_panels', '1')),
                              action='/', method='GET')
            return wiking.HtmlRenderer(content)
        else:
            return None

    def bottom_bar_left_content(self, req):
        result = self._powered_by_wiking(req)
        if not wiking.cms.cfg.allow_login_panel:
            link = self._accessibility_statement_link(req)
            if link:
                result = (result, ' | ', link)
        return result

    def bottom_bar_right_content(self, req):
        if wiking.cms.cfg.allow_login_panel:
            return self._accessibility_statement_link(req)
        elif req.user() is None:
            return self.WMILink()
        elif wiking.module('WikingManagementInterface').authorized(req):
            return (wiking.LoginCtrl(inline=True), ' ', self.WMILink())
        else:
            return wiking.LoginCtrl(inline=True)

    def _text_content(self, req, text):
        texts = wiking.module('Texts')
        # Default to English to avoid raising NotAcceptable where it is not handled.
        lang = req.preferred_language(raise_error=False) or 'en'
        return texts.text(req, text, lang=lang)

    def top_content(self, req):
        return text2content(req, self._text_content(req, wiking.cms.texts.top))

    def footer_content(self, req):
        text = self._text_content(req, wiking.cms.texts.footer)
        return text2content(req, text.replace('$webmaster_address', wiking.cfg.webmaster_address))
