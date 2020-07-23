# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2017 OUI Technology Ltd.
# Copyright (C) 2019-2020 Tomáš Cerha <t.cerha@gmail.com>
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

import argparse
import copy
import os
import random
import re
import sys
import time
import unittest
import webtest

import wiking.wsgi_interface

import http.cookiejar
import urllib.parse


class _TestBase(unittest.TestCase):

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

    @classmethod
    def set_options(class_, config_file, host, options=None):
        class_._config_file = config_file
        class_._host = host
        class_._options = options

    def setUp(self):
        self._options = self._process_options(self.__class__._options)

    def _process_options(self, options):
        if options is None:
            options = object()
        for k, v in self._DEFAULT_OPTIONS:
            if getattr(options, k, None) is None:
                setattr(options, k, v)
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


class Test(_TestBase):

    def setUp(self):
        super(Test, self).setUp()
        self._headers = self._make_headers()
        self._environment = self._make_environment()
        self._cookies = http.cookiejar.CookieJar()
        self._application = webtest.TestApp(wiking.wsgi_interface.application,
                                            cookiejar=self._cookies)
        self._set_language()

    def _make_headers(self):
        headers = {'Host': self._host,
                   'User-Agent': 'Wiking Tester'}
        return headers

    def _make_environment(self):
        return {'wiking.config_file': self._config_file}

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
            response = response.follow(headers=self._headers)
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
        form[field] = value

    def _set_select_field(self, form, field, value=None, text=None):
        kwargs = dict(text=text) if text is not None else dict(value=value)
        form[field].select(**kwargs)

    def _submit_form(self, form, follow=True, **kwargs):
        form_kwargs = copy.copy(self._default_request_kwargs())
        form_kwargs.update(kwargs)
        response = form.submit(**form_kwargs)
        if follow and response:
            response = response.maybe_follow()
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
