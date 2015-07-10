import cookielib
import optparse
import random
import re
import sys
import unittest
import urlparse

import webtest

import wiking.wsgi_interface

class Test(unittest.TestCase):

    class _Visited(set):

        def __call__(self, url):
            if url in self:
                visited = True
            else:
                self.add(url)
                visited = False
            return visited

    class _RandomlyVisited(object):

        def __init__(self, transform=None):
            self._visited = dict()
            if transform is None:
                transform = lambda url: None
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
        self._headers = self._make_headers()
        self._environment = self._make_environment()
        self._cookies = cookielib.CookieJar()
        self._application = webtest.TestApp(wiking.wsgi_interface.application,
                                            cookiejar=self._cookies)

    def _process_options(self, options):
        if options is None:
            options = object()
        for k, v in self._DEFAULT_OPTIONS:
            if getattr(options, k, None) is None:
                setattr(options, k, v)
        return options

    def _make_headers(self):
        headers = {'Host': self._host,
                   'User-Agent': 'Wiking Tester'}
        language = self._options.language
        if language is not None:
            headers['Accept-Language'] = language
        return headers

    def _make_environment(self):
        return {'wiking.config_file': self._config_file}

    def _default_request_kwargs(self):
        return dict(headers=self._headers, extra_environ=self._environment)
        
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

    def _find_link(self, response, description=None, index=None, verbose=False):
        html = response.html
        if description is None:
            content_matcher = None
        else:
            content_matcher = re.compile(description).search
        links = []
        for element in html.find_all('a'):
            attrs = element
            href = attrs.get('href')
            self._info("Element: %s" % (element,))
            if not attrs.get('href'):
                self._info("  Skipped: no href")
                continue
            content = element.decode_contents()
            if href.startswith('#'):
                self._info("  Skipped: internal link")
                continue
            if href.startswith('javascript:'):
                self._info("  Skipped: JavaScript link")
                continue
            if href.startswith('mailto:'):
                self._info("  Skipped: mail link")
                continue
            if content_matcher is not None and content_matcher(content) is None:
                self._info("  Skipped: doesn't match")
                continue
            self._info("  Accepted")
            links.append(href)
        def exception_args():
            return (description, html,) if self._options.verbose else ()
        if not links:
            raise IndexError("No matching link found", *exception_args())
        if index is None:
            if len(links) > 1:
                raise IndexError("Multiple matching links", *exception_args())
            index = 0
        if index is True:
            return links
        return links[index]

    def _find_form(self, response, fields=()):
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
        return None
            
    def _click(self, response, description=None, index=None, status=None, verbose=False,
               follow=False):
        url = self._find_link(response, description=description, index=index, verbose=verbose)
        if follow:
            result = self._get_follow(url)
        else:
            result = self._get(url, status=status)
        return result

    def _click_all(self, response, visited=None, status=None, verbose=False, ignored=None):
        host = response.request.host
        all_responses = []
        for url in self._find_link(response, index=True):
            hostname = urlparse.urlparse(url).hostname
            if hostname and hostname != host:
                continue
            if ignored is not None and ignored(url):
                continue
            if visited is None or not visited(url):
                all_responses.append(self._get(url, status=status))
        return all_responses

    def _submit_form(self, form, **kwargs):
        form_kwargs = self._default_request_kwargs()
        form_kwargs.update(kwargs)
        return form.submit(**form_kwargs)

    def _info(self, message):
        if self._options.verbose:
            sys.stdout.write('%s\n' % (message,))

    def _warning(self, message):
        sys.stderr.write('WARNING: %s\n' % (message,))

def parse_options():
    usage = "usage: %prog [ OPTIONS ] CONFIG-FILE HOST [ TEST-METHOD ... ]"
    parser = optparse.OptionParser(usage)
    parser.add_option('-l', '--language', dest='language',
                      help="set Accept-Language header to LANGUAGE", metavar='LANGUAGE')
    parser.add_option('-u', '--user', dest='user',
                      help="use given USER in login forms", metavar='USER')
    parser.add_option('-p', '--password', dest='password',
                      help="use given PASSWORD in login forms", metavar='PASSWORD')
    parser.add_option('-v', '--verbose', dest='verbose', action="store_true", default=False,
                      help="be verbose about some actions")
    options, args = parser.parse_args()
    if len(args) < 2:
        parser.error("invalid number of arguments")
    return options, args
    
def main():
    options, args = parse_options()
    config_file = args[0]
    host = args[1]
    Test.set_options(config_file, host, options=options)
    argv = [sys.argv[0]] + args[2:]
    unittest.main(argv=argv)
