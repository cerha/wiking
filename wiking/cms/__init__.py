# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2012 OUI Technology Ltd.
# Copyright (C) 2019-2020, 2022 Tomáš Cerha <t.cerha@gmail.com>
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

"""Wiking Content Management System implemented as a Wiking application."""

from .cms import (  # noqa: F401
    Attachments, BrailleExporter, CMSExtension, CMSExtensionMenuModule, CMSExtensionModule,
    CMSModule, CmsPageExcerpts, CommonTexts, Config, ContactForm, ContentField,
    ContentManagementModule, Countries, Discussions, EmailSpool, EmailText, Emails,
    Embeddable, EmbeddableCMSModule, Languages, NavigablePages, News, NewsletterEditions,
    NewsletterPosts, NewsletterSubscription, Newsletters, PDFExporter, PageHistory,
    PageStructure, PageTitles, Pages, Panels, Planner, PublicationChapters,
    PublicationExports, Publications, Resources, Roles, SettingsManagementModule,
    SiteMap, SiteSpecificContentModule, StyleManagementModule, StyleSheets, Text,
    TextReferrer, Texts, Themes, UserManagementModule, WikingManagementInterface,
    text2content, enum, now, ASC, DESC, NEVER, ONCE,
)

from .users import (  # noqa: F401
    ActivationForm, ActiveUsers, ApplicationRoles, ContainingRoles, Registration,
    Role, RoleMembers, RoleSets, Session, UserGroups, UserRoles, Users, LoginFailures,
    SessionHistory,
)

from .appl import AdminControl, Application  # noqa: F401
from .crypto import CryptoKeys, CryptoNames  # noqa: F401
from .configuration import CMSConfiguration  # noqa: F401
from . import texts  # noqa: F401

from wiking import CachedTables, Documentation, SiteIcon, Robots  # noqa: F401

cfg = CMSConfiguration()
