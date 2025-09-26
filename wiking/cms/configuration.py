# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2016 OUI Technology Ltd.
# Copyright (C) 2019-2021 Tomáš Cerha <t.cerha@gmail.com>
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

"""Wiking CMS configuration.

This configuration class defines the options specific for Wiking Content
Management System.

"""

import lcg
import wiking

from wiking import ApplicationConfiguration as cfg

_ = lcg.TranslatableTextFactory('wiking-cms')


class CMSConfiguration(cfg):
    """CMS Specific Configuration."""

    class _Option_always_show_admin_control(cfg.BooleanOption):
        # Translators: Yes/No configuration option label.  Should site
        # administration menu be always displayed?
        _DESCR = _("Always show admin control")
        _DOC = ("The site administration menu is normally only displayed "
                "to logged-in users with administration privileges.  When "
                "set to true, the menu (the gear icon at the top right "
                "corner of the page) will be displayed also to anonymous "
                "users (authorization will be requested after invocation "
                "of any administrative action).  This may be particilarly "
                "useful in combination with option 'Show login control' "
                "set to false.")
        _DEFAULT = False

    class _Option_allow_registration(cfg.BooleanOption):
        # Translators: Yes/no configuration label. Can new users register to this
        # website/application?
        _DESCR = _("Allow new user registration")
        # Mention dependence on autoapprove_new_users
        _DOC = _("If enabled, all visitors are allowed to create a new user account.  If disabled, "
                 "new user accounts must be created by administrator.")
        _DEFAULT = True

    class _Option_upload_limit(cfg.NumericOption):
        # Translators: Maximal size an uploaded file can have.
        _DESCR = _("Maximal upload size")
        _DOC = _("The maximal size of uploaded files in bytes.  The server "
                 "needs to be reloaded for the changes in this option to take effect.")
        _DEFAULT = 3 * 1024 * 1024

    class _Option_password_storage(cfg.StringOption):
        _DESCR = "Subclass of  for storing user passwords in the database"
        _DOC = ("This option defines in which way user passwords are stored in a database. "
                "The value is an instance of 'wiking.PasswordStorage' subclass.")
        _DEFAULT = wiking.UniversalPasswordStorage()

        def value(self):
            # Temporary hack: Automatically upgrade the legacy values 'plain' and 'md5'
            # to the new UniversalPasswordStorage instance.  This instance is compatible
            # with existing passwords when upgrade.72.sql was applied.
            value = super(CMSConfiguration._Option_password_storage, self).value()
            if value in ('plain', 'md5'):
                from pytis.util import OPERATIONAL, log
                log(OPERATIONAL,
                    ("Value '%s' of configuration option 'password_storage' is not valid anymore. "
                     "Using 'wiking.UniversalPasswordStorage() instead.") % value)
                value = wiking.UniversalPasswordStorage()
            return value

    class _Option_password_strength(cfg.Option):
        _DESCR = "Specification of password strength checking."
        _DOC = ("If 'None', no special checks are performed.  If 'True', default "
                "checking is performed (both characters and non-characters "
                "must be used).  If anything else, it must be a function of "
                "a single argument, the password string, that returns either "
                "'None' when the password is strong enough or an error message "
                "if the password is weak.")
        _DEFAULT = None

    class _Option_password_min_length(cfg.NumericOption):
        _DESCR = "Minimal password length"
        _DOC = "The minimal length of a Wiking CMS user password."
        _DEFAULT = 4

    class _Option_login_is_email(cfg.BooleanOption):
        _DESCR = _("Whether to use e-mails as login names")
        _DOC = _("Iff true, users must use e-mail addresses as their login names.")
        _DEFAULT = False

    class _Option_registration_expiry_days(cfg.NumericOption):
        _DESCR = "Number of days after which an unanswered user registration expires"
        _DOC = ("When registration by e-mail is enabled, each newly registered user is required "
                "to answer the registration e-mail within the limit given here.")
        _DEFAULT = 2

    class _Option_reset_password_expiry_minutes(cfg.NumericOption):
        _DESCR = "Number of minutes after which an unanswered password reset request expires"
        _DOC = ("Forgotten password can be reset using an e-mail loop. The user is required "
                "to follow the link in e-mail within the limit given here.  Extending this "
                "limit gives more space to attackers, so you should rarely set it to more "
                "than the default (15 minutes).")
        _DEFAULT = 15

    class _Option_autoapprove_new_users(cfg.StringOption):
        # Change in this option requires server restart to take full effect (the
        # default value of system text 'cms.regsucess' depends on it and system
        # texts are global variables).
        _DESCR = "Approve new users automatically"
        _DOC = _("If set, the newly registered users will be automatically approved without any "
                 "administrator's action.  The administrator may still need to assign users to "
                 "groups to grant them further privileges, but the accounts are enabled right "
                 "after the user confirms the registration code.")
        _DEFAULT = False

    class _Option_storage(cfg.StringOption):
        _DESCR = "Directory for storing uploaded files"
        _DOC = ("The directory must be writable by the web-server user.")
        _DEFAULT = '/var/lib/wiking'

    class _Option_sql_dir(cfg.StringOption):
        _DESCR = "SQL directory"
        _DOC = ("The directory where Wiking CMS database initialization/upgrade scripts "
                "can be found.")
        _DEFAULT = '/usr/local/share/wiking/sql'

    class _Option_image_thumbnail_sizes(cfg.Option):
        _DESCR = "Sequence available image thumbnail sizes"
        _DOC = ("Sequence of three integers denoting the pixel size of small, "
                "medium and large image thumbnail.  The images are resized so "
                "that their longer side is at most given size (the short side "
                "is smaller to maintain the image proportion).")
        _DEFAULT = (120, 180, 240)

    class _Option_image_screen_size(cfg.Option):
        _DESCR = "Enlarged image screen size"
        _DOC = ("Pair of integers (width, height) in pixels denoting the maximal size "
                "of an image when displayed on screen (after clicking the thumbnail). "
                "This "
                "size is usually smaller than the original image size (which "
                "may be larger than the screen size).  If the original is smaller")
        _DEFAULT = (1024, 1024)

    class _Option_content_editor(cfg.StringOption):
        _DESCR = "CMS text editor to be used"
        _DOC = ("The currently supported options are 'plain' for plain text editor "
                "using the LCG Structured Text formatting and 'html' for a JavaScript "
                "based HTML editor (currently CKEditor from http://ckeditor.com is "
                "used).  Note, that it is currently not possible to change this option "
                "for an existing database and there is no support for conversion.  You "
                "must decide before site creation.")
        _DEFAULT = 'plain'

    class _Option_registration_fields(cfg.Option):
        _DESCR = "Optional fields displayed in the registration form."
        _DOC = ("The form includes only the mandatory fields by default.  The optional "
                "fields may be added to the form by including their identifiers in this "
                "sequence.  The identifiers of the available optional fields are: "
                "'nickname', 'gender', 'phone', 'address', 'uri' and 'note'")
        _DEFAULT = ()

    class _Option_formatting_manual_uri(cfg.Option):
        _DESCR = "Formatting manual URI."
        _DOC = ("Content field descriptions contain a link to the formatting manual. "
                "The default manual is the LCG's Structured Text Formatting Manual, "
                "but some sites may want to link to a different manual which also "
                "contains other information such as site specific conventions and "
                "best practices.  Note, that the manual link is only present when "
                "'content_editor' is set to 'plain'.  Set to None to suppress the "
                "link altogether.")
        _DEFAULT = '/_doc/lcg/structured-text'
