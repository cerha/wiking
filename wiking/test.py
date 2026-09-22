# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2017 OUI Technology Ltd.
# Copyright (C) 2019-2020 Tomáš Cerha <cerha@truecode.cz>
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

"""Base classes for testing Wiking applications.

The tests defined here only excercise the framework itself, so they don't need
a database.  The tests of Wiking CMS (and of the applications built on top of
it) live in 'wiking.cms.test', which adds the database fixtures they need.

Applications are tested through their WSGI interface within the test process
(using webtest), so no web server is involved.

"""

import argparse
import copy
import os
import random
import re
import sys
import tempfile
import time
import types
import unittest
import webtest

import lcg

import wiking
import wiking.wsgi_interface


_configured = None
"""Configuration file of the application currently initialized in this process.

See 'Test._reset_application()'.

"""

import http.cookiejar
import urllib.parse


class _TestBase(unittest.TestCase):
    """Base class of Wiking application tests.

    Derived classes must define the tested application by 'config_file' and
    'host' class attributes (or by calling 'set_options()', which is what the
    command line runner in 'main()' does).

    """
    config_file = None
    """Configuration file of the tested application.

    When None, a temporary configuration file is created from 'config_options'.

    """
    config_options = dict(modules=('wiking.test',),
                          # Authentication requires a database (see 'wiking.cms.test').
                          authentication_providers=())
    """Wiking configuration of the tested application as a dictionary.

    Only used when 'config_file' is not defined.  Only options with values
    which can be written as their Python representation may be defined this
    way.

    """
    host = 'localhost'
    language = None
    user = None
    password = None
    profile = None
    verbose = False

    _OPTIONS = ('language', 'profile', 'user', 'password', 'verbose')
    """Names of the options which may be overriden from the command line."""

    class _Visited(set):

        def __call__(self, url):
            if url in self:
                visited = True
            else:
                self.add(url)
                visited = False
            return visited

    class _RandomlyVisited:

        def __init__(self, transform=None):
            self._visited = dict()
            if transform is None:
                def transform(url):
                    return None
            self._transform = transform

        def __call__(self, url):
            transformed_url = self._transform(url)
            if transformed_url == url:
                visited = transformed_url in self._visited
                self._visited[transformed_url] = True
            else:
                n = self._visited.get(transformed_url, 0) + 1
                self._visited[transformed_url] = n
                if n == 1:
                    visited = False
                else:
                    visited = random.random() > 1.0 / n
            return visited

        def add(self, url):
            url = self._transform(url)
            self._visited[url] = self._visited.get(url, 0) + 1

        _numeric_suffix_regexp = re.compile('^(.*/)[0-9]+$')

        @classmethod
        def numeric_suffix_transformer(class_, url):
            match = class_._numeric_suffix_regexp.match(url)
            if match is not None:
                url = url[:match.end(1)] + '*'
            return url

    _options = None

    @classmethod
    def setUpClass(class_):
        super(_TestBase, class_).setUpClass()
        if not class_.config_file:
            class_._config_directory = tempfile.TemporaryDirectory()
            class_.config_file = os.path.join(class_._config_directory.name, 'config.py')
            with open(class_.config_file, 'w') as f:
                f.write(''.join('%s = %r\n' % item for item in class_._config_options().items()))

    @classmethod
    def _config_options(class_):
        """Return the configuration of the tested application as a dictionary."""
        return dict(class_.config_options, server_hostname=class_.host)

    @classmethod
    def set_options(class_, config_file, host, options=None):
        class_.config_file = config_file
        class_.host = host
        class_._options = options

    def setUp(self):
        assert self.config_file, "Tested application not defined by 'config_file'."
        self._config_file = self.config_file
        self._host = self.host
        self._options = self._process_options(self.__class__._options)

    def _process_options(self, options):
        # Command line options take precedence over the class attributes.
        if options is None:
            options = types.SimpleNamespace()
        for name in self._OPTIONS:
            if getattr(options, name, None) is None:
                setattr(options, name, getattr(self, name))
        return options

    def _credentials(self, index=0):
        user_string = self._options.user
        if user_string is None:
            return None, None
        users = user_string.split(':')
        try:
            the_user = users[index]
        except IndexError:
            the_user = users[0]
        password_string = self._options.password
        if password_string is None:
            return the_user, None
        passwords = password_string.split(':')
        try:
            the_password = passwords[index]
        except IndexError:
            the_password = passwords[0]
        return the_user, the_password

    def _find_link(self, browser, description=None, index=None, verbose=False):
        if description is None:
            content_matcher = None
        else:
            content_matcher = re.compile(description).search
        links = []
        for element in self._find_all_links(browser):
            href = self._attribute(element, 'href')
            self._info("Element: %s" % (href,))
            if not href:
                self._info("  Skipped: no href")
                continue
            if href.startswith('#'):
                self._info("  Skipped: internal link")
                continue
            if href.startswith('javascript:'):
                self._info("  Skipped: JavaScript link")
                continue
            if href.startswith('mailto:'):
                self._info("  Skipped: mail link")
                continue
            if content_matcher is not None and content_matcher(self._element_text(element)) is None:
                self._info("  Skipped: doesn't match")
                continue
            self._info("  Accepted")
            url = urllib.parse.urljoin(self._current_url(browser), href)
            links.append(url)

        def exception_args():
            return (description, browser,) if self._options.verbose else ()
        if not links:
            raise IndexError("No matching link found", *exception_args())
        if index is None:
            if len(links) > 1:
                raise IndexError("Multiple matching links", *exception_args())
            index = 0
        if index is True:
            return links
        return links[index]

    def _login(self, login=None, password=None, path='/'):
        """Log in through the Wiking login form and return the resulting page.

        Arguments:
          login, password -- the credentials to use.  The credentials passed
            through the command line options (see '_credentials()') are used
            when None.
          path -- path of the page to log in at.  Wiking displays the login
            form on any page when the request contains the 'command=login'
            parameter, so any existing path may be used.

        """
        if login is None:
            login, password = self._credentials()
        uri = path + ('&' if '?' in path else '?') + 'command=login'
        # Wiking returns the login form with the status 401 on protected pages.
        response = self._get(uri, status='*')
        form = self._find_form(response, fields=('login', 'password'))
        self._set_field(form, 'login', login)
        self._set_field(form, 'password', password)
        # The status is not checked -- the login form is returned with the
        # status 401 when the credentials are invalid and also when the target
        # page is not accessible to the logged in user.
        return self._submit_form(form, status='*')

    def _logged_in(self, response):
        """Return true if given page belongs to a logged in user's session."""
        # The logout control is only present when a user is logged in.
        return self._contains(response, 'command=logout')

    def _filter_form(self, browser, options):
        form_fields = [o[0] for o in options]
        for field, text in options:
            form = self._find_form(browser, fields=form_fields)
            self._set_select_field(form, field, text=text)
            self._ajax_delay()
        form = self._find_form(browser, fields=form_fields)
        return self._submit_form(form, {'class': 'apply-filters'})

    def _click(self, browser, description=None, index=None, status=None, verbose=False,
               follow=False):
        url = self._find_link(browser, description=description, index=index, verbose=verbose)
        if follow:
            browser = self._get_follow(url)
        else:
            browser = self._get(url, status=status)
        return browser

    def _click_all(self, browser, visited=None, status=None, verbose=False, ignored=None):
        host = self._host
        all_responses = []
        for url in self._find_link(browser, index=True):
            hostname = urllib.parse.urlparse(url).hostname
            if hostname and hostname != host:
                continue
            if ignored is not None and ignored(url):
                continue
            if visited is None or not visited(url):
                all_responses.append(self._get(url, status=status))
        return all_responses

    def _info(self, message):
        if self._options.verbose:
            sys.stdout.write('%s\n' % (message,))

    def _warning(self, message):
        sys.stderr.write('WARNING: %s\n' % (message,))


