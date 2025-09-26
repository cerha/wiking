# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2018 OUI Technology Ltd.
# Copyright (C) 2019-2020 Tomáš Cerha <t.cerha@gmail.com>
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

"""Wiking Content Management System application definition.

The CMS application is defined as an implementation of Wiking Application Interface.

"""
import lcg
import wiking
from wiking.cms import CMSExtension, CMSExtensionModule, Roles, Users, text2content

_ = lcg.TranslatableTextFactory('wiking-cms')


class AdminControl(wiking.TopBarControl):

    def _icon(self, context):
        if wiking.module.Application.preview_mode(context.req()):
            return 'gear-larger-red'
        else:
            return 'gear-larger'

    def _menu_title(self, context):
        if wiking.module.WikingManagementInterface.authorized(context.req()):
            return _("Website Administration")
        else:
            return _("Content Management")

    def _menu_items(self, context):
        req = context.req()
        items = []
        if wiking.module.WikingManagementInterface.authorized(req):
            if not req.wmi:
                items.append(lcg.PopupMenuItem(_("Enter the Management Interface"), uri='/_wmi/',
                                               icon='gear-icon'))
            else:
                items.append(lcg.PopupMenuItem(_("Leave the Management Interface"), uri='/',
                                               icon='circle-out-icon'))
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
                label, value = _("Switch to Production Mode"), '0'
            else:
                label, value = _("Switch to Preview Mode"), '1'
            param = wiking.module.Application._PREVIEW_MODE_PARAM
            items.append(lcg.PopupMenuItem(label, uri='%s?%s=%s' % (req.uri(), param, value),
                                           icon='refresh-icon'))
        if not req.wmi:
            if hasattr(req, 'page_write_access') and req.page_write_access:
                items.append(lcg.PopupMenuItem(_("Edit the Current Page"),
                                               uri=req.uri() + '?action=update',
                                               icon='edit-icon'))
            if req.check_roles(wiking.cms.Roles.CONTENT_ADMIN):
                items.append(lcg.PopupMenuItem(_("Create a New Page"), uri='/?action=insert',
                                               icon='create-icon'))
        if not items and wiking.cms.cfg.always_show_admin_control:
            items.append(lcg.PopupMenuItem(_("Log in for site administration"),
                                           uri='/?command=login', icon='circle-in-icon'))
        return items


