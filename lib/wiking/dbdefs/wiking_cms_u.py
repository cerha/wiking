# -*- coding: utf-8 -*-

# Copyright (C) 2006-2013 Brailcom, o.p.s.
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


# Untrusted definitions, to be imported by a PostgreSQL superuser.


from __future__ import unicode_literals

import pytis.data.gensqlalchemy as sql
import pytis.data

from wiking_cms import RoleSets

class RoleSetsCycleCheck(sql.SQLPyFunction):
    name = 'role_sets_cycle_check'
    arguments = ()
    result_type = pytis.data.Boolean()
    @staticmethod
    def role_sets_cycle_check():
        connections = {}
        unvisited = {}
        for row in plpy.execute("select role_id, member_role_id from role_sets"):
            role_id, member_role_id = row['role_id'], row['member_role_id']
            edges = connections.get(role_id)
            if edges is None:
                edges = connections[role_id] = []
                unvisited[role_id] = True
            edges.append(member_role_id)
        def dfs(node):
            unvisited[node] = False
            for next in connections[node]:
                status = unvisited.get(next)
                if status is None:
                    continue
                if status is False or not dfs(next):
                    return False
            del unvisited[node]
            return True
        while unvisited:
            if not dfs(unvisited.keys()[0]):
                return False
        return True

class RoleSetsTriggerAfter(sql.SQLPlFunction, sql.SQLTrigger):
    name = 'role_sets_trigger_after'
    arguments = ()
    table = RoleSets
    position = 'after'
    events = ('insert', 'update', 'delete',)
