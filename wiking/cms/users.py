# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2017 OUI Technology Ltd.
# Copyright (C) 2019-2025 Tomáš Cerha <t.cerha@gmail.com>
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

"""Wiking CMS users and roles.

The most important class here is L{Users}.  It defines all the basic
functionality regarding user management in Wiking CMS and Wiking CMS based
applications.

Wiking CMS, unlike plain Wiking, can store role related data in a database.
There are several classes for manipulation with role database data:
L{RoleSets}, L{RoleMembers}, L{ApplicationRoles}.

"""

import datetime
import random
import socket
import string

import lcg
import pytis.data as pd
import pytis.presentation as pp
import pytis.web as pw
import pytis.util
import wiking
import wiking.dbdefs

from pytis.presentation import (
    Action, Binding, CodebookSpec, Enumeration, Field, FieldSet, computer,
)
from wiking import (
    Module, ActionHandler, PytisModule, CachingPytisModule, Document,
    Role, send_mail, log, OPR,
)
from wiking.cms import (
    EmbeddableCMSModule, UserManagementModule, Roles,
    now, ASC, DESC, NEVER, ONCE
)

_ = lcg.TranslatableTextFactory('wiking-cms')


class RoleSets(UserManagementModule, CachingPytisModule):
    """Accessor of role containment information stored in the database.

    Roles can contain other roles.  Those may be any L{Role} instances,
    including L{Role} subclasses.  Semantic interpretation of the contained
    roles is undefined here, it's completely up to the application.

    @invariant: There may be no cycles in role containment, i.e. no role may
      contain itself, including transitive relations.  For instance, group role
      I{foo} may not contain I{foo}; or if I{foo} contains I{bar} and I{bar}
      contains I{baz} then I{baz} may not contain I{foo} nor I{bar} nor I{baz}.

    """
    class Spec(wiking.Specification):
        table = 'role_sets'
        fields = (
            Field('role_set_id'),
            Field('role_id', _("Group"), not_null=True, codebook='ApplicationRoles',
                  selection_type=pp.SelectionType.CHOICE),
            Field('member_role_id', _("Gets rights of"), not_null=True, codebook='UserGroups',
                  selection_type=pp.SelectionType.CHOICE),
        )
        columns = layout = ('role_id', 'member_role_id')

    _TITLE_COLUMN = 'member_role_id'
    _INSERT_LABEL = _("Add rights of group")
    _DELETE_LABEL = _("Revoke")
    _DELETE_PROMPT = _("Please, confirm revoking group relationship.")
    _ROW_ACTIONS = True

    _roles_instance = None
    _cache_ids = ('containment', 'resolution',)
    _DEFAULT_CACHE_ID = 'containment'

    def _authorized(self, req, action, **kwargs):
        if action in ('view', 'update'):
            return False
        else:
            return super(RoleSets, self)._authorized(req, action, **kwargs)

    def _layout(self, req, action, record=None):
        return (self._TITLE_COLUMN,)

    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid is None:
            cid = self._TITLE_COLUMN
        return super(RoleSets, self)._link_provider(req, uri, record, cid, **kwargs)

    def _load_cache(self, transaction=None):
        super(RoleSets, self)._load_cache(transaction=transaction)
        cache = self._get_cache('containment')

        def add(row):
            role_id = row['role_id'].value()
            contained_role_id = row['member_role_id'].value()
            contained_roles = cache.get(role_id)
            if contained_roles is None:
                contained_roles = cache[role_id] = []
            contained_roles.append(contained_role_id)
        self._data.select_map(add, transaction=transaction)

    def related(self, req, binding, record, uri):
        content = super(RoleSets, self).related(req, binding, record, uri)
        if binding.id() == 'contained':
            info = _("Users of group '%s' automatically gain rights of the following groups:",
                     record['xname'].value())
        elif binding.id() == 'containing':
            info = _("Users of the following groups automatically get rights of group '%s':",
                     record['xname'].value())
        else:
            info = None
        return info and lcg.Container((lcg.p(info), content)) or content

    def _related_role_ids(self, role, what_to_add, instances=False):
        assert isinstance(role, wiking.Role), role
        return self._related_role_ids_by_role_ids([role.id()], what_to_add, instances=instances)

    def _related_role_ids_by_role_ids(self, init_role_ids, what_to_add, instances=False):
        self._check_cache(load=True)
        key = tuple(init_role_ids) + (what_to_add, instances,)
        resolution_cache = self._get_cache('resolution')
        result = resolution_cache.get(key)
        if result is not None:
            return result
        containment = self._get_cache('containment')
        if what_to_add == 'including':
            c = {}
            for r, role_list in containment.items():
                for rr in role_list:
                    c[rr] = [r]
            containment = c
        else:
            assert what_to_add == 'included', what_to_add
        role_ids = set()
        queue = set([r for r in init_role_ids])
        while queue:
            r_id = queue.pop()
            if r_id not in role_ids:
                role_ids.add(r_id)
                queue = queue.union(set(containment.get(r_id, [])))
        if instances:
            if self._roles_instance is None:
                self._roles_instance = wiking.module.Users.Roles()
            roles_instance = self._roles_instance
            result = [roles_instance[role_id] for role_id in role_ids]
        else:
            result = list(role_ids)
        resolution_cache[key] = result
        return result

    def included_role_ids(self, role, instances=False):
        """
        @type role: L{Role}
        @param role: Role whose contained roles should be returned.
        @type instances: boolean
        @param instances: Iff true then return L{Role} instances rather than
          role ids

        @rtype: sequence of strings
        @return: Sequence of role identifiers included in the given role,
          including the identifier of C{role} itself.

        """
        return self._related_role_ids(role, 'included', instances=instances)

    def included_role_ids_by_role_ids(self, role_ids, instances=False):
        """
        @type role_ids: sequence of strings
        @param role_ids: Ids of roles whose contained role ids should be returned.
        @type instances: boolean
        @param instances: Iff true then return L{Role} instances rather than
          role ids

        @rtype: sequence of strings
        @return: Sequence of role identifiers included in the given role,
          including C{role_ids} themselves.

        """
        return self._related_role_ids_by_role_ids(role_ids, 'included', instances=instances)

    def containing_role_ids(self, role):
        """
        @type role: L{Role}
        @param role: Role whose containing roles should be returned.

        @rtype: sequence of strings
        @return: Sequence of identifiers of roles containing the given role,
          including the identifier of C{role} itself.

        """
        return self._related_role_ids(role, 'including')


class ContainingRoles(RoleSets):
    """UI customization of the L{RoleSets} module for listing of containing roles.

    Containing roles are the opposite view of the L{RoleSets} relationship used
    in the role's bindings.  The modifications are actually implemented in the
    parent class and the attribute L{_TITLE_COLUMN} is used to control the
    final presentation (apart from its primary purpose).  See the
    implementation of parent class methods L{_layout()}, L{_link_provider()}
    and L{_form()}.

    """
    _TITLE_COLUMN = 'role_id'
    _INSERT_LABEL = _("Add rights to another group")


class RoleMembers(UserManagementModule):
    """Accessor of user role membership information stored in the database."""
    class Spec(wiking.Specification):
        title = _("User Roles")
        table = 'cms_v_role_members'

        def fields(self):
            return (
                Field('role_member_id'),
                Field('role_id', _("Group"), not_null=True, codebook='UserGroups',
                      selection_type=pp.SelectionType.CHOICE),
                Field('role_name'),
                Field('uid', _("User"), not_null=True, codebook='Users',
                      selection_type=pp.SelectionType.CHOICE,
                      inline_display='user_name', inline_referer='user_login'),
                Field('user_login'),
                Field('user_name'),
            )
        columns = layout = ('role_id', 'uid',)

    _TITLE_COLUMN = 'uid'
    _INSERT_LABEL = _("Add member")
    _DELETE_LABEL = _("Remove from group")
    _DELETE_PROMPT = _("Please, confirm removing the user from the group.")
    _ROW_ACTIONS = True

    def _authorized(self, req, action, **kwargs):
        if action in ('view', 'update'):
            return False
        else:
            return super(RoleMembers, self)._authorized(req, action, **kwargs)

    def _layout(self, req, action, record=None):
        return (self._TITLE_COLUMN,)

    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid is None:
            cid = self._TITLE_COLUMN
        return super(RoleMembers, self)._link_provider(req, uri, record, cid, **kwargs)

    def user_ids(self, role, strict=False):
        """
        @type role: L{Role}
        @param role: Role whose users should be returned.
        @type strict: boolean
        @param strict: If true then include only direct L{role} members, otherwise
          include users of all roles L{role} is member of.

        @rtype: sequence of integers
        @return: Sequence of identifiers of the users belonging to the given
          role

        """
        assert isinstance(role, wiking.Role), role
        assert isinstance(strict, bool), strict
        if strict:
            included_role_ids = (role.id(),)
        else:
            included_role_ids = wiking.module.RoleSets.containing_role_ids(role)
        condition = pd.OR(*[pd.EQ('role_id', pd.sval(m_id)) for m_id in included_role_ids])
        user_ids = []

        def add_user_id(row):
            uid = row['uid'].value()
            if uid not in user_ids:
                user_ids.append(uid)
        self._data.select_map(add_user_id, condition=condition)
        return user_ids

    def user_role_ids(self, uid):
        """
        @type uid: integer
        @param uid: User id of the user to get the roles for.

        @rtype: sequence of strings
        @return: Identifiers of all the roles explicitly assigned to the given user.
        """
        assert isinstance(uid, int)
        condition = pd.EQ('uid', pd.Value(pd.Integer(), uid))

        def role_id(row):
            return row['role_id'].value()
        return self._data.select_map(role_id, condition=condition)


