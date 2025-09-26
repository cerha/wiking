# -*- coding: utf-8 -*-

# Copyright (C) 2013 OUI Technology Ltd.
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

import pytis.data.gensqlalchemy as sql
import pytis.data


class CommonAccesRights:
    access_rights = (('all', 'www-data'),)


class CachedTables(CommonAccesRights, sql.SQLTable):
    """Information about data versions of cached tables.
    Cached tables are tables or views with data cached in Wiking application
    accross HTTP requests.
    """
    name = 'cached_tables'
    fields = (sql.Column('object_schema', pytis.data.String()),
              sql.Column('object_name', pytis.data.String()),
              sql.Column('version', pytis.data.Integer(), default=1),
              sql.Column('stamp', pytis.data.DateTime(utc=True)),
              sql.Column('_processed', pytis.data.Boolean(not_null=True), default=False,
                         doc="Flag for processing in FUpdateCachedTables"),
              )


class FUpdateCachedTables(sql.SQLPlFunction):
    """Trigger function to increase data versions of cached tables.
    It increments version of both the given SCHEMA_.NAME_ table and
    of all the dependent tables.
    """
    name = 'f_update_cached_tables'
    arguments = (sql.Argument('schema_', pytis.data.String()),
                 sql.Argument('name_', pytis.data.String()),
                 sql.Argument('top_', pytis.data.Boolean()),
                 )
    result_type = None
    depends_on = (CachedTables,)


class FUpdateCachedTablesAfter(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'f_update_cached_tables_after'
    events = ()
    arguments = ()
    depends_on = (FUpdateCachedTables,)


class CachedTablesUpdateTrigger(sql.SQLTrigger):
    name = 'cached_tables_update_trigger'
    events = ('insert', 'update', 'delete', 'truncate',)
    position = 'after'
    each_row = False
    body = FUpdateCachedTablesAfter


class Base_CachingTable(sql.SQLTable):
    """Base class for tables with CachedTablesUpdateTrigger.
    Such tables increase their version in CachedTables on each modification.
    """
    @property
    def triggers(self):
        return (super(Base_CachingTable, self).triggers +
                ((CachedTablesUpdateTrigger, self.schema, self.pytis_name(), True,),))
