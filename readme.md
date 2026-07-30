# Wiking

[![PyPI](https://img.shields.io/pypi/v/wiking.svg)](https://pypi.org/project/wiking/)

Wiking is a Python web application development framework.

Wiking comes together with Wiking CMS -- an extensible content management
system built on top of this framework.


## Wiking as a framework

A Wiking application defines its structure and content as a hierarchy of Python
objects.  The framework takes care of the rest -- HTML output, page layout,
authentication, authorization, localization and error handling -- so that the
application code stays about the application.

- **Content, not markup.**  Pages are composed of content element classes
  (paragraphs, sections, images, database forms) rather than HTML.  Rendering
  is the exporter's job and can be extended or replaced.  Thanks to
  [LCG](https://github.com/cerha/lcg), the same content can also be exported to
  PDF, EPUB or Braille.
- **Authentication and authorization.**  Cookie based authentication, HTTP
  Basic authentication and OAuth are implemented; the application only verifies
  the credentials.  Access rights are checked before a request reaches the
  module method which serves it, with the authorization logic left to the
  application.
- **Accessibility as a design goal.**  The generated pages follow the W3C
  standards, use ARIA landmarks and are fully operable by keyboard.
- **Multilingual by default.**  The user interface is localized through gettext
  and the content itself may exist in language variants, selected by content
  negotiation.  Translations of the common user interface strings already exist
  in a number of languages.
- **Database applications.**  Through [Pytis](https://github.com/cerha/pytis),
  database tables are published as browsing and editing forms derived from an
  abstract specification, rather than implemented page by page.


## Wiking CMS

Wiking CMS is a website managed entirely from a web browser -- and a framework
of its own at the same time.  Applications such as digital library catalogues
are built as its extensions, which add their own modules and menu items while
reusing everything the CMS already provides:

- **User management** -- registration with e-mail verification, account
  approval, password management, sessions and login failure logging, user roles
  and groups with role hierarchies.
- **Content management** -- hierarchical page structure with per page access
  rights, revision history, attachments, structured text editing in the
  browser, side panels and a site map.
- **Publications** -- multi chapter documents exportable to EPUB, PDF and
  Braille.
- **Communication** -- news, a planner, discussions and newsletters with
  subscription management.
- **Presentation** -- colour themes and style sheets managed from the browser,
  so that the look can be changed without touching the code.

Everything is administered through the Wiking Management Interface, which is a
part of the site itself.


## License

Wiking is Free Software, distributed under the terms of the **GNU General Public
License v2 (GPLv2)**.  See the `COPYING` file for details.


## Installation

Wiking is a pure Python library running on Python 3.5 or later and may be
installed simply by `pip install wiking`.  Use `pip install wiking[cms]` for
Wiking CMS, which needs a few additional dependencies.

See the Deployment chapter of the documentation for the recommended production
setup.


## Usage

Documentation is included in the package.  To generate the HTML version, run
`make doc` from the package root directory.

Wiking is developed at
[github.com/cerha/wiking](https://github.com/cerha/wiking).
