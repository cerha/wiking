# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2016 OUI Technology Ltd.
# Copyright (C) 2019-2022 Tomáš Cerha <t.cerha@gmail.com>
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

import os
import glob
import sqlalchemy

import pytis.data.gensqlalchemy as sql
import pytis.data
from pytis.data.dbdefs import and_, coalesce, func, ival, null, select, stype, sval
from .wiking_db import Base_CachingTable, CommonAccesRights

current_timestamp_0 = sqlalchemy.sql.functions.Function('current_timestamp', ival(0))

name_is_not_null = sql.SQLFlexibleValue('name_not_null', default=True)

upgrade_directory = os.path.abspath(os.path.join(os.path.realpath(os.path.dirname(__file__)),
                                                 '..', '..', '..', 'upgrade'))
upgrade_files = glob.glob(os.path.join(upgrade_directory, 'upgrade.*.sql'))
assert upgrade_files, 'No upgrade files found in upgrade directory: %s' % upgrade_directory
last_upgrade_script = max(upgrade_files)
version = int(last_upgrade_script[len(upgrade_directory) + len(os.sep) + 8:-4])


class CmsDatabaseVersion(sql.SQLTable):
    name = 'cms_database_version'
    fields = (sql.Column('version', pytis.data.Integer()),)
    init_columns = ('version',)
    init_values = ((version,),)


class CmsLanguages(CommonAccesRights, Base_CachingTable):
    name = 'cms_languages'
    fields = (sql.PrimaryColumn('lang_id', pytis.data.Serial()),
              sql.Column('lang', pytis.data.String(minlen=2, maxlen=2, not_null=True),
                         unique=True),
              )
    init_columns = ('lang',)
    init_values = (('en',),)


class CmsConfig(CommonAccesRights, Base_CachingTable):
    name = 'cms_config'
    fields = (sql.PrimaryColumn('site', pytis.data.String()),
              sql.Column('site_title', pytis.data.String()),
              sql.Column('site_subtitle', pytis.data.String()),
              sql.Column('allow_registration', pytis.data.Boolean(not_null=True), default=True),
              sql.Column('login_is_email', pytis.data.Boolean(not_null=True), default=False),
              sql.Column('registration_expiration', pytis.data.Integer()),
              sql.Column('force_https_login', pytis.data.Boolean(not_null=True), default=False),
              sql.Column('https_port', pytis.data.Integer()),
              sql.Column('smtp_server', pytis.data.String()),
              sql.Column('webmaster_address', pytis.data.String()),
              sql.Column('bug_report_address', pytis.data.String()),
              sql.Column('default_sender_address', pytis.data.String()),
              sql.Column('upload_limit', pytis.data.Integer()),
              sql.Column('session_expiration', pytis.data.Integer()),
              sql.Column('default_language', pytis.data.String(minlen=2, maxlen=2),
                         references=sql.a(sql.r.CmsLanguages.lang, onupdate='CASCADE')),
              sql.Column('theme_id', pytis.data.Integer(),
                         references=sql.r.CmsThemes),
              )
    init_columns = ('site',)
    init_values = (('*',),)


class CmsCountries(CommonAccesRights, sql.SQLTable):
    name = 'cms_countries'
    fields = (sql.PrimaryColumn('country_id', pytis.data.Serial(not_null=True)),
              sql.Column('country', pytis.data.String(minlen=2, maxlen=2, not_null=True),
                         unique=True),
              )
    init_columns = ('country',)
    init_values = [(country,) for country in (
        'AD', 'AE', 'AF', 'AG', 'AI', 'AL', 'AM', 'AO', 'AQ', 'AR', 'AS', 'AT',
        'AU', 'AW', 'AX', 'AZ', 'BA', 'BB', 'BD', 'BE', 'BF', 'BG', 'BH', 'BI',
        'BJ', 'BL', 'BM', 'BN', 'BO', 'BQ', 'BR', 'BS', 'BT', 'BV', 'BW', 'BY',
        'BZ', 'CA', 'CC', 'CD', 'CF', 'CG', 'CH', 'CI', 'CK', 'CL', 'CM', 'CN',
        'CO', 'CR', 'CU', 'CV', 'CW', 'CX', 'CY', 'CZ', 'DE', 'DJ', 'DK', 'DM',
        'DO', 'DZ', 'EC', 'EE', 'EG', 'EH', 'ER', 'ES', 'ET', 'FI', 'FJ', 'FK',
        'FM', 'FO', 'FR', 'GA', 'GB', 'GD', 'GE', 'GF', 'GG', 'GH', 'GI', 'GL',
        'GM', 'GN', 'GP', 'GQ', 'GR', 'GS', 'GT', 'GU', 'GW', 'GY', 'HK', 'HM',
        'HN', 'HR', 'HT', 'HU', 'ID', 'IE', 'IL', 'IM', 'IN', 'IO', 'IQ', 'IR',
        'IS', 'IT', 'JE', 'JM', 'JO', 'JP', 'KE', 'KG', 'KH', 'KI', 'KM', 'KN',
        'KP', 'KR', 'KW', 'KY', 'KZ', 'LA', 'LB', 'LC', 'LI', 'LK', 'LR', 'LS',
        'LT', 'LU', 'LV', 'LY', 'MA', 'MC', 'MD', 'ME', 'MF', 'MG', 'MH', 'MK',
        'ML', 'MM', 'MN', 'MO', 'MP', 'MQ', 'MR', 'MS', 'MT', 'MU', 'MV', 'MW',
        'MX', 'MY', 'MZ', 'NA', 'NC', 'NE', 'NF', 'NG', 'NI', 'NL', 'NO', 'NP',
        'NR', 'NU', 'NZ', 'OM', 'PA', 'PE', 'PF', 'PG', 'PH', 'PK', 'PL', 'PM',
        'PN', 'PR', 'PS', 'PT', 'PW', 'PY', 'QA', 'RE', 'RO', 'RS', 'RU', 'RW',
        'SA', 'SB', 'SC', 'SD', 'SE', 'SG', 'SH', 'SI', 'SJ', 'SK', 'SL', 'SM',
        'SN', 'SO', 'SR', 'SS', 'ST', 'SV', 'SX', 'SY', 'SZ', 'TC', 'TD', 'TF',
        'TG', 'TH', 'TJ', 'TK', 'TL', 'TM', 'TN', 'TO', 'TR', 'TT', 'TV', 'TW',
        'TZ', 'UA', 'UG', 'UM', 'US', 'UY', 'UZ', 'VA', 'VC', 'VE', 'VG', 'VI',
        'VN', 'VU', 'WF', 'WS', 'YE', 'YT', 'ZA', 'ZM', 'ZW',
    )]


class Roles(CommonAccesRights, Base_CachingTable):
    name = 'roles'
    fields = (sql.PrimaryColumn('role_id', pytis.data.Name()),
              sql.Column('name', pytis.data.String()),
              sql.Column('system', pytis.data.Boolean(not_null=True), default=False),
              sql.Column('auto', pytis.data.Boolean(not_null=True), default=False),
              )
    init_columns = ('role_id', 'system', 'auto',)
    init_values = (
        ('anyone', 't', 't'),
        ('authenticated', 't', 't'),
        ('owner', 't', 't'),
        ('user', 't', 't'),
        ('registered', 't', 't'),
        ('cms-user-admin', 't', 'f'),
        ('cms-crypto-admin', 't', 'f'),
        ('cms-content-admin', 't', 'f'),
        ('cms-settings-admin', 't', 'f'),
        ('cms-mail-admin', 't', 'f'),
        ('cms-style-admin', 't', 'f'),
        ('cms-admin', 't', 'f'),
    )


class RoleSets(CommonAccesRights, Base_CachingTable):
    name = 'role_sets'
    fields = (sql.PrimaryColumn('role_set_id', pytis.data.Serial(not_null=True)),
              sql.Column('role_id', pytis.data.Name(not_null=True),
                         references=sql.a(sql.r.Roles, onupdate='CASCADE', ondelete='CASCADE')),
              sql.Column('member_role_id', pytis.data.Name(not_null=True),
                         references=sql.a(sql.r.Roles, onupdate='CASCADE', ondelete='CASCADE')),
              )
    unique = (('role_id', 'member_role_id',),)
    init_columns = ('role_id', 'member_role_id',)
    init_values = (
        ('cms-admin', 'cms-user-admin'),
        ('cms-admin', 'cms-crypto-admin'),
        ('cms-admin', 'cms-content-admin'),
        ('cms-admin', 'cms-settings-admin'),
        ('cms-admin', 'cms-mail-admin'),
        ('cms-admin', 'cms-style-admin'),
    )


class ExpandedRole(sql.SQLPlFunction):
    name = 'expanded_role'
    arguments = (sql.Column('role_id_', pytis.data.Name()),)
    result_type = pytis.data.Name()
    multirow = True
    stability = 'stable'


class UnrelatedRoles(sql.SQLFunction):
    name = 'unrelated_roles'
    arguments = (sql.Column('role_id', pytis.data.Name()),)
    result_type = Roles
    multirow = True
    stability = 'stable'


