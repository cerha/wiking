#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2008 Brailcom, o.p.s.
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


## This script serves for importing texts into database (the `_text' table).
## It requires two command line arguments:
##   DATABASE -- name of the database to connect to
##   DIRECTORY -- directory containing text files
## DIRECTORY is typically `sql/texts/' subdirectory of a Wiking extension and
## it must contain files named NAMESPACE.LABEL@LANGUAGECODE.  For each such
## file the contents of the file, that must be a structured text, is imported
## into the database.  NAMESPACE, LABEL and LANGUAGECODE attributes of the
## stored text are defined by the file name.


import codecs
import os
import re
import sys

import pytis.data

def usage():
    print 'usage: %s DATABASE DIRECTORY' % (sys.argv[0],)
    sys.exit(1)

def import_texts(database, directory):
    connection = pytis.data.DBConnection(database=database)
    # `texts' specification
    C = pytis.data.DBColumnBinding
    columns = [pytis.data.DBColumnBinding(column, 'texts', column) for column in 'text_id', 'label', 'lang', 'content',]
    factory = pytis.data.DataFactory(pytis.data.DBDataDefault, columns, columns[0])
    data = factory.create(dbconnection_spec=connection)
    data_columns = data.columns()
    # `text_labels' specification
    label_columns = [pytis.data.DBColumnBinding('label', 'text_labels', 'label')]
    label_factory = pytis.data.DataFactory(pytis.data.DBDataDefault, label_columns, label_columns[0])
    label_data = label_factory.create(dbconnection_spec=connection)
    label_column_type = label_data.columns()[0].type()
    # Data insertion
    file_regexp = re.compile('^(.+\..+)@(.+)$')
    for file in os.listdir(directory):
        match = file_regexp.match(file)
        if match:
            print "Importing file %s ..." % (file,),
            label, lang = match.groups()
            label_key = label_column_type.validate(label)[0]
            if not label_data.row(label_key):
                print "[adding new text label `%s'] ..." % (label,),
                label_data.insert(pytis.data.Row([('label', label_key,)]))
            content = codecs.open(os.path.join(directory, file), 'r', 'utf-8').read()
            row_data = [(c.id(), c.type().validate(v)[0],) for c, v in zip(data_columns, [file, label, lang, content])]
            row = pytis.data.Row(row_data)
            if data.update(row[0], row)[1]:
                print "done"
            else:
                print "FAILED"
        else:
            print "File name doesn't match required pattern, ignored: %s" % (file,)
    
def run():
    if len(sys.argv) != 3:
        usage()
    database = sys.argv[1]
    directory = sys.argv[2]
    import_texts(database, directory)

if __name__ == '__main__':
    run()

