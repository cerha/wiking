# Copyright (C) 2006, 2007, 2008, 2009, 2010 Brailcom, o.p.s.
# Author: Tomas Cerha <cerha@brailcom.org>
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

import pytis.data
from wiking import *

_ = lcg.TranslatableTextFactory('wiking')

class Handler(object):
    """Wiking handler.

    The handler passes the actual request processing to the current application.  Its main job is
    handling errors during this processing and dealing with its result (typically exporting the
    document into HTML and sending it to the client).

    """
    def __init__(self, hostname):
        self._hostname = hostname
        self._application = cfg.resolver.wiking_module('Application')
        self._exporter = cfg.exporter(translations=cfg.translation_path)
        #log(OPR, 'New Handler instance for %s.' % hostname)

    def _serve_document(self, req, document):
        """Serve a document using the Wiking exporter."""
        node = document.build(req, self._application)
        context = self._exporter.context(node, node.lang(), sec_lang=node.sec_lang(), req=req)
        exported = self._exporter.export(context)
        req.result(context.translate(exported))

    def _serve_error_document(self, req, error):
        """Serve an error page using the Wiking exporter."""
        error.log(req)
        error.set_status(req)
        document = Document(error.title(req), error.message(req))
        self._serve_document(req, document)

    def _serve_minimal_error_document(self, req, error):
        """Serve a minimal error page using the minimalistic exporter."""
        error.log(req)
        error.set_status(req)
        node = lcg.ContentNode(req.uri().encode('utf-8'),
                               title=error.title(req),
                               content=error.message(req))
        exporter = MinimalExporter(translations=cfg.translation_path)
        try:
            lang = req.prefered_language()
        except:
            lang = cfg.default_language_by_domain.get(req.server_hostname(current=True),
                                                      cfg.default_language) or 'en'
        context = exporter.context(node, lang=lang)
        exported = exporter.export(context)
        req.result(context.translate(exported))

    def handle(self, req):
        application = self._application
        try:
            try:
                result = application.handle(req)
                if isinstance(result, Document):
                    # Always perform authentication (if it was not performed before) to handle
                    # authentication exceptions here and prevent them in export time.
                    req.user()
                    self._serve_document(req, result)
                elif isinstance(result, (tuple, list)):
                    content_type, data = result
                    req.result(data, content_type=content_type)
                else:
                    # int is deprecated! Just for backwards compatibility.  
                    assert result is None or isinstance(result, int)
            except RequestError, error:
                try:
                    req.user()
                except RequestError:
                    # Ignore all errors within authentication except for AuthenticationError.
                    pass
                except AuthenticationError, auth_error:
                    self._serve_error_document(req, auth_error)
                self._serve_error_document(req, error)
            except (ClosedConnection, Done, Redirect):
                raise
            except Exception, e:
                # Try to return a nice error document produced by the exporter.
                try:
                    return application.handle_exception(req, e)
                except RequestError, error:
                    return self._serve_error_document(req, error)
        except ClosedConnection:
            pass
        except Done:
            pass
        except Redirect, r:
            req.redirect(r.uri(), args=r.args(), permanent=r.permanent())
        except Exception, e:
            # If error document export fails, return a minimal error page.  It is reasonable to
            # assume, that if RequestError handling fails, somethong is wrong with the exporter and
            # error document export will fail too, so it is ok, to have them handled both at the
            # same level above.
            try:
                application.handle_exception(req, e)
            except RequestError, error:
                self._serve_minimal_error_document(req, error)
            

