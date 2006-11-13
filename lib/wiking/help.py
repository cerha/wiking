# Copyright (C) 2006 Brailcom, o.p.s.
# Author: Tomas Cerha.
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

from wiking import *

"""This module just separates the help texts from the code."""

_ = lcg.TranslatableTextFactory('wiking-help')

HELP = {

'Mapping':

_("""This module maps the available URIs to particular Wiking modules which
handle them.  The /Identifier/ is the name of the resource as seen from
outside.  The corresponding URI may be for example
\http://www.yourdomain.com/identifier/.  Each identifier maps to a single
/Module/, which is responsible to handle all requests to this URI.

See the documentation of particular modules to learn more how they handle
requests and how to manage the content.

= Main menu management =

You can also manage the main navigation of the site here.  In the field
/Menu order/, you simply assign a number to each item you want to appear in
the main menu.  The items will appear in the navigation bar according to
given order.  The items which have no number assigned will not appear in
the menu, but they can be still referenced using their identifier.  You
will probably want to link to those items from other pages to make them
visible to website users.

= Published/Unpublished items =

Mapping items, as well as many other content elements, can be
published/unpublished.  An unpublished item exists in the database, so the
author can work on it, but it is not publicly visible to the website users.

Publishing a Mapping item makes the URI available on the server, however
you also need to publish some content for this URI.  This must be done in
the corresponding module.  On the other hand, by unpublishing an item here,
all content becomes unavailable, even though this content may be published.
This way you can for example unpublish all language variants of one page at
one place."""),

#==============================================================================

'Content':

_("""This module handles generic content pages.  Each item in the table
assigns the actual content to one /Mapping/ item (identifier).

The content itself can be directly edited as an ``LCG structured text''
document.  See the [/wiking-doc/data-formats/structured-text formatting
manual].

Multiple language variants of each page are managed by this module, but
only records corresponding to the /currently selected language/ are
displayed, so you always see one page corresponding to one /Mapping/ item
(identifier).  You need to switch the language to be able to manage pages
of other languages.

To /add a new page/, you first need to create a new /Mapping/ item, which
makes a new identifier available.  Then you can create a new page which
assigns a content to this identifier in one particular language.

To /create a new language variant/ of an existing page, first select the
existing language variant and then select ``Translate'' in the actions
menu.  You can also Create a new record assigning the new language variant
to given identifier, but the advantage of the ``Translate'' action is that
you get the original text pre-filled and you can translate by overwriting
this text directly.

As described in [/wmi/Mapping Mapping], the content can be
published/unpublished."""),

#==============================================================================

'News':

_("""The News module is designed for short messages.  Each message has a
brief summary, a time-stamp and a more descriptive text.  The basic view is
handled by displaying a list of recent messages (newer messages at the
top).

The message text can be formatted as an ``LCG structured text'' document.
See the [/wiking-doc/data-formats/structured-text formatting manual].

The news items for each language variant of the website are managed
independently.  Only messages for the /currently selected language/ are
displayed, so you need to switch the language to be able to manage news for
a different language."""),

#==============================================================================

'Panels':

_("""``Panels'' are small boxes which are usually displayed sidewise.
Unlike other content, panels appear on every page of the website beside its
main content.  The main content changes while browsing different sections
of the site, but the panels remain where they are.

There may be arbitrary textual content on each panel, but probably the most
practical feature of panels is that they can display recent items of a
particular section of the website.  You just select a Mapping item in the
field ``Overview'' and recent items of the corresponding module will be
displayed.  For example you select the item which is assigned to a News
module and recent news will be displayed on the panel.  You can also select
how many items are displayed.

There may be a different set of panels for each language variant of the
website.  Only panels for the /currently selected language/ are displayed,
so you need to switch the language to be able to manage panels for a
different language.

The order of panels on the page is determined by the ``Order'' number.
This order is also respected by the above table."""),

#==============================================================================

'Titles':

_("""This module assigns titles to particular mapping items (identifiers).
These titles then, among others, appear in the main menu.

The titles are normally assigned automatically when you create new pages,
but you will need to assign the title here for the items which are either
not regular pages (are handled by some other module), or which don't have a
corresponding page in all supported language variants.

When there is a title missing for an item, you will realize that easilly.
There will be just the identifier displayed in the main menu, instead of
the title.  This may be sufficient at some cases, but you will often want
to supply better titles.  This can be done by adding a new title assignment
to this table.  Please remember, that you should specify titles for all
supported languages.  This way the main menu will be fully translated in
all available language variants.  When there is no content for some item in
given language, the user will be automatically redirected to a different
language version of the document according to his language preferences.

Only titles for the /currently selected language/ are displayed, so you
need to switch the language to be able to manage titles for a different
language."""),

#==============================================================================

'Modules':

_("""Here you manage the modules recognized by your wiking site.  You
can add new modules, remove unused modules and enable/disable the existing
ones.  This is a system module and it doesn't handle content.

Before adding a new module, this module first needs to be installed by the
system administrator.  Adding it into the list only makes the module
available from within the management interface.  Removing (or disabling)
hides the module from the management interface."""),

#==============================================================================

'Languages':

_("""This module allows you to manage the set of languages supported by
your site.  You can add any language as it's lowercase ISO 639-1 Alpha-2
language code.

The configured languages become automatically available for creating new
content.  This is a system module and it doesn't itself handle any content.

= Language selection in WMI =

The Wiking Management Interface allows you to switch to any of the
configured languages at any time.  The important think to know is, that
when you view a content listing of a particular module in WMI, only the
items corresponding to the current language are shown, if the items are
language dependent.  For language independent content, all items are shown,
of course.

= Serving the content in multiple languages =

For the website visitors, the content is always selected according to their
language preferences (browser setting).  When the content is available in
one of the accepted languages, the best-matching variant is served.  If
not, Error 406 (Not Acceptable) is returned and the user is allowed to
select manually from the available language variants.""")

}
