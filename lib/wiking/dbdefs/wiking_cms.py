# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2016 OUI Technology Ltd.
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

import os
import glob
import sqlalchemy

import pytis.data.gensqlalchemy as sql
import pytis.data as pd
from pytis.data.dbdefs import and_, or_, coalesce, func, ival, null, select, stype, sval
from .wiking_db import Base_CachingTable, CommonAccesRights

current_timestamp_0 = sqlalchemy.sql.functions.Function('current_timestamp', ival(0))

name_is_not_null = sql.SQLFlexibleValue('name_not_null', default=True)

upgrade_directory = os.path.abspath(os.path.join(os.path.realpath(os.path.dirname(__file__)),
                                                 '..', '..', '..', 'upgrade'))
upgrade_files = glob.glob(os.path.join(upgrade_directory, 'upgrade.*.sql'))
assert upgrade_files, 'No upgrade files found in upgrade directory: %s' % upgrade_directory
last_upgrade_script = max(upgrade_files)
version = int(last_upgrade_script[len(upgrade_directory) + len(os.sep) + 8:-4])


class SQLView(sql.SQLView):

    @classmethod
    def _reference(cls, kind):
        """Refer NEW and OLD columns in rules."""
        class Reference:
            def __init__(self, kind):
                self._kind = kind
            def __getattr__(self, name):
                return sqlalchemy.literal_column(self._kind + '.' + name)
        return Reference(kind)


class cms_database_version(sql.SQLTable):
    name = 'cms_database_version'
    fields = (
        sql.Column('version', pd.Integer()),
    )
    init_columns = ('version',)
    init_values = ((version,),)


class cms_languages(CommonAccesRights, Base_CachingTable):
    name = 'cms_languages'
    fields = (
        sql.PrimaryColumn('lang_id', pd.Serial()),
        sql.Column('lang', pd.String(minlen=2, maxlen=2, not_null=True),
                   unique=True),
    )
    init_columns = ('lang',)
    init_values = (('en',),)


class cms_config(CommonAccesRights, Base_CachingTable):
    name = 'cms_config'
    fields = (
        sql.PrimaryColumn('site', pd.String()),
        sql.Column('site_title', pd.String()),
        sql.Column('site_subtitle', pd.String()),
        sql.Column('allow_registration', pd.Boolean(not_null=True), default=True),
        sql.Column('login_is_email', pd.Boolean(not_null=True), default=False),
        sql.Column('registration_expiration', pd.Integer()),
        sql.Column('force_https_login', pd.Boolean(not_null=True), default=False),
        sql.Column('https_port', pd.Integer()),
        sql.Column('smtp_server', pd.String()),
        sql.Column('webmaster_address', pd.String()),
        sql.Column('bug_report_address', pd.String()),
        sql.Column('default_sender_address', pd.String()),
        sql.Column('upload_limit', pd.Integer()),
        sql.Column('session_expiration', pd.Integer()),
        sql.Column('default_language', pd.String(minlen=2, maxlen=2),
                   references=sql.a(sql.r.cms_languages.lang, onupdate='CASCADE')),
        sql.Column('theme_id', pd.Integer(),
                   references=sql.r.cms_themes),
    )
    init_columns = ('site',)
    init_values = (('*',),)


