#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 OUI Technology Ltd.
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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import unittest
import wiking


class Utils(unittest.TestCase):

    def test_password_storage(self):
        ustorage = wiking.UniversalPasswordStorage()
        for prefix, storage in (('plain', wiking.PlainTextPasswordStorage()),
                                ('md5u', wiking.UnsaltedMd5PasswordStorage()),
                                ('pbkdf2', wiking.Pbkdf2PasswordStorage()),
                                ('pbkdf2/md5', wiking.Pbkdf2Md5PasswordStorage()),
                                (None, wiking.UniversalPasswordStorage())):
            for passwd in ('bla', 'xxxxx', 'wer2d544aSWdD5', '34čůdl1G5'):
                stored = storage.stored_password(passwd)
                if not isinstance(storage, wiking.PlainTextPasswordStorage):
                    self.assertNotEqual(stored, passwd, (storage, passwd, stored))
                    if not isinstance(storage, wiking.UnsaltedMd5PasswordStorage):
                        stored2 = storage.stored_password(passwd)
                        # Check that salting works (two hashes of the same password not equal)
                        self.assertNotEqual(stored, stored2, (storage, passwd, stored))
                self.assertTrue(storage.check_password(passwd, stored), (storage, passwd, stored))
                self.assertFalse(storage.check_password('xx', stored), (storage, passwd, stored))
                if prefix:
                    self.assertTrue(ustorage.check_password(passwd, prefix + ':' + stored),
                                    (prefix, storage, passwd, stored))
                    self.assertFalse(ustorage.check_password('xx', prefix + ':' + stored),
                                     (prefix, storage, passwd, stored))


if __name__ == '__main__':
    unittest.main()
