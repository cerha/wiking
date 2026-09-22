# -*- coding: utf-8 -*-

# Copyright (C) 2026 Tomáš Cerha <cerha@truecode.cz>
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

"""Tests of Wiking CMS and base classes for tests of applications based on it.

Wiking CMS is an application built on top of the Wiking framework, so unlike
the framework tests in 'wiking.test' (which these classes derive from), the
tests here need the application's database -- a PostgreSQL database containing
the Wiking CMS schema (see the 'db' target in the Makefile).  The database name
may be changed through the environment variable 'WIKING_TEST_DB'.

The class 'CMSTest' also serves as the base class of the tests of applications
built on top of Wiking CMS, as they share its database schema (and thus the
fixtures defined here).

"""

import os
import re

import psycopg2

import wiking
import wiking.test


class CMSTest(wiking.test.Test):
    """Base class of tests of Wiking CMS applications.

    Creates a temporary user of the roles given by 'ROLES' and removes it, with
    everything it created in the database, when done.  The tests thus neither
    depend on the contents of the database nor leave anything behind.

    Applications based on Wiking CMS may derive their tests from this class.
    They will typically define their own 'config_file' (the configuration of
    this class only enables the plain CMS), 'database', 'host' and 'ROLES'.

    """
    host = 'localhost'
    language = 'en'
    config_options = dict(modules=('wiking.cms',))

    database = os.environ.get('WIKING_TEST_DB', 'wiking-test')
    """Name of the tested application's database."""

    LOGIN = 'wiking-test@example.com'
    PASSWORD = 'W1king-t3st'
    ROLES = ()
    """Identifiers of the roles assigned to the test user (strings)."""

    PAGE_CONTENT = 'The content of the page created by the test suite.'
    PAGE_IDENTIFIER_PREFIX = 'wiking-test-'
    """Identifier prefix of the pages created by the tests.

    All pages with this prefix are deleted when the tests are done.

    """

    @classmethod
    def _config_options(class_):
        return dict(super(CMSTest, class_)._config_options(), dbname=class_.database)

    @classmethod
    def setUpClass(class_):
        super(CMSTest, class_).setUpClass()
        class_._connection = psycopg2.connect(database=class_.database)
        if not class_.query("select site from cms_config where site = %s", (class_.host,)):
            # The application renames the initial '*' configuration row to the
            # actual site name itself, but only on the first request, while the
            # pages created below need the site to exist already.
            class_.query("update cms_config set site = %s where site = '*'", (class_.host,))
        class_._delete_test_user()
        class_.uid = class_.query(
            "insert into users (login, password, firstname, surname, user_, email, "
            "last_password_change, state) "
            "values (%s, %s, 'Wiking', 'Test', 'Wiking Test', %s, now(), 'enabled') "
            "returning uid",
            (class_.LOGIN, wiking.UniversalPasswordStorage().stored_password(class_.PASSWORD),
             class_.LOGIN),
        )[0][0]
        for role_id in class_.ROLES:
            class_.query("insert into role_members (role_id, uid) values (%s, %s)",
                         (role_id, class_.uid))
        class_._create_pages()

    @classmethod
    def _create_pages(class_):
        """Create the pages needed by the tests.

        The plain CMS database contains no pages at all, so a publicly readable
        page is created here to make the site behave as a real site does.
        Applications tested against their own database usually have their pages
        already, so they override this method to do nothing.

        """
        class_.query(
            "insert into cms_v_pages (site, kind, identifier, lang, title, _content, "
            "published, parents_published, creator, created, menu_visibility, "
            "read_role_id, write_role_id, ord) "
            "values (%s, 'page', %s, %s, 'Wiking Test Page', %s, true, true, %s, now(), "
            "'always', 'anyone', 'cms-content-admin', 1)",
            (class_.host, class_.PAGE_IDENTIFIER_PREFIX + 'home', class_.language,
             class_.PAGE_CONTENT, class_.uid))

    @classmethod
    def tearDownClass(class_):
        class_._delete_test_user()
        class_._connection.close()

    @classmethod
    def query(class_, query, args=()):
        """Perform given SQL query and return its result as a list of tuples (or None)."""
        cursor = class_._connection.cursor()
        cursor.execute(query, args)
        result = cursor.fetchall() if cursor.description else None
        class_._connection.commit()
        return result

    @classmethod
    def _delete_test_user(class_):
        class_.query("delete from cms_pages where identifier like %s",
                     (class_.PAGE_IDENTIFIER_PREFIX + '%',))
        class_.delete_user(class_.LOGIN)

    @classmethod
    def delete_user(class_, login):
        """Delete given user account and everything it created in the database."""
        rows = class_.query("select uid from users where login = %s", (login,))
        if not rows:
            return
        uid = rows[0][0]
        # Delete the rows referring to the user from the tables which don't
        # cascade the deletion themselves (pages, the access log etc.).
        for table, column in class_.query(
                "select c.conrelid::regclass::text, a.attname from pg_constraint c "
                "join pg_attribute a on a.attrelid = c.conrelid and a.attnum = c.conkey[1] "
                "where c.contype = 'f' and c.confrelid = 'users'::regclass "
                "and c.confdeltype = 'a'"):
            class_.query("delete from %s where %s = %%s" % (table, column), (uid,))
        class_.query("delete from users where uid = %s", (uid,))


