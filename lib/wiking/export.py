# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2018 OUI Technology Ltd.
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

import re

import lcg
import pytis
import wiking

_ = lcg.TranslatableTextFactory('wiking')
Part = lcg.Html5Exporter.Part


class MinimalExporter(lcg.Html5Exporter):
    _PAGE_STRUCTURE = (
        Part('main'),
        Part('bottom-bar'),
    )

    def _head(self, context):
        g = context.generator()
        try:
            uri = context.req().module_uri('Resources')
        except Exception:
            uri = '_resources'
        return super(MinimalExporter, self)._head(context) + \
            [g.link(rel='stylesheet', type='text/css', href='/%s/default.css' % uri)]

    def _meta(self, context):
        import wiking
        return (('generator', 'Wiking %s, LCG %s, Pytis %s' %
                 (wiking.__version__, lcg.__version__, pytis.__version__)),)

    def _main(self, context):
        g = context.generator()
        return (g.h1(context.node().title()),
                super(MinimalExporter, self)._content(context))

    def _bottom_bar(self, context):
        g = context.generator()
        import wiking
        return (g.hr(),
                g.span(g.a("Wiking", href="http://www.freebsoft.org/wiking") + ' ' +
                       wiking.__version__))


class Exporter(lcg.StyledHtmlExporter, lcg.Html5Exporter):

    class Context(lcg.Html5Exporter.Context):

        def _init_kwargs(self, req=None, layout='default', **kwargs):
            super(Exporter.Context, self)._init_kwargs(timezone=req.timezone(), **kwargs)
            assert layout in pytis.util.public_attr_values(self._exporter.Layout), layout
            self._req = req
            self._layout = layout
            node = top_node = self.node()
            root = node.root()
            while top_node and top_node.parent() and top_node.parent() is not root:
                top_node = top_node.parent()
            self._top_node = top_node
            application = wiking.module.Application
            self._panels = application.panels(req, self.lang())
            # Allow simple access to some often used data through context attributes ...
            # These attributes are not the part of the official context extension (such as the
            # 'req()' method, so their use should be limited to this module only!
            self.has_submenu = (wiking.cfg.show_submenu and
                                any(not n.hidden() for n in top_node.children()))
            self.application = application
            # Make sure that Prototype.js is always loaded first, so that it is
            # available in any other scripts.
            scripts = ('prototype.js', 'effects.js', 'gettext.js', 'lcg.js', 'wiking.js')
            for filename in scripts + tuple(wiking.cfg.extra_scripts):
                self.resource(filename)
            if self.lang() != 'en':
                self.resource('wiking.%s.po' % self.lang())  # Translations for Javascript

        def req(self):
            """Return the current request as a 'wiking.Request' instance.

            This method is the official Wiking extension of LCG export context.

            """
            return self._req

        def panels(self):
            """Return the list of 'wiking.Panel' instances to be displayed on the page."""
            return self._panels

        def top_node(self):
            """Return the top level parent of this node before the root node."""
            return self._top_node

        def layout(self):
            """Return the current export layout as one of 'Exporter.Layout' constants."""
            return self._layout

    class Layout:
        """Enumeration of output document layout styles."""
        DEFAULT = 'default'
        """Default Wiking layout wrapping the page content in menus, panels etc."""
        FRAME = 'frame'
        """Frame layout displaying just the document content wrapped in html body.

        This layout is typically useful for rendering the IFRAME content.  The
        exported document content is wrapped into HTML body with HTML head
        automatically created.

        """

    class MainMenu(lcg.FoldableTree):

        def _javascript_widget_class(self, context):
            return 'wiking.MainMenu'

        def _css_class_name(self, context):
            return 'foldable-tree-widget'

    _PAGE_STRUCTURE = (
        Part('root', content=(
            Part('root-wrap', content=(
                Part('top', aria_label=_("Page heading"), role='banner', content=(
                    Part('top-wrap', content=(
                        Part('top-bar', content=(
                            Part('top-content'),
                            Part('top-controls'),
                        )),
                        Part('menu',
                             aria_label=_("Main navigation"),
                             accesskey="3",
                             role='navigation'),
                    )),
                )),
                Part('main', content=(
                    Part('main-wrap', content=(
                        # Part('breadcrumbs'),
                        Part('submenu', role='navigation', aria_hidden='true'),
                        Part('page',
                             aria_label=_("Main content"),
                             aria_labelledby='main-heading',
                             role='main',
                             content=(
                                 Part('heading'),
                                 Part('messages'),
                                 Part('content'),
                             )),
                        Part('panels'),
                    )),
                )),
                Part('bottom', content=(
                    Part('bottom-wrap', content=(
                        Part('bottom-bar'),
                        Part('footer', aria_label=_("Page footer"), role='contentinfo'),
                    )),
                )),
            )),
        )),
    )
    _UNSAFE_CHARS = re.compile(r"[^a-zA-Z0-9_-]")

    def _safe_css_id(self, id):
        return self._UNSAFE_CHARS.sub('-', id)

    def _uri_node(self, context, node, lang=None):
        uri = node.id()
        if not uri.startswith('/'):
            uri = '/' + uri
        if '#' in uri:
            uri, anchor = uri.split('#', 1)
            args = (anchor,)
        else:
            args = ()
        return context.generator().uri(uri, *args, setlang=lang)

    def _resource_uri_prefix(self, context, resource):
        return context.req().module_uri('Resources')

    def _uri_resource(self, context, resource):
        uri = super(Exporter, self)._uri_resource(context, resource)
        # Minor hack to make CMS theme preview work (pass theme_id to styles heets).
        theme_id = context.req().param('preview_theme')
        if theme_id and isinstance(resource, lcg.Stylesheet):
            uri += '?preview_theme=%s' % theme_id
        return uri

    def _meta(self, context):
        import wiking
        result = [('generator', 'Wiking %s, LCG %s, Pytis %s' %
                   (wiking.__version__, lcg.__version__, pytis.__version__))]
        if wiking.cfg.viewport:
            result.append(('viewport', wiking.cfg.viewport))
        return result

    def _head(self, context):
        g = self._generator
        tags = super(Exporter, self)._head(context) + \
            [g.link(rel='alternate', type='application/rss+xml', title=p.title(), href=p.channel())
             for p in context.panels() if p.channel() is not None]
        if wiking.cfg.site_icon:
            tags.append(g.link(rel='shortcut icon', href='/favicon.ico'))
        req = context.req()
        server_uri = req.server_uri()
        return tags + [g.meta(property='og:' + name, content=val) for name, val in (
            ('title', context.node().title()),
            ('type', 'article'),
            ('url', server_uri + req.uri()),
            ('site_name', context.application.site_title(req)),
            ('description', context.application.site_subtitle(req)),
            ('image', server_uri + wiking.cfg.site_image if wiking.cfg.site_image else None),
        ) if val is not None]

    def _body_content(self, context):
        if context.layout() == self.Layout.FRAME:
            messages = self._messages(context)
            return (messages and self._generator.div(messages, id='messages') or '',
                    self._content(context))
        else:
            return super(Exporter, self)._body_content(context)

    def _body_attr(self, context):
        attr = super(Exporter, self)._body_attr(context)
        cls = ['page-id-' + self._safe_css_id(context.node().id().strip('/'))]
        cls.extend(['parent-page-id-' + self._safe_css_id(node.id().strip('/'))
                    for node in context.node().path()[1:-1]])
        cls.extend(('lang-%s' % context.lang(),
                    context.layout() + '-layout'))
        req = context.req()
        if req.maximized():
            cls.append('maximized')
        else:
            cls.append('non-maximized')
        if context.panels():
            cls.append('with-panels')
        if context.has_submenu:
            cls.append('with-submenu')
        cls.extend(context.application.body_class_names(req))
        return dict(attr,
                    onload=context.generator().js_call('new wiking.Handler'),
                    cls=' '.join(cls))

    def _site_title(self, context):
        g = self._generator
        title = context.application.site_title(context.req())
        subtitle = context.application.site_subtitle(context.req())
        content = g.strong(title, cls='title')
        if subtitle:
            content += (g.strong(g.noescape(' &ndash; '), cls='separator') +
                        g.strong(subtitle, cls='subtitle'))
        return content

    def _title(self, context):
        return context.node().title() + ' - ' + context.application.site_title(context.req())

    def _top_content(self, context):
        content = context.application.top_content(context.req())
        if content:
            return lcg.coerce(content).export(context)
        else:
            return None

    def _top_controls(self, context):
        return lcg.coerce(context.application.top_controls(context.req())).export(context)

    def _breadcrumbs(self, context):
        links = [lcg.link(n).export(context) for n in context.node().path()[1:]]
        # Translators: A label followed by location information in webpage navigation
        return _("You are here:") + ' ' + lcg.concat(links, separator=' / ')

    def _menu(self, context):
        g = self._generator
        return (g.div(g.span('', cls='menu-icon', tabindex=0),
                      aria_label=_("Menu"), aria_role='button', cls='menu-button'),
                self.MainMenu(context.node().root()).export(context))

    def _submenu(self, context):
        if not context.has_submenu:
            return None
        g = self._generator
        top = context.top_node()
        tree = lcg.FoldableTree(top, label=_("Local navigation: %s", top.title()),
                                tooltip=_("Expand/collapse complete menu hierarchy"))
        content = tree.export(context)
        req = context.req()
        application = context.application
        title = application.menu_panel_title(req)
        if title:
            content = lcg.concat(g.h3(title, role='presentation', aria_hidden='true'), content)
        bottom_content = application.menu_panel_bottom_content(req)
        if bottom_content:
            content = lcg.concat(content, bottom_content.export(context))
        return g.div(content, cls='menu-panel')

    def _messages(self, context):
        messages = context.req().messages()
        if messages:
            return [wiking.Message(message, kind=kind, formatted=formatted).export(context)
                    for message, kind, formatted in messages]
        else:
            return None

    def _heading(self, context):
        g = self._generator
        return g.h1(g.a(context.node().heading().export(context), tabindex=0,
                        name='main-heading', id='main-heading'))

    def _panels(self, context):
        if not context.panels():
            return None
        g = self._generator
        req = context.req()
        panels = context.panels()
        if not panels:
            return None
        result = []
        for panel in panels:
            title = g.a(panel.title(), name='panel-' + panel.id() + '-anchor', tabindex=0,
                        cls='panel-anchor')
            titlebar_content = panel.titlebar_content()
            if titlebar_content:
                title += titlebar_content.export(context)
            channel = panel.channel()
            if channel:
                # Translators: ``RSS channel'' is terminology idiom, see Wikipedia.
                # The placeholder %s is replaced by channel title.
                channel_title = _("RSS channel %s") + ' ' + panel.title()
                title += g.a(g.span('', cls='feed-icon'),
                             href=channel, aria_label=channel_title, title=channel_title,
                             type='application/rss+xml', cls='feed-link')
            content = panel.content()
            # Add a fake container to force the heading level start at 4.
            lcg.Container(lcg.Section('', lcg.Section('', content)))
            result.append(g.div((g.h3(title),
                                 g.div(content.export(context), cls='panel-content')),
                                id='panel-' + self._safe_css_id(panel.id()), cls='panel',
                                role='complementary',
                                aria_label=panel.accessible_title()))
        extra_content = context.application.right_panels_bottom_content(req)
        if extra_content:
            result.append(g.div(extra_content.export(context), cls='panels-bottom-content'))
        return result

    def _last_change(self, context):
        # Currently unused, left here just to have the translation.
        # Translators: Information about last change of a webpage (when and who)
        return _("Last change: %(date)s, %(user)s")

    def _bottom_bar(self, context):
        req = context.req()
        left = context.application.bottom_bar_left_content(req)
        right = context.application.bottom_bar_right_content(req)
        if left or right:
            g = self._generator
            result = [g.hr()]
            if left:
                content = lcg.coerce(left)
                if right:
                    result.append(g.span(content.export(context), cls="left"))
                else:
                    result.append(g.div(content.export(context), cls="left"))
            if right:
                content = lcg.coerce(right)
                result.append(g.span(content.export(context), cls="right"))
            return result
        else:
            return None

    def _footer(self, context):
        content = context.application.footer_content(context.req())
        if content:
            return lcg.coerce(content).export(context)
        else:
            return None

    def uri(self, context, target, **kwargs):
        return (context.req().root() or '') + super().uri(context, target, **kwargs)