class Users(CommonAccesRights, Base_CachingTable):
    name = 'users'
    fields = (sql.PrimaryColumn('uid', pytis.data.Serial(not_null=True)),
              sql.Column('login', pytis.data.String(maxlen=64, not_null=True), unique=True),
              sql.Column('password', pytis.data.String(not_null=True)),
              sql.Column('firstname',
                         pytis.data.String(not_null=name_is_not_null.value(globals()))),
              sql.Column('surname',
                         pytis.data.String(not_null=name_is_not_null.value(globals()))),
              sql.Column('nickname', pytis.data.String()),
              sql.Column('user_', pytis.data.String(not_null=True)),
              sql.Column('email', pytis.data.String(not_null=True)),
              sql.Column('phone', pytis.data.String()),
              sql.Column('address', pytis.data.String()),
              sql.Column('uri', pytis.data.String()),
              sql.Column('state', pytis.data.String(not_null=True), default='new'),
              sql.Column('last_password_change', pytis.data.DateTime(not_null=True)),
              sql.Column('since', pytis.data.DateTime(not_null=True),
                         default=func.timezone(sval('GMT'), current_timestamp_0)),
              sql.Column('lang', pytis.data.String(minlen=2, maxlen=2),
                         references=sql.a(sql.r.CmsLanguages.lang, onupdate='CASCADE',
                                          ondelete='SET NULL')),
              sql.Column('regexpire', pytis.data.DateTime()),
              sql.Column('regcode', pytis.data.String()),
              sql.Column('passexpire', pytis.data.DateTime()),
              sql.Column('passcode', pytis.data.String()),
              sql.Column('certauth', pytis.data.Boolean(not_null=True), default=False),
              sql.Column('note', pytis.data.String()),
              sql.Column('confirm', pytis.data.Boolean(not_null=True), default=False),
              sql.Column('gender', pytis.data.String(minlen=1, maxlen=1),
                         doc="[m]ale, [f]emale, NULL=unknown"),
              )
    access_rights = (('ALL', 'www-data',),)

    init_columns = ('login', 'password', 'firstname', 'surname', 'nickname', 'user_',
                    'email', 'state', 'last_password_change',)
    init_values = (('admin', 'plain:wiking', 'Wiking', 'Admin', 'Admin', 'Admin',
                    '-', 'enabled', '2012-01-01 00:00'),)


class CmsFInsertOrUpdateUser(sql.SQLPlFunction):
    name = 'cms_f_insert_or_update_user'
    arguments = (sql.Column('uid_', pytis.data.Integer()),
                 sql.Column('login_', pytis.data.String(maxlen=64)),
                 sql.Column('password_', pytis.data.String()),
                 sql.Column('firstname_', pytis.data.String()),
                 sql.Column('surname_', pytis.data.String()),
                 sql.Column('nickname_', pytis.data.String()),
                 sql.Column('user__', pytis.data.String()),
                 sql.Column('email_', pytis.data.String()),
                 sql.Column('phone_', pytis.data.String()),
                 sql.Column('address_', pytis.data.String()),
                 sql.Column('uri_', pytis.data.String()),
                 sql.Column('state_', pytis.data.String()),
                 sql.Column('last_password_change_', pytis.data.DateTime()),
                 sql.Column('since_', pytis.data.DateTime()),
                 sql.Column('lang_', pytis.data.String(minlen=2, maxlen=2)),
                 sql.Column('regexpire_', pytis.data.DateTime()),
                 sql.Column('regcode_', pytis.data.String()),
                 sql.Column('passexpire_', pytis.data.DateTime()),
                 sql.Column('passcode_', pytis.data.String()),
                 sql.Column('certauth_', pytis.data.Boolean()),
                 sql.Column('note_', pytis.data.String()),
                 sql.Column('confirm_', pytis.data.Boolean()),
                 sql.Column('gender_', pytis.data.String(minlen=1, maxlen=1)),
                 )
    result_type = None


class RoleMembers(CommonAccesRights, Base_CachingTable):
    name = 'role_members'
    fields = (sql.PrimaryColumn('role_member_id', pytis.data.Serial(not_null=True)),
              sql.Column('role_id', pytis.data.Name(not_null=True),
                         references=sql.a(sql.r.Roles, onupdate='CASCADE', ondelete='CASCADE')),
              sql.Column('uid', pytis.data.Integer(not_null=True),
                         references=sql.a(sql.r.Users, onupdate='CASCADE', ondelete='CASCADE')),
              )
    unique = (('role_id', 'uid',),)
    init_columns = ('role_id', 'uid')
    init_values = (('cms-admin', 1),)


class CmsVRoleMembers(CommonAccesRights, sql.SQLView):
    name = 'cms_v_role_members'

    @classmethod
    def query(cls):
        m = sql.t.RoleMembers.alias('m')
        r = sql.t.Roles.alias('r')
        u = sql.t.Users.alias('u')
        return select([m,
                       r.c.name.label('role_name'),
                       u.c.user_.label('user_name'),
                       u.c.login.label('user_login'),
                       ],
                      from_obj=[m.join(r, r.c.role_id == m.c.role_id).join(u, m.c.uid == u.c.uid)])
    insert_order = (RoleMembers,)
    update_order = (RoleMembers,)
    delete_order = (RoleMembers,)
    no_insert_columns = ('role_member_id',)


class AUserRoles(CommonAccesRights, sql.SQLTable):
    name = 'a_user_roles'
    fields = (sql.Column('uid', pytis.data.Integer(), index=True,
                         references=sql.a(sql.r.Users, onupdate='CASCADE', ondelete='CASCADE')),
              sql.Column('role_id', pytis.data.Name(not_null=True),
                         references=sql.a(sql.r.Roles, onupdate='CASCADE', ondelete='CASCADE')),
              )
    access_rights = (('ALL', 'www-data',),)


