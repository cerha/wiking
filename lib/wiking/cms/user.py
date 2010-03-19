# -*- coding: utf-8 -*-

# Copyright (C) 2006-2010 Brailcom, o.p.s.
#
# COPYRIGHT NOTICE
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import pytis.data as pd
import pytis.presentation as pp
import pytis.util
import wiking
from wiking.cms import *

"""Wiking CMS users and roles.

The most important class here is L{Users}.  It defines all the basic
functionality regarding user management in Wiking CMS and Wiking CMS based
applications.

Wiking CMS, unlike plain Wiking, can store role related data in a database.
There are several classes for manipulation with role database data:
L{RoleSets}, L{RoleUsers}, L{ApplicationRoles}.

"""

class RoleSets(wiking.PytisModule):
    """Accessor of role membership information stored in the database.

    Roles can contain other roles.  Such roles serve as shorthands for typical
    combinations of other roles, those may be any L{Role} instances, including
    L{Role} subclasses.

    @invariant: There may be no cycles in role memberships, i.e. no role may
      contain itself, including transitive relations.  For instance, group role
      I{foo} may not contain I{foo}; or if I{foo} contains I{bar} and I{bar}
      contains I{baz} then I{baz} may not contain I{foo} nor I{bar} nor I{baz}.

    @see: L{wiking.cms.Role} for explanation of I{role members}.
    
    """
    class Spec(wiking.Specification):
        table = 'role_sets'
        fields = (pp.Field('role_id'),
                  pp.Field('member_role_id'),
                  )
    
    def _dictionary(self):
        """
        @rtype: dictionary of strings as keys and sequences of strings as values
        @return: Role membership information in the form of dictionary with
          role identifiers as keys and sequences of identifiers of their
          corresponding member roles.

        @note: The dictionary contains only roles contained in other roles.  It
          doesn't contain any information about users.
          
        """
        dictionary = {}
        def add(row):
            role_id = row['role_id'].value()
            member = row['member_role_id'].value()
            role_members = dictionary.get(role_id)
            if role_members is None:
                role_members = dictionary[role_id] = []
            role_members.append(member)
        self._data.select_map(add)
        return dictionary

    def included_role_ids(self, role):
        """
        @type role: L{Role}
        @param role: Role whose member roles should be returned.

        @rtype: sequence of strings
        @return: Sequence of role identifiers included in the given role,
          including the identifier of C{role} itself.
          
        """
        assert isinstance(role, wiking.Role), role
        membership = self._dictionary()
        role_ids = []
        queue = [role.id()]
        while queue:
            r_id = queue.pop()
            if r_id not in role_ids:
                role_ids.append(r_id)
            queue += list(membership.get(r_id, []))
        return role_ids

class RoleUsers(wiking.PytisModule):
    """Accessor of role users information stored in the database.
    """
    class Spec(wiking.Specification):
        table = 'user_roles'
        title = _("User Roles")
        def fields(self):
            return (pp.Field('role_id', _("Group id")),
                    pp.Field('uid', _("User id")),
                    pp.Field('name', _("Group"), codebook='ApplicationRoles'),
                    )
        columns = ('name',)
        cb = pp.CodebookSpec(display='name', prefer_display=True)
        
    def user_ids(self, role):
        """
        @type role: L{Role}
        @param role: Role whose users should be returned.

        @rtype: sequence of strings
        @return: Sequence of identifiers of the users belonging to the given
          role, including all member roles.
          
        """
        included_role_ids = self._module('RoleSets').included_role_ids(role)
        S = pd.String()
        condition = pd.OR(*[pd.EQ('role_id', pd.Value(S, m_id)) for m_id in included_role_ids])
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
        condition = pd.EQ('uid', pd.Value(pd.Integer(), uid))
        def role_id(row):
            return row['role_id'].value()
        return self._data.select_map(role_id, condition=condition)
    
    RIGHTS_insert = (Roles.USER_ADMIN,)
    RIGHTS_update = (Roles.USER_ADMIN,)
    RIGHTS_delete = (Roles.USER_ADMIN,)


class ApplicationRoles(wiking.PytisModule):
    """Accessor and editor of application roles.

    This class can read roles from and store them to the database.  Its main
    purpose is to handle user defined roles.

    """
    class Spec(wiking.Specification):
        table = 'roles'
        # Translators: Form heading.
        title = _("User Groups")
        fields = (# Translators: Form field label.
                  pp.Field('role_id', _("Identifier")),
                  # Translators: Form field label, noun.
                  pp.Field('name', _("Name")),
                  # Translators: Form field label, adjective.
                  pp.Field('system', _("System"), editable=pp.Editable.NEVER),
                  )
        layout = ('role_id', 'name',)
        def cb(self):
            return pp.CodebookSpec(display=self._xname_computer, prefer_display=True)
        _ROLES = None
        def _xname_computer(self, row):
            name = row['name'].value()
            role_id = row['role_id'].value()
            if name is None and role_id is not None and self._ROLES is not None:
                name = self._ROLES[role_id].name()
            return name

    def __init__(self, *args, **kwargs):
        super(ApplicationRoles, self).__init__(*args, **kwargs)
        self.Spec._ROLES = self._module('Users').Roles()
    
    def user_defined_roles(self):
        """
        @rtype: sequence of L{Role}s
        @return: All user defined roles, i.e. roles defined by the application
          administrators and not the application code.
        """
        role_sets = RoleSets(cfg.resolver)
        def make_role(row):
            role_id = row['role_id'].value()
            name = row['name'].value()
            return Role(role_id, name)
        condition = pd.EQ('system', pd.Value(pd.Boolean(), False))
        return tuple(self._data.select_map(make_role, condition=condition))
    
    WMI_SECTION = WikingManagementInterface.SECTION_USERS
    WMI_ORDER = 1500
    
    RIGHTS_list = (Roles.USER,)
    RIGHTS_view = (Roles.USER,)
    RIGHTS_insert = (Roles.USER_ADMIN,)
    RIGHTS_update = (Roles.USER_ADMIN,)
    RIGHTS_delete = (Roles.USER_ADMIN,)