class Mail:
    """An e-mail message sent by the tested application.

    The arguments of 'wiking.send_mail()' are available as the instance
    attributes of the same names.  See 'Test.mail'.

    """
    def __init__(self, addr, subject, text, **kwargs):
        self.addr = addr
        self.subject = subject
        self.text = text
        for name, value in kwargs.items():
            setattr(self, name, value)

    def __repr__(self):
        return '<%s for %r: %r>' % (self.__class__.__name__, self.addr, self.subject)


class Test(_TestBase):
    """Test of a Wiking application running in process through its WSGI interface."""

    mail = ()
    """The e-mail messages sent so far as a list of 'Mail' instances.

    The application's e-mails are captured during the test instead of being
    sent, so that the tests can check them (and so that they never leave the
    test process).

    """

    def setUp(self):
        super(Test, self).setUp()
        self._reset_application()
        self._headers = self._make_headers()
        self._environment = self._make_environment()
        self._cookies = http.cookiejar.CookieJar()
        self._application = webtest.TestApp(wiking.wsgi_interface.application,
                                            cookiejar=self._cookies)
        self._set_language()
        self._capture_mail()

    def _reset_application(self):
        """Make the WSGI entry point use the configuration of this test.

        The Wiking configuration is a process global and the WSGI entry point
        only initializes the application once, so the application must be
        thrown away when another test runs against another configuration (the
        framework tests here and the tests of Wiking CMS run in the same
        process).

        """
        global _configured
        if _configured != self._config_file:
            wiking.cfg = wiking.Configuration()
            # The resolver caches the modules in its class, so the cache is
            # shared even by its new instances.
            wiking.WikingResolver._wiking_module_class_cache.clear()
            wiking.WikingResolver._wiking_module_instance_cache.clear()
            wiking.wsgi_interface.application._handler = None
            _configured = self._config_file

    def tearDown(self):
        for module in self._mail_patched_modules:
            module.send_mail = wiking.send_mail
        super(Test, self).tearDown()

    def _capture_mail(self):
        self.mail = []

        def send_mail(addr, subject, text, **kwargs):
            self.mail.append(Mail(addr, subject, text, **kwargs))
            return None  # The real function returns an error message or None.

        # The function is imported into the modules which use it, so the name
        # must be replaced in each of them, not just in 'wiking'.
        self._mail_patched_modules = [module for module in list(sys.modules.values())
                                      if getattr(module, 'send_mail', None) is wiking.send_mail]
        for module in self._mail_patched_modules:
            module.send_mail = send_mail

    def _probe(self, probe, path='/', **kwargs):
        """Return the value returned by 'probe(req)' called while handling a request.

        Arguments:
          probe -- callable of one argument, the 'wiking.Request' instance of
            the request performed by this method.
          path -- path of the request as a string.
          kwargs -- passed to '_get()'.

        This gives the tests direct access to the request instance of a real
        request, so that the API of 'wiking.Request' can be tested as the
        applications use it.  Only works with the application defined in this
        module (see 'Application').

        """
        _probe_state.function = probe
        _probe_state.result = _probe_state.exception = None
        try:
            self._get(path, status='*', **kwargs)
            if _probe_state.exception:
                raise _probe_state.exception
            return _probe_state.result
        finally:
            _probe_state.function = None

    def _make_headers(self):
        headers = {'Host': self._host,
                   'User-Agent': 'Wiking Tester'}
        return headers

    def _make_environment(self):
        # Pretend HTTPS -- Wiking marks the session cookie as secure, so the
        # cookie jar would not send it back over a plain HTTP connection.  The
        # port matters too -- 'Request.server_uri()' derives the scheme from it.
        return {'wiking.config_file': self._config_file,
                'wsgi.url_scheme': 'https',
                'SERVER_PORT': '443'}

    def _set_language(self):
        language = self._options.language
        if language is not None:
            self._headers['Accept-Language'] = language

    def _default_request_kwargs(self):
        return dict(headers=self._headers, extra_environ=self._environment)

    def _current_url(self, response):
        return response.request.url

    def _get(self, path, status=None):
        if self._options.verbose:
            self._info('GET: %s' % (path,))
        return self._application.get(path, status=status, **self._default_request_kwargs())

    def _get_follow(self, path):
        response = self._get(path)
        return self._follow(response, path=path)

    def _follow(self, response, path=None):
        for i in range(10):
            if response.status_int != 302:
                return response
            response = response.follow(**self._default_request_kwargs())
        raise Exception("Too many redirections", path)

    def _find_all_links(self, response):
        return response.html.find_all('a')

    def _find_form(self, response, fields=(), check_found=True):
        for form_id in response.forms:
            form = response.forms[form_id]
            for f in fields:
                if isinstance(f, tuple):
                    name, value = f
                else:
                    name, value = f, None
                form_field = form.get(name, index=0, default=None)
                if form_field is None:
                    break
                if value is not None and form_field.value != value:
                    break
            else:
                return form
        self.assertFalse(check_found)
        return None

    def _find_elements(self, response, tag, attributes=None):
        if attributes is None:
            attributes = {}
        obj = response.html if isinstance(response, webtest.response.TestResponse) else response
        return obj.find_all(tag, **attributes)

    def _attribute(self, element, name):
        return element.get(name)

    def _element_text(self, element):
        return element.decode_contents()

    def _set_field(self, form, field, value):
        fields = form.fields[field]
        if len(fields) > 1:
            # Password fields are present twice -- for the confirmation.
            for f in fields:
                f.value = value
        else:
            form[field] = value

    def _set_select_field(self, form, field, value=None, text=None):
        kwargs = dict(text=text) if text is not None else dict(value=value)
        form[field].select(**kwargs)

    def _submit_form(self, form, follow=True, **kwargs):
        form_kwargs = copy.copy(self._default_request_kwargs())
        form_kwargs.update(kwargs)
        response = form.submit(**form_kwargs)
        if follow and response:
            response = response.maybe_follow(**self._default_request_kwargs())
        return response

    def _contains(self, response, text):
        return text in response

    def _search(self, response, regexp):
        if isinstance(regexp, str):
            regexp = re.compile(regexp)
        return regexp.search(response.text)