class UserRoles(RoleMembers):
    """UI customization of the L{RoleMembers} module for listing of user's roles.

    User's roles are the opposite view of the L{RoleMembers} relationship used
    in the user's bindings.  The modifications are actually implemented in the
    parent class and the attribute L{_TITLE_COLUMN} is used to control the
    final presentation (apart from its primary purpose).  See the
    implementation of parent class methods L{_layout()}, L{_link_provider()}
    and L{_form()}.

    """
    _TITLE_COLUMN = 'role_id'
    _INSERT_LABEL = _("Add to group")


class ApplicationRoles(UserManagementModule, CachingPytisModule):
    """Accessor and editor of application roles.

    This class can read roles from and store them to the database.  Its main
    purpose is to handle user defined roles.

    """
    class Spec(wiking.Specification):
        table = 'roles'
        # Translators: Form heading.
        title = _("User Groups")

        def __init__(self, *args, **kwargs):
            super(ApplicationRoles.Spec, self).__init__(*args, **kwargs)
            self._roles = wiking.module.Users.Roles()

        def fields(self):
            return (
                # Translators: Form field label.
                Field('role_id', _("Identifier"), editable=computer(self._editable)),
                # Translators: Form field label, noun.
                Field('name', _("Name"), not_null=True, editable=computer(self._editable)),
                Field('xname', _("Name"), computer=computer(self._xname_computer), virtual=True),
                # Translators: Form field label, adjective related to a "User group" (use the
                # appropriate gender.
                Field('system', _("System"), default=False, editable=pp.Editable.NEVER),
                Field('auto', _("Automatic"), default=False, editable=pp.Editable.NEVER),
                Field('role_info', computer=computer(self._role_info), virtual=True),
            )

        def _editable(self, record, system):
            return not system

        def _xname_computer(self, record, role_id, name):
            return name or role_id and self._xname(role_id)  # 'role_id' is None in a new record.

        def _xname_display(self, row):
            return (row['name'].value() or
                    self._xname(row['role_id'].value()) or
                    row['role_id'].value())

        def _xname(self, role_id):
            try:
                role = self._roles[role_id]
            except KeyError:
                return None
            else:
                return role.name()

        def _role_info(self, record, role_id, system, auto):
            if auto:
                info = _("This is a special system group with no explicit "
                         "members. The system decides automatically which "
                         "users belong into the group. Thus you can not "
                         "manage their membership manually. You can, "
                         "however, still add rights of other groups to it.")
            elif system:
                info = _("This is a system group defined by one of the installed "
                         "applications. You cannot change or delete this group, "
                         "but you can manage membership of users and add rights of other groups "
                         "to it.")
            else:
                info = _("This is a user defined group. You can manage membership "
                         "of users and add rights of other groups to it as well as modify or "
                         "delete the group itself.")
            return info
        columns = ('xname', 'role_id', 'system')
        layout = ('role_id', 'name', 'system')

        def cb(self):
            return pp.CodebookSpec(display=self._xname_display, prefer_display=True)

        def bindings(self):
            return (wiking.Binding('contained', _("Gets Rights of Groups"), 'RoleSets',
                                   'role_id', form=pw.ItemizedView),
                    wiking.Binding('containing', _("Passes Rights to Groups"), 'ContainingRoles',
                                   'member_role_id', form=pw.ItemizedView,
                                   enabled=lambda r: not r['auto'].value()),
                    wiking.Binding('members', _("Members"), 'RoleMembers',
                                   'role_id', form=pw.ItemizedView,
                                   enabled=lambda r: not r['auto'].value()))
    _TITLE_COLUMN = 'xname'

    def _authorized(self, req, action, **kwargs):
        if action in ('view', 'list'):
            return req.check_roles(Roles.USER)
        else:
            return super(ApplicationRoles, self)._authorized(req, action, **kwargs)

    def _layout(self, req, action, **kwargs):
        if 'action' == 'view':
            return (('role_id', 'xname', 'system'),
                    lambda r: wiking.Message(r['role_info'].value()))
        else:
            return super(ApplicationRoles, self)._layout(req, action, **kwargs)

    def _update_enabled(self, req, record):
        return not record['system'].value()

    def _delete_enabled(self, req, record):
        return not record['system'].value()

    def _make_role(self, row):
        role_id = row['role_id'].value()
        name = row['name'].value()
        return Role(role_id, name)

    def user_defined_roles(self):
        """
        @rtype: sequence of L{Role}s
        @return: All user defined roles, i.e. roles defined by the application
          administrators and not the application code.
        """
        condition = pd.EQ('system', pd.Value(pd.Boolean(), False))
        return tuple(self._data.select_map(self._make_role, condition=condition))

    def _read_roles(self):
        roles = {}
        try:
            self._data.select()
            while True:
                row = self._data.fetchone()
                if row is None:
                    break
                role = self._make_role(row)
                roles[role.id()] = role
        finally:
            try:
                self._data.close()
            except Exception:
                pass
        return roles

    def get_role(self, role_id):
        """
        @type role_id: string
        @param role_id: Role id.

        @rtype: L{Role}
        @return: Role instance corresponding to given role_id.
        """
        return self._get_value(role_id, loader=self._load_role)

    def _load_role(self, role_id, transaction=None):
        row = self._data.row(pd.Value(pd.String(), role_id))
        if row:
            return self._make_role(row)
        else:
            return None


class UserGroups(ApplicationRoles):
    """Codebook of user roles where users are explicitly assigned.

    The L{ApplicationRoles} module contains all roles, including special roles
    that are not explicitly assigned to users, such as L{Roles.ANYONE},
    L{Roles.AUTHENTICATED} (also called automatically assigned roles, as users
    are assigned to them automatically by the system according to the current
    state or other conditions).

    This module is filtered to contain only roles where users are assigned
    explicitly by the administrator.  It is typically used as a codebook in
    situations, where roles are used to refer to a particular group of users
    (role members).

    """
    class Spec(ApplicationRoles.Spec):
        condition = pd.EQ('auto', pd.Value(pd.Boolean(), False))

    def _base_uri(self, req):
        # The available codebook values are limited, but the links refer to the
        # unlimited list of all ApplicationRoles.
        return req.module_uri('ApplicationRoles')


