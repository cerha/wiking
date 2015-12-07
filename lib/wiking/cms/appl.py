# -*- coding: utf-8 -*-
# Copyright (C) 2006-2015 Brailcom, o.p.s.
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

class AdminControl(wiking.TopBarControl):

    def _icon(self, context):
        if wiking.module.Application.preview_mode(context.req()):
            return 'gear-larger-red'
        else:
            return 'gear-larger'

    def _menu_title(self, context):
        return _("Website Administration")

    def _menu_items(self, context):
        req = context.req()
        items = []
        if wiking.module.WikingManagementInterface.authorized(req):
            if not req.wmi:
                items.append(lcg.PopupMenuItem(_("Enter the Management Interface"), uri='/_wmi/',
                                               cls='wmi'))
            else:
                items.append(lcg.PopupMenuItem(_("Leave the Management Interface"), uri='/',
                                               cls='leave-wmi'))
        if wiking.module.Application.preview_mode_possible(req):
            # Translators: There are two modes of operation in the CMS
            # management.  The "Production Mode" displays only the content
            # publically visible to the website visitors.  "Preview Mode",
            # on the other hand, displays also the content which is not
            # published yet.  This content is only visible to the
            # administrators until it is published.  Please make sure you
            # translate these two modes consistently acros all their
            # occurences.
            if wiking.module.Application.preview_mode(req):
                label, value, cls = _("Switch to Production Mode"), '0', 'production-mode'
            else:
                label, value, cls = _("Switch to Preview Mode"), '1', 'preview-mode'
            param = wiking.module.Application._PREVIEW_MODE_PARAM
            items.append(lcg.PopupMenuItem(label, uri='%s?%s=%s' % (req.uri(), param, value),
                                           cls='switch-mode ' + cls))
        if not req.wmi:
            if hasattr(req, 'page_write_access') and req.page_write_access:
                items.append(lcg.PopupMenuItem(_("Edit the Current Page"),
                                               uri=req.uri() + '?action=update', cls='edit-page'))
            if req.check_roles(wiking.cms.Roles.CONTENT_ADMIN):
                items.append(lcg.PopupMenuItem(_("Create a New Page"), uri='/?action=insert',
                                               cls='new-page'))
        return items