class BrowserTest(_TestBase):

    def setUp(self):
        super(BrowserTest, self).setUp()
        profile = self._options.profile
        kwargs = {}
        if profile:
            profile_dir = os.path.expanduser('~/.mozilla/firefox')
            profile_candidates = [os.path.join(profile_dir, d) for d in os.listdir(profile_dir)
                                  if d.endswith('.' + profile)]
            if not profile_candidates:
                raise Exception("Profile %s not found" % (profile,))
            elif len(profile_candidates) > 1:
                raise Exception("Multiple directories matching profile %s:" % (profile,),
                                profile_candidates)
            kwargs['profile'] = profile_candidates[0]
        import splinter
        self._browser = splinter.Browser(**kwargs)
        self._set_language()
        self._ajax_delay_seconds = 1
        self._ajax_timeout_seconds = 10

    def tearDown(self):
        self._browser.quit()
        super(BrowserTest, self).tearDown()

    def _set_language(self):
        # Not possible in a general way
        pass

    def _current_url(self, browser):
        return browser.url

    def _get(self, path, status=None):
        browser = self._browser
        if path.startswith('/'):
            url = 'http://%s%s' % (self._host, path,)
        else:
            url = path
        browser.visit(url)
        status_code = browser.status_code
        if status is None:
            self.assertTrue(status_code.is_success())
        else:
            self.assertEqual(status_code, status)
        return browser

    def _get_follow(self, path):
        return self._get(path)

    def _find_elements(self, browser, tag, attributes=None):
        xpath = 'descendant::' + tag
        if attributes:
            equations = ['attribute::%s="%s"' % (k, v.replace('"', '\\"'),)
                         for k, v in attributes.items()]
            xpath += '[%s]' % (' and '.join(equations),)
        return browser.find_by_xpath(xpath)

    def _find_all_links(self, browser):
        return browser.find_link_by_partial_text('')

    def _find_form(self, browser, fields=(), check_found=True):
        for form in browser.find_by_tag('form'):
            if not form.visible:
                continue
            for f in fields:
                if isinstance(f, tuple):
                    name, value = f
                else:
                    name, value = f, None
                form_fields = form.find_by_name(name)
                if not form_fields:
                    break
                if value is not None and all([f.value != value for f in form_fields]):
                    break
            else:
                return form
        self.assertFalse(check_found)
        return None

    def _attribute(self, element, name):
        return element[name]

    def _element_text(self, element):
        return element.text

    def _set_field(self, form, field, value):
        form.find_by_name(field)[0].fill(value)

    def _set_select_field(self, form, field, value=None, text=None):
        select_field = form.find_by_name(field)[0]
        if text is not None:
            for element in select_field.find_by_xpath('descendant::option[@value]'):
                if element.text == text:
                    value = element['value']
                    break
            else:
                raise KeyError(field, text)
        select_field.select(value)

    def _ajax_delay(self, seconds=None, text=None):
        if text is None:
            time.sleep(seconds or self._ajax_delay_seconds)
        else:
            if seconds is None:
                seconds = self._ajax_timeout_seconds
            return self._browser.is_text_present(text, wait_time=seconds)

    def _attach_file(self, form, field, filename):
        form.attach_file(field, filename)

    def _click_element(self, element):
        element.click()

    def _submit_form(self, form, attributes=None, follow=None):
        if attributes is None:
            attributes = {}
        if 'type' not in attributes:
            attributes['type'] = 'submit'
        buttons = self._find_elements(form, 'button', attributes)
        if not buttons:
            raise Exception("No button found")
        buttons[0].click()
        return self._browser

    def _contains(self, browser, text):
        return browser.is_text_present(text)

    def _search(self, browser, regexp):
        if isinstance(regexp, str):
            regexp = re.compile(regexp)
        return regexp.search(browser.html)


