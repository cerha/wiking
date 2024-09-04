#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011, 2012, 2013 OUI Technology Ltd.
# Copyright (C) 2019-2021, 2024 Tomáš Cerha <t.cerha@gmail.com>
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
image_thumbnail_sizes of Wiking CMS) or resized image size (configuration
option image_screen_size), thumbnails and rezized images must be regenerated to
match the new settings.

"""
import sys
import getopt
import os
import io
import PIL.Image

import pytis
import pytis.util
import pytis.data as pd
import wiking
import wiking.cms


def usage(msg=None):
    sys.stderr.write("""Update Wiking attachment thumbnails in the database.
Usage: %s [options]
Options: Pytis command line options, such as --config or --dbhost and --dbname.
""" % sys.argv[0])
    if msg:
        sys.stderr.write(msg)
        sys.stderr.write('\n')
    sys.exit(1)


def resize(image, size):
    img = image.copy()
    img.thumbnail(size, PIL.Image.LANCZOS)
    stream = io.BytesIO()
    img.save(stream, image.format)
    return stream.getvalue(), img.size


def run():
    if '--help' in sys.argv:
        usage()
    try:
        pytis.config.add_command_line_options(sys.argv)
        if len(sys.argv) > 1:
            usage()
    except getopt.GetoptError as e:
        usage(e.msg)
    wiking.cfg.user_config_file = pytis.config.config_file
    pytis.config.dblisten = False
    pytis.config.log_exclude = [pytis.util.ACTION, pytis.util.EVENT,
                                pytis.util.DEBUG, pytis.util.OPERATIONAL]
    while True:
        try:
            data = pd.dbtable('cms_page_attachments',
                              ('attachment_id', 'filename', 'width', 'height',
                               'image', 'image_width', 'image_height', 'thumbnail',
                               'thumbnail_size', 'thumbnail_width', 'thumbnail_height'),
                              pytis.config.dbconnection)
        except pd.DBLoginException as e:
            if pytis.config.dbconnection.password() is None:
                import getpass
                login = pytis.config.dbuser
                password = getpass.getpass("Enter database password for %s: " % login)
                pytis.config.dbconnection.update_login_data(user=login, password=password)
        else:
            break
    image_screen_size = wiking.cms.cfg.image_screen_size
    image_thumbnail_sizes = wiking.cms.cfg.image_thumbnail_sizes
    transaction = pd.transaction()
    data.select(transaction=transaction)
    try:
        while True:
            row = data.fetchone()
            if row is None:
                break
            ext = os.path.splitext(row['filename'].value())[1].lower()
            path = os.path.join(wiking.cms.cfg.storage, pytis.config.dbname, 'attachments',
                                row['attachment_id'].export() + (ext or '.'))
            attachment = open(path, 'rb')
            try:
                image = PIL.Image.open(attachment)
            except IOError as e:
                continue
            sys.stderr.write("Resizing %s (%dx%d): " %
                             (row['filename'].value(), image.size[0], image.size[1]))
            thumbnail_size = row['thumbnail_size'].value()
            if thumbnail_size is None:
                thumbnail_value, real_thumbnail_size = None, (None, None)
            else:
                if thumbnail_size == 'small':
                    size = image_thumbnail_sizes[0]
                elif thumbnail_size == 'medium':
                    size = image_thumbnail_sizes[1]
                else:
                    size = image_thumbnail_sizes[2]
                thumbnail_value, real_thumbnail_size = resize(image, (size, size))
                sys.stderr.write("%dx%d, " % real_thumbnail_size)
            resized_image_value, resized_image_size = resize(image, image_screen_size)
            sys.stderr.write("%dx%d\n" % resized_image_size)
            values = dict(
                width=image.size[0],
                height=image.size[1],
                thumbnail=thumbnail_value,
                thumbnail_width=real_thumbnail_size[0],
                thumbnail_height=real_thumbnail_size[1],
                image=resized_image_value,
                image_width=resized_image_size[0],
                image_height=resized_image_size[1],
            )
            r = pd.Row([(key, pd.Value(row[key].type(), value)) for key, value in values.items()])
            data.update(row['attachment_id'], r, transaction=transaction)
    except Exception:
        try:
            transaction.rollback()
        except Exception:
            pass
        sys.stderr.write("Transaction rolled back.\n")
        raise
    else:
        sys.stderr.write("Transaction commited.\n")
        transaction.commit()
    transaction.close()


if __name__ == '__main__':
    run()