class Application(wiking.Application):

    _MAPPING = dict(
        wiking.Application._MAPPING,
        _wmi='WikingManagementInterface',
        _registration='Registration',
        _sitemap='SiteMap',
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

    def _resolve_modname(self, req):
        """Return the wiking module name to handle this request.

        Determine the name of the module responsible for handling this request.
        The module is most typically determined from the request path and/or
        request parameters.  The relavant part of 'req.unresolved_path' must be
        consumed.

        This method may be overriden in derived classes.

        """
        if req.unresolved_path:
            try:
                modname = self._mapping[req.unresolved_path[0]]
            except KeyError:
                return 'Pages'
            # Consume the unresolved path if it was in static mapping or
            # leave it for further resolution when passing to Pages.
            del req.unresolved_path[0]
            return modname
        elif req.param('action'):
            if req.param('_manage_cms_panels') == '1':
                return 'Panels'
            else:
                return 'Pages'
        else:
            return None

    def handle(self, req):
        req.wmi = False  # Will be set to True by `WikingManagementInterface' if needed.
        preview_mode_param = req.param(self._PREVIEW_MODE_PARAM)
        if preview_mode_param is not None:
            req.set_cookie(self._PREVIEW_MODE_COOKIE, preview_mode_param == '1' and '1' or None)
        wiking.module.CachedTables.reload_info(req)
        wiking.module.Config.configure(req)
        modname = self._resolve_modname(req)
        if modname:
            return req.forward(wiking.module(modname))
        else:
            try:
                return super(Application, self).handle(req)
            except wiking.Forbidden:
                # The parent method raises Forbidden when there are no menu items to redirect to.
                if req.check_roles(Roles.CONTENT_ADMIN):
                    # Give the administrator some hints on a fresh install.
                    if wiking.module.Pages.empty(req):
                        return wiking.Document(
                            title=_("Welcome to Wiking CMS"),
                            content=lcg.Container((lcg.p("There are currently no pages."),
                                                   lcg.p(lcg.link("/?action=insert",
                                                                  _("Create a new page"))))),
                        )
                    elif not self.preview_mode(req):
                        req.message(_("There are no published pages. "
                                      "You need to switch to the Preview mode "
                                      "to be able to access the unpublished pages."),
                                    req.WARNING)
                raise

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
                        parent = mod.parent()  # It's hopefully not None now...
                    if parent is not None:
                        uri = parent.submodule_uri(req, modname)
                if uri is None:
                    uri = wiking.module.WikingManagementInterface.module_uri(req, modname)
        return uri

    def site_subtitle(self, req):
        if req.wmi:
            return _("Management Interface")
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

    def body_class_names(self, req):
        if self.preview_mode(req):
            return ('preview-mode',)
        else:
            return ('production-mode',)

    def authenticate(self, req, login, password, auth_type):
        user = wiking.module.Users.user(req, login)
        if user is None and wiking.cms.cfg.allow_registration:
            # It is possible, that the user doesn't exist in the
            # application specific users table, but exists in the base
            # table of wiking CMS (the user was registered for some other
            # application sharing the same database).  Here we test if
            # that's the case and handle the situation in the login_hook()
            # below.
            u = wiking.module('wiking.cms.Users').user(req, login)
            if u and u.state() != Users.AccountState.NEW:
                user = u
        if user:
            stored_password = user.data()['password'].value()
            if wiking.cms.cfg.password_storage.check_password(password, stored_password):
                return user
        wiking.module.LoginFailures.failure(req, login, auth_type)
        return None

    def login_hook(self, req, user):
        import wiking.cms.texts
        if not wiking.module.Users.user(req, user.login()):
            # This account needs re-registration.  See 'user()' for comments.
            regcode = wiking.module('wiking.cms.Users').regenerate_registration_code(user)
            req.message(_("User %s is already registered for another site. "
                          "Please, confirm the account for this site.", user.login()))
            raise wiking.Redirect(req.module_uri('Registration'),
                                  action='reinsert', login=user.login(), regcode=regcode)
        # This is done in the login hook to display the message only once after logging in...
        state = user.state()
        text = wiking.module.Texts.text
        if state == Users.AccountState.DISABLED:
            message = text(wiking.cms.texts.disabled)
        elif state == Users.AccountState.NEW:
            uri = req.make_uri(req.module_uri('Registration'), action='confirm', uid=user.uid())
            message = text(wiking.cms.texts.unconfirmed).interpolate(lambda x: dict(uri=uri)[x])
        elif state == Users.AccountState.UNAPPROVED:
            message = text(wiking.cms.texts.unapproved)
        else:
            return
        req.message(message, req.WARNING, formatted=True)

    def logout_hook(self, req, user):
        super(Application, self).logout_hook(req, user)
        if user is not None:
            wiking.module.CryptoKeys.clear_crypto_passwords(req, user)

    def contained_roles(self, role):
        role_sets = wiking.module.RoleSets
        if isinstance(role, (list, tuple, set)):  # role is actually role ids
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
            def content(context, element):
                g = context.generator()
                return g.form((g.button(g.span('', cls='icon plus-icon') +
                                        g.span(_("New Panel"), cls='label'), type='submit'),
                               g.hidden('action', 'insert'),
                               g.hidden('_manage_cms_panels', '1')),
                              action='/', method='GET')
            return lcg.HtmlContent(content)
        else:
            return None

    def _text_content(self, req, text):
        # Default to English to avoid raising NotAcceptable where it is not handled.
        lang = req.preferred_language(raise_error=False) or 'en'
        return wiking.module.Texts.localized_text(req, text, lang=lang)

    def top_content(self, req):
        content = super(Application, self).top_content(req)
        top_text = self._text_content(req, wiking.cms.texts.top)
        if top_text:
            content.append(lcg.Container(text2content(req, top_text), name='top-text'))
        return content

    def top_controls(self, req):
        return [
            wiking.LoginControl(),
            AdminControl(),
            wiking.LanguageSelection(),
            wiking.MaximizedModeControl(),
        ]

    def bottom_bar_left_content(self, req):
        return lcg.Link('/_sitemap', wiking.module.SiteMap.title())

    def footer_content(self, req):
        text = self._text_content(req, wiking.cms.texts.footer)
        return text2content(req, text.replace('$webmaster_address', wiking.cfg.webmaster_address))

    def login_dialog_top_content(self, req):
        return text2content(req, self._text_content(req, wiking.cms.texts.login_dialog_top_text))

    def login_dialog_bottom_content(self, req):
        return text2content(req, self._text_content(req, wiking.cms.texts.login_dialog_bottom_text))