_probe_state = types.SimpleNamespace(function=None, result=None, exception=None)
"""State of the currently running request probe (see 'Test._probe()')."""


class Application(wiking.Application):
    """Minimal application used by the tests of the framework below.

    It is the application which the tests derived from 'Test' run against
    unless they define their own (see 'config_options').

    """
    def handle(self, req):
        if _probe_state.function:
            try:
                _probe_state.result = _probe_state.function(req)
            except Exception as e:
                _probe_state.exception = e
            return wiking.Document('Probe', lcg.p("Probed."))
        elif req.unresolved_path == ['hello']:
            return wiking.Document(
                'Hello', lcg.p("Hello, %s!" % (req.param('name') or 'world')),
            )
        elif req.unresolved_path == ['secret']:
            raise wiking.Forbidden()
        else:
            raise wiking.NotFound()


class TestRequest(Test):
    """Test the API of 'wiking.Request'.

    The request instance is probed within a real request (see '_probe()'), so
    the tests excercise the same code path as the applications do.

    """
    def test_param(self):
        self.assertEqual('x', self._probe(lambda req: req.param('a'), '/?a=x'))
        self.assertEqual('', self._probe(lambda req: req.param('a'), '/?a='))
        self.assertIsNone(self._probe(lambda req: req.param('a'), '/?b=x'))
        self.assertEqual('dflt', self._probe(lambda req: req.param('a', 'dflt'), '/?b=x'))
        # Repeated parameters are returned as a tuple.
        self.assertEqual(('1', '2'), self._probe(lambda req: req.param('a'), '/?a=1&a=2'))

    def test_has_param(self):
        self.assertTrue(self._probe(lambda req: req.has_param('a'), '/?a=x'))
        self.assertTrue(self._probe(lambda req: req.has_param('a'), '/?a='))
        self.assertFalse(self._probe(lambda req: req.has_param('a'), '/?b=x'))

    def test_params(self):
        self.assertEqual(['a', 'b'], sorted(self._probe(lambda req: req.params(), '/?a=x&b=y')))
        self.assertEqual([], list(self._probe(lambda req: req.params(), '/')))

    def test_set_param(self):
        def probe(req):
            req.set_param('a', 'y')
            req.set_param('b', 'z')
            return req.param('a'), req.param('b')
        self.assertEqual(('y', 'z'), self._probe(probe, '/?a=x'))

    def test_uri(self):
        self.assertEqual('/x/y', self._probe(lambda req: req.uri(), '/x/y?a=1'))
        self.assertEqual(['x', 'y'], self._probe(lambda req: req.unresolved_path, '/x/y'))

    def test_make_uri(self):
        self.assertEqual('/x?a=1&b=2',
                         self._probe(lambda req: req.make_uri('/x', a=1, b=2)))

    def test_server_uri(self):
        # The scheme is derived from the port, not from the request scheme.
        self.assertEqual('https://localhost', self._probe(lambda req: req.server_uri()))


