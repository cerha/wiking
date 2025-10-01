# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2016 OUI Technology Ltd.
# Copyright (C) 2019-2025 Tomáš Cerha <t.cerha@gmail.com>
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

__version__ = '2.2.1'

from .util import (  # noqa: F401
    DBG, EVT, OPR,
    Abort, AuthenticationError, AuthenticationProvider, AuthenticationRedirect,
    AuthorizationError, BadRequest, Binding, Channel, ChannelContent, ConfirmationDialog,
    CookieAuthenticationProvider, Date, DateTime, DecryptionDialog, Document,
    Forbidden, HTTPBasicAuthenticationProvider, HtmlContent, IFrame, InputForm,
    InternalServerError, LanguageSelection, LoginControl, LoginDialog, MailAttachment,
    MaximizedModeControl, MenuItem, Message, ModuleInstanceResolver, NotAcceptable, NotFound,
    NotModified, Panel, PasswordStorage,
    Pbkdf2Md5PasswordStorage, Pbkdf2PasswordStorage, PermanentRedirect, PlainTextPasswordStorage,
    Redirect, RequestError, Response, RssWriter, ServiceUnavailable,
    Specification, TZInfo, Theme, Time, TopBarControl, UniversalPasswordStorage,
    UnsaltedMd5PasswordStorage, WikingDefaultDataClass, WikingResolver,
    ajax_response, format_http_date, generate_random_string, log, module,
    parse_http_date, pdf_document, send_mail, serve_file, validate_email_address, breakpoint,
)

from .request import (  # noqa: F401
    ClosedConnection, FileUpload, Request, Role, Roles, ServerInterface, User,
)
from .modules import (  # noqa: F401
    ActionHandler, Documentation, Module, Reload, RequestHandler, Resources,
    Robots, Search, Session, SiteIcon, SubmenuRedirect,
)
from .db import (  # noqa: F401
    APIProvider, CachedTables, CachingPytisModule, CbCachingPytisModule, DBException,
    PytisModule, PytisRssModule, RssModule,
)

from .application import Application  # noqa: F401
from .export import Exporter, MinimalExporter  # noqa: F401
from .handler import Handler  # noqa: F401

from lcg import log as debug  # noqa: F401

# Initialize the global configuration object 'wiking.cfg'.
from .configuration import Configuration, ApplicationConfiguration  # noqa: F401
cfg = Configuration()