class Users(UserManagementModule, CachingPytisModule):
    """
    TODO: General description

    This module defines several inner classes closely related to user
    management.  By subclassing this module and its inner classes you can
    extend or change behavior of user management in your application.

    There is no easy way to delete a particular user, since that could have
    unexpected consequences to other content in the system.  Instead, to
    remove a user from the system, his account is disabled.  User related data
    are preserved, but he can no longer access the system, doesn't figure in
    the lists of users, doesn't receive any email notifications etc.

    A state is assigned to every user according to L{AccountState} enumeration
    class.  Note the difference between user states and user roles.  User
    states define overall access to the application, e.g. whether the user may
    access the application at all.  User roles are independent of user states
    and define (among other) access rights to various parts of the
    application.  When you need to block a user from access to the application
    completely, you set his state to C{Users.AccountState.DISABLED}.  When you
    need to enable or disable user access to a particular application feature,
    you change his roles.

    """
    class AccountState(Enumeration):
        """The available user account states are defined by the public constants."""

        NEW = 'new'
        """New users who are registered but haven't confirmed the activation code yet."""
        UNAPPROVED = 'unapproved'
        """New users who are registered, have confirmed the activation code,
           but haven't been approved by the user administrator yet."""
        ENABLED = 'enabled'
        """Users with full access to the application."""
        DISABLED = 'disabled'
        """Users explicitly blocked from access to the application by administrator."""

        enumeration = (
            (NEW, _("New account")),
            (UNAPPROVED, _("Unapproved account")),
            (DISABLED, _("Account disabled")),
            (ENABLED, _("Active account")),
        )
        selection_type = pp.SelectionType.CHOICE

    class Gender(Enumeration):
        enumeration = ((wiking.User.MALE, _("Male")),
                       (wiking.User.FEMALE, _("Female")))
        prefer_display = True
        selection_type = pp.SelectionType.RADIO

    class Spec(wiking.Specification):
        title = _("User Management")
        help = _("Manage registered users and their privileges.")
        table = wiking.dbdefs.users

        def _fullname(self, record, firstname, surname, login):
            if firstname and surname:
                return firstname + " " + surname
            else:
                return firstname or surname or login

        def _registration_expiry(self):
            expiry_days = wiking.cms.cfg.registration_expiry_days
            return now() + datetime.timedelta(days=expiry_days)

        @staticmethod
        def _generate_registration_code():
            return wiking.generate_random_string(16)

        def fields(self):
            pwdtype = pd.Password(strength=wiking.cms.cfg.password_strength,
                                  minlen=wiking.cms.cfg.password_min_length,
                                  maxlen=32, verify=True, not_null=True)
            return (
                Field('uid', width=8, editable=NEVER),
                # Translators: Login name for a website. Registration form field.
                Field('login', _("Login name"), width=36, editable=ONCE,
                      type=(pd.Email(not_null=True) if wiking.cms.cfg.login_is_email else
                            pd.RegexString(maxlen=64, not_null=True,
                                           regex=r'^[a-zA-Z][0-9a-zA-Z_\.-]*$')),
                      computer=computer(self._login),
                      descr=_("A valid login name can only contain letters, digits, underscores, "
                              "dashes, at signs and dots and must start with a letter.")),
                # UI Fields for new user insertion (by admin or by registration).
                Field('initial_password', _("Password"), virtual=True, width=16, type=pwdtype,
                      visible=computer(lambda r: r.req().param('action') != 'reinsert'),
                      descr=_("Write the same password into both fields.")),
                # UI Fields for password change.
                Field('old_password', _("Old password"), virtual=True, width=16,
                      type=pd.Password(verify=False, not_null=True),
                      descr=_("Verify your identity by entering your original (current) "
                              "password.")),
                # The only difference between initial_password and new_password is in label.
                Field('new_password', _("New password"), virtual=True, width=16, type=pwdtype,
                      descr=_("Write the same password into both fields.")),
                # The actual DB password field (never present in the UI)
                Field('password', type=pd.Password(not_null=True),
                      computer=computer(self._password)),
                # Translators: User account information field label (contains date and time).
                # TODO: Last password change is currently not displayed anywhere.  It should be only
                # visible to the admin and to the user himself, so it requires a dynamic 'view'
                # layout.
                Field('last_password_change', _("Last password change"),
                      default=now, computer=computer(self._last_password_change)),
                # Translators: Full name of a person. Registration form field.
                Field('fullname', _("Full Name"), virtual=True, editable=NEVER,
                      computer=computer(self._fullname), type=pd.String()),
                # TODO: What does this mean (missing translators note): Translators:
                Field('user', _("User"), dbcolumn='user_',
                      computer=computer(lambda r, nickname, fullname: nickname or fullname)),
                Field('firstname', _("First name")),
                Field('surname', _("Surname")),
                # Translators: Name of a user to display on a website if he doesn't want the
                # default "Name Surname". Registration form field.
                Field('nickname', _("Displayed name"),
                      descr=_("Leave blank if you want to be referred by your full name "
                              "or enter an alternate name, such as nickname or monogram."),
                      visible=self._field_visible('nickname')),
                Field('gender', _("Gender"), not_null=False, enumerator=Users.Gender,
                      visible=self._field_visible('gender')),
                # Translators: E-mail address. Registration form field.
                Field('email', _("E-mail"), width=36, type=pd.Email(not_null=True)),
                # Translators: Telephone number. Registration form field.
                Field('phone', _("Phone"), visible=self._field_visible('phone')),
                # Translators: Post address. Registration form field.
                Field('address', _("Address"), width=20, height=3,
                      visible=self._field_visible('address')),
                # Translators: Do not translate (means Uniform Resource Identifier).
                Field('uri', _("URI"), width=36, visible=self._field_visible('uri')),
                # Translators: Generic note for further information. Registration form field.
                Field('note', _("Note"), width=60, height=6, compact=True,
                      descr=wiking.module.Texts.text(wiking.cms.texts.registration_note_descr),
                      visible=self._field_visible('note')),
                # Translators: Label of a checkbox to confirm usage conditions or a
                # similar kind of agreement specific for given website.
                Field('confirm', _("I agree"), type=pd.Boolean,
                      editable=computer(lambda r, confirm: not confirm),
                      descr=_("Please check if (and only if) you have read the conditions above "
                              "and you agree with them.")),
                # Translators: Since when the user is registered. Table column heading
                # and field label for a date/time value.
                Field('since', _("Registered since"), default=now),
                # Translators: The state of the user account (e.g. Enabled vs Disabled).  Column
                # heading and field label.
                Field('state', _("State"), enumerator=Users.AccountState,
                      default=Users.AccountState.NEW, style=self._state_style),
                Field('lang', computer=computer(self._lang)),
                Field('regexpire', default=self._registration_expiry),
                Field('regcode', default=self._generate_registration_code),
            )

        def _login(self, record, email):
            if record.req().param('action') == 'reinsert' and record['login'].value() is None:
                # This is necessary, because the value of login is needed for
                # the DB function cms_f_insert_or_update_user() and the hidden
                # field value (see _hidden_fields) is not processed by
                # validation.
                return record.req().param('login')
            elif wiking.cms.cfg.login_is_email:
                return email
            else:
                return record['login'].value()

        def _field_visible(self, field):
            return computer(lambda r: field in wiking.cms.cfg.registration_fields)

        def _state_style(self, record):
            if record['state'].value() in (Users.AccountState.NEW, Users.AccountState.UNAPPROVED):
                return pp.Style(foreground='#a20')
            else:
                return None

        def _last_password_change(self, record, password):
            if record.field_changed('password'):
                return now()
            else:
                return record['last_password_change'].value()

        def _password(self, record, initial_password, new_password):
            if initial_password is not None:
                password = initial_password
            else:
                password = new_password
            if password is not None:
                storage = wiking.cms.cfg.password_storage
                password = storage.stored_password(password)
            return password

        def _lang(self, record):
            if record.new():
                # This language is used for translation of email messages
                # sent to the user.  This way it is set only once during
                # registration.  It would make sense to change it on each
                # change of user interface language by that user.
                return record.req().preferred_language()
            else:
                return record['lang'].value()

        def _check_email(self, record):
            if not record.req().param('_pytis_form_update_request') \
                    and record['email'].value() and record.field_changed('email'):
                ok, error = wiking.validate_email_address(record['email'].value())
                if not ok:
                    return ('email', error)

        def _check_old_password(self, record):
            req = record.req()
            if req.param('action') == 'passwd' and req.user().uid() == record['uid'].value():
                old_password = record['old_password'].value()
                if not old_password:
                    return ('old_password', _("Enter your current password."))
                stored_old_password = record.original_row()['password'].value()
                storage = wiking.cms.cfg.password_storage
                if not storage.check_password(old_password, stored_old_password):
                    return ('old_password', _("Invalid password."))

        def _check_new_password(self, record):
            if record.req().param('action') == 'passwd':
                new_password = record['new_password'].value()
                if not new_password:
                    return ('new_password', _("Enter the new password."))
                storage = wiking.cms.cfg.password_storage
                if storage.check_password(new_password, record.original_row()['password'].value()):
                    return ('new_password', _("The new password is the same as the old one."))

        def check(self):
            return (self._check_email, self._check_old_password, self._check_new_password)

        def bindings(self):
            return (
                wiking.Binding('roles', _("User's Groups"), 'UserRoles', 'uid',
                               form=pw.ItemizedView),
                Binding('session-history', _("Login History"), 'SessionHistory', 'uid',
                        enabled=lambda r: r.req().check_roles(Roles.USER_ADMIN)),
                Binding('crypto', _("Crypto Keys"), 'CryptoKeys', 'uid',
                        enabled=self._crypto_user),
            )
        columns = ('fullname', 'nickname', 'email', 'state', 'since')
        sorting = (('surname', ASC), ('firstname', ASC))
        layout = ()  # Force specific layout definition for each action.
        cb = CodebookSpec(display='user', prefer_display=True)

        def profiles(self):
            return pp.Profiles(
                # Translators: Name of group of users who have full access to the system.
                pp.Profile('enabled', _("Active users"),
                           filter=pd.EQ('state', pd.sval(Users.AccountState.ENABLED))),
                # Translators: Name for a group of users accounts, who were not yet approved by the
                # administrator.
                pp.Profile('unapproved', _("Unapproved accounts (pending admin approvals)"),
                           filter=pd.EQ('state', pd.sval(Users.AccountState.UNAPPROVED))),
                # Translators: Name for a group of users which did not confirm their registration
                # yet by replying to an email with an activation code.
                pp.Profile('new',
                           _("Unfinished registrations (activation code not confirmed)"),
                           filter=pd.EQ('state', pd.sval(Users.AccountState.NEW))),
                # Translators: Name for a group of users whose accounts were blocked.
                pp.Profile('disabled', _("Disabled users"),
                           filter=pd.EQ('state', pd.sval(Users.AccountState.DISABLED)),
                           ),
                # Translators: Accounts as in user accounts (computer terminology).
                pp.Profile('all', _("All accounts"), None),
                default='enabled',
            )
        actions = (
            Action('passwd', _("Change password"), icon='key-icon',
                   descr=_("Change user's password")),
            # Translators: Button label.  Used to approve user's account by the administrator.
            Action('enable', _("Approve"), icon='ok-icon',
                   descr=_("Approve this account"),
                   # Note: We use "Approve" just for consistency of the
                   # terminology in the user interface.  Technically it is the
                   # same as "Enable" (changes state to enabled).
                   visible=lambda r: r['state'].value() in (Users.AccountState.NEW,
                                                            Users.AccountState.UNAPPROVED)),
            # Translators: Button label. Computer terminology. Use common word and form.
            Action('enable', _("Enable"), icon='thumb-up-icon',
                   descr=_("Enable this account"),
                   enabled=lambda r: r['state'].value() != Users.AccountState.ENABLED,
                   visible=lambda r: r['state'].value() not in (Users.AccountState.NEW,
                                                                Users.AccountState.UNAPPROVED)),
            # Translators: Button label. Computer terminology. Use common word and form.
            Action('disable', _("Disable"), icon='thumb-down-icon',
                   descr=_("Disable this account"),
                   enabled=lambda r: r['state'].value() == Users.AccountState.ENABLED,
                   visible=lambda r: r['state'].value() not in (Users.AccountState.NEW,
                                                                Users.AccountState.UNAPPROVED)),
            Action('regreminder', _("Resend activation code"), icon='mail-icon',
                   descr=_("Resend registration mail"),
                   visible=lambda r: r['state'].value() == Users.AccountState.NEW),
            Action('delete', _("Delete"), icon='remove-icon',
                   descr=_("Remove the account completely"),
                   visible=lambda r: r['state'].value() in (Users.AccountState.NEW,
                                                            Users.AccountState.UNAPPROVED)),
        )

        def _crypto_user(self, record):
            uid = record.req().user().uid()
            if uid is None:
                return None
            crypto_keys = wiking.module.CryptoKeys
            if crypto_keys.assigned_names(uid):
                return True
            else:
                return False

    class User(wiking.User):
        """CMS specific User class."""

        def __init__(self, login, firstname=None, surname=None, state=None, confirm=None, **kwargs):
            """
            @type state: string
            @param state: User's account state.
            @type confirm: boolean
            @param confirm: Value of the user's 'confirm' flag.
            """
            wiking.User.__init__(self, login, **kwargs)
            self._firstname = firstname
            self._surname = surname
            self._state = state
            self._confirm = confirm

        def state(self):
            """
            @rtype: string
            @return: User's account state; one of L{Users.AccountState} constans.
            """
            return self._state

        def confirm(self):
            """
            @rtype: boolean or 'None'
            @return: Value of the user's 'confirm' flag.
            """
            return self._confirm

        def firstname(self):
            """
            @rtype: string or 'None'
            @return: User's first name.
            """
            return self._firstname

        def surname(self):
            """
            @rtype: string or 'None'
            @return: User's surname.
            """
            return self._surname

        def fullname(self):
            """
            @rtype: str
            @return: User's full name.
            """
            fullname = self._firstname + ' ' if self._firstname else ''
            fullname += self._surname or ''
            return fullname

    class Roles(Roles):
        """Definition of the 'Roles' class used by the application.

        You may define a custom class derived from L{wiking.Roles} here.  It is
        nested within the 'Users' module so that the application is able to
        locate the right class to use.

        """
        pass

    _REFERER = 'login'
    _PANEL_FIELDS = ('fullname',)
    _ASYNC_LOAD = True
    # Translators: Button label.
    _INSERT_LABEL = _("New user")
    # Translators: Button label.
    _UPDATE_LABEL = _("Edit profile")
    # Translators: Button label. Modify the users data (email, address...)
    _UPDATE_DESCR = _("Modify user's record")

    _cache_dependencies = ('roles', 'role_sets', 'role_members')
    _cache_ids = ('default', 'find',)

    def _authorized(self, req, action, record=None, **kwargs):
        if action in ('insert', 'confirm', 'regreminder'):
            return True
        elif action in ('update', 'passwd'):
            return req.check_roles(Roles.USER_ADMIN) or self._check_uid(req, record, 'uid')
        elif action in ('enable', 'disable', 'reinsert', 'export'):
            return req.check_roles(Roles.USER_ADMIN)
        else:
            return super(Users, self)._authorized(req, action, record=record, **kwargs)

    def _exported_columns(self, req):
        return ['uid'] + list(self._columns(req))

    def _insert_form_content(self, req, form, record):
        return (self._registration_form_intro(req, record) +
                super(Users, self)._insert_form_content(req, form, record))

    def _registration_form_intro(self, req, record):
        content = wiking.module.Texts.parsed_text(req, wiking.cms.texts.regintro,
                                                  lang=req.preferred_language())
        return [content] if content else []

    def _layout(self, req, action, record=None):
        def cms_text(cms_text):
            if wiking.module.Texts.localized_text(req, cms_text, lang=req.preferred_language()):
                return wiking.module.Texts.parsed_text(req, cms_text, lang=req.preferred_language())
            else:
                return None
        if action in ('insert', 'view', 'update'):
            login_is_email = wiking.cms.cfg.login_is_email
            layout = [
                # Translators: Personal data -- first name, surname, nickname ...
                FieldSet(_("Personal data"), ('firstname', 'surname', 'nickname', 'gender')),
                # Translators: Contact information -- email, phone, address...
                FieldSet(_("Contact information"),
                         (('email',) if (not login_is_email or action != 'insert') else ()) +
                         ('phone', 'address', 'uri')),
            ]
            if action == 'insert':
                layout.append(
                    FieldSet(_("Login information"),
                             (login_is_email and 'email' or 'login', 'initial_password'))
                )
            elif action == 'view':
                layout.extend((
                    FieldSet(_("Account state"), ('state', 'last_password_change')),
                    lambda r: self._state_info(req, r),
                ))
            regconfirm = cms_text(wiking.cms.texts.regconfirm)
            if regconfirm:
                # Translators: Confirmation of website terms&conditions. Form label.
                layout.append(FieldSet(_("Confirmation"), (regconfirm, 'confirm')))
            if action == 'insert' or action == 'view' and record['note'].value():
                # Translators: Others is a label for a group of unspecified form fields
                # (as in Personal data, Contact information, Others).
                layout.append(FieldSet(_("Others"), ('note',))),
            layout.append(wiking.Message(cms_text(wiking.cms.texts.personal_data_management)))
            return layout
        elif action in ('passwd', 'reset_password') and record is not None:
            layout = ['new_password']
            if action == 'passwd' and req.user().uid() == record['uid'].value():
                # Don't require old password for admin, unless he is changing his own password.
                layout.insert(0, 'old_password')
            if not wiking.cms.cfg.login_is_email:
                # Add read-only login to make sure the user knows which password is edited.  It
                # also helps the browser password helper to recognize which password is changed
                # (if the user has multiple accounts).
                layout.insert(0, 'login')  # Don't include email, since it is editable.
            return layout
        return super(Users, self)._layout(req, action, record=record)

    def _default_actions_last(self, req, record):
        # Omit the default `delete' action to allow its redefinition in Spec.actions.
        return tuple([a for a in super(Users, self)._default_actions_last(req, record)
                      if a.id() != 'delete'])

    def _base_uri(self, req):
        if req.path[0] == '_registration':
            return '_registration'
        return super(Users, self)._base_uri(req)

    def _form_actions(self, req, record, form, exclude=()):
        if req.path[0] == '_registration':
            exclude += ('list',)
        return super(Users, self)._form_actions(req, record, form, exclude=exclude)

    def _hidden_fields(self, req, action, record=None):
        fields = super(Users, self)._hidden_fields(req, action, record=record)
        if action == 'insert' and req.param('action') == 'reinsert':
            fields = [(name, value) for name, value in fields if name != 'action'] + [
                # Force 'action' to 'reinsert', the super method produces 'insert'...
                ('action', 'reinsert'),
                # The regcode serves as a temporary authorization token.
                ('regcode', req.param('regcode')),
            ]
            layout = self._layout_instance(self._layout(req, action))
            if 'login' not in layout.order():
                # Pass the login field as hidden when it is not in the layout
                # (typically when the current aplication has
                # 'wiking.cms.cfg.login_is_email' = True)
                fields.append(('login', req.param('login')))
        if action == 'reset_password':
            fields.append(('passcode', req.param('passcode'),))
        return fields

    def _insert_transaction(self, req, record):
        # To roll back the insertion if sending mail fails.
        return self._transaction()

    def _insert(self, req, record, transaction):
        try:
            result = super(Users, self)._insert(req, record, transaction)
        except pytis.data.DBException as e:
            msg = str(e.exception()).splitlines()[0].strip()
            if msg == 'duplicate key value violates unique constraint "users_login_key"':
                login = record['login'].value()
                # Redirect to reinsert when the user doesn't exist in application specific user
                # tables but exists in the main CMS user table.
                user = wiking.module('wiking.cms.Users').user(req, login)
                if user and not wiking.module.Users.user(req, login):
                    if not req.check_roles(Roles.USER_ADMIN):
                        code = wiking.module('wiking.cms.Users').regenerate_registration_code(user)
                    else:
                        code = None
                    req.message(_("User %s is already registered for another site. "
                                  "Please, confirm the account for this site.", login))
                    raise wiking.Redirect(req.uri(), action='reinsert', login=login, regcode=code)
                else:
                    if wiking.cms.cfg.login_is_email:
                        msg = _("This e-mail address is already registered. Just log in. "
                                "Use the forgotten password link under the log in form if you "
                                "forgot your password.")
                        column = 'email'
                    else:
                        msg = _("This login name is already taken.  Please choose another.")
                        column = 'login'
                    raise wiking.DBException(msg, column=column)
            raise
        row = self._data.get_row(login=record['login'].value(), transaction=transaction)
        # Don't send e-mails after re-registration (the account is already confirmed).
        if row['state'].value() == Users.AccountState.NEW:
            err = self._send_registration_email(req, record)
            if err:
                message = _("Failed sending e-mail:") + ' ' + err
                if req.check_roles(Roles.USER_ADMIN):
                    # If the new user is inserted by admin, we can continue.
                    req.message(message, req.ERROR)
                else:
                    # This is a critical error (the user is not able to use the
                    # account without the information from the mail), so we rather
                    # rollback the insertion by raising an error.
                    raise wiking.DBException(err)
            else:
                # Translators: '%(email)s' is replaced by a real e-mail addres.
                req.message(_("The activation code has been sent to %(email)s.",
                              email=record['email'].value()))

        return result

    def _redirect_after_insert(self, req, record):
        row = self._data.get_row(login=record['login'].value())
        if row['state'].value() != Users.AccountState.NEW:
            # This is a re-registration: The user is already confirmed in the
            # Wiking CMS user table.  No need to confirm again.
            req.message(_("Registration completed. You can log in now."), req.SUCCESS)
            raise wiking.Redirect(req.module_uri('Registration'))
        elif req.user() is not None:
            # The registration was done by admin.
            req.message(_("The account has been created."), req.SUCCESS)
            raise wiking.Redirect(self._current_record_uri(req, record))
        else:
            # Handled in action_insert() below.
            req.message(_("To finish your registration, please confirm the "
                          "activation code that was just sent to %(email)s.",
                          email=record['email'].value()))
            raise wiking.Redirect(req.uri(), action='insert', success='yes')

    def action_insert(self, req, **kwargs):
        if req.param('success') == 'yes':
            # Handle redirection in _redirect_after_insert() above (to honour Post/Redirect/Get).
            return Document(_("Account created"), content=())
        return super(Users, self).action_insert(req, **kwargs)

    def _send_registration_email(self, req, record):
        text = (
            # Translators: %(server_hostname)s is replaced by server's name,
            # such as www.yourdomain.com.
            _("Your account at %(server_hostname)s has been created.",
              server_hostname=wiking.cfg.server_hostname),
            '',
            _("Follow the link below to finish your registration:"),
            req.make_uri(req.server_uri() + req.module_uri('Registration'),
                         action='confirm', uid=record['uid'].value(),
                         regcode=record['regcode'].value()),
        )
        return send_mail(record['email'].value(),
                         _("Your registration at %(server_hostname)s",
                           server_hostname=wiking.cfg.server_hostname),
                         lcg.concat(text, separator='\n'), lang=record['lang'].value())

    def _send_admin_approval_mail(self, req, record):
        subject = _("New user account at %(server_hostname)s",
                    server_hostname=wiking.cfg.server_hostname)
        text = (
            _("New user registered at %(server_hostname)s has just confirmed the activation code.",
              fullname=record['fullname'].value(),
              server_hostname=wiking.cfg.server_hostname),
            '',
            _("The account has been approved automatically according to server setup.") + "\n"
            if wiking.cms.cfg.autoapprove_new_users else
            _("Please approve the account:"),
            req.make_uri(req.server_uri() + req.module_uri('Users'), uid=record['uid'].value()),
        )
        sent, errors = self.send_mail(Roles.USER_ADMIN, subject, lcg.concat(text, separator='\n'))
        for err in errors:
            log(OPR, "Failed sending e-mail notification:", err)

    def _redirect_after_update(self, req, record):
        if record.field_changed('login'):
            req.message(_("You can use %s to log in next time.", record['login'].value()))
        if req.param('action') == 'reset_password':
            req.message(_("You can log in now with the new password."), req.SUCCESS)
            raise wiking.Redirect('/', command='login')
        return super(Users, self)._redirect_after_update(req, record)

    def _action_subtitle(self, req, action, record=None):
        if action == 'reset_password':
            return _("Forgotten Password Reset")
        return super(Users, self)._action_subtitle(req, action, record=record)

    def _state_info(self, req, record):
        state = record['state'].value()
        if state == Users.AccountState.NEW:
            if record['regexpire'].value() > now():
                texts = (_("The activation code has not yet been confirmed by the user. "
                           "Therefore it is not possible to trust that given e-mail "
                           "address belongs to the person who requested the registration."),
                         # Translators: %(date)s is replaced by date and time of registration
                         # expiration.
                         _("The activation code will expire on %(date)s and the user will "
                           "not be able to complete the registration anymore.",
                           date=pw.localizable_export(record['regexpire'])))
                if req.check_roles(Roles.USER_ADMIN):
                    texts += _("Use the button \"Resend activation code\" below to remind the "
                               "user of his pending registration."),
            else:
                # Translators: %(date)s is replaced by date and time of registration expiration.
                texts = (_("The registration expired on %(date)s.  The user didn't confirm the "
                           "activation code sent to the declared e-mail address in time.",
                           date=pw.localizable_export(record['regexpire'])),)
                if req.check_roles(Roles.USER_ADMIN):
                    texts += _("The account should be deleted automatically if the server "
                               "maintenance script is installed correctly.  Otherwise you can "
                               "delete the account manually."),
        elif state == Users.AccountState.UNAPPROVED:
            texts = _("The activation code has been successfully confirmed."),
            if req.check_roles(Roles.USER_ADMIN):
                texts = (texts[0] + ' ' +
                         _("Therefore it was verified that given e-mail address "
                           "belongs to the person who requested the registration."),)
                texts += _("The user is now able to log in, but still has no rights "
                           "(other than an anonymous user)."),
            texts += _("The account now awaits administrator's action to be approved."),
        elif state == Users.AccountState.DISABLED:
            texts = (_("The account is blocked.  The user is able to log in, but has no "
                       "access to protected services until the administrator enables the "
                       "account again."),)
        else:
            texts = ()
        if texts:
            return wiking.Message([lcg.p(text) for text in texts])
        else:
            return lcg.Content()

    def _confirmation_success_content(self, req):
        if wiking.cms.cfg.autoapprove_new_users:
            text = wiking.cms.texts.regsuccess_autoapproved
        else:
            text = wiking.cms.texts.regsuccess
        return wiking.module.Texts.parsed_text(req, text, lang=req.preferred_language())

    def action_confirm(self, req):
        """Confirm the activation code sent by e-mail to make user registration valid.

        Additionally send e-mail notification to the administrator to ask him for account approval.

        """
        if req.param('success') == 'yes':
            return Document(_("Account activated"),
                            content=self._confirmation_success_content(req))
        try:
            uid = int(req.param('uid'))
        except (ValueError, TypeError):
            raise wiking.BadRequest()
        regcode = req.param('regcode')
        if regcode:
            row = self._data.get_row(uid=uid)
            if row is None or row['state'].value() != Users.AccountState.NEW:
                raise wiking.BadRequest()
            if row['regcode'].value() == regcode:
                if wiking.cms.cfg.autoapprove_new_users:
                    state = self.AccountState.ENABLED
                else:
                    state = self.AccountState.UNAPPROVED
                record = self._record(req, row)
                record.update(state=state, regcode=None)
                self._send_admin_approval_mail(req, record)
                req.message(_("Activation code confirmed successfully."), type=req.SUCCESS)
                if wiking.cms.cfg.autoapprove_new_users:
                    req.message(_("Your account is now active."))
                else:
                    req.message(_("Your account now awaits administrator's approval."))
                # Redirect - don't display the response here to avoid multiple submissions...
                return self._redirect_after_confirm(req, record)
            else:
                req.message(_("Invalid activation code."), req.ERROR)
        return wiking.Document(
            title=_("Activate your account"),
            content=ActivationForm(uid),
        )

    def _redirect_after_confirm(self, req, record):
        raise wiking.Redirect(req.uri(), action='confirm', success='yes')

    def _change_state(self, req, record, state, transaction=None):
        # Note: The return value is important for overriding this method,
        # which is used for example in Wiking Biblio.
        try:
            record.update(state=state, transaction=transaction)
        except pd.DBException as e:
            req.message(self._error_message(*self._analyze_exception(e)), req.ERROR)
            return False
        else:
            if state == self.AccountState.ENABLED:
                req.message(_("The account has been enabled."), req.SUCCESS)
                email = record['email'].value()
                text = _("Your account at %(uri)s has been enabled. "
                         "Please log in with username %(login)s and your password.",
                         uri=req.server_uri(), login=record['login'].value()) + "\n"
                err = send_mail(email, _("Your account has been enabled."),
                                text, lang=record['lang'].value())
                if err:
                    req.message(_("Failed sending e-mail notification:") + ' ' + err, req.ERROR)
                else:
                    req.message(_("E-mail notification has been sent to:") + ' ' + email)
            elif state == self.AccountState.DISABLED:
                req.message(_("The account has been disabled."), req.SUCCESS)
            return True

    def action_enable(self, req, record):
        if record['state'].value() == self.AccountState.NEW and not req.param('submit'):
            if record['regexpire'].value() <= now():
                req.message(_("The registration expired on %(date)s.",
                              date=pw.localizable_export(record['regexpire'])), req.WARNING)
            form = self._form(pw.ShowForm, req, record,
                              layout=self._layout(req, 'view', record=record),
                              actions=(Action('enable', _("Continue"), submit=1, icon='ok-icon'),
                                       # Translators: Button label to get to a previous state.
                                       Action('view', _("Back"), icon='arrow-left-icon')))
            req.message(_("The registration code has not been confirmed by the user!"), req.WARNING)
            req.message(_("Please enable the account only if you are sure that "
                          "the e-mail address belongs to given user."), req.WARNING)
            return self._document(req, (form), record)
        else:
            self._change_state(req, record, self.AccountState.ENABLED)
            raise wiking.Redirect(self._current_record_uri(req, record))

    def action_disable(self, req, record):
        self._change_state(req, record, self.AccountState.DISABLED)
        raise wiking.Redirect(self._current_record_uri(req, record))

    def action_passwd(self, req, record):
        return self.action_update(req, record, action='passwd')

    def action_reset_password(self, req):
        title = _("Forgotten Password Reset")
        expiry_minutes = wiking.cms.cfg.reset_password_expiry_minutes
        uid, query = req.param('uid'), req.param('query')
        if uid or query:
            if uid:
                try:
                    uid = int(uid)
                except (TypeError, ValueError,):
                    raise wiking.BadRequest(_("Invalid password reset request."))
                user = wiking.module.Users.user(req, uid=uid)
            elif '@' not in query:
                user = wiking.module.Users.user(req, login=query)
            else:
                users = wiking.module.Users.find_users(req, query)
                if not users:
                    user = None
                elif len(users) == 1:
                    user = users[0]
                else:
                    return Document(title, (
                        lcg.p(_("Multiple user accounts found for given email address.")),
                        lcg.p(_("Please, select the account for which you want to reset "
                                "the password:")),
                        lcg.ul([lcg.link(req.make_uri(req.uri(), action='reset_password',
                                                      uid=u.uid()), u.name())
                                for u in users]),
                    ))
            if user:
                record = user.data()
                passcode = req.param('passcode')
                if passcode:
                    if record['passexpire'].value() is None or record['passcode'].value() is None:
                        req.message(_("This password reset request has already been processed."),
                                    req.ERROR)
                        return Document(title, lcg.p(_("Can not repeat the action.")))
                    elif passcode != record['passcode'].value():
                        raise wiking.BadRequest(_("Invalid password reset request."))
                    elif record['passexpire'].value() < now():
                        req.message(_("The request has expired. Please, repeat the "
                                      "request and finish the procedure in %d minutes.",
                                      expiry_minutes), req.ERROR)
                    else:
                        record = self._record(req, user.data().row())
                        if req.param('submit'):
                            record['passcode'] = pd.Value(record.type('passcode'), None)
                            record['passexpire'] = pd.Value(record.type('passexpire'), None)
                        else:
                            req.message(_("Security code verified. "
                                          "You can change your password now."), req.SUCCESS)
                        return self.action_update(req, record, action='reset_password')
                else:
                    passcode = wiking.generate_random_string(32)
                    try:
                        record.update(passcode=passcode,
                                      passexpire=now() + datetime.timedelta(minutes=expiry_minutes))
                    except pd.DBException as e:
                        req.message(str(e), req.ERROR)
                    else:
                        # Translators: Credentials such as password...
                        text = lcg.concat(
                            _("A password reset request has been made at %(server_uri)s.",
                              server_uri=req.server_uri()),
                            '',
                            _("Please, follow this link to reset the password for user %s:",
                              user.name()),
                            req.make_uri(req.server_uri() + req.module_uri('Registration'),
                                         action='reset_password', uid=user.uid(),
                                         passcode=passcode),
                            '',
                            _("The link expires in %d minutes. You need to act immediately.",
                              expiry_minutes),
                            '',
                            _("If you didn't request to reset your password at %(server_uri)s, "
                              "it is possible that someone is trying to break into your account. "
                              "Contact the administrator if in doubt.",
                              server_uri=req.server_uri()),
                            '', separator='\n')
                        err = send_mail(user.email(), title, text, lang=req.preferred_language())
                        if err:
                            req.message(_("Failed sending e-mail:") + ' ' + err, req.ERROR)
                            msg = _("Please, try repeating your request later "
                                    "or contact the administrator if the problem persists.")
                        else:
                            msg = _("E-mail with a security code has been sent to your "
                                    "e-mail address for verification of the request. "
                                    "Please, check your inbox and follow the link "
                                    "within %d minutes to be able reset your password.",
                                    expiry_minutes)
                        return Document(title, lcg.p(msg))
            else:
                req.message(_("No user account for your query."), req.ERROR)

        class PasswordResetForm(lcg.Content):

            def export(self, context):
                g = context.generator()
                ids = context.id_generator()
                req = context.req()
                return g.form((
                    g.strong(g.label(_("Enter your login name or e-mail address") + ':',
                                     ids.query)),
                    g.div((
                        g.input(name='query', value=req.param('query'), id=ids.query,
                                tabindex=0, size=60),
                        g.noescape('&nbsp;'),
                        # Translators: Button name. Computer terminology. Use an appropriate
                        # term common for submitting forms in a computer application.
                        g.button(g.span(_("Submit")), type='submit', cls='submit'),
                    )),
                    g.hidden('action', 'reset_password'),
                ), method='POST', action=req.uri(), cls='password-reset-form')
        return Document(title, PasswordResetForm())

    def action_regreminder(self, req, record):
        err = self._send_registration_email(req, record)
        if err:
            req.message(_("Failed sending e-mail:") + ' ' + err, req.ERROR)
        else:
            req.message(_("The activation code was just sent to %s.", record['email'].value()))
        raise wiking.Redirect(self._current_record_uri(req, record))

    def action_reinsert(self, req):
        # Add user which already exists in the global CMS users table to an application
        # specific user table.
        if not req.param('submit'):
            user = wiking.module('wiking.cms.Users').user(req, req.param('login'))
            row = user.data().row()
            prefill = dict([(key, row[key].value(),) for key in row.keys()])
        else:
            prefill = None
        return self.action_insert(req, _prefill=prefill)

    def _special_roles(self, row):
        """Return the list of predefined special roles for given user row.

        'Predefined special roles' are application defined roles which can not
        be assigned explicitly to a particular user by the administrator, but
        the application logic decides which users belong to them.

        See the docstring of L{wiking.Role} class for a more precise definition.

        """
        roles = [Roles.ANYONE, Roles.AUTHENTICATED]
        if row['state'].value() != self.AccountState.NEW:
            roles.append(Roles.REGISTERED)
        if row['state'].value() == self.AccountState.ENABLED:
            roles.append(Roles.USER)
        return roles

    def _user_arguments(self, login, row, base_uri, registration_uri):
        if base_uri:
            uri = base_uri + '/' + login
        else:
            uri = registration_uri
        uid = row['uid'].value()
        role_ids = set([role.id() for role in self._special_roles(row)])
        if row['state'].value() == self.AccountState.ENABLED:
            role_ids.update(wiking.module.RoleMembers.user_role_ids(uid))
        # Resolve contained roles here to also count with roles contained in
        # AUTHENTICATED, and REGISTERED.
        roles = wiking.module.Application.contained_roles(role_ids)
        return dict(login=login, uid=uid, name=row['user'].value(),
                    firstname=row['firstname'].value(), surname=row['surname'].value(),
                    uri=uri, email=row['email'].value(), data=self._record(None, row),
                    roles=roles, state=row['state'].value(), gender=row['gender'].value(),
                    lang=row['lang'].value(), confirm=row['confirm'].value())

    def _make_user(self, kwargs):
        return self.User(**kwargs)

    def user(self, req, login=None, uid=None, transaction=None):
        """Return a user for given login name or user id.

        Arguments:
          login -- login name of the user as a string.
          uid -- unique identifier of the user as integer.

        Only one of 'uid' or 'login' may be passed (not None).  Argument 'login' may also be passed
        as positional (its position is guaranteed to remain).

        Returns a 'User' instance (defined in request.py) or None.

        """
        key = (login, uid, req.module_uri('ActiveUsers'), req.module_uri('Registration'))
        return self._get_value(key, transaction=transaction, loader=self._load_user)

    def _load_user(self, key, transaction=None):
        login, uid, base_uri, registration_uri = key
        # Get the user data from db
        if login is not None and uid is None:
            kwargs = dict(login=login)
        elif uid is not None and login is None:
            kwargs = dict(uid=uid)
        else:
            raise Exception("Invalid 'user()' arguments.", (login, uid))
        row = self._data.get_row(transaction=transaction, **kwargs)
        if row is None:
            user = None
        else:
            # Convert user data into a User instance
            user_kwargs = self._user_arguments(row['login'].value(), row,
                                               base_uri, registration_uri)
            user = self._make_user(user_kwargs)
        return user

    def find_user(self, req, query):
        """Return the user record for given uid, login or email address (for password reset).

        This method is DEPRECATED because it doesn't follow proper
        encapsulation and doesn't work for queries based on email (it
        only returns the first user with that email, not all users).

        Use 'user()' or 'find_users()' instead.

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

    def find_users(self, req, email=None, state=None, role=None, confirm=None):
        """Return a list of 'User' instances corresponding to given criteria.

        Arguments:

          req -- wiking request
          email -- if not 'None', only users registered with given e-mail
            address (string) are returned
          state -- if not 'None', only users with the given state (one of the
            state codes defined by L{Users.AccountState}) are returned
          role -- if not 'None', only users belonging to the given role ('Role'
            instance or role name as string) are returned
          confirm -- if not 'None', only users with this value of 'confirm' flag
            (boolean) are returned

        If all the criteria arguments are 'None', all users are returned.

        """
        if role is None:
            role_id = None
        elif isinstance(role, Role):
            role_id = role.id()
        elif isinstance(role, str):
            role_id = role
            role = wiking.module.ApplicationRoles.get_role(role_id)
        else:
            raise Exception("Invalid role argument", role)
        key = (email, state, role_id, confirm,)
        return self._get_value(key, cache_id='find', loader=self._load_find_users, role=role)

    def _load_find_users(self, key, transaction=None, role=None):
        email, state, role_id, confirm = key
        application = wiking.module.Application
        if role is not None:
            role_user_ids = wiking.module.RoleMembers.user_ids(role)
        base_uri = application.module_uri(None, 'ActiveUsers')
        registration_uri = application.module_uri(None, 'Registration')

        def make_user(row):
            if role is not None and row['uid'].value() not in role_user_ids:
                return None
            kwargs = self._user_arguments(row['login'].value(), row, base_uri, registration_uri)
            return self._make_user(kwargs)
        kwargs = {}
        if email is not None:
            kwargs['email'] = email
        if state is not None:
            kwargs['state'] = state
        if confirm is not None:
            kwargs['confirm'] = confirm
        users = [make_user(row) for row in self._data.get_rows(**kwargs)]
        if role is not None:
            users = [u for u in users if u is not None]
        return users

    def generate_password(self):
        random.seed()
        return ''.join(random.sample(string.digits + string.ascii_letters, 10))

    def regenerate_registration_code(self, user):
        """Generate a new registration code for given user and store it in the database.

        @rtype: str
        @return: The newly generated registration code.

        Such code may be used as one time authentication code.  It is now used
        for the 'reinsert' action.

        """
        record = user.data()
        regcode = wiking.generate_random_string(16)
        record.update(regcode=regcode)
        return regcode

    def send_mail(self, role, subject, text, include_uids=(), exclude_uids=(), **kwargs):
        """Send mail to all active users of given C{role}.

        @type role: L{wiking.Role} or sequence of L{wiking.Role}s or C{None}
        @param role: Destination role to send the mail to, all active users
          belonging to the role will receive the mail.  If C{None}, the mail is
          sent to all active users.
        @type include_uids: iterable of L{wiking.User} uid values.
        @param include_uids: uid of users that must receive the email even if
          not members of C{role}.  Must be disjunct with C{exclude_uids}
        @type exclude_uids: iterable of L{wiking.User} uid values.
        @param exclude_uids: uid of users that must not receive the email even
          if members of C{role}.  Must be disjunct with C{include_uids}
        @param subject, text, kwargs: Just forwarded to L{wiking.send_mail} call.

        @note: The mail is sent only to active users, i.e. users with the state
          L{Users.AccountState.ENABLED}.  There is no way to send bulk e-mail
          to inactive (i.e. new, disabled) users using this method.

        @rtype: tuple of two items (int, list)
        @return: The first value is the number of successfully sent messages
        and the second value is the sequence of error messages for all
        unsuccesful attempts.

        """
        assert (role is None or isinstance(role, wiking.Role) or
                (isinstance(role, (tuple, list)) and
                 all([isinstance(r, wiking.Role) for r in role]))), role
        # TODO: Shall we use find_users() instead of different implementation
        # of the same thing here?
        if role is not None:
            if not isinstance(role, (tuple, list)):
                role = (role,)
            user_ids = set()
            for r in role:
                user_ids |= set(wiking.module.RoleMembers.user_ids(r))
            user_ids |= set(include_uids)
            user_ids -= set(exclude_uids)
        user_rows = self._data.get_rows(state=Users.AccountState.ENABLED)
        n = 0
        errors = []
        for row in user_rows:
            if role is None or row['uid'].value() in user_ids:
                email = row['email'].value()
                error = send_mail(email, subject, text, lang=row['lang'].value(), **kwargs)
                if error:
                    errors.append(error)
                else:
                    n += 1
        return n, errors


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
        condition = pd.EQ('state', pd.Value(pd.String(), Users.AccountState.ENABLED))
        profiles = ()
        columns = ('fullname', 'nickname', 'email', 'since')
    _INSERT_LABEL = lcg.TranslatableText("New user registration", _domain='wiking')


class Registration(Module, ActionHandler):
    """User registration and account management.

    This module is statically mapped by Wiking CMS to the reserved `_registration' URI to always
    provide an interface for new user registration, password reset, password change and other
    user account related operations.

    All these operations are in fact provided by the 'Users' module.  The 'Users' module, however,
    may not be reachable from outside unless used as an extension module for an existing page.  If
    that's not the case, the 'Registration' module provides the needed operations (by proxying the
    requests to the 'Users' module).

    """

    def _authorized(self, req, action, **kwargs):
        if action in ('view', 'insert', 'reset_password', 'confirm'):
            return True
        elif action == 'list':
            return False
        elif action in ('update', 'passwd'):
            return req.check_roles(Roles.REGISTERED)
        elif action == 'reinsert':
            login = req.param('login')
            regcode = req.param('regcode')
            if login and regcode:
                user = wiking.module('wiking.cms.Users').user(req, login=login)
                if user and regcode == user.data()['regcode'].value():
                    return True
            return False
        else:
            return super(Registration, self)._authorized(req, action, **kwargs)

    def _default_action(self, req, **kwargs):
        return 'view'

    def _handle(self, req, action, **kwargs):
        if len(req.unresolved_path) > 1 and req.user() \
                and req.unresolved_path[0] == req.user().login():
            return wiking.module.Users.handle(req)
        else:
            return super(Registration, self)._handle(req, action, **kwargs)

    def _user_record(self, req):
        # We can not use the record from user.data() directly as it
        # doesn't contain reference to the current request (cached instance).
        return wiking.module.Users._record(req, req.user().data().row())

    def action_view(self, req):
        if req.user():
            return wiking.module.Users.action_view(req, self._user_record(req))
        elif req.param('command') == 'logout':
            raise wiking.Redirect('/')
        else:
            raise wiking.AuthenticationError()

    def action_insert(self, req, **kwargs):
        if not wiking.cms.cfg.allow_registration:
            raise wiking.Forbidden()
        return wiking.module.Users.action_insert(req, **kwargs)

    def action_reinsert(self, req):
        if not wiking.cms.cfg.allow_registration:
            raise wiking.Forbidden()
        return wiking.module.Users.action_reinsert(req)

    def action_update(self, req):
        return wiking.module.Users.action_update(req, self._user_record(req))

    def action_passwd(self, req):
        return wiking.module.Users.action_passwd(req, self._user_record(req))

    def action_confirm(self, req):
        return wiking.module.Users.action_confirm(req)

    def action_reset_password(self, req):
        return wiking.module.Users.action_reset_password(req)


class ActivationForm(lcg.Content):
    """Form for entering the registration activation code.

    The form is displayed automatically to users after logging in to an account
    which was not activated yet.  The activation code is normally entered
    through the link in the registration email, but the link may not always
    work (MUA may not interpret it correctly etc.) or the user may try to log
    in without even attempting to click that link previsously.  So this form
    will be displayed in such cases prompting the user for the code.

    """

    def __init__(self, uid):
        self._uid = uid
        super(ActivationForm, self).__init__()

    def export(self, context):
        g = context.generator()
        req = context.req()
        field_id = 'confirmation-code-field'
        return g.form(
            content=(
                g.hidden('action', 'confirm'),
                g.hidden('uid', self._uid),
                g.label(_("Enter the activation code:"), field_id),
                g.input(name='regcode', value=req.param('regcode'), id=field_id),
                g.button(g.span(_("Submit")), type='submit'),
            ),
            action=req.module_uri('Registration'),
            method='POST',
            cls='activation-form',
        )


class Session(PytisModule, wiking.Session):
    """Implement Wiking session management by storing session information in database.

    The session key returned by 'init()' (and accepted by 'check()' and
    'close()') consists of session id and the actual session key (the random
    token) separated by a colon.  Thus something like "2341:c167a28ab0d3...".
    This makes the session table row lookup faster, as we look it up by
    session_id (indexed int primary column) and then we only verify if the key
    in this row matches the second part.

    """
    class Spec(wiking.Specification):
        table = wiking.dbdefs.cms_sessions

    def _split_key(self, key):
        try:
            session_id, session_key = key.split(':')
            return int(session_id), session_key
        except (AttributeError, ValueError):
            return None, None

    def _is_expired(self, row):
        expiration = datetime.timedelta(hours=wiking.cfg.session_expiration)
        return row['last_access'].value() < now() - expiration

    def _update_last_access(self, row):
        self._data.update((row['session_id'],), self._data.make_row(last_access=now()))

    def _new_session(self, uid, auth_type, session_key):
        data = self._data
        expiration = datetime.timedelta(hours=wiking.cfg.session_expiration)
        # Delete all expired records first (can't do in trigger due to the configuration option).
        data.delete_many(pd.LE('last_access', pd.Value(pd.DateTime(), now() - expiration)))
        return data.insert(data.make_row(
            session_key=session_key,
            auth_type=auth_type,
            uid=uid,
            last_access=now())
        )[0]

    def init(self, req, user, auth_type, reuse=False):
        if reuse:
            row = self._data.get_row(uid=user.uid(), auth_type=auth_type)
            if row and not self._is_expired(row):
                self._update_last_access(row)
                return None
        row = self._new_session(user.uid(), auth_type, wiking.generate_random_string(64))
        return row['session_id'].export() + ':' + row['session_key'].value()

    def check(self, req, session_key):
        session_id, session_key = self._split_key(session_key)
        row = self._data.row(pd.ival(session_id))
        if row and row['session_key'].value() == session_key and not self._is_expired(row):
            self._update_last_access(row)
            return wiking.module.Users.user(req, uid=row['uid'].value())
        else:
            return None

    def close(self, req, session_key):
        session_id, session_key = self._split_key(session_key)
        # We don't verify session_key here, because we know that
        # 'CookieAuthenticationProvider.authenticate()' only calls
        # 'close()' after 'check()' or 'init()', but this is not
        # required by definition.  Thus it should be either
        # documented somewhere or not relied upon.
        self._data.delete(pd.ival(session_id))


class SessionHistory(UserManagementModule):
    class Spec(wiking.Specification):
        # Translators: Heading for an overview when and how the user has accessed the application.
        title = _("Login History")
        help = _("History of login sessions.")
        table = wiking.dbdefs.cms_v_session_history

        def _customize_fields(self, fields):
            field = fields.modify
            field('auth_type', label=_("Authentication method"))
            field('uid', label=_('User'), not_null=True, codebook='Users',
                  selection_type=pp.SelectionType.CHOICE,
                  inline_display='user', inline_referer='login')
            # Translators: Table column heading: Date and time of the user session beginning.
            field('start_time', label=_("Start time"))
            # Translators: Table column heading: The length of user session. Contains time.
            field('duration', label=_("Duration"), type=pytis.data.TimeInterval())
            # Translators: Table column heading: Whether the user session is active (Yes/No).
            field('active', label=_("Active"))

        def query_fields(self):
            return (
                Field('from', _("From"), type=pd.Date()),
                Field('to', _("To"), type=pd.Date()),
            )

        def condition_provider(self, query_fields={}, **kwargs):
            conditions = []
            if query_fields['from'].value():
                conditions.append(pd.GE('start_time', query_fields['from']))
            to = query_fields['to'].value()
            if to:
                dt = datetime.datetime(to.year, to.month, to.day, 23, 59, 59, tzinfo=now().tzinfo)
                conditions.append(pd.LE('start_time', pd.dtval(dt)))
            return pd.AND(*conditions) if conditions else None

        columns = ('start_time', 'duration', 'active', 'uid', 'auth_type')
        sorting = (('start_time', DESC),)

    _ASYNC_LOAD = True

    def _authorized(self, req, action, **kwargs):
        if action != 'list':
            return False
        else:
            return super(SessionHistory, self)._authorized(req, action, **kwargs)

    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid == 'uid':
            return super(SessionHistory, self)._link_provider(req, uri, record, cid, **kwargs)
        else:
            return None


class LoginFailures(UserManagementModule):
    class Spec(wiking.Specification):
        # Translators: Heading for a listing of unsuccesful login attempts.
        title = _("Login Failures")
        help = _("History of unsuccessful login attempts.")
        table = wiking.dbdefs.cms_login_failures
        sorting = (('timestamp', DESC),)

        def _customize_fields(self, fields):
            field = fields.modify
            field('timestamp', label=_("Time"))
            field('ip_address', label=_("IP address"))
            field('login', label=_("Login name"))
            field('auth_type', label=_("Authentication method"))
            # Translators: Internet name of the remote computer (computer terminology).
            fields.append(Field('hostname', _("Hostname"), virtual=True,
                                computer=computer(self._hostname)))
            # Translators: "User agent" is a generalized name for browser or more precisely the
            # software which produced the HTTP request (was used to access the website).
            field('user_agent', label=_("User agent"))

        def _hostname(self, row, ip_address):
            try:
                return socket.gethostbyaddr(ip_address)[0]
            except Exception:
                return None  # _("Unknown")

        columns = ('timestamp', 'login', 'auth_type', 'ip_address', 'user_agent')
        layout = ('timestamp', 'login', 'auth_type', 'ip_address', 'hostname', 'user_agent')

    _ASYNC_LOAD = True

    def failure(self, req, login, auth_type):
        row = self._data.make_row(
            timestamp=now(),
            login=login,
            auth_type=auth_type,
            ip_address=req.header('X-Forwarded-For') or req.remote_host() or '?',
            user_agent=req.header('User-Agent'),
        )
        self._data.insert(row)

    def _authorized(self, req, action, **kwargs):
        # TODO: Disable view as well and display hostname in a tooltip...
        if action not in ('list', 'view'):
            return False
        else:
            return super(LoginFailures, self)._authorized(req, action, **kwargs)
