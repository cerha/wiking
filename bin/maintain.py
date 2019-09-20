#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2008, 2010 OUI Technology Ltd.
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


# This is the Wiking periodic maintenance script.
# It is recommended to run it (at least) once a day.
# Currently it is only needed to be run if you use user registration with
# e-mails as login names.


import psycopg2 as dbapi

import wiking


def open_database():
    database = wiking.cfg.dbname
    connection = dbapi.connect(database=database)
    return connection


def delete_expired_registrations():
    db_connection = open_database()
    db_cursor = db_connection.cursor()
    sql_query = "delete from users where state='new' and regexpire < now()"
    db_cursor.execute(sql_query)


def run():
    delete_expired_registrations()

if __name__ == '__main__':
    run()