class cms_countries(CommonAccesRights, sql.SQLTable):
    name = 'cms_countries'
    fields = (
        sql.PrimaryColumn('country_id', pd.Serial(not_null=True)),
        sql.Column('country', pd.String(minlen=2, maxlen=2, not_null=True),
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


class roles(CommonAccesRights, Base_CachingTable):
    name = 'roles'
    fields = (
        sql.PrimaryColumn('role_id', pd.PgName()),
        sql.Column('name', pd.String()),
        sql.Column('system', pd.Boolean(not_null=True), default=False),
        sql.Column('auto', pd.Boolean(not_null=True), default=False),
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


class role_sets(CommonAccesRights, Base_CachingTable):
    name = 'role_sets'
    fields = (
        sql.PrimaryColumn('role_set_id', pd.Serial(not_null=True)),
        sql.Column('role_id', pd.PgName(not_null=True),
                   references=sql.a(sql.r.roles, onupdate='CASCADE', ondelete='CASCADE')),
        sql.Column('member_role_id', pd.PgName(not_null=True),
                   references=sql.a(sql.r.roles, onupdate='CASCADE', ondelete='CASCADE')),
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


class expanded_role(sql.SQLPlFunction):
    name = 'expanded_role'
    arguments = (sql.Column('role_id_', pd.PgName()),)
    result_type = pd.PgName()
    multirow = True
    stability = 'stable'


class unrelated_roles(sql.SQLFunction):
    name = 'unrelated_roles'
    arguments = (sql.Column('role_id', pd.PgName()),)
    result_type = roles
    multirow = True
    stability = 'stable'


class users(CommonAccesRights, Base_CachingTable):
    name = 'users'
    fields = (
        sql.PrimaryColumn('uid', pd.Serial(not_null=True)),
        sql.Column('login', pd.String(maxlen=64, not_null=True), unique=True),
        sql.Column('password', pd.String(not_null=True)),
        sql.Column('firstname',
                   pd.String(not_null=name_is_not_null.value(globals()))),
        sql.Column('surname',
                   pd.String(not_null=name_is_not_null.value(globals()))),
        sql.Column('nickname', pd.String()),
        sql.Column('user_', pd.String(not_null=True)),
        sql.Column('email', pd.String(not_null=True)),
        sql.Column('phone', pd.String()),
        sql.Column('address', pd.String()),
        sql.Column('uri', pd.String()),
        sql.Column('state', pd.String(not_null=True), default='new'),
        sql.Column('last_password_change', pd.DateTime(not_null=True)),
        sql.Column('since', pd.DateTime(not_null=True),
                   default=func.timezone(sval('GMT'), current_timestamp_0)),
        sql.Column('lang', pd.String(minlen=2, maxlen=2),
                   references=sql.a(sql.r.cms_languages.lang, onupdate='CASCADE',
                                    ondelete='SET NULL')),
        sql.Column('regexpire', pd.DateTime()),
        sql.Column('regcode', pd.String()),
        sql.Column('passexpire', pd.DateTime()),
        sql.Column('passcode', pd.String()),
        sql.Column('certauth', pd.Boolean(not_null=True), default=False),
        sql.Column('note', pd.String()),
        sql.Column('confirm', pd.Boolean(not_null=True), default=False),
        sql.Column('gender', pd.String(minlen=1, maxlen=1),
                   doc="[m]ale, [f]emale, NULL=unknown"),
    )
    access_rights = (('ALL', 'www-data',),)

    init_columns = ('login', 'password', 'firstname', 'surname', 'nickname', 'user_',
                    'email', 'state', 'last_password_change',)
    init_values = (('admin', 'plain:wiking', 'Wiking', 'Admin', 'Admin', 'Admin',
                    '-', 'enabled', '2012-01-01 00:00'),)


class cms_f_insert_or_update_user(sql.SQLPlFunction):
    name = 'cms_f_insert_or_update_user'
    arguments = (sql.Column('uid_', pd.Integer()),
                 sql.Column('login_', pd.String(maxlen=64)),
                 sql.Column('password_', pd.String()),
                 sql.Column('firstname_', pd.String()),
                 sql.Column('surname_', pd.String()),
                 sql.Column('nickname_', pd.String()),
                 sql.Column('user__', pd.String()),
                 sql.Column('email_', pd.String()),
                 sql.Column('phone_', pd.String()),
                 sql.Column('address_', pd.String()),
                 sql.Column('uri_', pd.String()),
                 sql.Column('state_', pd.String()),
                 sql.Column('last_password_change_', pd.DateTime()),
                 sql.Column('since_', pd.DateTime()),
                 sql.Column('lang_', pd.String(minlen=2, maxlen=2)),
                 sql.Column('regexpire_', pd.DateTime()),
                 sql.Column('regcode_', pd.String()),
                 sql.Column('passexpire_', pd.DateTime()),
                 sql.Column('passcode_', pd.String()),
                 sql.Column('certauth_', pd.Boolean()),
                 sql.Column('note_', pd.String()),
                 sql.Column('confirm_', pd.Boolean()),
                 sql.Column('gender_', pd.String(minlen=1, maxlen=1)),
                 )
    result_type = None


class role_members(CommonAccesRights, Base_CachingTable):
    name = 'role_members'
    fields = (
        sql.PrimaryColumn('role_member_id', pd.Serial(not_null=True)),
        sql.Column('role_id', pd.PgName(not_null=True),
                   references=sql.a(sql.r.roles, onupdate='CASCADE', ondelete='CASCADE')),
        sql.Column('uid', pd.Integer(not_null=True),
                   references=sql.a(sql.r.users, onupdate='CASCADE', ondelete='CASCADE')),
    )
    unique = (('role_id', 'uid',),)
    init_columns = ('role_id', 'uid')
    init_values = (('cms-admin', 1),)


class cms_v_role_members(CommonAccesRights, SQLView):
    name = 'cms_v_role_members'

    @classmethod
    def query(cls):
        m = sql.t.role_members.alias('m')
        r = sql.t.roles.alias('r')
        u = sql.t.users.alias('u')
        return select([m,
                       r.c.name.label('role_name'),
                       u.c.user_.label('user_name'),
                       u.c.login.label('user_login'),
                       ],
                      from_obj=[m.join(r, r.c.role_id == m.c.role_id).join(u, m.c.uid == u.c.uid)])
    insert_order = (role_members,)
    update_order = (role_members,)
    delete_order = (role_members,)
    no_insert_columns = ('role_member_id',)


class a_user_roles(CommonAccesRights, sql.SQLTable):
    name = 'a_user_roles'
    fields = (
        sql.Column('uid', pd.Integer(), index=True,
                   references=sql.a(sql.r.users, onupdate='CASCADE', ondelete='CASCADE')),
        sql.Column('role_id', pd.PgName(not_null=True),
                   references=sql.a(sql.r.roles, onupdate='CASCADE', ondelete='CASCADE')),
    )
    access_rights = (('ALL', 'www-data',),)


class update_user_roles(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'update_user_roles'
    arguments = ()
    events = ()


class role_sets_update_user_roles_trigger(sql.SQLTrigger):
    name = 'role_sets_update_user_roles_trigger'
    table = role_sets
    events = ('insert', 'update', 'delete',)
    each_row = False
    body = update_user_roles


class role_members_update_user_roles_trigger(sql.SQLTrigger):
    name = 'role_members_update_user_roles_trigger'
    table = role_members
    events = ('insert', 'update', 'delete',)
    each_row = False
    body = update_user_roles


class cms_f_all_user_roles(sql.SQLFunction):
    """Return all user's roles and their included roles.
    Both explicitly assigned and implicit roles (such as 'anyone') are considered."""
    name = 'cms_f_all_user_roles'
    arguments = (sql.Column('uid_', pd.Integer()),)
    result_type = pd.PgName()
    multirow = True
    stability = 'stable'
    depends_on = (a_user_roles,)


class cms_f_role_member(sql.SQLPlFunction):
    name = 'cms_f_role_member'
    arguments = (sql.Column('uid_', pd.Integer()),
                 sql.Column('role_id_', pd.PgName()),)
    result_type = pd.Boolean()
    stability = 'stable'


class role_sets_cycle_check(sql.SQLFunction):
    name = 'role_sets_cycle_check'
    arguments = ()
    result_type = pd.Boolean()
    depends_on = (role_sets,)


class role_sets_trigger_after(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'role_sets_trigger_after'
    arguments = ()
    table = role_sets
    position = 'after'
    events = ('insert', 'update', 'delete',)


class cms_sessions(CommonAccesRights, sql.SQLTable):
    name = 'cms_sessions'
    fields = (
        sql.PrimaryColumn('session_id', pd.Serial(not_null=True)),
        sql.Column('session_key', pd.String(not_null=True)),
        sql.Column('auth_type', pd.String(not_null=True)),
        sql.Column('uid', pd.Integer(not_null=True),
                   references=sql.a(sql.r.users, ondelete='CASCADE')),
        sql.Column('last_access', pd.DateTime()),
    )
    unique = (('uid', 'session_key',),)

class cms_session_history(CommonAccesRights, sql.SQLTable):
    name = 'cms_session_history'
    fields = (
        sql.PrimaryColumn('session_id', pd.Integer(not_null=True)),
        sql.Column('auth_type', pd.String(not_null=True)),
        sql.Column('uid', pd.Integer(not_null=True),
                   references=sql.a(sql.r.users, ondelete='CASCADE')),
        sql.Column('start_time', pd.DateTime(not_null=True)),
        sql.Column('end_time', pd.DateTime()),
    )

class cms_update_session_history(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'cms_update_session_history'
    arguments = ()
    events = ()

class cms_sessions_trigger(sql.SQLTrigger):
    name = 'cms_sessions_trigger'
    table = cms_sessions
    events = ('insert', 'delete',)
    each_row = True
    body = cms_update_session_history

class cms_v_session_history(CommonAccesRights, SQLView):
    name = 'cms_v_session_history'
    @classmethod
    def query(cls):
        h = sql.t.cms_session_history.alias('h')
        u = sql.t.users.alias('u')
        return select(list(h.c) + [
            u.c.login,
            u.c.user_.label('user'),
            sqlalchemy.cast(h.c.end_time == null, sqlalchemy.Boolean()).label('active'),
            (coalesce(h.c.end_time, func.now()) - h.c.start_time).label('duration'),
        ], from_obj=[h.outerjoin(u, u.c.uid == h.c.uid)])


class cms_login_failures(CommonAccesRights, sql.SQLTable):
    name = 'cms_login_failures'
    fields = (
        sql.PrimaryColumn('failure_id', pd.Serial(not_null=True)),
        sql.Column('timestamp', pd.DateTime(not_null=True)),
        sql.Column('login', pd.String(not_null=True)),
        sql.Column('auth_type', pd.String(not_null=True)),
        sql.Column('ip_address', pd.String(not_null=True)),
        sql.Column('user_agent', pd.String()),
    )


class cms_pages(CommonAccesRights, Base_CachingTable):
    name = 'cms_pages'
    fields = (
        sql.PrimaryColumn('page_id', pd.Serial(not_null=True)),
        sql.Column('site', pd.String(not_null=True),
                   references=sql.a(sql.r.cms_config.site,
                                    onupdate='CASCADE', ondelete='CASCADE')),
        sql.Column('kind', pd.String(not_null=True)),
        sql.Column('identifier', pd.String(not_null=True)),
        sql.Column('parent', pd.Integer(), references=sql.r.cms_pages),
        sql.Column('modname', pd.String()),
        sql.Column('menu_visibility', pd.String(not_null=True)),
        sql.Column('foldable', pd.Boolean(not_null=False)),
        sql.Column('ord', pd.Integer(not_null=True)),
        sql.Column('tree_order', pd.String()),
        sql.Column('owner', pd.Integer(), references=sql.r.users),
        sql.Column('read_role_id', pd.PgName(not_null=True), default='anyone',
                   references=sql.a(sql.r.roles, onupdate='CASCADE')),
        sql.Column('write_role_id', pd.PgName(not_null=True),
                   default='cms-content-admin',
                   references=sql.a(sql.r.roles, onupdate='CASCADE', ondelete='SET DEFAULT')),
    )
    unique = (('identifier', 'site',),)

    @property
    def index_columns(self):
        parent = sqlalchemy.func.coalesce(sql.c.cms_pages.parent, ival(0))
        return (sql.a('ord', parent, 'site', 'kind', unique=True),)


class cms_pages_update_order(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'cms_pages_update_order'
    table = cms_pages
    events = ('insert', 'update',)
    position = 'before'


class cms_page_texts(CommonAccesRights, Base_CachingTable):
    name = 'cms_page_texts'
    fields = (
        sql.Column('page_id', pd.Integer(not_null=True),
                   references=sql.a(sql.r.cms_pages, ondelete='CASCADE')),
        sql.Column('lang', pd.String(minlen=2, maxlen=2, not_null=True),
                   references=sql.a(sql.r.cms_languages.lang, onupdate='CASCADE')),
        sql.Column('published', pd.Boolean(not_null=True), default=True),
        sql.Column('parents_published', pd.Boolean(not_null=True)),
        sql.Column('creator', pd.Integer(not_null=True), references=sql.r.users),
        sql.Column('created', pd.DateTime(not_null=True), default=func.now()),
        sql.Column('published_since', pd.DateTime()),
        sql.Column('title', pd.String(not_null=True)),
        sql.Column('description', pd.String()),
        sql.Column('content', pd.String()),
        sql.Column('_title', pd.String()),
        sql.Column('_description', pd.String()),
        sql.Column('_content', pd.String()),
    )
    unique = (('page_id', 'lang',),)


class cms_page_tree_order(sql.SQLFunction):
    name = 'cms_page_tree_order'
    arguments = (sql.Column('page_id', pd.Integer()),)
    result_type = pd.String()
    depends_on = (cms_pages,)
    stability = 'stable'


class cms_page_tree_published(sql.SQLFunction):
    name = 'cms_page_tree_published'
    arguments = (sql.Column('page_id', pd.Integer()),
                 sql.Column('lang', pd.String()),)
    result_type = pd.Boolean()
    depends_on = (cms_pages, cms_page_texts)
    stability = 'stable'


class cms_v_pages(CommonAccesRights, SQLView):
    name = 'cms_v_pages'
    primary_column = 'page_key'

    @classmethod
    def query(cls):
        p = sql.t.cms_pages.alias('p')
        lang = sql.t.cms_languages.alias('l')
        t = sql.t.cms_page_texts.alias('t')
        cu = sql.t.users.alias('cu')
        ou = sql.t.users.alias('ou')
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
        pages = sql.t.cms_pages
        texts = sql.t.cms_page_texts
        new = self._reference('new')
        return (
            pages.insert().inline().values(**{c.name: getattr(new, c.name) for c in pages.c
                                              if c.name not in ('page_id', 'tree_order')}),
            pages.update().values(tree_order=func.cms_page_tree_order(pages.c.page_id)).where(
                and_(pages.c.site == new.site,
                     or_(pages.c.identifier == new.identifier,
                         pages.c.tree_order != func.cms_page_tree_order(pages.c.page_id)))
            ),
            texts.insert().from_select(
                texts.c,
                select(*[
                    pages.c.page_id if c.name == 'page_id' else getattr(new, c.name)
                    for c in texts.c
                ]).select_from(
                    pages
                ).where(and_(
                    pages.c.identifier == new.identifier,
                    pages.c.site == new.site,
                    pages.c.kind == new.kind,
                ))
            ).returning(*[
                (stype(texts.c.page_id) + sval('.') + texts.c.lang).label(c.name)
                if c.name == 'page_key' else
                getattr(texts.c, c.name) if hasattr(texts.c, c.name) else
                sqlalchemy.cast(null, c.type).label(c.name)
                for c in self.c
            ]),

        )

    def on_update(self):
        pages = sql.t.cms_pages
        texts = sql.t.cms_page_texts
        new = self._reference('new')
        old = self._reference('old')
        published = select(
            pages.c.page_id, texts.c.lang,
            func.cms_page_tree_published(pages.c.parent, texts.c.lang).label('parents_published')
        ).select_from(pages.join(texts, texts.c.page_id == pages.c.page_id)).alias('published')
        return (
            # Set the ord=0 first to work around the problem with recursion order in
            # cms_pages_update_order trigger (see the comment there for more info).
            pages.update().values(
                ord=ival(0)
            ).where(and_(
                pages.c.page_id == old.page_id,
                new.ord < old.ord,
            )),
            # Update the page structure and global data.
            pages.update().values(**{
                c.name: getattr(new, c.name) for c in pages.c
            }).where(
                pages.c.page_id == old.page_id
            ),
            # Update tree order for the whole site in case page structure has changed.
            pages.update().values(
                tree_order=func.cms_page_tree_order(pages.c.page_id)
            ).where(and_(
                pages.c.site == new.site,
                pages.c.tree_order != func.cms_page_tree_order(pages.c.page_id)
            )),
            # Update texts if they already exist for given page in given lang.
            texts.update().values(**{
                c.name: getattr(new, c.name)
                for c in texts.c if c.name not in ('page_id', 'lang', 'parents_published')
            }).where(and_(
                texts.c.page_id == old.page_id,
                texts.c.lang == new.lang
            )),
            # Insert texts if they didn't exist for given page in given lang.
            texts.insert().from_select(
                texts.c,
                select(*[
                    getattr(old if c.name == 'page_id' else new, c.name) for c in texts.c
                ]).where(and_(
                    new.lang.not_in(select(texts.c.lang).select_from(texts).where(texts.c.page_id==old.page_id)),
                    func.coalesce(new.title, new.description, new.content,
                                  new._title, new._description, new._content) != null,
                ))
            ),
            texts.update().values(
                parents_published=published.c.parents_published
            ).where(and_(
                texts.c.page_id == published.c.page_id,
                texts.c.lang == published.c.lang,
                texts.c.parents_published != published.c.parents_published,
            )),
        )

    delete_order = (cms_pages,)
    depends_on = (cms_pages, cms_page_texts, cms_page_tree_published,)


class cms_page_history(CommonAccesRights, sql.SQLTable):
    name = 'cms_page_history'
    fields = (
        sql.PrimaryColumn('history_id', pd.Serial(not_null=True)),
        sql.Column('page_id', pd.Integer(not_null=True)),
        sql.Column('lang', pd.String(minlen=2, maxlen=2, not_null=True)),
        sql.Column('uid', pd.Integer(not_null=True), references=sql.r.users),
        sql.Column('timestamp', pd.DateTime(not_null=True)),
        sql.Column('content', pd.String()),
        sql.Column('comment', pd.String()),
        sql.Column('inserted_lines', pd.Integer(not_null=True)),
        sql.Column('changed_lines', pd.Integer(not_null=True)),
        sql.Column('deleted_lines', pd.Integer(not_null=True)),
    )
    foreign_keys = (sql.a(('page_id', 'lang',),
                          (sql.r.cms_page_texts.page_id, sql.r.cms_page_texts.lang,),
                          ondelete='cascade'),)


class cms_v_page_history(CommonAccesRights, SQLView):
    name = 'cms_v_page_history'

    @classmethod
    def query(cls):
        h = sql.t.cms_page_history.alias('h')
        u = sql.t.users.alias('u')
        return select([h,
                       u.c.user_.label('user'),
                       u.c.login,
                       (stype(h.c.page_id) + sval('.') + h.c.lang).label('page_key'),
                       (stype(h.c.inserted_lines) + sval(' / ') +
                        stype(h.c.changed_lines) + sval(' / ') +
                        stype(h.c.deleted_lines)).label('changes')],
                      from_obj=[h.join(u, h.c.uid == u.c.uid)])
    insert_order = (cms_page_history,)


class cms_page_excerpts(sql.SQLTable):
    """Excerpts from CMS pages.
    Currently serving for printing parts of e-books in Braille.
    """
    name = 'cms_page_excerpts'
    fields = (
        sql.PrimaryColumn('id', pd.Serial(not_null=True)),
        sql.Column('page_id', pd.Integer(),
                   references=sql.a(sql.r.cms_pages, onupdate='CASCADE', ondelete='CASCADE')),
        sql.Column('lang', pd.String(not_null=True)),
        sql.Column('title', pd.String(not_null=True)),
        sql.Column('content', pd.String(not_null=True)),
    )
    access_rights = (('ALL', 'www-data',),)

#


class cms_page_attachments(CommonAccesRights, sql.SQLTable):
    name = 'cms_page_attachments'
    fields = (
        sql.PrimaryColumn('attachment_id', pd.Serial(not_null=True)),
        sql.Column('page_id', pd.Integer(not_null=True),
                   references=sql.a(sql.r.cms_pages, ondelete='CASCADE')),
        sql.Column('filename', pd.String(not_null=True)),
        sql.Column('mime_type', pd.String(not_null=True)),
        sql.Column('bytesize', pd.Integer(not_null=True)),
        sql.Column('created', pd.DateTime(not_null=True)),
        sql.Column('last_modified', pd.DateTime(not_null=True)),
        sql.Column('image', pd.Binary(),
                   doc="Resized image"),
        sql.Column('image_width', pd.Integer(),
                   doc="Resized image pixel width."),
        sql.Column('image_height', pd.Integer(),
                   doc="Resized image pixel height."),
        sql.Column('thumbnail', pd.Binary()),
        sql.Column('thumbnail_size', pd.String(),
                   doc="Desired thumbnail size - small/medium/large"),
        sql.Column('thumbnail_width', pd.Integer(),
                   doc="Thumbnail pixel width."),
        sql.Column('thumbnail_height', pd.Integer(),
                   doc="Thumbnail pixel height."),
        sql.Column('in_gallery', pd.Boolean(not_null=True), default=False),
        sql.Column('listed', pd.Boolean(not_null=True), default=False),
        sql.Column('author', pd.String()),
        sql.Column('location', pd.String()),
        sql.Column('width', pd.Integer()),
        sql.Column('height', pd.Integer()),
    )
    unique = (('filename', 'page_id',),)


class cms_page_attachment_texts(CommonAccesRights, sql.SQLTable):
    name = 'cms_page_attachment_texts'
    fields = (
        sql.Column('attachment_id', pd.Integer(not_null=True),
                   references=sql.a(sql.r.cms_page_attachments, ondelete='CASCADE',
                                    initially='DEFERRED')),
        sql.Column('lang', pd.String(minlen=2, maxlen=2, not_null=True),
                   references=sql.a(sql.r.cms_languages.lang,
                                    onupdate='CASCADE', ondelete='CASCADE')),
        sql.Column('title', pd.String()),
        sql.Column('description', pd.String()),
    )
    unique = (('attachment_id', 'lang',),)


class cms_v_page_attachments(CommonAccesRights, SQLView):
    name = 'cms_v_page_attachments'

    @classmethod
    def query(cls):
        a = sql.t.cms_page_attachments.alias('a')
        lang = sql.t.cms_languages.alias('l')
        t = sql.t.cms_page_attachment_texts.alias('t')
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


class cms_attachments_after_update_trigger(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'cms_attachments_after_update_trigger'
    table = cms_page_attachments
    events = ('update',)
    position = 'after'

#


class cms_publications(CommonAccesRights, sql.SQLTable):
    """bibliographic data of the original (paper) books"""
    name = 'cms_publications'
    fields = (
        sql.PrimaryColumn('page_id', pd.Integer(not_null=True),
                          references=sql.a(sql.r.cms_pages, ondelete='CASCADE')),
        sql.Column('author', pd.String(not_null=True),
                   doc="creator(s) of the original work; full name(s), one name per line"),
        sql.Column('contributor', pd.String(),
                   doc=("creator(s) of the original work with less significant "
                        "role than author(s); full name(s), one name per line")),
        sql.Column('illustrator', pd.String(),
                   doc=("author(s) of illustrations in the original work; "
                        "full name(s), one name per line")),
        sql.Column('publisher', pd.String(),
                   doc="full name of the publisher"),
        sql.Column('published_year', pd.Integer(),
                   doc="year published"),
        sql.Column('edition', pd.Integer(),
                   doc="first, second, ..."),
        sql.Column('original_isbn', pd.String(),
                   doc=("ISBN identifier of the original work; if not null, the "
                        "publication is a work derived from it and fields author, "
                        "contributor, illustrator, publisher, published_year and "
                        "edition relate to the original work")),
        sql.Column('isbn', pd.String(),
                   'ISBN of this publication if it has one assigned'),
        sql.Column('uuid', pd.String(),
                   'Universally Unique Identifier if ISBN is not assigned'),
        sql.Column('adapted_by', pd.String(),
                   doc=("people or organization(s), who created this digital "
                        "publication if these are not already mentioned in the "
                        "above fields; full name(s), one name per line")),
        sql.Column('adapted_for', pd.String(),
                   doc=("organization or project for which this adaptation of the original "
                        "work into a digital publication has been done.")),
        sql.Column('cover_image', pd.Integer(),
                   references=sql.a(sql.r.cms_page_attachments, ondelete='SET NULL')),
        sql.Column('copyright_notice', pd.String()),
        sql.Column('notes', pd.String(),
                   doc="any other additional info, such as translator(s), reviewer(s) etc."),
        sql.Column('download_role_id', pd.PgName(),
                   references=sql.a(sql.r.roles, onupdate='CASCADE'),
                   doc="role allowed to download the offline version of the publication."),
    )


class cms_v_publications(CommonAccesRights, SQLView):
    name = 'cms_v_publications'
    primary_column = 'page_key'

    @classmethod
    def query(cls):
        pages = sql.t.cms_v_pages.alias('pages')
        publications = sql.t.cms_publications.alias('publications')
        attachments = sql.t.cms_page_attachments.alias('attachments')
        return select(
            cls._exclude(pages, pages.c.page_id) +
            cls._exclude(publications) +
            [attachments.c.filename.label('cover_image_filename')]
        ).select_from(
            pages
            .join(publications, publications.c.page_id == pages.c.page_id)
            .outerjoin(attachments, attachments.c.attachment_id == publications.c.cover_image)
        )

    def on_insert(self):
        pages = sql.t.cms_pages
        vpages = sql.t.cms_v_pages
        publications = sql.t.cms_publications
        texts = sql.t.cms_page_texts.alias('texts')
        new = self._reference('new')
        return (
            vpages.insert().values(**{
                c.name: getattr(new, c.name) for c in vpages.c if c.name not in ('page_id', 'page_key')
            }),
            publications.insert().from_select(
                publications.c,
                select([
                    c if hasattr(vpages.c, c.name) else getattr(new, c.name) for c in publications.c
                ]).select_from(
                    pages
                ).where(and_(
                    pages.c.identifier == new.identifier,
                    pages.c.site == new.site,
                    pages.c.kind == new.kind,
                )),
            ).returning(*[
                (stype(publications.c.page_id) + sval('.') +
                 select(func.min(texts.c.lang)).select_from(texts).where(
                     texts.c.page_id == publications.c.page_id
                 ).as_scalar()).label(c.name)
                if c.name == 'page_key' else
                getattr(publications.c, c.name) if hasattr(publications.c, c.name) else
                sqlalchemy.cast(null, c.type).label(c.name)
                for c in self.c
            ]),
        )

    update_order = (cms_v_pages, cms_publications)
    no_update_columns = ('page_id', 'page_key', 'lang')
    delete_order = (cms_v_pages,)


class cms_publication_languages(CommonAccesRights, sql.SQLTable):
    """list of content languages available for given publication"""
    name = 'cms_publication_languages'
    fields = (
        sql.Column('page_id', pd.Integer(not_null=True),
                   references=sql.a(sql.r.cms_publications.page_id, ondelete='CASCADE')),
        sql.Column('lang', pd.String(not_null=True),
                   doc="language code"),
    )
    unique = (('page_id', 'lang',),)


class cms_publication_indexes(CommonAccesRights, sql.SQLTable):
    """list of indexes available for given publication"""
    name = 'cms_publication_indexes'
    fields = (
        sql.PrimaryColumn('index_id', pd.Serial(not_null=True)),
        sql.Column('page_id', pd.Integer(not_null=True),
                   references=sql.a(sql.r.cms_publications.page_id, ondelete='CASCADE')),
        sql.Column('title', pd.String(not_null=True)),
    )
    unique = (('page_id', 'title',),)


class cms_publication_exports(CommonAccesRights, sql.SQLTable):
    """Exported publication versions."""
    name = 'cms_publication_exports'
    fields = (
        sql.PrimaryColumn('export_id', pd.Serial()),
        sql.Column('page_id', pd.Integer(not_null=True),
                   references=sql.a(sql.r.cms_publications.page_id, ondelete='CASCADE')),
        sql.Column('lang', pd.String(minlen=2, maxlen=2, not_null=True),
                   references=sql.a(sql.r.cms_languages.lang,
                                    onupdate='CASCADE', ondelete='CASCADE')),
        sql.Column('format', pd.String(not_null=True)),
        sql.Column('version', pd.String(not_null=True)),
        sql.Column('timestamp', pd.DateTime(not_null=True)),
        sql.Column('public', pd.Boolean(not_null=True), default=True),
        sql.Column('bytesize', pd.Integer(not_null=True)),
        sql.Column('notes', pd.String()),
        sql.Column('log', pd.String()),
    )
    unique = (('page_id', 'lang', 'format', 'version',),)


class cms_v_publication_exports(CommonAccesRights, SQLView):
    name = 'cms_v_publication_exports'

    @classmethod
    def query(cls):
        exports = sql.t.cms_publication_exports.alias('e')
        return select(list(exports.c) +
                      [(stype(exports.c.page_id) + sval('.') + exports.c.lang).label('page_key')],
                      from_obj=exports)
    insert_order = (cms_publication_exports,)
    update_order = (cms_publication_exports,)
    delete_order = (cms_publication_exports,)


class cms_news(CommonAccesRights, Base_CachingTable):
    name = 'cms_news'
    fields = (
        sql.PrimaryColumn('news_id', pd.Serial(not_null=True)),
        sql.Column('page_id', pd.Integer(not_null=True),
                   references=sql.a(sql.r.cms_pages, ondelete='CASCADE')),
        sql.Column('lang', pd.String(minlen=2, maxlen=2, not_null=True),
                   references=sql.a(sql.r.cms_languages.lang, onupdate='CASCADE')),
        sql.Column('author', pd.Integer(not_null=True),
                   references=sql.r.users),
        sql.Column('timestamp', pd.DateTime(not_null=True), default=func.now()),
        sql.Column('title', pd.String(not_null=True)),
        sql.Column('content', pd.String(not_null=True)),
        sql.Column('days_displayed', pd.Integer(not_null=True)),
    )


class cms_v_news(CommonAccesRights, SQLView):
    name = 'cms_v_news'

    @classmethod
    def query(cls):
        n = sql.t.cms_news.alias('n')
        u = sql.t.users.alias('u')
        return select([n,
                       u.c.user_.label('author_name'),
                       u.c.login.label('author_login'),
                       ],
                      from_obj=[n.join(u, n.c.author == u.c.uid)])
    insert_order = (cms_news,)
    update_order = (cms_news,)
    delete_order = (cms_news,)
    no_insert_columns = ('news_id',)


class cms_recent_timestamp(sql.SQLFunction):
    """Return true if `ts' is not older than `max_days' days.  Needed for a pytis
    filtering condition (FunctionCondition is currently too simple to express
    this directly).
    """
    name = 'cms_recent_timestamp'
    arguments = (sql.Column('ts', pd.DateTime()),
                 sql.Column('max_days', pd.Integer()),)
    result_type = pd.Boolean()
    stability = 'stable'

    def body(self):
        """Return true if `ts' is not older than `max_days' days.  Needed for a pytis
        filtering condition (FunctionCondition is currently too simple to express
        this directly).
        """
        return 'select (current_date - $1::date) < $2'


class cms_planner(CommonAccesRights, Base_CachingTable):
    name = 'cms_planner'
    fields = (
        sql.PrimaryColumn('planner_id', pd.Serial(not_null=True)),
        sql.Column('page_id', pd.Integer(not_null=True),
                   references=sql.a(sql.r.cms_pages, ondelete='CASCADE')),
        sql.Column('lang', pd.String(minlen=2, maxlen=2, not_null=True),
                   references=sql.a(sql.r.cms_languages.lang, onupdate='CASCADE')),
        sql.Column('author', pd.Integer(not_null=True),
                   references=sql.r.users),
        sql.Column('timestamp', pd.DateTime(not_null=True), default=func.now()),
        sql.Column('start_date', pd.Date(not_null=True)),
        sql.Column('end_date', pd.Date()),
        sql.Column('title', pd.String(not_null=True)),
        sql.Column('content', pd.String(not_null=True)),
    )


class cms_v_planner(CommonAccesRights, SQLView):
    name = 'cms_v_planner'

    @classmethod
    def query(cls):
        p = sql.t.cms_planner.alias('p')
        u = sql.t.users.alias('u')
        return select([p,
                       u.c.user_.label('author_name'),
                       u.c.login.label('author_login'),
                       ],
                      from_obj=[p.join(u, p.c.author == u.c.uid)])
    insert_order = (cms_planner,)
    update_order = (cms_planner,)
    delete_order = (cms_planner,)
    no_insert_columns = ('planner_id',)


class cms_newsletters(CommonAccesRights, Base_CachingTable):
    name = 'cms_newsletters'
    fields = (
        sql.PrimaryColumn('newsletter_id', pd.Serial(not_null=True)),
        sql.Column('page_id', pd.Integer(not_null=True),
                   references=sql.a(sql.r.cms_pages, ondelete='CASCADE')),
        sql.Column('lang', pd.String(minlen=2, maxlen=2, not_null=True),
                   references=sql.a(sql.r.cms_languages.lang, onupdate='CASCADE')),
        sql.Column('title', pd.String(not_null=True)),
        sql.Column('image', pd.Binary(not_null=True)),
        sql.Column('image_width', pd.Integer(not_null=True)),
        sql.Column('image_height', pd.Integer(not_null=True)),
        sql.Column('description', pd.String(not_null=True)),
        sql.Column('sender', pd.String(not_null=True)),
        sql.Column('address', pd.String(not_null=True)),
        sql.Column('read_role_id', pd.PgName(not_null=True), default='anyone',
                   references=sql.a(sql.r.roles, onupdate='CASCADE')),
        sql.Column('write_role_id', pd.PgName(not_null=True), default='cms-content-admin',
                   references=sql.a(sql.r.roles, onupdate='CASCADE', ondelete='SET DEFAULT')),
        sql.Column('bg_color', pd.String(not_null=True)),
        sql.Column('text_color', pd.String(not_null=True)),
        sql.Column('link_color', pd.String(not_null=True)),
        sql.Column('heading_color', pd.String(not_null=True)),
        sql.Column('top_bg_color', pd.String(not_null=True)),
        sql.Column('top_text_color', pd.String(not_null=True)),
        sql.Column('top_link_color', pd.String(not_null=True)),
        sql.Column('footer_bg_color', pd.String(not_null=True)),
        sql.Column('footer_text_color', pd.String(not_null=True)),
        sql.Column('footer_link_color', pd.String(not_null=True)),
        sql.Column('signature', pd.String()),
    )


class cms_newsletter_subscription(CommonAccesRights, Base_CachingTable):
    name = 'cms_newsletter_subscription'
    fields = (
        sql.PrimaryColumn('subscription_id', pd.Serial(not_null=True)),
        sql.Column('newsletter_id', pd.Integer(not_null=True),
                   references=sql.a(sql.r.cms_newsletters, ondelete='CASCADE')),
        sql.Column('uid', pd.Integer(), references=sql.r.users),
        sql.Column('email', pd.String()),
        sql.Column('code', pd.String(), doc='Unsubscription code (email only)'),
        sql.Column('timestamp', pd.DateTime(not_null=True), default=func.now()),
    )
    check = ('(uid is not null or email is not null and code is not null) '
             'and (uid is null or email is null and code is null)',)
    unique = (('newsletter_id', 'uid',),
              ('newsletter_id', 'email',),)


class cms_v_newsletter_subscription(CommonAccesRights, SQLView):
    name = 'cms_v_newsletter_subscription'

    @classmethod
    def query(cls):
        s = sql.t.cms_newsletter_subscription.alias('s')
        u = sql.t.users.alias('u')
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
    delete_order = (cms_newsletter_subscription,)
    no_insert_columns = ('subscription_id',)


class cms_newsletter_editions(CommonAccesRights, Base_CachingTable):
    name = 'cms_newsletter_editions'
    fields = (
        sql.PrimaryColumn('edition_id', pd.Serial(not_null=True)),
        sql.Column('newsletter_id', pd.Integer(not_null=True),
                   references=sql.a(sql.r.cms_newsletters, ondelete='CASCADE')),
        sql.Column('creator', pd.Integer(not_null=True), references=sql.r.users),
        sql.Column('created', pd.DateTime(not_null=True), default=func.now()),
        sql.Column('sent', pd.DateTime()),
        sql.Column('access_code', pd.String()),
    )


class cms_newsletter_posts(CommonAccesRights, Base_CachingTable):
    name = 'cms_newsletter_posts'
    fields = (
        sql.PrimaryColumn('post_id', pd.Serial(not_null=True)),
        sql.Column('edition_id', pd.Integer(not_null=True),
                   references=sql.a(sql.r.cms_newsletter_editions, ondelete='CASCADE')),
        sql.Column('ord', pd.Integer()),
        sql.Column('title', pd.String(not_null=True)),
        sql.Column('content', pd.String(not_null=True)),
        sql.Column('image', pd.Binary()),
        sql.Column('image_position', pd.String()),
        sql.Column('image_width', pd.Integer()),
        sql.Column('image_height', pd.Integer()),
    )


class cms_discussions(CommonAccesRights, sql.SQLTable):
    name = 'cms_discussions'
    fields = (
        sql.PrimaryColumn('comment_id', pd.Serial(not_null=True)),
        sql.Column('page_id', pd.Integer(not_null=True),
                   references=sql.a(sql.r.cms_pages, ondelete='CASCADE')),
        sql.Column('lang', pd.String(minlen=2, maxlen=2, not_null=True),
                   references=sql.a(sql.r.cms_languages.lang, onupdate='CASCADE')),
        sql.Column('author', pd.Integer(not_null=True),
                   references=sql.r.users),
        sql.Column('timestamp', pd.DateTime(not_null=True), default=func.now()),
        sql.Column('in_reply_to', pd.Integer(),
                   references=sql.a(sql.r.cms_discussions, ondelete='SET NULL')),
        sql.Column('tree_order', pd.String(not_null=True), index=True),
        sql.Column('text', pd.String(not_null=True)),
    )


class cms_discussions_trigger_before_insert(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'cms_discussions_trigger_before_insert'
    arguments = ()
    table = cms_discussions
    position = 'before'
    events = ('insert',)


class cms_panels(CommonAccesRights, Base_CachingTable):
    name = 'cms_panels'
    fields = (
        sql.PrimaryColumn('panel_id', pd.Serial(not_null=True)),
        sql.Column('site', pd.String(not_null=True),
                   references=sql.a(sql.r.cms_config.site,
                                    onupdate='CASCADE', ondelete='CASCADE')),
        sql.Column('lang', pd.String(minlen=2, maxlen=2, not_null=True),
                   references=sql.a(sql.r.cms_languages.lang, onupdate='CASCADE')),
        sql.Column('identifier', pd.String()),
        sql.Column('title', pd.String(not_null=True)),
        sql.Column('ord', pd.Integer()),
        sql.Column('page_id', pd.Integer(),
                   references=sql.a(sql.r.cms_pages, ondelete='SET NULL')),
        sql.Column('size', pd.Integer()),
        sql.Column('content', pd.String()),
        sql.Column('_content', pd.String()),
        sql.Column('published', pd.Boolean(not_null=True), default=False),
    )
    unique = (('identifier', 'site', 'lang',),)


class cms_v_panels(CommonAccesRights, SQLView):
    name = 'cms_v_panels'

    @classmethod
    def query(cls):
        cms_panels = sql.t.cms_panels
        cms_pages = sql.t.cms_pages
        return select([cms_panels, cms_pages.c.modname, cms_pages.c.read_role_id],
                      from_obj=[cms_panels.
                                outerjoin(cms_pages, cms_panels.c.page_id == cms_pages.c.page_id)])
    insert_order = (cms_panels,)
    update_order = (cms_panels,)
    delete_order = (cms_panels,)

#


class cms_stylesheets(CommonAccesRights, Base_CachingTable):
    name = 'cms_stylesheets'
    fields = (
        sql.PrimaryColumn('stylesheet_id', pd.Serial(not_null=True)),
        sql.Column('site', pd.String(not_null=True),
                   references=sql.a(sql.r.cms_config.site,
                                    onupdate='CASCADE', ondelete='CASCADE')),
        sql.Column('filename', pd.String(maxlen=32, not_null=True)),
        sql.Column('active', pd.Boolean(not_null=True), default=True),
        sql.Column('scope', pd.String()),
        sql.Column('description', pd.String()),
        sql.Column('content', pd.String()),
        sql.Column('ord', pd.Integer()),
    )
    unique = (('filename', 'site',),)
    init_columns = ('filename', 'site', 'ord',)
    init_values = (
        ('default.css', '*', 10),
    )


class cms_themes(CommonAccesRights, Base_CachingTable):
    name = 'cms_themes'
    fields = (
        sql.PrimaryColumn('theme_id', pd.Serial(not_null=True),
                          references=sql.r.cms_themes),
        sql.Column('name', pd.String(not_null=True), unique=True),
        sql.Column('foreground', pd.String(maxlen=7)),
        sql.Column('background', pd.String(maxlen=7)),
        sql.Column('border', pd.String(maxlen=7)),
        sql.Column('heading_fg', pd.String(maxlen=7)),
        sql.Column('heading_bg', pd.String(maxlen=7)),
        sql.Column('heading_line', pd.String(maxlen=7)),
        sql.Column('frame_fg', pd.String(maxlen=7)),
        sql.Column('frame_bg', pd.String(maxlen=7)),
        sql.Column('frame_border', pd.String(maxlen=7)),
        sql.Column('link', pd.String(maxlen=7)),
        sql.Column('link_visited', pd.String(maxlen=7)),
        sql.Column('link_hover', pd.String(maxlen=7)),
        sql.Column('meta_fg', pd.String(maxlen=7)),
        sql.Column('meta_bg', pd.String(maxlen=7)),
        sql.Column('help', pd.String(maxlen=7)),
        sql.Column('error_fg', pd.String(maxlen=7)),
        sql.Column('error_bg', pd.String(maxlen=7)),
        sql.Column('error_border', pd.String(maxlen=7)),
        sql.Column('message_fg', pd.String(maxlen=7)),
        sql.Column('message_bg', pd.String(maxlen=7)),
        sql.Column('message_border', pd.String(maxlen=7)),
        sql.Column('table_cell', pd.String(maxlen=7)),
        sql.Column('table_cell2', pd.String(maxlen=7)),
        sql.Column('top_fg', pd.String(maxlen=7)),
        sql.Column('top_bg', pd.String(maxlen=7)),
        sql.Column('top_border', pd.String(maxlen=7)),
        sql.Column('highlight_bg', pd.String(maxlen=7)),
        sql.Column('inactive_folder', pd.String(maxlen=7)),
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


class cms_system_text_labels(CommonAccesRights, Base_CachingTable):
    name = 'cms_system_text_labels'
    fields = (
        sql.Column('label', pd.PgName(not_null=True)),
        sql.Column('site', pd.String(not_null=True),
                   references=sql.a(sql.r.cms_config.site,
                                    onupdate='CASCADE', ondelete='CASCADE')),
    )
    unique = (('label', 'site',),)


class cms_add_text_label(sql.SQLPlFunction):
    """"""
    name = 'cms_add_text_label'
    arguments = (
        sql.Column('_label', pd.PgName()),
        sql.Column('_site', pd.String()),
    )
    result_type = None


class cms_system_texts(CommonAccesRights, Base_CachingTable):
    name = 'cms_system_texts'
    fields = (
        sql.Column('label', pd.PgName(not_null=True)),
        sql.Column('site', pd.String(not_null=True)),
        sql.Column('lang', pd.String(minlen=2, maxlen=2, not_null=True),
                   references=sql.a(sql.r.cms_languages.lang,
                                    onupdate='CASCADE', ondelete='CASCADE')),
        sql.Column('description', pd.String(), default=''),
        sql.Column('content', pd.String(), default=''),
    )
    unique = (('label', 'site', 'lang',),)
    foreign_keys = (sql.a(('label', 'site',),
                          (sql.r.cms_system_text_labels.label, sql.r.cms_system_text_labels.site,),
                          onupdate='CASCADE', ondelete='CASCADE'),)


class cms_v_system_text_labels(CommonAccesRights, SQLView):
    name = 'cms_v_system_text_labels'

    @classmethod
    def query(cls):
        labels = sql.t.cms_system_text_labels
        languages = sql.t.cms_languages
        return select([labels.c.label, labels.c.site, languages.c.lang],
                      from_obj=[labels, languages])


class cms_v_system_texts(CommonAccesRights, SQLView):
    name = 'cms_v_system_texts'

    @classmethod
    def query(cls):
        labels = sql.t.cms_v_system_text_labels
        texts = sql.t.cms_system_texts
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
    # delete_order = (cms_system_text_labels,)

    def on_delete(self):
        return ("delete from cms_system_text_labels where label = old.label and site = old.site;",)

#


class cms_email_labels(CommonAccesRights, sql.SQLTable):
    name = 'cms_email_labels'
    fields = (
        sql.PrimaryColumn('label', pd.PgName(not_null=True)),
    )


class cms_add_email_label(sql.SQLPlFunction):
    name = 'cms_add_email_label'
    arguments = (
        sql.Column('_label', pd.PgName()),
    )
    result_type = None


class cms_emails(CommonAccesRights, sql.SQLTable):
    name = 'cms_emails'
    fields = (
        sql.Column('label', pd.PgName(not_null=True),
                   references=sql.r.cms_email_labels),
        sql.Column('lang', pd.String(minlen=2, maxlen=2, not_null=True),
                   references=sql.a(sql.r.cms_languages.lang,
                                    onupdate='CASCADE', ondelete='CASCADE')),
        sql.Column('description', pd.String()),
        sql.Column('subject', pd.String()),
        sql.Column('cc', pd.String()),
        sql.Column('content', pd.String(), default=''),
    )
    unique = (('label', 'lang',),)


class cms_v_emails(CommonAccesRights, SQLView):
    name = 'cms_v_emails'

    @classmethod
    def query(cls):
        el = sql.c.cms_email_labels
        lang = sql.c.cms_languages
        e = sql.c.cms_emails
        return select([(el.label + sval(':') + lang.lang).label('text_id'),
                       el.label, lang.lang, e.description, e.subject, e.cc, e.content],
                      from_obj=[sql.t.cms_email_labels,
                                sql.t.cms_languages.outerjoin(sql.t.cms_emails)],
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


class cms_email_attachments(CommonAccesRights, sql.SQLTable):
    name = 'cms_email_attachments'
    fields = (
        sql.PrimaryColumn('attachment_id', pd.Serial(not_null=True)),
        sql.Column('label', pd.PgName(not_null=True),
                   references=sql.a(sql.r.cms_email_labels, ondelete='CASCADE')),
        sql.Column('filename', pd.String(not_null=True)),
        sql.Column('mime_type', pd.String(not_null=True)),
    )


class cms_email_spool(CommonAccesRights, sql.SQLTable):
    name = 'cms_email_spool'
    fields = (
        sql.PrimaryColumn('id', pd.Serial(not_null=True)),
        sql.Column('sender_address', pd.String()),
        sql.Column('role_id', pd.PgName(),
                   references=sql.a(sql.r.roles, onupdate='CASCADE', ondelete='CASCADE'),
                   doc="recipient role, if NULL then all users"),
        sql.Column('subject', pd.String()),
        sql.Column('content', pd.String(),
                   doc="body of the e-mail"),
        sql.Column('date', pd.DateTime(), default=func.now(),
                   doc="time of insertion"),
        sql.Column('pid', pd.Integer()),
        sql.Column('finished', pd.Boolean(not_null=False), default=False,
                doc="set TRUE after the mail was successfully sent"),
    )


class cms_crypto_names(CommonAccesRights, sql.SQLTable):
    name = 'cms_crypto_names'
    fields = (
        sql.PrimaryColumn('name', pd.String(not_null=True)),
        sql.Column('description', pd.String()),
    )
    init_columns = ('name', 'description',)
    access_rights = (('ALL', 'www-data',),)


class cms_crypto_keys(CommonAccesRights, sql.SQLTable):
    name = 'cms_crypto_keys'
    fields = (
        sql.PrimaryColumn('key_id', pd.Serial(not_null=True)),
        sql.Column('name', pd.String(not_null=True),
                   references=sql.a(sql.r.cms_crypto_names,
                                    onupdate='CASCADE', ondelete='CASCADE')),
        sql.Column('uid', pd.Integer(not_null=True),
                   references=sql.a(sql.r.users, onupdate='CASCADE', ondelete='CASCADE')),
        sql.Column('key', pd.Binary(not_null=True)),
    )
    unique = (('name', 'uid',),)
    access_rights = (('ALL', 'www-data',),)


class cms_crypto_extract_key(sql.SQLPlFunction):
    name = 'cms_crypto_extract_key'
    arguments = (sql.Column('encrypted', pd.Binary()),
                 sql.Column('psw', pd.String()),)
    result_type = pd.String()
    stability = 'immutable'


class cms_crypto_store_key(sql.SQLPlFunction):
    "This is a PL/pgSQL, and not SQL, function in order to prevent direct dependency on pg_crypto."
    name = 'cms_crypto_store_key'
    arguments = (sql.Column('key', pd.String()),
                 sql.Column('psw', pd.String()),)
    result_type = pd.Binary()
    stability = 'immutable'

    def body(self):
        return "begin return pgp_sym_encrypt('wiking:'||$1, $2); end;"


class cms_crypto_insert_key(sql.SQLPlFunction):
    name = 'cms_crypto_insert_key'
    arguments = (sql.Column('name_', pd.String()),
                 sql.Column('uid_', pd.Integer()),
                 sql.Column('key_', pd.String()),
                 sql.Column('psw', pd.String()),)
    result_type = pd.Boolean()


class cms_crypto_change_password(sql.SQLPlFunction):
    name = 'cms_crypto_change_password'
    arguments = (sql.Column('id_', pd.Integer()),
                 sql.Column('old_psw', pd.String()),
                 sql.Column('new_psw', pd.String()),)
    result_type = pd.Boolean()


class cms_crypto_copy_key(sql.SQLPlFunction):
    name = 'cms_crypto_copy_key'
    arguments = (sql.Column('name_', pd.String()),
                 sql.Column('from_uid', pd.Integer()),
                 sql.Column('to_uid', pd.Integer()),
                 sql.Column('from_psw', pd.String()),
                 sql.Column('to_psw', pd.String()),)
    result_type = pd.Boolean()


class cms_crypto_delete_key(sql.SQLPlFunction):
    name = 'cms_crypto_delete_key'
    arguments = (sql.Column('name_', pd.String()),
                 sql.Column('uid_', pd.Integer()),
                 sql.Column('force', pd.Boolean()),)
    result_type = pd.Boolean()

#


class cms_crypto_unlocked_passwords(CommonAccesRights, sql.SQLTable):
    name = 'cms_crypto_unlocked_passwords'
    fields = (
        sql.Column('key_id', pd.Integer(not_null=True),
                   references=sql.a(sql.r.cms_crypto_keys,
                                    onupdate='CASCADE', ondelete='CASCADE')),
        sql.Column('password', pd.Binary()),
    )
    access_rights = (('ALL', 'www-data',),)


class cms_crypto_unlocked_passwords_insert_trigger(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'cms_crypto_unlocked_passwords_insert_trigger'
    arguments = ()
    table = cms_crypto_unlocked_passwords
    position = 'before'
    events = ('insert',)


class cms_crypto_unlock_passwords(sql.SQLFunction):
    name = 'cms_crypto_unlock_passwords'
    arguments = (sql.Column('uid_', pd.Integer()),
                 sql.Column('psw', pd.String()),
                 sql.Column('cookie', pd.String()),)
    result_type = None
    depends_on = (cms_crypto_unlocked_passwords,)


class cms_crypto_lock_passwords(sql.SQLFunction):
    name = 'cms_crypto_lock_passwords'
    arguments = (sql.Column('uid_', pd.Integer()),)
    result_type = None
    depends_on = (cms_crypto_unlocked_passwords,)


class cms_crypto_cook_passwords(sql.SQLPlFunction):
    name = 'cms_crypto_cook_passwords'
    arguments = (sql.Column('uid_', pd.Integer()),
                 sql.Column('cookie', pd.String()),)
    result_type = pd.String()
    multirow = True


class pytis_crypto_unlock_current_user_passwords(sql.SQLFunction):
    """Dummy function to avoid error messages in logs (called by Pytis)."""
    name = 'pytis_crypto_unlock_current_user_passwords'
    arguments = (sql.Column('password_', pd.String()),)
    result_type = pd.String()
    multirow = True
    stability = 'immutable'

    def body(self):
        return "select ''::text where false;"


class pytis_crypto_db_key(sql.SQLFunction):
    """Dummy function needed by Pytis initialization when dbpass is set."""
    name = 'pytis_crypto_db_key'
    arguments = (
        sql.Column('key_name_', pd.String()),
    )
    result_type = pd.String()
    multirow = False
    stability = 'STABLE'
    security_definer = True

    def body(self):
        return "select null::text;"
