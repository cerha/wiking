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
import urllib.parse

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
        class_.uid = class_.create_user(class_.LOGIN, class_.PASSWORD)
        for role_id in class_.ROLES:
            class_.query("insert into role_members (role_id, uid) values (%s, %s)",
                         (role_id, class_.uid))

    _MAIL_URI_MATCHER = re.compile(r'https?://\S+')

    def _mail_uri(self, mail, index=0):
        """Return the URI of the application found in given e-mail message.

        Only the path and the query are returned, so that the result may be
        passed directly to '_get()'.  'index' selects among the URIs when the
        message contains more than one (the URIs pointing to the server root,
        such as the site name in the message text, are not counted).

        """
        uris = [urllib.parse.urlsplit(uri.rstrip('.,;'))._replace(scheme='', netloc='').geturl()
                for uri in self._MAIL_URI_MATCHER.findall(str(mail.text))]
        return [uri for uri in uris if uri.startswith('/')][index]

    @classmethod
    def create_user(class_, login, password, state='enabled'):
        """Create a user account of given state and return its uid."""
        return class_.query(
            "insert into users (login, password, firstname, surname, user_, email, "
            "last_password_change, state) "
            "values (%s, %s, 'Wiking', 'Test', 'Wiking Test', %s, now(), %s) returning uid",
            (login, wiking.UniversalPasswordStorage().stored_password(password),
             login if '@' in login else login + '@example.com', state),
        )[0][0]

    @classmethod
    def create_page(class_, identifier, content, read_role_id='anyone'):
        """Create a published page owned by the test user."""
        class_.query(
            # Both the production version of the text ('content') and the
            # concept the editors work on ('_content') must be set -- a page
            # which only has a concept is invisible outside the preview mode.
            "insert into cms_v_pages (site, kind, identifier, lang, title, content, _content, "
            "published, parents_published, creator, created, menu_visibility, "
            "read_role_id, write_role_id, ord) "
            "values (%s, 'page', %s, %s, 'Wiking Test Page', %s, %s, true, true, %s, now(), "
            "'always', %s, 'cms-content-admin', "
            # The pages are ordered as created, so that the first one created
            # by the test case is the one the site root leads to.
            "(select coalesce(max(ord), 0) + 1 from cms_pages where site = %s))",
            (class_.host, identifier, class_.language, content, content, class_.uid,
             read_role_id, class_.host))

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


class _SiteTest(CMSTest):
    """Base class of the tests of Wiking CMS itself.

    The plain CMS database contains no pages at all, so a publicly readable
    page is created here to make the site behave as a real site does.  The
    applications tested against their own database have their pages already,
    so they derive their tests from 'CMSTest' directly.

    """
    PAGE_IDENTIFIER_PREFIX = 'wiking-test-'
    """Identifier prefix of the pages created by the tests.

    All pages with this prefix are deleted when the test case is done.

    """
    PAGE_CONTENT = 'The content of the page created by the test suite.'

    @classmethod
    def setUpClass(class_):
        super(_SiteTest, class_).setUpClass()
        class_.create_page(class_.PAGE_IDENTIFIER_PREFIX + 'home', class_.PAGE_CONTENT)

    @classmethod
    def tearDownClass(class_):
        class_.query("delete from cms_pages where identifier like %s",
                     (class_.PAGE_IDENTIFIER_PREFIX + '%',))
        super(_SiteTest, class_).tearDownClass()


class TestLogin(_SiteTest):
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


class TestPages(_SiteTest):
    """Test creating a page in the CMS and reading it as an anonymous user."""

    ROLES = ('cms-admin',)
    IDENTIFIER = _SiteTest.PAGE_IDENTIFIER_PREFIX + 'created'
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


class TestRegistration(_SiteTest):
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
        return self._mail_uri(self.mail[0])

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

    def test_rejection(self):
        self._get_follow(self._register())
        self._login(self.LOGIN, self.PASSWORD)
        self._get_follow('/_wmi/users/Users/%s?action=reject' % self.NEW_LOGIN)
        self.assertEqual('rejected', self._state())


class TestUserRoles(_SiteTest):
    """Test assigning a role to a user through the administration interface."""

    ROLES = ('cms-admin',)
    ASSIGNED_ROLE = 'cms-style-admin'

    def test_assign_role(self):
        self._login(self.LOGIN, self.PASSWORD)
        uri = '/_wmi/users/Users/%s/roles' % self.LOGIN
        form = self._find_form(self._get_follow(uri + '?action=insert'), fields=('role_id',))
        self._set_select_field(form, 'role_id', value=self.ASSIGNED_ROLE)
        self._submit_form(form)
        self.assertEqual([(self.ASSIGNED_ROLE,)],
                         self.query("select role_id from role_members "
                                    "where uid = %s and role_id = %s",
                                    (self.uid, self.ASSIGNED_ROLE)))
        self.assertIn(self.ASSIGNED_ROLE, self._get_follow(uri))


class TestPasswordReset(_SiteTest):
    """Test the reset of a forgotten password."""

    NEW_PASSWORD = 'W1king-r3set'

    def test_password_reset(self):
        form = self._find_form(self._get_follow('/_registration?action=reset_password'),
                               fields=('query',))
        self._set_field(form, 'query', self.LOGIN)
        self._submit_form(form, status='*')
        # The security code is sent by e-mail.
        self.assertEqual(self.LOGIN, self.mail[0].addr)
        uri = self._mail_uri(self.mail[0])
        self._get(uri.replace('passcode=', 'passcode=x'), status=400)
        # The valid code leads to the form for setting a new password.
        response = self._get_follow(uri)
        self.assertIn('Security code verified', response)
        form = self._find_form(response, fields=('new_password', 'passcode'))
        self._set_field(form, 'new_password', self.NEW_PASSWORD)
        # The redirect leads to the login page, which is returned with 401.
        self._submit_form(form, follow=False)
        # The old password stops working and the new one logs the user in.
        self.assertFalse(self._logged_in(self._login(self.LOGIN, self.PASSWORD)))
        self.assertTrue(self._logged_in(self._login(self.LOGIN, self.NEW_PASSWORD)))


class TestAuthorization(_SiteTest):
    """Test that the state of the account controls the access to the site."""

    UNAPPROVED_LOGIN = 'wiking-test-unapproved'
    UNAPPROVED_PASSWORD = 'W1king-unappr'

    @classmethod
    def setUpClass(class_):
        super(TestAuthorization, class_).setUpClass()
        class_.create_user(class_.UNAPPROVED_LOGIN, class_.UNAPPROVED_PASSWORD,
                           state='unapproved')
        class_.page = class_.PAGE_IDENTIFIER_PREFIX + 'restricted'
        class_.create_page(class_.page, class_.PAGE_CONTENT, read_role_id='user')

    @classmethod
    def tearDownClass(class_):
        class_.delete_user(class_.UNAPPROVED_LOGIN)
        super(TestAuthorization, class_).tearDownClass()

    def test_anonymous_user(self):
        self._get('/' + self.page, status=401)

    def test_enabled_user(self):
        self._login(self.LOGIN, self.PASSWORD)
        self.assertIn(self.PAGE_CONTENT, self._get_follow('/' + self.page))

    def test_unapproved_user(self):
        # An unapproved account may log in, but it has no rights beyond the
        # anonymous ones until the administrator approves it.
        response = self._login(self.UNAPPROVED_LOGIN, self.UNAPPROVED_PASSWORD)
        self.assertTrue(self._logged_in(response))
        self._get('/' + self.page, status=403)
