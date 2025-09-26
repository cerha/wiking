# -*- coding: utf-8 -*-
#
# Copyright (C) 2009-2016 OUI Technology Ltd.
# Copyright (C) 2019 Tomáš Cerha <t.cerha@gmail.com>
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

import lcg
from wiking.cms import Text
from pytis.presentation import TextFormat

_ = lcg.TranslatableTextFactory('wiking-cms')

top = Text(
    'cms.top',
    _("Text displayed at the very top of every page next to the site title"),
    '')

disabled = Text(
    'cms.disabled',
    # Translators: Web form label (account in the meaning of user account)
    _("Information about a locked account"),
    # Translators: Text presented to a user in a web page
    _("Your account is disabled. Protected services are not available. "
      "Contact the administrators to get the account enabled."),
    text_format=TextFormat.PLAIN)

unconfirmed = Text(
    'cms.unconfirmed',
    # Translators: Web form label
    _("Information about an account waiting for activation code confirmation"),
    # Translators: Text presented to a user in a web page
    _("Your account has not been activated yet.  Please, check your e-mail and follow "
      "the provided link or enter the activation code into the [%(uri)s activation "
      "form].  Protected services will not be available until you perform "
      "activation."),
    text_format=TextFormat.PLAIN)

unapproved = Text(
    'cms.unapproved',
    # Translators: Web form label
    _("Information about an account waiting for admin approval"),
    # Translators: Text presented to a user in a web page
    _("Your account is waiting for approval by the administrator. "
      "The protected services are not available until the account gets "
      "approved. Contact the administrators if you feel it takes too long."),
    text_format=TextFormat.PLAIN)

regintro = Text(
    'cms.regintro',
    _("Introductory text displayed above the registration form"),
    None)

regsuccess = Text(
    'cms.regsuccess',
    _("Text displayed after successful user registration"),
    _("Your account now awaits administrator's approval."))

regsuccess_autoapproved = Text(
    'cms.regsuccess_autoapproved',
    _("Text displayed after successful user registration when autoapprove_new_users is set "
      "in configuration"),
    _("Your account is now fully functional. You can [%s log in] now.\n\n"
      "You may still need some further privileges to access certain restricted services.",
      '?command=login'))

regconfirm = Text(
    'cms.regconfirm',
    _("Information displayed above the checkbox for confirmation of site specific "
      "conditions during registration and in profile edit form (if empty, no confirmation "
      "is required)"),
    None)

personal_data_management = Text(
    'cms.personal_data_management',
    _("Information about personal data management (displayed in the registration "
      "form and user profile)."),
    _("Personal data which you are submitting in this form and which arise from your "
      "usage of this application are processed by its operator >>insert name and contact<< "
      "who also shares them for specifically delimited purposes with >>insert<<. "
      "You have a possibility to adjust your personal data at any time as well as "
      "to cancel your account and have your data deleted.  See >>insert link<< for "
      "more details."))

registration_note_descr = Text(
    'cms.registration_note_descr',
    _("Description of the field \"Note\" in the registration form (server reload required "
      "on change)."),
    _("Optional message for the administrator. If you wish to communicate something "
      "to the administrator processing your registration, you can do so here. This "
      "is not normally necessary."),
    text_format=TextFormat.PLAIN)

footer = Text(
    'cms.footer',
    _("Text displayed at the very bottom of every page"),
    # Translators: Label followed by an email address link.
    _("Contact:") + ' $webmaster_address')

default_copyright_notice = Text(
    'cms.default_copyright_notice',
    _("Default value of the Copyright Notice field for newly created publications."),
    None)

login_dialog_top_text = Text(
    'cms.login_dialog_top_text',
    _("Text displayed above the login dialog"),
    None)

login_dialog_bottom_text = Text(
    'cms.login_dialog_bottom_text',
    _("Text displayed below the login dialog"),
    None)