class TestLogin(CMSTest):
    """Test logging in and out through the login form."""

    def test_login(self):
        response = self._login(self.LOGIN, self.PASSWORD)
        self.assertTrue(self._logged_in(response))
        self.assertIn('Wiking Test', response)

    def test_invalid_password(self):
        response = self._login(self.LOGIN, 'invalid password')
        self.assertFalse(self._logged_in(response))
        self.assertIn('Invalid login!', response)

    def test_logout(self):
        self._login(self.LOGIN, self.PASSWORD)
        response = self._get_follow('/?command=logout')
        self.assertFalse(self._logged_in(response))


class TestPages(CMSTest):
    """Test creating a page in the CMS and reading it as an anonymous user."""

    ROLES = ('cms-admin',)
    IDENTIFIER = CMSTest.PAGE_IDENTIFIER_PREFIX + 'created'
    CONTENT = 'The content of the page created through the CMS user interface.'

    def test_create_page(self):
        self._login(self.LOGIN, self.PASSWORD)
        form = self._find_form(self._get_follow('/?action=insert'),
                               fields=('title', 'identifier', '_content'))
        self._set_field(form, 'title', 'Created Page')
        self._set_field(form, 'identifier', self.IDENTIFIER)
        self._set_field(form, '_content', self.CONTENT)
        self._set_field(form, 'published', True)
        response = self._submit_form(form)
        self.assertIn(self.CONTENT, response)
        # The page must be readable by anonymous users as well.
        self._get_follow('/?command=logout')
        response = self._get_follow('/' + self.IDENTIFIER)
        self.assertIn(self.CONTENT, response)


class TestRegistration(CMSTest):
    """Test the registration of a new user account and its approval."""

    ROLES = ('cms-admin',)
    """The test user approves the newly registered account."""

    NEW_LOGIN = 'wiking-test-new'
    NEW_EMAIL = 'wiking-test-new@example.com'
    NEW_PASSWORD = 'W1king-n3w'

    @classmethod
    def tearDownClass(class_):
        class_.delete_user(class_.NEW_LOGIN)
        super(TestRegistration, class_).tearDownClass()

    def setUp(self):
        super(TestRegistration, self).setUp()
        self.delete_user(self.NEW_LOGIN)

    def _register(self):
        """Submit the registration form and return the activation URI from the e-mail."""
        form = self._find_form(self._get_follow('/_registration?action=insert'),
                               fields=('firstname', 'surname', 'email', 'login'))
        for field, value in (('firstname', 'New'),
                             ('surname', 'User'),
                             ('email', self.NEW_EMAIL),
                             ('login', self.NEW_LOGIN),
                             ('initial_password', self.NEW_PASSWORD)):
            self._set_field(form, field, value)
        self._submit_form(form)
        self.assertEqual(self.NEW_EMAIL, self.mail[0].addr)
        match = re.search(r'https://[^/]+(/\S+)', self.mail[0].text)
        self.assertIsNotNone(match, self.mail[0].text)
        return match.group(1)

    def _state(self):
        return self.query("select state from users where login = %s", (self.NEW_LOGIN,))[0][0]

    def test_registration(self):
        uri = self._register()
        # The registration is only finished when the activation code is confirmed.
        self.assertEqual('new', self._state())
        self.assertIn('Invalid activation code',
                      self._get(uri.replace('regcode=', 'regcode=x'), status='*'))
        self.assertEqual('new', self._state())
        # The correct code confirms the e-mail address, but the account still
        # awaits the administrator's approval.
        self._get_follow(uri)
        self.assertEqual('unapproved', self._state())
        # The administrators are notified about the new account.
        self.assertIn(self.LOGIN, [mail.addr for mail in self.mail[1:]])

    def test_approval(self):
        self._get_follow(self._register())
        self._login(self.LOGIN, self.PASSWORD)
        self._get_follow('/_wmi/users/Users/%s?action=enable' % self.NEW_LOGIN)
        self.assertEqual('enabled', self._state())
        self.assertEqual(self.NEW_EMAIL, self.mail[-1].addr)
        # Now the user can log in.
        self._get_follow('/?command=logout')
        self.assertTrue(self._logged_in(self._login(self.NEW_LOGIN, self.NEW_PASSWORD)))