class Application(CookieAuthentication, wiking.Application):

    _MAPPING = dict(
        wiking.Application._MAPPING,
        _wmi='WikingManagementInterface',
        _registration='Registration',
    )

    _PREVIEW_MODE_COOKIE = 'wiking_cms_preview_mode'
    _PREVIEW_MODE_PARAM = '_wiking_cms_preview_mode'

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
        if self.preview_mode_possible(req):
            return req.cookie(self._PREVIEW_MODE_COOKIE) == '1'
        else:
            return False

    def preview_mode_possible(self, req):
        """Return true if the current user is allowed to switch to the preview mode.

        Doesn't depend on the current mode, just indicates the possibility.

        """
        return req.check_roles(Roles.CONTENT_ADMIN) or req.__dict__.get('page_write_access', False)

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
            req.message(message, req.WARNING)
            req.set_cookie(self._PREVIEW_MODE_COOKIE, value and '1' or '0')

    def handle(self, req):
        req.wmi = False # Will be set to True by `WikingManagementInterface' if needed.
        preview_mode_param = req.param(self._PREVIEW_MODE_PARAM)
        if preview_mode_param is not None:
            req.set_cookie(self._PREVIEW_MODE_COOKIE, preview_mode_param == '1' and '1' or None)
        wiking.module.CachedTables.reload_info(req)
        wiking.module.Config.configure(req)
        if req.unresolved_path:
            try:
                modname = self._mapping[req.unresolved_path[0]]
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
                    if wiking.module.Pages.empty(req):
                        raise wiking.Abort(_("Welcome to Wiking CMS"),
                                           lcg.Container((lcg.p("There are currently no pages."),
                                                          lcg.p(lcg.link("/?action=insert",
                                                                         _("Create a new page"))))))
                    elif not self.preview_mode(req):
                        req.message(_("There are no published pages. "
                                      "You need to switch to the Preview mode "
                                      "to be able to access the unpublished pages."),
                                    req.WARNING)
                raise
        return req.forward(wiking.module(modname))

    def module_uri(self, req, modname):
        """Return the base URI of given Wiking module (relative to server root).

        This method implements the interface defined by
        'wiking.Application.module_uri()' specifically for the Wiking CMS
        application.


        The method bahaves as follows:

          1. Static URI mapping (see 'wiking.Application._MAPPING') is searched
             first.  If the module is found there, the corresponding path is
             returned.
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

           req.module_uri('Users')

         Returns '/users' if the module 'Users' is used in a CMS page with an
         identifier 'users'.  If the module is not used in any CMS page
         '/_wmi/users/Users' is returned.

           req.module_uri('Planner')

         Returns '/events' if the module 'Planner' is used in a CMS page with an
         identifier 'events' or None if it is not used.

           req.module_uri('BugComments')

         Returns '/bts/bug-comments' if the CMS extension module
         'BugTrackingSystem' is used in a page with an identifier 'bts' and
         'BugComments' is a submodule of 'BugTrackingSystem' with a static
         subpath 'bug-comments').

        """
        # Try the static mapping first.
        uri = super(Application, self).module_uri(req, modname)
        if uri is None:
            # Try if the module is directly embedded in a page.
            uri = wiking.module.Pages.module_uri(req, modname)
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
                    uri = wiking.module.WikingManagementInterface.module_uri(req, modname)
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
        return wiking.module.Panels.panels(req, lang)

    def languages(self):
        return wiking.module.Languages.languages()

    def stylesheets(self, req):
        return wiking.module.StyleSheets.stylesheets(req)

    def _auth_user(self, req, login):
        user = wiking.module.Users.user(req, login)
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
        if not wiking.module.Users.user(req, user.login()):
            # See _auth_user() for comments.
            regcode = wiking.module('wiking.cms.Users').regenerate_registration_code(user)
            req.message(_("User %s is already registered for another site. "
                          "Please, confirm the account for this site.", user.login()))
            raise wiking.Redirect(req.module_uri('Registration'),
                                  action='reinsert', login=user.login(), regcode=regcode)

    def _auth_check_password(self, user, password):
        storage = wiking.cms.cfg.password_storage
        return storage.check_password(password, user.data()['password'].value())

    def _logout_hook(self, req, user):
        super(Application, self)._logout_hook(req, user)
        if user is None:
            return
        wiking.module.CryptoKeys.clear_crypto_passwords(req, user)

    def contained_roles(self, role):
        role_sets = wiking.module.RoleSets
        if isinstance(role, (list, tuple, set,)): # role is actually role ids
            role_ids = role_sets.included_role_ids_by_role_ids(role, instances=True)
        else:
            role_ids = role_sets.included_role_ids(role, instances=True)
        return role_ids

    def registration_uri(self, req):
        if wiking.cms.cfg.allow_registration:
            return req.make_uri(req.module_uri('Registration'), action='insert')
        return None

    def password_change_uri(self, req):
        return req.make_uri(req.module_uri('Registration'), action='passwd')

    def forgotten_password_uri(self, req):
        return req.make_uri(req.module_uri('Registration'), action='reset_password')

    def login_is_email(self, req):
        return wiking.cms.cfg.login_is_email

    def right_panels_bottom_content(self, req):
        if req.check_roles(Roles.CONTENT_ADMIN):
            def content(renderer, context):
                g = context.generator()
                return g.form((g.button(g.span(_("New Panel")), type='submit'),
                               g.hidden('action', 'insert'),
                               g.hidden('_manage_cms_panels', '1')),
                              action='/', method='GET')
            return wiking.HtmlRenderer(content)
        else:
            return None

    def _text_content(self, req, text):
        # Default to English to avoid raising NotAcceptable where it is not handled.
        lang = req.preferred_language(raise_error=False) or 'en'
        return wiking.module.Texts.localized_text(req, text, lang=lang)

    def top_controls(self, req):
        controls = [wiking.LoginControl(), AdminControl(), wiking.LanguageSelection()]
        top_text = self._text_content(req, wiking.cms.texts.top)
        if top_text:
            def export_top_content(renderer, context, content):
                return context.generator().span(content.export(context), cls='top-content')
            controls.insert(0, wiking.HtmlRenderer(export_top_content, text2content(req, top_text)))
        return controls

    def footer_content(self, req):
        text = self._text_content(req, wiking.cms.texts.footer)
        return text2content(req, text.replace('$webmaster_address', wiking.cfg.webmaster_address))
