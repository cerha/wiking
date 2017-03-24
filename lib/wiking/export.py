# Copyright (C) 2006-2017 Brailcom, o.p.s.
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

import re

import lcg
import pytis
import wiking

_ = lcg.TranslatableTextFactory('wiking')

class MinimalExporter(lcg.HtmlExporter):
    _BODY_PARTS = ('main', 'bottom_bar')

    def _head(self, context):
        g = context.generator()
        try:
            uri = context.req().module_uri('Resources')
        except:
            uri = '_resources'
        return super(MinimalExporter, self)._head(context) + \
            [g.link(rel='stylesheet', type='text/css', href='/%s/default.css' % uri)]

    def _meta(self, context):
        import wiking
        return (('generator', 'Wiking %s, LCG %s, Pytis %s' %
                 (wiking.__version__, lcg.__version__, pytis.__version__)),)

    def _main(self, context):
        g = context.generator()
        return (g.h(context.node().title(), 1),
                super(MinimalExporter, self)._content(context))

    def _bottom_bar(self, context):
        g = context.generator()
        import wiking
        return (g.hr(cls='hidden'),
                g.span(g.a("Wiking", href="http://www.freebsoft.org/wiking") + ' ' +
                       wiking.__version__))


class Exporter(lcg.StyledHtmlExporter, lcg.HtmlExporter):

    class Context(lcg.HtmlExporter.Context):
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
            self.has_submenu = any(not n.hidden() for n in top_node.children())
            self.application = application
            # Make sure that Prototype.js is always loaded first, so that it is
            # available in any other scripts.
            scripts = ('prototype.js', 'effects.js', 'gettext.js', 'lcg.js', 'wiking.js')
            for filename in scripts + tuple(wiking.cfg.extra_scripts):
                self.resource(filename)
            if self.lang() != 'en':
                self.resource('wiking.%s.po' % self.lang()) # Translations for Javascript

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

    class Layout(object):
        """Enumeration of output document layout styles."""
        DEFAULT = 'default'
        """Default Wiking layout wrapping the page content in menus, panels etc."""
        FRAME = 'frame'
        """Frame layout displaying just the document content wrapped in html body.

        This layout is typically useful for rendering the IFRAME content.  The
        exported document content is wrapped into HTML body with HTML head
        automatically created.

        """

    _BODY_PARTS = ('wrap',)
    _WRAP_PARTS = ('top', 'middle', 'bottom')
    _MIDDLE_PARTS = ('page',)
    _PAGE_PARTS = ('links', 'breadcrumbs', 'menu', 'submenu', 'main', 'panels', 'page_clearing')
    _BOTTOM_PARTS = ('bottom_bar', 'footer')
    _PART_TITLE = {
        'top': _("Page heading"),
        'menu': _("Main navigation"),
        'main': _("Main content"),
        'bottom': _("Page footer"),
        'language_selection': _("Language selection"),
    }
    _PART_LABELLEDBY = {
        'main': 'main-heading',
    }
    _LANDMARKS = {
        'top': 'banner',
        'menu': 'navigation',
        'main': 'main',
        'bottom': 'contentinfo',
    }
    _UNSAFE_CHARS = re.compile(r"[^a-zA-Z0-9_-]")

    def _safe_css_id(self, id):
        return self._UNSAFE_CHARS.sub('-', id)

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
        if context.application.preview_mode(req):
            cls.append('preview-mode')
        else:
            cls.append('production-mode')
        if context.panels():
            cls.append('with-panels')
        return dict(attr,
                    onload=context.generator().js_call('new wiking.Handler'),
                    cls=' '.join(cls))

    def _body_content(self, context):
        if context.layout() == self.Layout.FRAME:
            return (self._messages(context),
                    self._content(context))
        else:
            return super(Exporter, self)._body_content(context)

    def _meta(self, context):
        import wiking
        result = [('generator', 'Wiking %s, LCG %s, Pytis %s' %
                   (wiking.__version__, lcg.__version__, pytis.__version__))]
        if wiking.cfg.viewport:
            result.append(('viewport', wiking.cfg.viewport))
        return result

    def _wrap(self, context):
        g = self._generator
        return g.div(self._parts(context, self._WRAP_PARTS), id='wrap-layer1')

    def _middle(self, context):
        g = self._generator
        return g.div(self._parts(context, self._MIDDLE_PARTS), id='middle-layer1')

    def _bottom(self, context):
        return self._parts(context, self._BOTTOM_PARTS)

    def _page(self, context):
        return self._parts(context, self._PAGE_PARTS)

    def _page_attr(self, context):
        return dict(cls='with-submenu') if context.has_submenu else {}

    def _part(self, name, context):
        content = getattr(self, '_' + name)(context)
        if content is not None:
            if hasattr(self, '_' + name + '_attr'):
                attr = getattr(self, '_' + name + '_attr')(context)
            else:
                attr = {}
            if name in self._PART_TITLE:
                attr['aria_label'] = self._PART_TITLE[name]
            if name in self._PART_LABELLEDBY:
                attr['aria_labelledby'] = self._PART_LABELLEDBY[name]
            if name in self._LANDMARKS:
                attr['role'] = self._LANDMARKS[name]
            return self._generator.div(content, id=name.replace('_', '-'), **attr)
        else:
            return None

    def _hidden(self, *text):
        return self._generator.span(text, cls="hidden")

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

    def _top(self, context):
        g = self._generator
        return g.div(
            g.div(
                g.div([g.div(content, id=id_) for id_, content in
                       (('top-content', self._top_content(context)),
                        ('top-controls', self._top_controls(context)),
                        ('top-clearing', ''))
                       if content is not None],
                      id='top-layer3'),
                id='top-layer2'),
            id='top-layer1')

    def _top_content(self, context):
        content = context.application.top_content(context.req())
        if content:
            return lcg.coerce(content).export(context)
        else:
            return None

    def _top_controls(self, context):
        return lcg.coerce(context.application.top_controls(context.req())).export(context)

    def _links(self, context):
        g = self._generator
        links = [g.a(_("Main content"), href='#main-heading', accesskey="2")]
        for panel in context.panels():
            links.append(g.a(panel.accessible_title(), href='#panel-%s-anchor ' % panel.id()))
        return _("Jump in page") + ": " + lcg.concat(links, separator=' | ')

    def _breadcrumbs(self, context):
        links = [lcg.link(n).export(context) for n in context.node().path()[1:]]
        # Translators: A label followed by location information in webpage navigation
        return _("You are here:") + ' ' + lcg.concat(links, separator=' / ')

    def _menu(self, context):
        g = self._generator
        top = context.top_node()
        children = context.node().root().children()
        items = []
        for node in children:
            if not node.hidden():
                if not all(n.hidden() for n in node.children()):
                    tree = lcg.FoldableTree(node, label=_("Local navigation for: %s", node.title()))
                    dropdown = g.div(tree.export(context), cls='menu-dropdown',
                                     style='display: none')
                    arrow = g.span('', cls='dropdown-arrow', role='presentation')
                else:
                    dropdown = ''
                    arrow = ''
                items.append(g.li((g.a(node.title() + arrow,
                                       href=self._uri_node(context, node),
                                       title=node.descr(),
                                       cls=('navigation-link' +
                                            (' current' if node is top else '') +
                                            (' with-dropdown' if dropdown else ''))),
                                   dropdown),
                                  cls='main-menu-item'))
        return (
            g.h(_("Main navigation"), 3),
            g.div(g.ul(*items, cls='main-menu-items'), id='main-menu'),
        )

    def _menu_attr(self, context):
        return dict(accesskey="3")

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
            content = lcg.concat(g.h(title, 3, role='presentation', aria_hidden='true'), content)
        bottom_content = application.menu_panel_bottom_content(req)
        if bottom_content:
            content = lcg.concat(content, bottom_content.export(context))
        return g.div(content, cls='menu-panel')

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
            result.append(g.div((g.h(title, 3),
                                 g.div(content.export(context), cls='panel-content')),
                                id='panel-' + self._safe_css_id(panel.id()), cls='panel',
                                role='complementary',
                                aria_label=panel.accessible_title()))
        extra_content = context.application.right_panels_bottom_content(req)
        if extra_content:
            result.append(g.div(extra_content.export(context), cls='panels-bottom-content'))
        return result

    def _messages(self, context):
        messages = context.req().messages()
        if messages:
            g = self._generator
            return g.div([wiking.Message(message, kind=kind, formatted=formatted).export(context)
                          for message, kind, formatted in messages],
                         id='messages')
        else:
            return ''

    def _main(self, context):
        g = self._generator
        if context.req().maximized():
            label = _("Exit the maximized mode.")
            href = '?maximize=0'
            cls = 'unmaximize-icon'
        else:
            label = _("Maximize the main content to the full size of the browser window.")
            href = '?maximize=1'
            cls = 'maximize-icon'
        return (g.hr(cls='hidden'),
                g.div((
                    g.a('', href=href, title=label, aria_label=label, cls=cls,
                        id='maximized-mode-button', role='button'),
                    g.h(g.a(context.node().heading().export(context), tabindex=0,
                            name='main-heading', id='main-heading'), 1),
                    self._messages(context),
                    super(Exporter, self)._content(context)), id='content'),
                g.div('', id='clearing'))

    def _page_clearing(self, context):
        return ''

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
                if left:
                    result.append(self._hidden(" | "))
                content = lcg.coerce(right)
                result.append(g.span(content.export(context)))
            return result
        else:
            return None

    def _footer(self, context):
        g = self._generator
        content = context.application.footer_content(context.req())
        if content:
            return g.hr() + lcg.coerce(content).export(context)
        else:
            return None


class Html5Exporter(lcg.Html5Exporter, Exporter):
    pass
