#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2008, 2009 OUI Technology Ltd.
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

# This script serves for importing texts into database (the `_text' table).
# It requires two command line arguments:
#   DATABASE -- name of the database to connect to
#   DIRECTORY -- directory containing text files
# it must contain files named `NAMESPACE.LABEL.LANGUAGECODE.txt'.  For each such
# file the contents of the file, that must be a structured text, is imported
# into the database.  NAMESPACE, LABEL and LANGUAGECODE attributes of the
# stored text are defined by the file name.

import codecs
import os
import sys

import pytis
import pytis.data

pytis.config.log_exclude = [pytis.util.ACTION, pytis.util.EVENT, pytis.util.DEBUG]


def usage():
    print('usage: %s DATABASE DIRECTORY' % (sys.argv[0],))
    sys.exit(1)


def data_object(table, columns, connection):
    bindings = [pytis.data.DBColumnBinding(column, table, column) for column in columns]
    factory = pytis.data.DataFactory(pytis.data.DBDataDefault, bindings, bindings[0])
    return factory.create(dbconnection_spec=connection)


def import_texts(database, directory):
    connection = pytis.data.DBConnection(database=database)
    data = data_object('texts', ('text_id', 'label', 'lang', 'content'), connection)
    label_data = data_object('text_labels', ('label',), connection)
    label_column_type = label_data.columns()[0].type()
    for filename in os.listdir(directory):
        parts = filename.split('.')
        print("  - %s ..." % filename, end=' ')
        if filename.endswith('.txt') and len(parts) == 4:
            label = '.'.join(parts[:2])
            lang = parts[2]
            label_key = label_column_type.validate(label)[0]
            if not label_data.row(label_key):
                print("new label `%s' ..." % label, end=' ')
                label_data.insert(pytis.data.Row([('label', label_key)]))
            else:
                print("updating label `%s' ..." % label, end=' ')
            content = codecs.open(os.path.join(directory, filename), 'r', 'utf-8').read()
            text_id = label + '@' + lang
            row_data = [(c.id(), c.type().validate(v)[0],)
                        for c, v in zip(data.columns(), [text_id, label, lang, content])]
            row = pytis.data.Row(row_data)
            error, success = data.update(row[0], row)
            if success:
                print("done")
            else:
                print("FAILED:", error)
        else:
            print("ignored (file name doesn't match the required pattern)")


def run():
    if len(sys.argv) != 3:
        usage()
    database = sys.argv[1]
    directory = sys.argv[2]
    import_texts(database, directory)


if __name__ == '__main__':
    run()