class Users(CMSModule):
    """
    TODO: General description

    This module defines several inner classes closely related to user
    management.  By subclassing this module and its inner classes you can
    extend or change behavior of user management in your application.
    
    There is no easy way to delete a particular user, since that could
    have many unexpected consequences to other content in the
    system. Instead, to remove a user from the system, his role is
    changed to Disabled. His history is thus preserved in other
    modules, but he can no longer access the system, doesn't figure in
    the lists of users, doesn't receive any email notifications etc.

    A state is assigned to every user.  The state determines the level of
    access to the application.  The following state codes, as used in the
    database table, are defined:

     - C{none}: New users who are registered but haven't confirmed their
       registration yet.
     - C{unconfirmed}: New users who are registered, have confirmed their
       registration, but haven't been confirmed by the user administrator yet.
     - C{disa}: Users blocked from access to the application, such as deleted
       users, refused registration requests etc.
     - C{user}: Users with full access to the applications.

    Note the difference between user states and user roles.  User states define
    overall access to the application, e.g. whether the user may access the
    application at all.  User roles are independent of user states and define
    (among other) access rights to various parts of the application.  When you
    need to block a user from access to the application completely, you set his
    state to C{disa}.  When you need to enable or disable user access to a
    particular application feature, you change his roles.

    """
    class Spec(Specification):
        title = _("User Management")
        help = _("Manage registered users and their privileges.")
        _STATES = (('none', _("New account")),
                   ('unconfirmed', _("Unapproved account")),
                   ('disa', _("Account disabled")),
                   ('user', _("Regular account")),)
        _STATE_DICT = dict([(_code, _title,) for _code, _title in _STATES])

        def _fullname(self, record, firstname, surname, login):
            if firstname and surname:
                return firstname + " " + surname
            else:
                return firstname or surname or login
        def _registration_expiry(self):
            expiry_days = cfg.registration_expiry_days
            return mx.DateTime.now().gmtime() + mx.DateTime.TimeDelta(hours=expiry_days*24)
        @staticmethod
        def _generate_registration_code():
            import random
            random.seed()
            return ''.join(['%d' % (random.randint(0, 9),) for i in range(16)])
        def fields(self):
            md5_passwords = (cfg.password_storage == 'md5')
            return (
            Field('uid', width=8, editable=NEVER),
            # Translators: Login name for a website. Registration form field.
            Field('login', _("Login name"), width=16, editable=ONCE,
                  type=pd.RegexString(maxlen=16, not_null=True, regex='^[a-zA-Z][0-9a-zA-Z_\.-]*$'),
                  computer=(cfg.login_is_email and computer(lambda r, email: email) or None),
                  descr=_("A valid login name can only contain letters, digits, underscores, "
                          "dashes and dots and must start with a letter.")),
            Field('password', _("Password"), width=16,
                  type=pd.Password(minlen=4, maxlen=32, not_null=True, md5=md5_passwords),
                  descr=_("Please, write the password into each of the two fields to eliminate "
                          "typos.")),
            Field('old_password', _(u"Old password"), virtual=True, width=16,
                  type=pd.Password(verify=False, not_null=True, md5=md5_passwords),
                  descr=_(u"Verify your identity by entering your original (current) password.")),
            Field('new_password', _("New password"), virtual=True, width=16,
                  type=pd.Password(not_null=True),
                  descr=_("Please, write the password into each of the two fields to eliminate "
                          "typos.")),
            # Translators: User account information field label (contains date and time).
            # TODO: Last password change is currently not displayed anywhere.  It should be only
            # visible to the admin and to the user himself, so it requires a dynamic 'view' layout.
            Field('last_password_change', _("Last password change"), type=DateTime(), default=now,
                  computer=computer(lambda r, password:
                                    r.field_changed('password') and now() or r['last_password_change'].value())),
            # Translators: Full name of a person. Registration form field.
            Field('fullname', _("Full Name"), virtual=True, editable=NEVER,
                  computer=computer(self._fullname)),
            # TODO: What does this mean (missing translators note): Translators: 
            Field('user', _("User"), dbcolumn='user_',
                  computer=computer(lambda r, nickname, fullname: nickname or fullname)),
            Field('firstname', _("First name")),
            Field('surname', _("Surname")),
            # Translators: Name of a user to display on a website if he doesn't want the
            # default "Name Surname". Registration form field.
            Field('nickname', _("Displayed name"),
                  descr=_("Leave blank if you want to be referred by your full name or enter an "
                          "alternate name, such as nickname or monogram.")),
            # Translators: E-mail address. Registration form field.
            Field('email', _("E-mail"), width=36, constraints=(self._check_email,)),
            # Translators: Telephone number. Registration form field.
            Field('phone', _("Phone")),
            # Translators: Post address. Registration form field.
            Field('address', _("Address"), width=20, height=3),
            # Translators: Do not translate (means Uniform Resource Identifier).
            Field('uri', _("URI"), width=36),
            # Translators: Generic note for further information. Registration form field.
            Field('note', _("Note"), width=60, height=6,
                  descr=_("Optional message for the administrator.  If you summarize briefly why "
                          "you register, what role you expect in the system or whom you have "
                          "talked to, this may help in processing your request.")),
            # Translators: Since when the user is registered. Column heading in a table listing various users.
            Field('since', _("Registered since"), type=DateTime(show_time=False), default=now),
            # Translators: The state of the user in the system (e.g. Enabled vs Disabled, Registered
            # vs. Confirmed) Column heading in a table listing various users.
            Field('state', _("State"), display=self._state_name, prefer_display=True, default='none',
                  enumerator=enum([code for code, title in self._STATES]),
                  style=lambda r: r['state'].value() == 'none' and pp.Style(foreground='#a20') \
                        or None,
                  descr=_("Select one of the predefined states to grant or retract the user "
                          "access to the application.")),
            Field('lang'),
            Field('regexpire', default=self._registration_expiry, type=DateTime()),
            Field('regcode', default=self._generate_registration_code),
            #Field('organization', _("Organization"), editable=ONCE,
            #      descr=_(("If you are a member of an organization registered in the application "
            #               "write the name of the organization here. "
            #               "Otherwise leave the field empty."))),
            #Field('organization_id', _("Organization"), codebook='Organizations', not_null=False),
            # The value of the following field is a sequence even though its pytis type is
            # string...  But it is only used in AccountInfo.
            Field('xstate', virtual=True, computer=computer(self._state)),
            )
        def _state(self, record, state, regexpire):
            req = record.req()
            if state == 'disa':
                texts = (_("The account is blocked.  The user is able to log in, but has no "
                           "access to protected services until the administrator grants him "
                           "access rights again."),)
            elif state != 'none':
                texts = ()
            elif regexpire is None:
                texts = _("The activation code was succesfully confirmed."),
                if req.check_roles(Roles.ADMIN):
                    texts = (texts[0] +' '+ \
                             _("Therefore it was verified that given e-mail address "
                               "belongs to the person who requested the registration."),)
                    texts += _("The user is now able to log in, but still has no rights "
                               "(other than an anonymous user)."),
                # Translators: In other words, the administrator needs to approve the account first.
                texts += _("The account now awaits administrator's action to be given "
                          "access rights."),
            elif regexpire > mx.DateTime.now().gmtime():
                texts = (_("The activation code was not yet confirmed by the user. Therefore "
                           "it is not possible to trust that given e-mail address belongs to "
                           "the person who requested the registration."),
                        # Translators: %(date)s is replaced by date and time of registration
                        # expiration.
                        _("The activation code will expire on %(date)s and the user will not be "
                          "able to complete the registration anymore.",
                          date=record['regexpire'].export()))
                if req.check_roles(Roles.ADMIN):
                    texts += _("Use the button \"Resend activation code\" below to remind the "
                              "user of his pending registration."),
            else:
                # Translators: %(date)s is replaced by date and time of registration expiration.
                texts = _("The registration expired on %(date)s.  The user didn't confirm the "
                          "activation code sent to the declared e-mail address in time.",
                         date=record['regexpire'].export()),
                if req.check_roles(Roles.ADMIN):
                    texts += _("The account should be deleted automatically if the server "
                               "maintenence script is installed correctly.  Otherwise you can "
                               "delete the account manually."),
            return texts
        def _check_email(self, email):
            result = wiking.validate_email_address(email)
            if not result[0]:
                return _("Invalid e-mail address: %s", result[1])
        def _state_name(self, code):
            return self._STATE_DICT[code]
        @classmethod
        def _states(cls, row):
            return cls._STATE_DICT[row['state'].value()][1]
        def bindings(self):
            return (Binding('roles', _("User's Groups"), 'RoleUsers',
                            condition=(lambda row: pd.EQ('uid', row['uid']))),
                    Binding('login-history', _("Login History"), 'SessionLog', 'uid',
                            enabled=lambda r: r.req().check_roles(Roles.ADMIN)),)
        columns = ('fullname', 'nickname', 'email', 'state', 'since')
        sorting = (('surname', ASC), ('firstname', ASC))
        layout = () # Force specific layout definition for each action.
        cb = CodebookSpec(display='user', prefer_display=True)
        filters = (
            # Translators: Name of group of users who have access to the system, can use it etc.
            pp.Filter('active', _("Active users"),
                      pd.AND(pd.NE('state', pd.Value(pd.String(), 'none')),
                             pd.NE('state', pd.Value(pd.String(), 'disa')),
                             pd.EQ('regexpire', pd.Value(pd.DateTime(), None)))),
            # Translators: Name for a group of users accounts, who were not yet approved by the administrator
            pp.Filter('inactive', _("Unapproved accounts (pending admin approvals)"),
                      pd.AND(pd.EQ('state', pd.Value(pd.String(), 'none')),
                             pd.EQ('regexpire', pd.Value(pd.DateTime(), None)))),
            # Translators: Name for a group of users which did not confirm their registration yet by
            # replying to an email with an activation code
            pp.Filter('unconfirmed', _("Unfinished registration requests (activation code not confirmed)"),
                      pd.NE('regexpire', pd.Value(pd.DateTime(), None))),
            # Translators: Name for a group of users who were disabled (made inactive or removed
            # from the system).
            pp.Filter('disabled', _("Disabled users"),
                      pd.EQ('state', pd.Value(pd.String(), 'disa'))),
            # Translators: Accounts as in user accounts (computer terminology).
            pp.Filter('all', _("All accounts"), None),
            )
        default_filter = 'active'
        
    class User(wiking.User):
        """CMS specific User class."""

        def __init__(self, login, state=None, **kwargs):
            """
            @type state: string
            @param state: User's account state.
            """
            wiking.User.__init__(self, login, **kwargs)
            self._state = state
        
        def disabled(self):
            """Return true iff the user is currently disabled.
            @deprecated: Use L{state} and compare the resulting value with C{'disa'}.
            """
            return self.state() == 'disa'

        def preregistered(self):
            """Return true iff the user hasn't confirmed his registration code yet.
            @deprecated: Use L{state} and compare the resulting value with C{'none'}.
            """
            return self.state() == 'none'

        def active(self):
            """Return true iff the user is active.
            @deprecated: Use L{state} and compare the resulting value with C{'user'}.
            """
            return self.state() == 'user'

        def roles(self):
            if self.disabled() or (not self.active() and not self.preregistered()):
                return ()
            roles = wiking.User.roles(self)
            if self.preregistered():
                roles = roles + (Roles.REGISTERED,)
            elif self.active():
                roles = roles + (Roles.USER,)
            return roles

        def state(self):
            """
            @rtype: string
            @return: User's account state.
            """
            return self._state

        def role_description(self):
            """
            @deprecated: This facility is not available anymore, use other
              information instead, such as list of user roles.
            """
            return ''

    class AccountInfo(lcg.Content):
        """Content shown in 'view' layout describing the current account state.

        Exports to a series of paragraphs or to an empty string if the sequence of texts passed to
        the constructor is empty.

        """
        def __init__(self, texts):
            self._texts = texts
        def export(self, context):
            if not self._texts:
                return ''
            else:
                g = context.generator()
                return g.div([g.p(p) for p in self._texts], cls='account-info')

    class Roles(Roles):
        pass

    _REFERER = 'login'
    _PANEL_FIELDS = ('fullname',)
    _ALLOW_TABLE_LAYOUT_IN_FORMS = False
    _OWNER_COLUMN = 'uid'
    _SUPPLY_OWNER = False
    _LAYOUT = {
        # 'insert' and 'passwd' layout is constructed dynamicallly in _layout().
        # Translators: Personal data -- first name, surname, nickname ...
        'update': (FieldSet(_("Personal data"), ('firstname', 'surname', 'nickname')),
                   # Translators: Contact information -- email, phone, address...
                   FieldSet(_("Contact information"), ('email', 'phone', 'address', 'uri')),
                   # Translators: Others is a label for a group of unspecified form fields
                   # (as in Personal data, Contact information, Others).
                   FieldSet(_("Others"), ('note',))),
        'view': (FieldSet(_("Personal data"), ('firstname', 'surname', 'nickname',)),                 
                 FieldSet(_("Contact information"), ('email', 'phone', 'address','uri')),
                 FieldSet(_("Others"), ('note',)),
                 FieldSet(_("Account state"), ('state',)),
                 lambda r: Users.AccountInfo((r['state'].value(),))),
        'rights': ('state',),
        }
    # Translators: Button label.
    _INSERT_LABEL = _("New user")
    # Translators: Button label.
    _UPDATE_LABEL = _("Edit profile")
    # Translators: Button label. Modify the users data (email, address...)
    _UPDATE_DESCR = _("Modify user's record")
    RIGHTS_insert = (Roles.ANYONE,)
    RIGHTS_update = (Roles.ADMIN, Roles.OWNER)
    RIGHTS_delete = (Roles.ADMIN,) #, Roles.OWNER)
    WMI_SECTION = WikingManagementInterface.SECTION_USERS
    WMI_ORDER = 100

    @staticmethod
    def _embed_binding_condition(row):
        return pd.NE('state', pd.Value(pd.String(), 'none'))

    def _layout(self, req, action, record=None):
        if not self._LAYOUT.has_key(action): # Allow overriding this layout in derived classes.
            if action == 'insert':
                return (FieldSet(_("Personal data"), ('firstname', 'surname', 'nickname',)),
                        FieldSet(_("Contact information"),
                                 ((not cfg.login_is_email) and ('email',) or ()) +
                                 ('phone', 'address', 'uri')),
                        FieldSet(_("Others"), ('note',)),
                        FieldSet(_("Login information"),
                                 ((cfg.login_is_email and 'email' or 'login'), 'password')))
            elif action == 'passwd' and record is not None:
                layout = ['new_password']
                if not req.check_roles(Roles.ADMIN) or req.user().uid() == record['uid'].value():
                    # Don't require old password for admin, unless he is changing his own password.
                    layout.insert(0, 'old_password')
                if not cfg.login_is_email:
                    # Add read-only login to make sure the user knows which password is edited.  It
                    # also helps the browser password helper to recognize which password is changed
                    # (if the user has multiple accounts).
                    layout.insert(0, 'login') # Don't include email, since it is editable.
                return layout
        return super(Users, self)._layout(req, action, record=record)
                
    def _validate(self, req, record, layout):
        if record.new():
            # This language is used for translation of email messages sent to the user.  This way
            # it is set only once during registration.  It would make sense to change it on each
            # change of user interface language by that user.
            record['lang'] = pd.Value(record['lang'].type(), req.prefered_language())
        errors = []
        if 'old_password' in layout.order():
            #if not req.check_roles(Roles.ADMIN): Too dangerous?
            old_password = req.param('old_password')
            if not old_password:
                errors.append(('old_password', _(u"Enter your current password.")))
            else:
                error = record.validate('old_password', old_password, verify=old_password)
                if error or record['old_password'].value() != record['password'].value():
                    errors.append(('old_password', _(u"Invalid password.")))
        if 'new_password' in layout.order():
            new_password = req.param('new_password')
            if not new_password:
                errors.append(('new_password', _(u"Enter the new password.")))
            else:
                current_password_value = record['password'].value()
                error = record.validate('password', new_password[0], verify=new_password[1])
                if error:
                    errors.append(('new_password', error.message(),))
                elif record['password'].value() == current_password_value:
                    errors.append(('new_password',
                                   _(u"The new password is the same as the old one.")))
        if errors:
            return errors
        else:
            return super(Users, self)._validate(req, record, layout)
        
    def _base_uri(self, req):
        if req.path[0] == '_registration':
            return '_registration'
        return super(Users, self)._base_uri(req)

    def _insert_subtitle(self, req):
        if req.path[0] == '_registration':
            return None
        return super(Users, self)._insert_subtitle(req)
        
    def _default_actions_first(self, req, record):
        actions = super(Users, self)._default_actions_first(req, record) + \
                  (Action(_("Access rights"), 'rights', descr=_("Change access rights"),
                          enabled=lambda r: r['regexpire'].value() is None),)
        if record and record['state'].value() == 'none':
            # Translators: Button label. Computer terminology. Use common word and form.
            actions = (Action(_("Enable"), 'enable', descr=_("Enable this account"),
                              enabled=lambda r: r['regexpire'].value() is None),
                       ) + actions
        if record and record['regexpire'].value() is not None:
            # Currently inactive due to limited access rights (is this action really needed?).
            # Translators: Confirm button
            actions = (Action(_("Confirm"), 'admin_confirm',
                              descr=_("Confirm the account without checking the activation code")),
                       ) + actions
        if req.user():
            actions += (Action(_("Change password"), 'passwd', descr=_("Change user's password")),)
        return actions
    
    def _actions(self, req, record):
        actions = list(super(Users, self)._actions(req, record))
        if req.path[0] == '_registration':
            actions = [a for a in actions if a.name() != 'list']
        if record is not None and record['regexpire'].value() is not None:
            actions.append(Action(_("Resend activation code"), 'regreminder',
                                  descr=_("Re-send registration mail")))
        return actions

    def _make_registration_email(self, req, record):
        base_uri = req.module_uri('Registration') or '/_wmi/'+ self.name()
        server_hostname = req.server_hostname()
        uri = req.server_uri() + make_uri(base_uri, action='confirm', uid=record['uid'].value(),
                                          regcode=record['regcode'].value())
        text = _("The first step of your registration at %(server_hostname)s "
                 "was successfully completed.\n\n"
                 "For the next step visit the following URL and follow the instructions there:\n"
                 "%(uri)s\n\n"
                 "If the above link fails, you will be prompted for your activation code when\n"
                 "you attempt to log in.\n\n"
                 "Your activation code is: %(code)s\n",
                 server_hostname=server_hostname,
                 uri=uri,
                 code=record['regcode'].value())
        attachments = ()
        return text, attachments

    def _redirect_after_insert(self, req, record):
        if self._send_registration_email(req, record):
            content = (lcg.p(_("Registration accepted.")),
                       lcg.p(_("Please, check your mailbox for instructions how to proceed.")))
            
        else:
            self._data.delete(record['uid'])
            content = lcg.p(_("Registration cancelled."))
        return self._document(req, content, record, subtitle=None)

    def _send_registration_email(self, req, record):
        text, attachments = self._make_registration_email(req, record)
        err = send_mail(record['email'].value(),
                        _("Your registration at %s", req.server_hostname()),
                        text, export=True,
                        lang=record['lang'].value(), attachments=attachments)
        if err:
            req.message(_("Failed sending e-mail notification:") +' '+ err, type=req.ERROR)
            return False
        else:
            # Translators: Follows an email addres, e.g. ``Activation code was sent to joe@brailcom.org''
            req.message(_("Activation code was sent to %s.", record['email'].value()))
            return True

    def _redirect_after_update(self, req, record):
        orig_row = record.original_row()
        if record['regexpire'].value() is None \
               and (orig_row['state'].value() == 'none' and record['state'].value() != 'none' \
                    or orig_row['regexpire'].value() is not None):
            req.message(_("The account was enabled."))
            text = _("Your account at %(uri)s has been enabled. "
                     "Please log in with username '%(login)s' and your password.",
                     uri=req.server_uri(), login=record['login'].value()) + "\n"
            err = send_mail(record['email'].value(), _("Your account has been enabled."),
                            text, lang=record['lang'].value())
            if err:
                req.message(_("Failed sending e-mail notification:") +' '+ err, type=req.ERROR)
            else:
                req.message(_("E-mail notification has been sent to:")+' '+record['email'].value())
            return self.action_view(req, record)
        else:
            return super(Users, self)._redirect_after_update(req, record)
    
    def _check_registration_code(self, req):
        """Check whether given request contains valid login and activation code.

        Return a 'Record' instance corresponding to the user id given in the request (if the uid
        and activation code are valid) or raise 'BadRequest' exception.

        """
        uid, error = pytis.data.Integer().validate(req.param('uid'))
        if error is not None or uid.value() is None:
            raise BadRequest()
        # This doesn't prevent double registration confirmation, but how to
        # avoid it?
        row = self._data.get_row(uid=uid.value())
        if row is None:
            record = None
        else:
            record = self._record(req, row)
        if record is None:
            raise BadRequest()
        if not record['regexpire'].value() and record['state'] == 'none':
            raise BadRequest(_("User registration already confirmed."))
        code = record['regcode'].value()
        if not code or code != req.param('regcode'):
            req.message(_("Invalid activation code."), type=req.ERROR)
            raise Abort(_("Account not activated"), ActivationForm(uid.value(), allow_bypass=False))
        return record

    def _send_admin_approval_mail(self, req, record):
        addr = cfg.webmaster_address
        if addr:
            base_uri = req.module_uri(self.name()) or '/_wmi/'+ self.name()
            text = _("New user %(fullname)s registered at %(server_hostname)s. "
                     "Please approve the account: %(uri)s",
                     fullname=record['fullname'].value(), server_hostname=req.server_hostname(),
                     uri=req.server_uri() + base_uri +'/'+ record['login'].value()) + "\n"
            # TODO: The admin email is translated to users language.  It would be more approppriate
            # to subscribe admin messages from admin accounts and set the language for each admin.
            err = send_mail(addr, _("New user registration:") +' '+ record['fullname'].value(),
                            text, lang=record['lang'].value())
            
            if err:
                req.message(_("Failed sending e-mail notification:") +' '+ err, type=req.ERROR)
                return False
            else:
                req.message(_("E-mail notification has been sent to server administrator."))
                return True

    def _confirmation_success_content(self, req, record):
        # TODO: This method allows overriding the text in applications.
        # Better would be to use the `Texts' module.
        content = [lcg.p(_("Registration completed successfuly. "
                           "Your account now awaits administrator's approval."))]
        return content
    

    def action_admin_confirm(self, req, record):
        """Force registration confirmation without checking activation code."""
        if req.param('submit'):
            record.update(regexpire=None)
            req.message(_("The account was confirmed.  Grant the access rights now."))
            return self.action_view(req, record)
        else:
            form = self._form(pw.ShowForm, req, record, layout=self._layout(req, 'view', record))
            actions = (Action(_("Confirm"), 'admin_confirm', submit=1),
                       # Translators: Back button label. Standard computer terminology.
                       Action(_("Back"), 'view'))
            action_menu = self._action_menu(req, record, actions)
            req.message(_("Please confirm the account only if you are sure that "
                          "the e-mail address belongs to given user."))
            return self._document(req, (form, action_menu), record)
    RIGHTS_admin_confirm = () #Roles.ADMIN,)

    def action_confirm(self, req):
        """Confirm the activation code sent by e-mail to make user registration valid.

        Additionally send e-mail notification to the administrator to ask him for account approval.
        
        """
        record = self._check_registration_code(req)
        record.update(regexpire=None)
        self._send_admin_approval_mail(req, record)
        return Document(_("Registration confirmed"),
                        content=self._confirmation_success_content(req, record))
    RIGHTS_confirm = (Roles.ANYONE,)

    def action_enable(self, req, record):
        state = record['state'].value()
        if state == 'none':
            state = 'user'
        try:
            record.update(state=state, regexpire=None)
        except pd.DBException, e:
            req.message(self._error_message(*self._analyze_exception(e)), type=req.ERROR)
        return self._redirect_after_update(req, record)
    RIGHTS_enable = (Roles.ADMIN,)
    
    def action_rights(self, req, record):
        # TODO: Enable table layout for this form.
        return self.action_update(req, record, action='rights')
    RIGHTS_rights = (Roles.ADMIN,)
    
    def action_passwd(self, req, record):
        return self.action_update(req, record, action='passwd')
    RIGHTS_passwd = (Roles.ADMIN, Roles.OWNER)

    def action_regreminder(self, req, record):
        self._send_registration_email(req, record)
        return self.action_view(req, record)
    RIGHTS_regreminder = (Roles.ANYONE,)

    def _user_arguments(self, req, login, row):
        record = self._record(req, row)
        base_uri = req.module_uri(self.name())
        if base_uri:
            uri = base_uri +'/'+ login
        else:
            uri = req.module_uri('Registration')
        #organization_id_value = record['organization_id']
        #organization_id = organization_id_value.value()
        #if organization_id:
        #    organizations = self._module('Organizations')
        #    organization_record = organizations.record(req, organization_id_value)
        #    organization = organization_record['name'].value()
        #else:
        #    organization = None
        uid = record['uid'].value()
        role_ids = self._module('RoleUsers').user_role_ids(uid)
        role_members_module = self._module('RoleSets')
        roles = []
        Roles = self.Roles()
        for role_id in role_ids:
            role = Roles[role_id]
            for member_id in role_members_module.included_role_ids(role):
                r = Roles[member_id]
                if r not in roles:
                    roles.append(r)
        return dict(login=login, name=record['user'].value(), uid=uid,
                    uri=uri, email=record['email'].value(), data=record, roles=roles,
                    state=record['state'].value(), lang=record['lang'].value(),
                    #organization_id=organization_id, organization=organization)
                    )

    def _make_user(self, kwargs):
        return self.User(**kwargs)

    def user(self, req, login=None, uid=None):
        """Return a user for given login name or user id.

        Arguments:
          login -- login name of the user as a string.
          uid -- unique identifier of the user as integer.

        Only one of 'uid' or 'login' may be passed (not None).  Argument 'login' may also be passed
        as positional (its position is guaranteed to remain).

        Returns a 'User' instance (defined in request.py) or None.

        """
        # Get the user data from db
        if login is not None and uid is None:
            row = self._data.get_row(login=login)
        elif uid is not None and login is None:
            row = self._data.get_row(uid=uid)
        else:
            raise Exception("Invalid 'user()' arguments.")
        if row is None:
            return None
        # Convert user data into a User instance
        kwargs = self._user_arguments(req, row['login'].value(), row)
        user = self._make_user(kwargs)
        return user

    def find_user(self, req, query):
        """Return the user record for given uid, login or email address (for password reminder).

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

    def find_users(self, req, email=None, state=None, role=None):
        """Return a list of 'User' instances corresponding to given criteria.

        Arguments:

          req -- wiking request
          email -- if not 'None', only users registered with given e-mail
            address (string) are returned
          state -- if not 'None', only users with the given state (one of the
            state string codes) are returned
          role -- if not 'None', only users belonging to the given role ('Role'
            instance) are returned

        If all the criteria arguments are 'None', all users are returned.

        """
        if role is not None:
            role_user_ids = self._module('RoleUsers').user_ids(role)
        def make_user(row):
            if role is not None and row['uid'].value() not in role_user_ids:
                return None
            kwargs = self._user_arguments(req, row['login'].value(), row)
            return self._make_user(kwargs)
        kwargs = {}
        if email is not None:
            kwargs['email'] = email
        if state is not None:
            kwargs['state'] = state
        users = [make_user(row) for row in self._data.get_rows(**kwargs)]
        if role is not None:
            users = [u for u in users if u is not None]
        return users

    def all_states(self):
        """Return information about all user states.

        The returned value is a sequence of tuples.  Each of the tuples is of
        the form '(CODE, TITLE,)' where CODE is the state code (as stored
        in the database data) and TITLE human readable state description.

        """
        return self.Spec._STATES
    
    def _generate_password(self):
        characters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ01233456789'
        random.seed()
        return string.join([random.choice(characters) for i in range(8)], '')

    def reset_password(self, user):
        """Reset md5 password for given 'User' instance and return the new password.

        May raise 'pd.DBException' if the database operation fails.
        
        """
        record = user.data()
        password = self._generate_password()
        value, error = pytis.data.Password(md5=True).validate(password, verify=password)
        assert error is None, error
        record.update(password=value.value(), last_password_change=now())
        return password

    def send_mail(self, role, *args, **kwargs):
        """Send mail to all active users of given C{role}.
        
        @type role: L{wiking.Role} or C{None}
        @param role: Destination role to send the mail to, all active users
          belonging to the role will receive the mail.  If C{None}, the mail is
          sent to all active users.
        @param args, kwargs: Just forwarded to L{wiking.send_mail} call.

        @note: The mail is sent only to active users, i.e. users with the state
          C{user}.  There is no way to sent bulk e-mail to inactive (i.e. new,
          disabled) users using this method.

        """
        assert role is None or isinstance(role, basestring)
        String = pd.String()
        condition = pd.EQ('state', pd.Value(String, 'user'))
        if role is not None:
            user_ids = self._module('RoleUsers').user_ids(role)
        user_rows = self._data.get_rows()
        import copy
        kwargs = copy.copy(kwargs)
        for row in user_rows:
            if role is not None and row['uid'].value() not in user_ids:
                continue
            email = row['email'].value()
            language = row['lang'].value()
            kwargs['lang'] = language
            send_mail(email, *args, **kwargs)

    
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
        condition = pd.AND(pd.NE('state', pd.Value(pd.String(), 'none')),
                           pd.EQ('regexpire', pd.Value(pd.DateTime(), None)))
        filters = ()
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

    WMI_SECTION = None #WikingManagementInterface.SECTION_USERS
    WMI_ORDER = 500

    _TITLE_COLUMN = 'name'


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
        def export(self, context):
            g = context.generator()
            req = context.req()
            controls = (
                g.label(_("Enter your login name or e-mail address")+':', id='query'),
                g.field(name='query', value=req.param('query'), id='query', tabindex=0, size=32),
                # Translators: Button name. Computer terminology. Use an appropriate term common
                # for submitting forms in a computer application.
                g.submit(_("Submit"), cls='submit'),)
            return g.form(controls, method='POST', cls='password-reminder-form') #+ \
                   #g.p(_(""))
    
    def _default_action(self, req, **kwargs):
        return 'view'

    def _action(self, req):
        if len(req.unresolved_path) > 1:
            return 'subpath'
        else:
            return super(Registration, self)._action(req)
        
    def action_subpath(self, req):
        user = req.user()
        if req.unresolved_path and req.unresolved_path[0] == user.login():
            del req.unresolved_path[0]
            return self._module('Users').action_subpath(req, user.data())
        else:
            raise Forbidden()
    RIGHTS_subpath = (Roles.USER,)

    def action_view(self, req):
        if req.user():
            return self._module('Users').action_view(req, req.user().data())
        elif req.param('command') == 'logout':
            return req.redirect('/')
        else:
            raise AuthenticationError()
    RIGHTS_view = (Roles.ANYONE,)
    
    def action_insert(self, req):
        if not cfg.appl.allow_registration:
            raise Forbidden()
        return self._module('Users').action_insert(req)
    RIGHTS_insert = (Roles.ANYONE,)
    
    def action_remind(self, req):
        title = _("Password reminder")
        query = req.param('query')
        if query:
            users_module = self._module('Users')
            if query.find('@') == -1:
                user = users_module.user(req, query)
            else:
                users = users_module.find_users(req, query)
                if not users:
                    user = None
                elif len(users) == 1:
                    user = users[0]
                else:
                    content = (lcg.p(_("Multiple user accounts found for given email address.")),
                               lcg.p(_("Please, select the account for which you want to remind:")),
                               lcg.ul([lcg.link(make_uri(req.uri(), action='remind',
                                                         query=u.login()), u.name())
                                       for u in users]))
                    return Document(title, content)
            if user:
                if cfg.password_storage == 'md5':
                    try:
                        password = users_module.reset_password(user)
                    except Exception, e:
                        req.message(unicode(e.exception()), type=req.ERROR)
                        return Document(title, self.ReminderForm())
                    # Translators: Credentials such as password...
                    intro_text = _("Your credentials were reset to:")
                else:
                    password = user.data()['password'].value()
                    # Translators: Credentials such as password...
                    intro_text = _("Your credentials are:")
                text = concat(
                    _("A password reminder request has been made at %(server_uri)s.",
                      server_uri=req.server_uri()),
                    '',
                    intro_text,
                    '   '+_("Login name") +': '+ user.login(),
                    '   '+_("Password") +': '+ password,
                    '',
                    _("We strongly recommend you change your password at nearest occassion, "
                      "since it has been exposed to an unsecure channel."),
                    '', separator='\n')
                err = send_mail(user.email(), title, text, lang=req.prefered_language())
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


class SessionLog(PytisModule):
    class Spec(Specification):
        # Translators: Heading for an overview when and how the user has accessed the application.
        title = _("Login History")
        help = _("History of successful login sessions and unsuccessful login attempts.")
        def fields(self): return (
            Field('log_id'),
            Field('session_id'),
            Field('uid', _('User'), codebook='Users'),
            # Translators: Login name.
            Field('login', _("Login")),
            # Translators: Form field saying whether the users attempt was succesful. Values are Yes/No.
            Field('success', _("Success")),
            # Translators: Table column heading. Time of the start of user session, followed by a date and time.
            Field('start_time', _("Start time"), type=DateTime(exact=True, not_null=True)),
            # Translators: Table column heading. The length of user session. Contains time.
            Field('duration', _("Duration"), type=Time(exact=True)),
            # Translators: Table column heading. Whether the account is active. Values are yes/no.
            Field('active', _("Active")),
            Field('ip_address', _("IP address")),
            # Translators: Internet name of the remote computer (computer terminology).
            Field('hostname', _("Hostname"), virtual=True, computer=computer(self._hostname)),
            # Translators: "User agent" is a generalized name for browser or more precisely the
            # software which produced the HTTP request (was used to access the website).
            Field('user_agent', _("User agent")),
            # Translators: Meaning where the user came from. Computer terminology. Do not translate
            # "HTTP" and if unsure, don't translate at all (it is a very technical term).
            Field('referer', _("HTTP Referer")))
        def _hostname(self, row, ip_address):
            try:
                return socket.gethostbyaddr(ip_address)[0]
            except:
                return None # _("Unknown")
        def row_style(self, row):
            if row['success'].value():
                return None
            else:
                return pp.Style(foreground='#f00')
        layout = ('start_time', 'duration', 'active', 'success', 'uid', 'login', 'ip_address',
                  'hostname', 'user_agent', 'referer')
        columns = ('start_time', 'duration', 'active', 'success', 'uid', 'login', 'ip_address')
        sorting = (('start_time', DESC),)
        
    def log(self, req, time, session_id, uid, login):
        row = self._data.make_row(session_id=session_id, uid=uid, login=login,
                                  success=session_id is not None, start_time=time,
                                  ip_address=req.header('X-Forwarded-For') or req.remote_host(),
                                  referer=req.header('Referer'),
                                  user_agent=req.header('User-Agent'))
        self._data.insert(row)
    WMI_SECTION = WikingManagementInterface.SECTION_USERS
    WMI_ORDER = 1000
    RIGHTS_view = (Roles.ADMIN,)
    RIGHTS_list = (Roles.ADMIN,)
