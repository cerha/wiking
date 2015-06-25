import cookielib
import optparse
import re
import sys
import urlparse

import webtest

import wiking.wsgi_interface

class Test(object):

    def __init__(self, config_file, host, options=None):
        self._config_file = config_file
        self._host = host
        self._options = self._process_options(options)
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
            sys.stdout.write('GET: %s\n' % (path,))
        return self._application.get(path, status=status, **self._default_request_kwargs())

    def _get_follow(self, path):
        response = self._get(path)
        for i in range(10):
            if response.status_int != 302:
                return response
            response = response.follow(headers=self._headers)
        raise Exception("Too many redirections", path)

    def _find_link(self, html, description=None, index=None, verbose=False):
        if description is None:
            content_matcher = None
        else:
            content_matcher = re.compile(description).search
        def log(message):
            if verbose:
                print message
        links = []
        for element in html.find_all('a'):
            attrs = element
            href = attrs.get('href')
            log("Element: %s" % (element,))
            if not attrs.get('href'):
                log("  Skipped: no href")
                continue
            content = element.decode_contents()
            if href.startswith('#'):
                log("  Skipped: internal link")
                continue
            if href.startswith('javascript:'):
                log("  Skipped: JavaScript link")
                continue
            if content_matcher is not None and content_matcher(content) is None:
                log("  Skipped: doesn't match")
                continue
            log("  Accepted")
            links.append(href)
        if not links:
            raise IndexError("No matching link found")
        if index is None:
            if len(links) > 1:
                raise IndexError("Multiple matching links")
            index = 0
        if index is True:
            return links
        return links[index]
            
    def _click(self, response, description=None, index=None, status=None, verbose=False):
        url = self._find_link(response.html, description=description, index=index,
                              verbose=verbose)
        return self._get(url, status=status)

    def _click_all(self, response, visited=None, status=None, verbose=False):
        host = response.request.host
        all_responses = []
        for url in self._find_link(response.html, index=True):
            hostname = urlparse.urlparse(url).hostname
            if hostname and hostname != host:
                continue
            if visited is None or url not in visited:
                if visited is not None:
                    visited.add(url)
                all_responses.append(self._get(url, status=status))
        return all_responses

    def _submit_form(self, form, **kwargs):
        form_kwargs = self._default_request_kwargs()
        form_kwargs.update(kwargs)
        return form.submit(**form_kwargs)

    def _warning(self, message):
        sys.stderr.write('WARNING: %s\n' % (message,))

    def run(self):
        response = None
        for f in dir(self):
            if f.startswith('test_'):
                response = getattr(self, f)(response)

def parse_options():
    usage = "usage: %prog [ OPTIONS ] CONFIG-FILE HOST"
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
    if len(args) != 2:
        parser.error("invalid number of arguments")
    return options, args
    
def main(test_class):
    options, args = parse_options()
    test_class(*args, options=options).run()