class TestApplication(Test):
    """Test the basic request handling of the framework.

    The application (see 'Application' above) is as simple as it gets, so what
    is actually tested here is the framework -- request handling, error
    handling and the export of the resulting document.  No database is
    involved.

    """
    def test_document(self):
        response = self._get('/hello')
        self.assertIn('Hello, world!', response)
        self.assertIn('<title>Hello', response)

    def test_request_parameters(self):
        self.assertIn('Hello, Wiking!', self._get('/hello?name=Wiking'))

    def test_not_found(self):
        response = self._get('/nonexistent', status=404)
        self.assertIn('Item Not Found', response)
        self.assertIn("The item '/nonexistent' does not exist on this server", response)

    def test_forbidden(self):
        self.assertIn('Access Denied', self._get('/secret', status=403))


def parse_options():
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--language', dest='language', metavar='LANGUAGE',
                        help="try to use given LANGUAGE")
    parser.add_argument('--profile', dest='profile', metavar='PROFILE',
                        help="use given web browser PROFILE")
    parser.add_argument('-u', '--user', dest='user', metavar='USER[:USER...]',
                        help="use given USER(s) in login forms")
    parser.add_argument('-p', '--password', dest='password', metavar='PASSWORD[:PASSWORD...]',
                        help="use given PASSWORD(s) in login forms")
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', default=False,
                        help="be verbose about some actions")
    parser.add_argument('config_file', metavar='CONFIG-FILE',
                        help="Wiking application configuration file")
    parser.add_argument('host', metavar='HOST',
                        help="HTTP host name")
    parser.add_argument('unittest_options', metavar='UNITTEST-OPTIONS', nargs='*')
    args = parser.parse_args()
    return args


def main():
    args = parse_options()
    _TestBase.set_options(args.config_file, args.host, options=args)
    argv = [sys.argv[0]] + args.unittest_options
    unittest.main(argv=argv)