class UpdateUserRoles(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'update_user_roles'
    arguments = ()
    events = ()


class RoleSetsUpdateUserRolesTrigger(sql.SQLTrigger):
    name = 'role_sets_update_user_roles_trigger'
    table = RoleSets
    events = ('insert', 'update', 'delete',)
    each_row = False
    body = UpdateUserRoles


class RoleMembersUpdateUserRolesTrigger(sql.SQLTrigger):
    name = 'role_members_update_user_roles_trigger'
    table = RoleMembers
    events = ('insert', 'update', 'delete',)
    each_row = False
    body = UpdateUserRoles


class CmsFAllUserRoles(sql.SQLFunction):
    """Return all user's roles and their included roles.
    Both explicitly assigned and implicit roles (such as 'anyone') are considered."""
    name = 'cms_f_all_user_roles'
    arguments = (sql.Column('uid_', pytis.data.Integer()),)
    result_type = pytis.data.Name()
    multirow = True
    stability = 'stable'
    depends_on = (AUserRoles,)


class CmsFRoleMember(sql.SQLPlFunction):
    name = 'cms_f_role_member'
    arguments = (sql.Column('uid_', pytis.data.Integer()),
                 sql.Column('role_id_', pytis.data.Name()),)
    result_type = pytis.data.Boolean()
    stability = 'stable'


class RoleSetsCycleCheck(sql.SQLFunction):
    name = 'role_sets_cycle_check'
    arguments = ()
    result_type = pytis.data.Boolean()
    depends_on = (RoleSets,)


class RoleSetsTriggerAfter(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'role_sets_trigger_after'
    arguments = ()
    table = RoleSets
    position = 'after'
    events = ('insert', 'update', 'delete',)


class CmsSessions(CommonAccesRights, sql.SQLTable):
    name = 'cms_sessions'
    fields = (
        sql.PrimaryColumn('session_id', pytis.data.Serial(not_null=True)),
        sql.Column('session_key', pytis.data.String(not_null=True)),
        sql.Column('auth_type', pytis.data.String(not_null=True)),
        sql.Column('uid', pytis.data.Integer(not_null=True),
                   references=sql.a(sql.r.Users, ondelete='CASCADE')),
        sql.Column('last_access', pytis.data.DateTime()),
    )
    unique = (('uid', 'session_key',),)

class CmsSessionHistory(CommonAccesRights, sql.SQLTable):
    name = 'cms_session_history'
    fields = (
        sql.PrimaryColumn('session_id', pytis.data.Integer(not_null=True)),
        sql.Column('auth_type', pytis.data.String(not_null=True)),
        sql.Column('uid', pytis.data.Integer(not_null=True),
                   references=sql.a(sql.r.Users, ondelete='CASCADE')),
        sql.Column('start_time', pytis.data.DateTime(not_null=True)),
        sql.Column('end_time', pytis.data.DateTime()),
    )

class CmsUpdateSesionHistory(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'cms_update_session_history'
    arguments = ()
    events = ()

class CmsSessionsTrigger(sql.SQLTrigger):
    name = 'cms_sessions_trigger'
    table = CmsSessions
    events = ('insert', 'delete',)
    each_row = True
    body = CmsUpdateSesionHistory

class CmsVSessionHistory(CommonAccesRights, sql.SQLView):
    name = 'cms_v_session_history'
    @classmethod
    def query(cls):
        h = sql.t.CmsSessionHistory.alias('h')
        u = sql.t.Users.alias('u')
        return select(list(h.c) + [
            u.c.login,
            u.c.user_.label('user'),
            sqlalchemy.cast(h.c.end_time == null, sqlalchemy.Boolean()).label('active'),
            (coalesce(h.c.end_time, func.now()) - h.c.start_time).label('duration'),
        ], from_obj=[h.outerjoin(u, u.c.uid == h.c.uid)])


class CmsLoginFailures(CommonAccesRights, sql.SQLTable):
    name = 'cms_login_failures'
    fields = (
        sql.PrimaryColumn('failure_id', pytis.data.Serial(not_null=True)),
        sql.Column('timestamp', pytis.data.DateTime(not_null=True)),
        sql.Column('login', pytis.data.String(not_null=True)),
        sql.Column('auth_type', pytis.data.String(not_null=True)),
        sql.Column('ip_address', pytis.data.String(not_null=True)),
        sql.Column('user_agent', pytis.data.String()),
    )



class CmsPages(CommonAccesRights, Base_CachingTable):
    name = 'cms_pages'
    fields = (sql.PrimaryColumn('page_id', pytis.data.Serial(not_null=True)),
              sql.Column('site', pytis.data.String(not_null=True),
                         references=sql.a(sql.r.CmsConfig.site,
                                          onupdate='CASCADE', ondelete='CASCADE')),
              sql.Column('kind', pytis.data.String(not_null=True)),
              sql.Column('identifier', pytis.data.String(not_null=True)),
              sql.Column('parent', pytis.data.Integer(), references=sql.r.CmsPages),
              sql.Column('modname', pytis.data.String()),
              sql.Column('menu_visibility', pytis.data.String(not_null=True)),
              sql.Column('foldable', pytis.data.Boolean(not_null=False)),
              sql.Column('ord', pytis.data.Integer(not_null=True)),
              sql.Column('tree_order', pytis.data.String()),
              sql.Column('owner', pytis.data.Integer(), references=sql.r.Users),
              sql.Column('read_role_id', pytis.data.Name(not_null=True), default='anyone',
                         references=sql.a(sql.r.Roles, onupdate='CASCADE')),
              sql.Column('write_role_id', pytis.data.Name(not_null=True),
                         default='cms-content-admin',
                         references=sql.a(sql.r.Roles, onupdate='CASCADE', ondelete='SET DEFAULT')),
              )
    unique = (('identifier', 'site',),)

    @property
    def index_columns(self):
        parent = sqlalchemy.func.coalesce(sql.c.CmsPages.parent, ival(0))
        return (sql.a('ord', parent, 'site', 'kind', unique=True),)


class CmsPagesUpdateOrder(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'cms_pages_update_order'
    table = CmsPages
    events = ('insert', 'update',)
    position = 'before'


class CmsPageTexts(CommonAccesRights, Base_CachingTable):
    name = 'cms_page_texts'
    fields = (sql.Column('page_id', pytis.data.Integer(not_null=True),
                         references=sql.a(sql.r.CmsPages, ondelete='CASCADE')),
              sql.Column('lang', pytis.data.String(minlen=2, maxlen=2, not_null=True),
                         references=sql.a(sql.r.CmsLanguages.lang, onupdate='CASCADE')),
              sql.Column('published', pytis.data.Boolean(not_null=True), default=True),
              sql.Column('parents_published', pytis.data.Boolean(not_null=True)),
              sql.Column('creator', pytis.data.Integer(not_null=True), references=sql.r.Users),
              sql.Column('created', pytis.data.DateTime(not_null=True), default=func.now()),
              sql.Column('published_since', pytis.data.DateTime()),
              sql.Column('title', pytis.data.String(not_null=True)),
              sql.Column('description', pytis.data.String()),
              sql.Column('content', pytis.data.String()),
              sql.Column('_title', pytis.data.String()),
              sql.Column('_description', pytis.data.String()),
              sql.Column('_content', pytis.data.String()),
              )
    unique = (('page_id', 'lang',),)


class CmsPageTreeOrder(sql.SQLFunction):
    name = 'cms_page_tree_order'
    arguments = (sql.Column('page_id', pytis.data.Integer()),)
    result_type = pytis.data.String()
    depends_on = (CmsPages,)
    stability = 'stable'


class CmsPageTreePublished(sql.SQLFunction):
    name = 'cms_page_tree_published'
    arguments = (sql.Column('page_id', pytis.data.Integer()),
                 sql.Column('lang', pytis.data.String()),)
    result_type = pytis.data.Boolean()
    depends_on = (CmsPages, CmsPageTexts)
    stability = 'stable'


class CmsVPages(CommonAccesRights, sql.SQLView):
    name = 'cms_v_pages'

    @classmethod
    def query(cls):
        p = sql.t.CmsPages.alias('p')
        lang = sql.t.CmsLanguages.alias('l')
        t = sql.t.CmsPageTexts.alias('t')
        cu = sql.t.Users.alias('cu')
        ou = sql.t.Users.alias('ou')
        return select([(stype(p.c.page_id) + sval('.') + lang.c.lang).label('page_key'),
                       p.c.site, p.c.kind, lang.c.lang,
                       p.c.page_id, p.c.identifier, p.c.parent, p.c.modname,
                       p.c.menu_visibility, p.c.foldable, p.c.ord, p.c.tree_order,
                       p.c.owner, p.c.read_role_id, p.c.write_role_id,
                       coalesce(t.c.published, False).label('published'),
                       coalesce(t.c.parents_published, False).label('parents_published'),
                       t.c.published_since,
                       t.c.creator, t.c.created,
                       coalesce(t.c.title, p.c.identifier).label('title_or_identifier'),
                       t.c.title, t.c.description, t.c.content, t.c._title,
                       t.c._description, t.c._content,
                       cu.c.login.label('creator_login'),
                       cu.c.user_.label('creator_name'),
                       ou.c.login.label('owner_login'),
                       ou.c.user_.label('owner_name'),
                       ],
                      from_obj=[p.
                                join(lang, ival(1) == 1).  # cross join
                                outerjoin(t, and_(t.c.page_id == p.c.page_id,
                                                  t.c.lang == lang.c.lang)).
                                outerjoin(cu, cu.c.uid == t.c.creator).
                                outerjoin(ou, ou.c.uid == p.c.owner)
                                ],
                      )

    def on_insert(self):
        return ("""(
     insert into cms_pages (site, kind, identifier, parent, modname,
                            owner, read_role_id, write_role_id,
                            menu_visibility, foldable, ord)
     values (new.site, new.kind, new.identifier, new.parent, new.modname,
             new.owner, new.read_role_id, new.write_role_id,
             new.menu_visibility, new.foldable, new.ord);
     update cms_pages set tree_order = cms_page_tree_order(page_id)
            where site = new.site and
                  (identifier = new.identifier or tree_order != cms_page_tree_order(page_id));
     insert into cms_page_texts (page_id, lang, published, parents_published,
                                 creator, created, published_since,
                                 title, description, content,
                                 _title, _description, _content)
     select page_id, new.lang, new.published, cms_page_tree_published(new.parent, new.lang),
            new.creator, new.created, new.published_since,
            new.title, new.description, new.content,
            new._title, new._description, new._content
     from cms_pages where identifier=new.identifier and site=new.site and kind=new.kind
     returning page_id ||'.'|| lang, null::text, null::text,
       lang, page_id, null::text, null::int, null::text, null::text, null::boolean,
       null::int, null::text, null::int, null::name, null::name,
       published, parents_published, published_since, creator,
       created, title, title, description, content, _title,
       _description, _content, null::varchar(64), null::text, null::varchar(64), null::text;
        )""",)

    def on_update(self):
        return ("""(
    -- Set the ord=0 first to work around the problem with recursion order in
    -- cms_pages_update_order trigger (see the comment there for more info).
    update cms_pages set ord=0 where cms_pages.page_id = old.page_id and new.ord < old.ord;
    update cms_pages set
        site = new.site,
        kind = new.kind,
        identifier = new.identifier,
        parent = new.parent,
        modname = new.modname,
        owner = new.owner,
        read_role_id = new.read_role_id,
        write_role_id = new.write_role_id,
        menu_visibility = new.menu_visibility,
        foldable = new.foldable,
        ord = new.ord
    where cms_pages.page_id = old.page_id;
    update cms_pages set tree_order = cms_page_tree_order(page_id)
           where site = new.site and tree_order != cms_page_tree_order(page_id);
    update cms_page_texts set
        published = new.published,
        title = new.title,
        description = new.description,
        creator = new.creator,
        created = new.created,
        published_since = new.published_since,
        content = new.content,
        _title = new._title,
        _description = new._description,
        _content = new._content
    where page_id = old.page_id and lang = new.lang;
    insert into cms_page_texts (page_id, lang, published, parents_published,
                                creator, created, published_since,
                                title, description, content,
                                _title, _description, _content)
           select old.page_id, new.lang, new.published,
                  cms_page_tree_published(new.parent, new.lang),
                  new.creator, new.created, new.published_since,
                  new.title, new.description, new.content,
                  new._title, new._description, new._content
           where new.lang not in (select lang from cms_page_texts where page_id=old.page_id)
                 and coalesce(new.title, new.description, new.content,
                              new._title, new._description, new._content) is not null;
    update cms_page_texts t set parents_published = x.parents_published
        from (select page_id, lang, cms_page_tree_published(parent, lang) as parents_published
              from cms_pages join cms_page_texts using (page_id)) as x
        where t.page_id=x.page_id and t.lang=x.lang
              and t.parents_published != x.parents_published;
    )""",)
    delete_order = (CmsPages,)
    depends_on = (CmsPageTreePublished,)


class CmsPageHistory(CommonAccesRights, sql.SQLTable):
    name = 'cms_page_history'
    fields = (sql.PrimaryColumn('history_id', pytis.data.Serial(not_null=True)),
              sql.Column('page_id', pytis.data.Integer(not_null=True)),
              sql.Column('lang', pytis.data.String(minlen=2, maxlen=2, not_null=True)),
              sql.Column('uid', pytis.data.Integer(not_null=True), references=sql.r.Users),
              sql.Column('timestamp', pytis.data.DateTime(not_null=True)),
              sql.Column('content', pytis.data.String()),
              sql.Column('comment', pytis.data.String()),
              sql.Column('inserted_lines', pytis.data.Integer(not_null=True)),
              sql.Column('changed_lines', pytis.data.Integer(not_null=True)),
              sql.Column('deleted_lines', pytis.data.Integer(not_null=True)),
              )
    foreign_keys = (sql.a(('page_id', 'lang',),
                          (sql.r.CmsPageTexts.page_id, sql.r.CmsPageTexts.lang,),
                          ondelete='cascade'),)


class CmsVPageHistory(CommonAccesRights, sql.SQLView):
    name = 'cms_v_page_history'

    @classmethod
    def query(cls):
        h = sql.t.CmsPageHistory.alias('h')
        u = sql.t.Users.alias('u')
        return select([h,
                       u.c.user_.label('user'),
                       u.c.login,
                       (stype(h.c.page_id) + sval('.') + h.c.lang).label('page_key'),
                       (stype(h.c.inserted_lines) + sval(' / ') +
                        stype(h.c.changed_lines) + sval(' / ') +
                        stype(h.c.deleted_lines)).label('changes')],
                      from_obj=[h.join(u, h.c.uid == u.c.uid)])
    insert_order = (CmsPageHistory,)


class CmsPageExcerpts(sql.SQLTable):
    """Excerpts from CMS pages.
    Currently serving for printing parts of e-books in Braille.
    """
    name = 'cms_page_excerpts'
    fields = (sql.PrimaryColumn('id', pytis.data.Serial(not_null=True)),
              sql.Column('page_id', pytis.data.Integer(),
                         references=sql.a(sql.r.CmsPages, onupdate='CASCADE', ondelete='CASCADE')),
              sql.Column('lang', pytis.data.String(not_null=True)),
              sql.Column('title', pytis.data.String(not_null=True)),
              sql.Column('content', pytis.data.String(not_null=True)),
              )
    access_rights = (('ALL', 'www-data',),)

#


class CmsPageAttachments(CommonAccesRights, sql.SQLTable):
    name = 'cms_page_attachments'
    fields = (sql.PrimaryColumn('attachment_id', pytis.data.Serial(not_null=True)),
              sql.Column('page_id', pytis.data.Integer(not_null=True),
                         references=sql.a(sql.r.CmsPages, ondelete='CASCADE')),
              sql.Column('filename', pytis.data.String(not_null=True)),
              sql.Column('mime_type', pytis.data.String(not_null=True)),
              sql.Column('bytesize', pytis.data.Integer(not_null=True)),
              sql.Column('created', pytis.data.DateTime(not_null=True)),
              sql.Column('last_modified', pytis.data.DateTime(not_null=True)),
              sql.Column('image', pytis.data.Binary(),
                         doc="Resized image"),
              sql.Column('image_width', pytis.data.Integer(),
                         doc="Resized image pixel width."),
              sql.Column('image_height', pytis.data.Integer(),
                         doc="Resized image pixel height."),
              sql.Column('thumbnail', pytis.data.Binary()),
              sql.Column('thumbnail_size', pytis.data.String(),
                         doc="Desired thumbnail size - small/medium/large"),
              sql.Column('thumbnail_width', pytis.data.Integer(),
                         doc="Thumbnail pixel width."),
              sql.Column('thumbnail_height', pytis.data.Integer(),
                         doc="Thumbnail pixel height."),
              sql.Column('in_gallery', pytis.data.Boolean(not_null=True), default=False),
              sql.Column('listed', pytis.data.Boolean(not_null=True), default=False),
              sql.Column('author', pytis.data.String()),
              sql.Column('location', pytis.data.String()),
              sql.Column('width', pytis.data.Integer()),
              sql.Column('height', pytis.data.Integer()),
              )
    unique = (('filename', 'page_id',),)


class CmsPageAttachmentTexts(CommonAccesRights, sql.SQLTable):
    name = 'cms_page_attachment_texts'
    fields = (sql.Column('attachment_id', pytis.data.Integer(not_null=True),
                         references=sql.a(sql.r.CmsPageAttachments, ondelete='CASCADE',
                                          initially='DEFERRED')),
              sql.Column('lang', pytis.data.String(minlen=2, maxlen=2, not_null=True),
                         references=sql.a(sql.r.CmsLanguages.lang,
                                          onupdate='CASCADE', ondelete='CASCADE')),
              sql.Column('title', pytis.data.String()),
              sql.Column('description', pytis.data.String()),
              )
    unique = (('attachment_id', 'lang',),)


class CmsVPageAttachments(CommonAccesRights, sql.SQLView):
    name = 'cms_v_page_attachments'

    @classmethod
    def query(cls):
        a = sql.t.CmsPageAttachments.alias('a')
        lang = sql.t.CmsLanguages.alias('l')
        t = sql.t.CmsPageAttachmentTexts.alias('t')
        return select([(stype(a.c.attachment_id) + sval('.') + lang.c.lang).label('attachment_key'),
                       lang.c.lang,
                       a.c.attachment_id, a.c.page_id, t.c.title, t.c.description,
                       a.c.filename, a.c.mime_type, a.c.bytesize,
                       a.c.image, a.c.image_width, a.c.image_height,
                       a.c.thumbnail, a.c.thumbnail_size, a.c.thumbnail_width, a.c.thumbnail_height,
                       a.c.in_gallery, a.c.listed, a.c.author, a.c.location, a.c.width, a.c.height,
                       a.c.created, a.c.last_modified],
                      from_obj=[a.join(lang, ival(1) == 1).  # cross join
                                outerjoin(t, and_(a.c.attachment_id == t.c.attachment_id,
                                                  lang.c.lang == t.c.lang))]
                      )

    def on_insert(self):
        return ("""(
    insert into cms_page_attachment_texts (attachment_id, lang, title, description)
           select new.attachment_id, new.lang, new.title, new.description
           where new.title is not null OR new.description is not null;
    insert into cms_page_attachments (attachment_id, page_id, filename, mime_type, bytesize,
                                 image, image_width, image_height,
                                 thumbnail, thumbnail_size, thumbnail_width, thumbnail_height,
                                 in_gallery, listed, author, "location", width, height,
                                 created, last_modified)
           values (new.attachment_id, new.page_id, new.filename, new.mime_type,
                   new.bytesize, new.image, new.image_width, new.image_height,
                   new.thumbnail, new.thumbnail_size,
                   new.thumbnail_width, new.thumbnail_height, new.in_gallery, new.listed,
                   new.author, new."location", new.width, new.height,
                   new.created, new.last_modified)
           returning
             attachment_id ||'.'|| (select max(lang) from cms_page_attachment_texts
                                    where attachment_id=attachment_id), null::char(2),
             attachment_id, page_id, null::text, null::text,
             filename, mime_type, bytesize, image, image_width, image_height, thumbnail,
             thumbnail_size, thumbnail_width, thumbnail_height, in_gallery, listed,
             author, "location", width, height, created, last_modified
        )""",)

    def on_update(self):
        return ("""(
    update cms_page_attachments set
           page_id = new.page_id,
           filename = new.filename,
           mime_type = new.mime_type,
           bytesize = new.bytesize,
           image = new.image,
           image_width = new.image_width,
           image_height = new.image_height,
           thumbnail = new.thumbnail,
           thumbnail_size = new.thumbnail_size,
           thumbnail_width = new.thumbnail_width,
           thumbnail_height = new.thumbnail_height,
           listed = new.listed,
           in_gallery = new.in_gallery,
           author = new.author,
           "location" = new."location",
           width = new.width,
           height = new.height,
           created = new.created,
           last_modified = new.last_modified
           where attachment_id = old.attachment_id;
    update cms_page_attachment_texts set
           title=new.title,
           description=new.description
           where attachment_id = old.attachment_id and lang = old.lang;
    insert into cms_page_attachment_texts (attachment_id, lang, title, description)
           select new.attachment_id, new.lang, new.title, new.description
           where old.attachment_id not in
             (select attachment_id from cms_page_attachment_texts where lang=old.lang);
        )""",)

    def on_delete(self):
        return ("""(
     delete from cms_page_attachments where attachment_id = old.attachment_id;
        )""",)


class CmsAttachmentsAfterUpdateTrigger(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'cms_attachments_after_update_trigger'
    table = CmsPageAttachments
    events = ('update',)
    position = 'after'

#


class CmsPublications(CommonAccesRights, sql.SQLTable):
    """bibliographic data of the original (paper) books"""
    name = 'cms_publications'
    fields = (
        sql.Column('page_id', pytis.data.Integer(not_null=True), unique=True,
                   references=sql.a(sql.r.CmsPages, ondelete='CASCADE')),
        sql.Column('author', pytis.data.String(not_null=True),
                   doc="creator(s) of the original work; full name(s), one name per line"),
        sql.Column('contributor', pytis.data.String(),
                   doc=("creator(s) of the original work with less significant "
                        "role than author(s); full name(s), one name per line")),
        sql.Column('illustrator', pytis.data.String(),
                   doc=("author(s) of illustrations in the original work; "
                        "full name(s), one name per line")),
        sql.Column('publisher', pytis.data.String(),
                   doc="full name of the publisher"),
        sql.Column('published_year', pytis.data.Integer(),
                   doc="year published"),
        sql.Column('edition', pytis.data.Integer(),
                   doc="first, second, ..."),
        sql.Column('original_isbn', pytis.data.String(),
                   doc=("ISBN identifier of the original work; if not null, the "
                        "publication is a work derived from it and fields author, "
                        "contributor, illustrator, publisher, published_year and "
                        "edition relate to the original work")),
        sql.Column('isbn', pytis.data.String(),
                   'ISBN of this publication if it has one assigned'),
        sql.Column('uuid', pytis.data.String(),
                   'Universally Unique Identifier if ISBN is not assigned'),
        sql.Column('adapted_by', pytis.data.String(),
                   doc=("people or organization(s), who created this digital "
                        "publication if these are not already mentioned in the "
                        "above fields; full name(s), one name per line")),
        sql.Column('adapted_for', pytis.data.String(),
                   doc=("organization or project for which this adaptation of the original "
                        "work into a digital publication has been done.")),
        sql.Column('cover_image', pytis.data.Integer(),
                   references=sql.a(sql.r.CmsPageAttachments, ondelete='SET NULL')),
        sql.Column('copyright_notice', pytis.data.String()),
        sql.Column('notes', pytis.data.String(),
                   doc="any other additional info, such as translator(s), reviewer(s) etc."),
        sql.Column('download_role_id', pytis.data.Name(),
                   references=sql.a(sql.r.Roles, onupdate='CASCADE'),
                   doc="role allowed to download the offline version of the publication."),
    )


class CmsVPublications(CommonAccesRights, sql.SQLView):
    name = 'cms_v_publications'

    @classmethod
    def query(cls):
        pages = sql.t.CmsVPages.alias('pages')
        publications = sql.t.CmsPublications.alias('publications')
        attachments = sql.t.CmsPageAttachments.alias('attachments')
        return select(([pages.c.page_id] +
                       cls._exclude(pages, publications.c.page_id) +
                       cls._exclude(publications, publications.c.page_id) +
                       [attachments.c.filename.label('cover_image_filename')]),
                      from_obj=[pages.
                                join(publications, publications.c.page_id == pages.c.page_id).
                                outerjoin(attachments,
                                          attachments.c.attachment_id == publications.c.cover_image)
                                ])

    def on_insert(self):
        def returning_column(c):
            if c.name == 'page_id':
                return c.name
            elif c.name == 'page_key':
                return ("page_id ||'.'|| (select min(lang) from cms_page_texts "
                        "where page_id=cms_publications.page_id)")
            elif c.name.endswith('_role_id'):
                return 'null::name'
            else:
                casted = str(sqlalchemy.cast(null, c.type))
                # force serial to int and varchar to text
                return casted.replace('SERIAL', 'INTEGER').replace('VARCHAR)', 'TEXT)')
        vpages = sql.t.CmsVPages
        page_columns = [c.name for c in vpages.c if c.name not in ('page_id', 'page_key')]
        publications = sql.t.CmsPublications
        return [sqlalchemy.text(q) for q in (
            "insert into cms_v_pages (%s) values (%s)" % (
                ', '.join(page_columns),
                ', '.join(['new.' + cname for cname in page_columns]),
            ),
            "insert into cms_publications (%s) "
            "select %s from cms_pages "
            "where identifier=new.identifier and site=new.site and kind=new.kind "
            "returning %s" % (
                ', '.join(c.name for c in publications.c),
                ', '.join([c.name if c.name in vpages.c else 'new.' + c.name
                           for c in publications.c]),
                ', '.join([returning_column(c) for c in self.c]),
            )
        )]

    def on_update(self):
        def update_columns(table):
            return ', '.join('%s = new.%s' % (c.name, c.name) for c in table.c
                             if c.name not in ('page_id', 'page_key'))
        return [sqlalchemy.text(q) for q in (
            "update cms_v_pages set %s where page_id = old.page_id and lang = old.lang" % (
                update_columns(sql.t.CmsVPages),),
            "update cms_publications set %s where page_id = old.page_id;" % (
                update_columns(sql.t.CmsPublications),)
        )]

    def on_delete(self):
        return ("delete from cms_pages where page_id = old.page_id",)

    update_order = (CmsVPages, CmsPublications)
    delete_order = (CmsPages,)


class CmsPublicationLanguages(CommonAccesRights, sql.SQLTable):
    """list of content languages available for given publication"""
    name = 'cms_publication_languages'
    fields = (sql.Column('page_id', pytis.data.Integer(not_null=True),
                         references=sql.a(sql.r.CmsPublications.page_id, ondelete='CASCADE')),
              sql.Column('lang', pytis.data.String(not_null=True),
                         doc="language code"),
              )
    unique = (('page_id', 'lang',),)


class CmsPublicationIndexes(CommonAccesRights, sql.SQLTable):
    """list of indexes available for given publication"""
    name = 'cms_publication_indexes'
    fields = (sql.PrimaryColumn('index_id', pytis.data.Serial(not_null=True)),
              sql.Column('page_id', pytis.data.Integer(not_null=True),
                         references=sql.a(sql.r.CmsPublications.page_id, ondelete='CASCADE')),
              sql.Column('title', pytis.data.String(not_null=True)),
              )
    unique = (('page_id', 'title',),)


class CmsPublicationExports(CommonAccesRights, sql.SQLTable):
    """Exported publication versions."""
    name = 'cms_publication_exports'
    fields = (
        sql.PrimaryColumn('export_id', pytis.data.Serial()),
        sql.Column('page_id', pytis.data.Integer(not_null=True),
                   references=sql.a(sql.r.CmsPublications.page_id, ondelete='CASCADE')),
        sql.Column('lang', pytis.data.String(minlen=2, maxlen=2, not_null=True),
                   references=sql.a(sql.r.CmsLanguages.lang,
                                    onupdate='CASCADE', ondelete='CASCADE')),
        sql.Column('format', pytis.data.String(not_null=True)),
        sql.Column('version', pytis.data.String(not_null=True)),
        sql.Column('timestamp', pytis.data.DateTime(not_null=True)),
        sql.Column('public', pytis.data.Boolean(not_null=True), default=True),
        sql.Column('bytesize', pytis.data.Integer(not_null=True)),
        sql.Column('notes', pytis.data.String()),
        sql.Column('log', pytis.data.String()),
    )
    unique = (('page_id', 'lang', 'format', 'version',),)


class CmsVPublicationExports(CommonAccesRights, sql.SQLView):
    name = 'cms_v_publication_exports'

    @classmethod
    def query(cls):
        exports = sql.t.CmsPublicationExports.alias('e')
        return select(list(exports.c) +
                      [(stype(exports.c.page_id) + sval('.') + exports.c.lang).label('page_key')],
                      from_obj=exports)
    insert_order = (CmsPublicationExports,)
    update_order = (CmsPublicationExports,)
    delete_order = (CmsPublicationExports,)


class CmsNews(CommonAccesRights, Base_CachingTable):
    name = 'cms_news'
    fields = (sql.PrimaryColumn('news_id', pytis.data.Serial(not_null=True)),
              sql.Column('page_id', pytis.data.Integer(not_null=True),
                         references=sql.a(sql.r.CmsPages, ondelete='CASCADE')),
              sql.Column('lang', pytis.data.String(minlen=2, maxlen=2, not_null=True),
                         references=sql.a(sql.r.CmsLanguages.lang, onupdate='CASCADE')),
              sql.Column('author', pytis.data.Integer(not_null=True),
                         references=sql.r.Users),
              sql.Column('timestamp', pytis.data.DateTime(not_null=True), default=func.now()),
              sql.Column('title', pytis.data.String(not_null=True)),
              sql.Column('content', pytis.data.String(not_null=True)),
              sql.Column('days_displayed', pytis.data.Integer(not_null=True)),
              )


class CmsVNews(CommonAccesRights, sql.SQLView):
    name = 'cms_v_news'

    @classmethod
    def query(cls):
        n = sql.t.CmsNews.alias('n')
        u = sql.t.Users.alias('u')
        return select([n,
                       u.c.user_.label('author_name'),
                       u.c.login.label('author_login'),
                       ],
                      from_obj=[n.join(u, n.c.author == u.c.uid)])
    insert_order = (CmsNews,)
    update_order = (CmsNews,)
    delete_order = (CmsNews,)
    no_insert_columns = ('news_id',)


class CmsRecentTimestamp(sql.SQLFunction):
    """Return true if `ts' is not older than `max_days' days.  Needed for a pytis
    filtering condition (FunctionCondition is currently too simple to express
    this directly).
    """
    name = 'cms_recent_timestamp'
    arguments = (sql.Column('ts', pytis.data.DateTime()),
                 sql.Column('max_days', pytis.data.Integer()),)
    result_type = pytis.data.Boolean()
    stability = 'stable'

    def body(self):
        """Return true if `ts' is not older than `max_days' days.  Needed for a pytis
        filtering condition (FunctionCondition is currently too simple to express
        this directly).
        """
        return 'select (current_date - $1::date) < $2'


class CmsPlanner(CommonAccesRights, Base_CachingTable):
    name = 'cms_planner'
    fields = (sql.PrimaryColumn('planner_id', pytis.data.Serial(not_null=True)),
              sql.Column('page_id', pytis.data.Integer(not_null=True),
                         references=sql.a(sql.r.CmsPages, ondelete='CASCADE')),
              sql.Column('lang', pytis.data.String(minlen=2, maxlen=2, not_null=True),
                         references=sql.a(sql.r.CmsLanguages.lang, onupdate='CASCADE')),
              sql.Column('author', pytis.data.Integer(not_null=True),
                         references=sql.r.Users),
              sql.Column('timestamp', pytis.data.DateTime(not_null=True), default=func.now()),
              sql.Column('start_date', pytis.data.Date(not_null=True)),
              sql.Column('end_date', pytis.data.Date()),
              sql.Column('title', pytis.data.String(not_null=True)),
              sql.Column('content', pytis.data.String(not_null=True)),
              )


class CmsVPlanner(CommonAccesRights, sql.SQLView):
    name = 'cms_v_planner'

    @classmethod
    def query(cls):
        p = sql.t.CmsPlanner.alias('p')
        u = sql.t.Users.alias('u')
        return select([p,
                       u.c.user_.label('author_name'),
                       u.c.login.label('author_login'),
                       ],
                      from_obj=[p.join(u, p.c.author == u.c.uid)])
    insert_order = (CmsPlanner,)
    update_order = (CmsPlanner,)
    delete_order = (CmsPlanner,)
    no_insert_columns = ('planner_id',)


class CmsNewsletters(CommonAccesRights, Base_CachingTable):
    name = 'cms_newsletters'
    fields = (
        sql.PrimaryColumn('newsletter_id', pytis.data.Serial(not_null=True)),
        sql.Column('page_id', pytis.data.Integer(not_null=True),
                   references=sql.a(sql.r.CmsPages, ondelete='CASCADE')),
        sql.Column('lang', pytis.data.String(minlen=2, maxlen=2, not_null=True),
                   references=sql.a(sql.r.CmsLanguages.lang, onupdate='CASCADE')),
        sql.Column('title', pytis.data.String(not_null=True)),
        sql.Column('image', pytis.data.Binary(not_null=True)),
        sql.Column('image_width', pytis.data.Integer(not_null=True)),
        sql.Column('image_height', pytis.data.Integer(not_null=True)),
        sql.Column('description', pytis.data.String(not_null=True)),
        sql.Column('sender', pytis.data.String(not_null=True)),
        sql.Column('address', pytis.data.String(not_null=True)),
        sql.Column('read_role_id', pytis.data.Name(not_null=True), default='anyone',
                   references=sql.a(sql.r.Roles, onupdate='CASCADE')),
        sql.Column('write_role_id', pytis.data.Name(not_null=True), default='cms-content-admin',
                   references=sql.a(sql.r.Roles, onupdate='CASCADE', ondelete='SET DEFAULT')),
        sql.Column('bg_color', pytis.data.String(not_null=True)),
        sql.Column('text_color', pytis.data.String(not_null=True)),
        sql.Column('link_color', pytis.data.String(not_null=True)),
        sql.Column('heading_color', pytis.data.String(not_null=True)),
        sql.Column('top_bg_color', pytis.data.String(not_null=True)),
        sql.Column('top_text_color', pytis.data.String(not_null=True)),
        sql.Column('top_link_color', pytis.data.String(not_null=True)),
        sql.Column('footer_bg_color', pytis.data.String(not_null=True)),
        sql.Column('footer_text_color', pytis.data.String(not_null=True)),
        sql.Column('footer_link_color', pytis.data.String(not_null=True)),
        sql.Column('signature', pytis.data.String()),
    )


class CmsNewsletterSubscription(CommonAccesRights, Base_CachingTable):
    name = 'cms_newsletter_subscription'
    fields = (
        sql.PrimaryColumn('subscription_id', pytis.data.Serial(not_null=True)),
        sql.Column('newsletter_id', pytis.data.Integer(not_null=True),
                   references=sql.a(sql.r.CmsNewsletters, ondelete='CASCADE')),
        sql.Column('uid', pytis.data.Integer(), references=sql.r.Users),
        sql.Column('email', pytis.data.String()),
        sql.Column('code', pytis.data.String(), doc='Unsubscription code (email only)'),
        sql.Column('timestamp', pytis.data.DateTime(not_null=True), default=func.now()),
    )
    check = ('(uid is not null or email is not null and code is not null) '
             'and (uid is null or email is null and code is null)',)
    unique = (('newsletter_id', 'uid',),
              ('newsletter_id', 'email',),)


class CmsVNewsletterSubscription(CommonAccesRights, sql.SQLView):
    name = 'cms_v_newsletter_subscription'

    @classmethod
    def query(cls):
        s = sql.t.CmsNewsletterSubscription.alias('s')
        u = sql.t.Users.alias('u')
        return select(cls._exclude(s, s.c.email) +
                      [coalesce(s.c.email, u.c.email).label('email'),
                       u.c.user_.label('user_name'),
                       u.c.login.label('user_login'),
                       ],
                      from_obj=[s.outerjoin(u, s.c.uid == u.c.uid)])

    def on_insert(self):
        return ("insert into public.cms_newsletter_subscription "
                "(newsletter_id, email, uid, code, timestamp) "
                "VALUES (new.newsletter_id, new.email, new.uid, new.code, new.timestamp);",)
    delete_order = (CmsNewsletterSubscription,)
    no_insert_columns = ('subscription_id',)


class CmsNewsletterEditions(CommonAccesRights, Base_CachingTable):
    name = 'cms_newsletter_editions'
    fields = (
        sql.PrimaryColumn('edition_id', pytis.data.Serial(not_null=True)),
        sql.Column('newsletter_id', pytis.data.Integer(not_null=True),
                   references=sql.a(sql.r.CmsNewsletters, ondelete='CASCADE')),
        sql.Column('creator', pytis.data.Integer(not_null=True), references=sql.r.Users),
        sql.Column('created', pytis.data.DateTime(not_null=True), default=func.now()),
        sql.Column('sent', pytis.data.DateTime()),
        sql.Column('access_code', pytis.data.String()),
    )


class CmsNewsletterPosts(CommonAccesRights, Base_CachingTable):
    name = 'cms_newsletter_posts'
    fields = (
        sql.PrimaryColumn('post_id', pytis.data.Serial(not_null=True)),
        sql.Column('edition_id', pytis.data.Integer(not_null=True),
                   references=sql.a(sql.r.CmsNewsletterEditions, ondelete='CASCADE')),
        sql.Column('ord', pytis.data.Integer()),
        sql.Column('title', pytis.data.String(not_null=True)),
        sql.Column('content', pytis.data.String(not_null=True)),
        sql.Column('image', pytis.data.Binary()),
        sql.Column('image_position', pytis.data.String()),
        sql.Column('image_width', pytis.data.Integer()),
        sql.Column('image_height', pytis.data.Integer()),
    )


class CmsDiscussions(CommonAccesRights, sql.SQLTable):
    name = 'cms_discussions'
    fields = (sql.PrimaryColumn('comment_id', pytis.data.Serial(not_null=True)),
              sql.Column('page_id', pytis.data.Integer(not_null=True),
                         references=sql.a(sql.r.CmsPages, ondelete='CASCADE')),
              sql.Column('lang', pytis.data.String(minlen=2, maxlen=2, not_null=True),
                         references=sql.a(sql.r.CmsLanguages.lang, onupdate='CASCADE')),
              sql.Column('author', pytis.data.Integer(not_null=True),
                         references=sql.r.Users),
              sql.Column('timestamp', pytis.data.DateTime(not_null=True), default=func.now()),
              sql.Column('in_reply_to', pytis.data.Integer(),
                         references=sql.a(sql.r.CmsDiscussions, ondelete='SET NULL')),
              sql.Column('tree_order', pytis.data.String(not_null=True), index=True),
              sql.Column('text', pytis.data.String(not_null=True)),
              )


class CmsDiscussionsTriggerBeforeInsert(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'cms_discussions_trigger_before_insert'
    arguments = ()
    table = CmsDiscussions
    position = 'before'
    events = ('insert',)


class CmsPanels(CommonAccesRights, Base_CachingTable):
    name = 'cms_panels'
    fields = (sql.PrimaryColumn('panel_id', pytis.data.Serial(not_null=True)),
              sql.Column('site', pytis.data.String(not_null=True),
                         references=sql.a(sql.r.CmsConfig.site,
                                          onupdate='CASCADE', ondelete='CASCADE')),
              sql.Column('lang', pytis.data.String(minlen=2, maxlen=2, not_null=True),
                         references=sql.a(sql.r.CmsLanguages.lang, onupdate='CASCADE')),
              sql.Column('identifier', pytis.data.String()),
              sql.Column('title', pytis.data.String(not_null=True)),
              sql.Column('ord', pytis.data.Integer()),
              sql.Column('page_id', pytis.data.Integer(),
                         references=sql.a(sql.r.CmsPages, ondelete='SET NULL')),
              sql.Column('size', pytis.data.Integer()),
              sql.Column('content', pytis.data.String()),
              sql.Column('_content', pytis.data.String()),
              sql.Column('published', pytis.data.Boolean(not_null=True), default=False),
              )
    unique = (('identifier', 'site', 'lang',),)


class CmsVPanels(CommonAccesRights, sql.SQLView):
    name = 'cms_v_panels'

    @classmethod
    def query(cls):
        cms_panels = sql.t.CmsPanels
        cms_pages = sql.t.CmsPages
        return select([cms_panels, cms_pages.c.modname, cms_pages.c.read_role_id],
                      from_obj=[cms_panels.
                                outerjoin(cms_pages, cms_panels.c.page_id == cms_pages.c.page_id)])
    insert_order = (CmsPanels,)
    update_order = (CmsPanels,)
    delete_order = (CmsPanels,)

#


class CmsStylesheets(CommonAccesRights, Base_CachingTable):
    name = 'cms_stylesheets'
    fields = (sql.PrimaryColumn('stylesheet_id', pytis.data.Serial(not_null=True)),
              sql.Column('site', pytis.data.String(not_null=True),
                         references=sql.a(sql.r.CmsConfig.site,
                                          onupdate='CASCADE', ondelete='CASCADE')),
              sql.Column('filename', pytis.data.String(maxlen=32, not_null=True)),
              sql.Column('active', pytis.data.Boolean(not_null=True), default=True),
              sql.Column('scope', pytis.data.String()),
              sql.Column('description', pytis.data.String()),
              sql.Column('content', pytis.data.String()),
              sql.Column('ord', pytis.data.Integer()),
              )
    unique = (('filename', 'site',),)
    init_columns = ('filename', 'site', 'ord',)
    init_values = (
        ('default.css', '*', 10),
    )


class CmsThemes(CommonAccesRights, Base_CachingTable):
    name = 'cms_themes'
    fields = (sql.PrimaryColumn('theme_id', pytis.data.Serial(not_null=True),
                                references=sql.r.CmsThemes),
              sql.Column('name', pytis.data.String(not_null=True), unique=True),
              sql.Column('foreground', pytis.data.String(maxlen=7)),
              sql.Column('background', pytis.data.String(maxlen=7)),
              sql.Column('border', pytis.data.String(maxlen=7)),
              sql.Column('heading_fg', pytis.data.String(maxlen=7)),
              sql.Column('heading_bg', pytis.data.String(maxlen=7)),
              sql.Column('heading_line', pytis.data.String(maxlen=7)),
              sql.Column('frame_fg', pytis.data.String(maxlen=7)),
              sql.Column('frame_bg', pytis.data.String(maxlen=7)),
              sql.Column('frame_border', pytis.data.String(maxlen=7)),
              sql.Column('link', pytis.data.String(maxlen=7)),
              sql.Column('link_visited', pytis.data.String(maxlen=7)),
              sql.Column('link_hover', pytis.data.String(maxlen=7)),
              sql.Column('meta_fg', pytis.data.String(maxlen=7)),
              sql.Column('meta_bg', pytis.data.String(maxlen=7)),
              sql.Column('help', pytis.data.String(maxlen=7)),
              sql.Column('error_fg', pytis.data.String(maxlen=7)),
              sql.Column('error_bg', pytis.data.String(maxlen=7)),
              sql.Column('error_border', pytis.data.String(maxlen=7)),
              sql.Column('message_fg', pytis.data.String(maxlen=7)),
              sql.Column('message_bg', pytis.data.String(maxlen=7)),
              sql.Column('message_border', pytis.data.String(maxlen=7)),
              sql.Column('table_cell', pytis.data.String(maxlen=7)),
              sql.Column('table_cell2', pytis.data.String(maxlen=7)),
              sql.Column('top_fg', pytis.data.String(maxlen=7)),
              sql.Column('top_bg', pytis.data.String(maxlen=7)),
              sql.Column('top_border', pytis.data.String(maxlen=7)),
              sql.Column('highlight_bg', pytis.data.String(maxlen=7)),
              sql.Column('inactive_folder', pytis.data.String(maxlen=7)),
              )
    init_columns = (
        'name', 'foreground', 'background', 'border', 'heading_fg', 'heading_bg',
        'heading_line', 'frame_fg', 'frame_bg', 'frame_border', 'link',
        'link_visited', 'link_hover', 'meta_fg', 'meta_bg', 'help', 'error_fg',
        'error_bg', 'error_border', 'message_fg', 'message_bg', 'message_border',
        'table_cell', 'table_cell2', 'top_fg', 'top_bg', 'top_border',
        'highlight_bg', 'inactive_folder',)
    init_values = (
        ('Yellowstone', '#000', '#fff9ec', '#eda', '#420', '#fff0b0', '#eca',
         '#000', '#fff0d4', '#ffde90', '#a30', '#a30', '#f40', None, None,
         '#553', None, None, None, None, None, None, '#fff', '#fff8f0', '#444',
         '#fff', '#db9', '#fb7', '#ed9'),
        ('Olive', '#000', '#fff', '#bcb', '#0b4a44', '#d2e0d8', None, '#000',
         '#e8eee8', '#d0d7d0', '#042', None, '#d72', None, None, None, None,
         '#fc9', '#fa8', None, '#dfd', '#aea', '#f8fbfa', '#f1f3f2', None,
         '#efebe7', '#8a9', '#fc8', '#d2e0d8'),
    )


class CmsSystemTextLabels(CommonAccesRights, Base_CachingTable):
    name = 'cms_system_text_labels'
    fields = (sql.Column('label', pytis.data.Name(not_null=True)),
              sql.Column('site', pytis.data.String(not_null=True),
                         references=sql.a(sql.r.CmsConfig.site,
                                          onupdate='CASCADE', ondelete='CASCADE')),
              )
    unique = (('label', 'site',),)


class CmsAddTextLabel(sql.SQLPlFunction):
    """"""
    name = 'cms_add_text_label'
    arguments = (sql.Column('_label', pytis.data.Name()),
                 sql.Column('_site', pytis.data.String()),)
    result_type = None


class CmsSystemTexts(CommonAccesRights, Base_CachingTable):
    name = 'cms_system_texts'
    fields = (sql.Column('label', pytis.data.Name(not_null=True)),
              sql.Column('site', pytis.data.String(not_null=True)),
              sql.Column('lang', pytis.data.String(minlen=2, maxlen=2, not_null=True),
                         references=sql.a(sql.r.CmsLanguages.lang,
                                          onupdate='CASCADE', ondelete='CASCADE')),
              sql.Column('description', pytis.data.String(), default=''),
              sql.Column('content', pytis.data.String(), default=''),
              )
    unique = (('label', 'site', 'lang',),)
    foreign_keys = (sql.a(('label', 'site',),
                          (sql.r.CmsSystemTextLabels.label, sql.r.CmsSystemTextLabels.site,),
                          onupdate='CASCADE', ondelete='CASCADE'),)


class CmsVSystemTextLabels(CommonAccesRights, sql.SQLView):
    name = 'cms_v_system_text_labels'

    @classmethod
    def query(cls):
        labels = sql.t.CmsSystemTextLabels
        languages = sql.t.CmsLanguages
        return select([labels.c.label, labels.c.site, languages.c.lang],
                      from_obj=[labels, languages])


class CmsVSystemTexts(CommonAccesRights, sql.SQLView):
    name = 'cms_v_system_texts'

    @classmethod
    def query(cls):
        labels = sql.t.CmsVSystemTextLabels
        texts = sql.t.CmsSystemTexts
        return select(
            [(labels.c.label + sval(':') + labels.c.site + sval(':') + labels.c.lang)
             .label('text_id'),
             labels.c.label, labels.c.site, labels.c.lang, texts.c.description, texts.c.content],
            from_obj=[labels.outerjoin(texts, and_(labels.c.lang == texts.c.lang,
                                                   labels.c.label == texts.c.label,
                                                   labels.c.site == texts.c.site))],
        )

    def on_update(self):
        return ("""(
    delete from cms_system_texts where label = new.label and lang = new.lang and site = new.site;
    insert into cms_system_texts (label, site, lang, description, content)
           values (new.label, new.site, new.lang, new.description, new.content);
        )""",)
    # gensqlalchemy doesn't generate a proper where clause here (maybe multicolumn foreign key?)
    # delete_order = (CmsSystemTextLabels,)

    def on_delete(self):
        return ("delete from cms_system_text_labels where label = old.label and site = old.site;",)

#


class CmsEmailLabels(CommonAccesRights, sql.SQLTable):
    name = 'cms_email_labels'
    fields = (sql.PrimaryColumn('label', pytis.data.Name(not_null=True)),)


class CmsAddEmailLabel(sql.SQLPlFunction):
    name = 'cms_add_email_label'
    arguments = (sql.Column('_label', pytis.data.Name()),)
    result_type = None


class CmsEmails(CommonAccesRights, sql.SQLTable):
    name = 'cms_emails'
    fields = (sql.Column('label', pytis.data.Name(not_null=True),
                         references=sql.r.CmsEmailLabels),
              sql.Column('lang', pytis.data.String(minlen=2, maxlen=2, not_null=True),
                         references=sql.a(sql.r.CmsLanguages.lang,
                                          onupdate='CASCADE', ondelete='CASCADE')),
              sql.Column('description', pytis.data.String()),
              sql.Column('subject', pytis.data.String()),
              sql.Column('cc', pytis.data.String()),
              sql.Column('content', pytis.data.String(), default=''),
              )
    unique = (('label', 'lang',),)


class CmsVEmails(CommonAccesRights, sql.SQLView):
    name = 'cms_v_emails'

    @classmethod
    def query(cls):
        el = sql.c.CmsEmailLabels
        lang = sql.c.CmsLanguages
        e = sql.c.CmsEmails
        return select([(el.label + sval(':') + lang.lang).label('text_id'),
                       el.label, lang.lang, e.description, e.subject, e.cc, e.content],
                      from_obj=[sql.t.CmsEmailLabels,
                                sql.t.CmsLanguages.outerjoin(sql.t.CmsEmails)],
                      whereclause=and_(el.label == e.label, lang.lang == e.lang))

    def on_insert(self):
        return ("""(
    select cms_add_email_label(new.label);
    insert into cms_emails values (new.label, new.lang, new.description, new.subject,
                                   new.cc, new.content);
        )""",)

    def on_update(self):
        return ("""(
    delete from cms_emails where label = new.label and lang = new.lang;
    insert into cms_emails values (new.label, new.lang, new.description, new.subject,
                                   new.cc, new.content);
        )""",)

    def on_delete(self):
        return ("""(
    delete from cms_emails where label = old.label;
    delete from cms_email_labels where label = old.label;
        )""",)


class CmsEmailAttachments(CommonAccesRights, sql.SQLTable):
    name = 'cms_email_attachments'
    fields = (sql.PrimaryColumn('attachment_id', pytis.data.Serial(not_null=True)),
              sql.Column('label', pytis.data.Name(not_null=True),
                         references=sql.a(sql.r.CmsEmailLabels, ondelete='CASCADE')),
              sql.Column('filename', pytis.data.String(not_null=True)),
              sql.Column('mime_type', pytis.data.String(not_null=True)),
              )


class CmsEmailSpool(CommonAccesRights, sql.SQLTable):
    name = 'cms_email_spool'
    fields = (sql.PrimaryColumn('id', pytis.data.Serial(not_null=True)),
              sql.Column('sender_address', pytis.data.String()),
              sql.Column('role_id', pytis.data.Name(),
                         references=sql.a(sql.r.Roles, onupdate='CASCADE', ondelete='CASCADE'),
                         doc="recipient role, if NULL then all users"),
              sql.Column('subject', pytis.data.String()),
              sql.Column('content', pytis.data.String(),
                         doc="body of the e-mail"),
              sql.Column('date', pytis.data.DateTime(), default=func.now(),
                         doc="time of insertion"),
              sql.Column('pid', pytis.data.Integer()),
              sql.Column('finished', pytis.data.Boolean(not_null=False), default=False,
                         doc="set TRUE after the mail was successfully sent"),
              )

#


class CmsCryptoNames(CommonAccesRights, sql.SQLTable):
    name = 'cms_crypto_names'
    fields = (sql.PrimaryColumn('name', pytis.data.String(not_null=True)),
              sql.Column('description', pytis.data.String()),
              )
    init_columns = ('name', 'description',)
    access_rights = (('ALL', 'www-data',),)


class CmsCryptoKeys(CommonAccesRights, sql.SQLTable):
    name = 'cms_crypto_keys'
    fields = (sql.PrimaryColumn('key_id', pytis.data.Serial(not_null=True)),
              sql.Column('name', pytis.data.String(not_null=True),
                         references=sql.a(sql.r.CmsCryptoNames,
                                          onupdate='CASCADE', ondelete='CASCADE')),
              sql.Column('uid', pytis.data.Integer(not_null=True),
                         references=sql.a(sql.r.Users, onupdate='CASCADE', ondelete='CASCADE')),
              sql.Column('key', pytis.data.Binary(not_null=True)),
              )
    unique = (('name', 'uid',),)
    access_rights = (('ALL', 'www-data',),)


class CmsCryptoExtractKey(sql.SQLPlFunction):
    name = 'cms_crypto_extract_key'
    arguments = (sql.Column('encrypted', pytis.data.Binary()),
                 sql.Column('psw', pytis.data.String()),)
    result_type = pytis.data.String()
    stability = 'immutable'


class CmsCryptoStoreKey(sql.SQLPlFunction):
    "This is a PL/pgSQL, and not SQL, function in order to prevent direct dependency on pg_crypto."
    name = 'cms_crypto_store_key'
    arguments = (sql.Column('key', pytis.data.String()),
                 sql.Column('psw', pytis.data.String()),)
    result_type = pytis.data.Binary()
    stability = 'immutable'

    def body(self):
        return "begin return pgp_sym_encrypt('wiking:'||$1, $2); end;"


class CmsCryptoInsertKey(sql.SQLPlFunction):
    name = 'cms_crypto_insert_key'
    arguments = (sql.Column('name_', pytis.data.String()),
                 sql.Column('uid_', pytis.data.Integer()),
                 sql.Column('key_', pytis.data.String()),
                 sql.Column('psw', pytis.data.String()),)
    result_type = pytis.data.Boolean()


class CmsCryptoChangePassword(sql.SQLPlFunction):
    name = 'cms_crypto_change_password'
    arguments = (sql.Column('id_', pytis.data.Integer()),
                 sql.Column('old_psw', pytis.data.String()),
                 sql.Column('new_psw', pytis.data.String()),)
    result_type = pytis.data.Boolean()


class CmsCryptoCopyKey(sql.SQLPlFunction):
    name = 'cms_crypto_copy_key'
    arguments = (sql.Column('name_', pytis.data.String()),
                 sql.Column('from_uid', pytis.data.Integer()),
                 sql.Column('to_uid', pytis.data.Integer()),
                 sql.Column('from_psw', pytis.data.String()),
                 sql.Column('to_psw', pytis.data.String()),)
    result_type = pytis.data.Boolean()


class CmsCryptoDeleteKey(sql.SQLPlFunction):
    name = 'cms_crypto_delete_key'
    arguments = (sql.Column('name_', pytis.data.String()),
                 sql.Column('uid_', pytis.data.Integer()),
                 sql.Column('force', pytis.data.Boolean()),)
    result_type = pytis.data.Boolean()

#


class CmsCryptoUnlockedPasswords(CommonAccesRights, sql.SQLTable):
    name = 'cms_crypto_unlocked_passwords'
    fields = (sql.Column('key_id', pytis.data.Integer(not_null=True),
                         references=sql.a(sql.r.CmsCryptoKeys,
                                          onupdate='CASCADE', ondelete='CASCADE')),
              sql.Column('password', pytis.data.Binary()),
              )
    access_rights = (('ALL', 'www-data',),)


class CmsCryptoUnlockedPasswordsInsertTrigger(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'cms_crypto_unlocked_passwords_insert_trigger'
    arguments = ()
    table = CmsCryptoUnlockedPasswords
    position = 'before'
    events = ('insert',)


class CmsCryptoUnlockPasswords(sql.SQLFunction):
    name = 'cms_crypto_unlock_passwords'
    arguments = (sql.Column('uid_', pytis.data.Integer()),
                 sql.Column('psw', pytis.data.String()),
                 sql.Column('cookie', pytis.data.String()),)
    result_type = None
    depends_on = (CmsCryptoUnlockedPasswords,)


class CmsCryptoLockPasswords(sql.SQLFunction):
    name = 'cms_crypto_lock_passwords'
    arguments = (sql.Column('uid_', pytis.data.Integer()),)
    result_type = None
    depends_on = (CmsCryptoUnlockedPasswords,)


class CmsCryptoCookPasswords(sql.SQLPlFunction):
    name = 'cms_crypto_cook_passwords'
    arguments = (sql.Column('uid_', pytis.data.Integer()),
                 sql.Column('cookie', pytis.data.String()),)
    result_type = pytis.data.String()
    multirow = True


class PytisCryptoUnlockCurrentUserPasswords(sql.SQLFunction):
    """This one is to avoid error messages in Apache logs (the function is required by Pytis)."""
    name = 'pytis_crypto_unlock_current_user_passwords'
    arguments = (sql.Column('password_', pytis.data.String()),)
    result_type = pytis.data.String()
    multirow = True
    stability = 'immutable'

    def body(self):
        return "select ''::text where false;"
