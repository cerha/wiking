#!/usr/bin/env python

# Copyright (C) 2011, 2012 Brailcom, o.p.s.
#
# COPYRIGHT NOTICE
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

"""Update Wiking CMS attachment thumbnails in the database.

Thumbnails are normally updated automatically on source image changes, but when
the administrator decides to change the thumbnail sizes (configuration option
image_thumbnail_sizes of Wiking CMS), all thumbnails must be regenerated to
match the new settings.

"""

import sys, getopt, types, os, cStringIO, PIL.Image
import pytis.util, pytis.data as pd, config

def usage(msg=None):
    sys.stderr.write("""Update Wiking attachment thumbnails in the database.
Usage: %s [options]
Options: Pytis command line options, such as --config or --dbhost and --dbname.
""" % sys.argv[0])
    if msg:
        sys.stderr.write(msg)
        sys.stderr.write('\n')
    sys.exit(1)

def run():
    if '--help' in sys.argv:
        usage()
    try:
        config.add_command_line_options(sys.argv)
        if len(sys.argv) > 1:
            usage()
    except getopt.GetoptError as e:
        usage(e.msg)
    # Disable pytis logging and notification thread.
    config.dblisten = False
    # Disable pytis logging of data operations etc.
    config.log_exclude = [pytis.util.ACTION, pytis.util.EVENT, pytis.util.DEBUG, pytis.util.OPERATIONAL]

    while True:
        try:
            data = pd.dbtable('_attachments',
                              ('attachment_id', 'mime_type', 'filename',
                               'listed', 'image', 'thumbnail', 'thumbnail_size',
                               'thumbnail_width', 'thumbnail_height'),
                              config.dbconnection)
        except pd.DBLoginException as e:
            if config.dbconnection.password() is None:
                import getpass
                login = config.dbuser
                password = getpass.getpass("Enter database password for %s: " % login)
                config.dbconnection.update_login_data(user=login, password=password)
            else:
                sys.stderr.write(e.message())
                sys.exit(1)
        else:
            break
    data.select()
    rows = []
    while True:
        row = data.fetchone()
        if row is None:
            break
        else:
            rows.append(row)
    for row in rows:
        ext = os.path.splitext(row['filename'].value())[1].lower()
        fname = os.path.join('/var/lib/wiking', config.dbname, 'attachments',
                             str(row['attachment_id'].value()) + ext)
        try:
            image = PIL.Image.open(file(fname))
        except IOError:
            continue
        else:
            if image.size[0] > 400 or image.size[1] > 400:
                img = image.copy()
                img.thumbnail((180, 180), PIL.Image.ANTIALIAS)
                stream = cStringIO.StringIO()
                img.save(stream, image.format)
                img2 = image.copy()
                img2.thumbnail((800, 600), PIL.Image.ANTIALIAS)
                stream2 = cStringIO.StringIO()
                img2.save(stream2, image.format)
                row['thumbnail'] = pd.Value(pd.Image(), pd.Image.Buffer(buffer(stream.getvalue())))
                row['image'] = pd.Value(pd.Image(), pd.Image.Buffer(buffer(stream2.getvalue())))
                row['thumbnail_size'] = pd.sval('medium')
                row['thumbnail_width'] = pd.ival(img.size[0])
                row['thumbnail_height'] = pd.ival(img.size[1])
                row['listed'] = pd.bval(False)
                print row['filename'].value(), image.size, img.size
                data.update(row['attachment_id'], row)


if __name__ == '__main__':
    run()
