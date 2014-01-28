# Copyright (C) 2006-2014 Brailcom, o.p.s.
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

from wiking import *
from lcg import concat

_ = lcg.TranslatableTextFactory('wiking')

class MinimalExporter(lcg.HtmlExporter):
    _BODY_PARTS = ('main', 'bottom_bar')

    def _head(self, context):
        try:
            uri = context.req().module_uri('Resources')
        except:
            uri = '_resources'
        return super(MinimalExporter, self)._head(context) + \
               ['<link rel="stylesheet" type="text/css" href="/%s/%s">' % (uri, style)
                for style in ('default.css', 'layout.css')]
    
    def _meta(self, context):
        import wiking
        return (('generator', 'Wiking %s, LCG %s, Pytis %s' %
                 (wiking.__version__, lcg.__version__, pytis.__version__)),)
    def _main(self, context):
        return (context.generator().h(context.node().title(), 1),
                super(MinimalExporter, self)._content(context))
        
    def _bottom_bar(self, context):
        g = context.generator()
        import wiking
        return (g.hr(cls='hidden'),
                g.span(g.a("Wiking", href="http://www.freebsoft.org/wiking") + ' ' +
                       wiking.__version__))


class Exporter(lcg.StyledHtmlExporter, lcg.HtmlExporter):

    class Context(lcg.HtmlExporter.Context):
        def _init_kwargs(self, req=None, **kwargs):
            self._req = req
            # Some harmless hacks for faster access to some often used parameters...
            # These attributes are not the part of the official context extension (such as the
            # 'req()' method, so their use should be limited to this module only!
            if isinstance(self.node(), wiking.WikingNode):
                # Not needed when exporting AJAX response content, which does not use WikingNode.
                self.has_menu = bool([n for n in self.node().root().children() if not n.hidden()])
                self.has_submenu = bool([n for n in self.node().top().children() if not n.hidden()])
            self.application = wiking.module.Application
            super(Exporter.Context, self)._init_kwargs(timezone=req.timezone(), **kwargs)
            # Make sure that Prototype.js is always loaded first, so that it is
            # available in any other scripts.
            scripts = ('prototype.js', 'effects.js', 'gettext.js', 'lcg.js', 'wiking.js')
            for filename in scripts + tuple(wiking.cfg.extra_scripts):
                self.resource(filename)
            if self.lang() != 'en':
                self.resource('wiking.%s.po' % self.lang()) # Translations for Javascript
            # TODO: Load these stylesheets conditionally (only when
            # lcg-widgets.css/pytis-forms.css are loaded).
            self.resource('lcg-widget-colors.css')
            self.resource('pytis-form-colors.css')

        def req(self):
            """Return the current request as a 'wiking.Request' instance.

            This method is the official Wiking extension of LCG export context.

            """
            return self._req

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

    _BODY_PARTS = ('wrap', 'media_player')
    _WRAP_PARTS = ('top', 'page', 'bottom')
    _TOP_PARTS = ('site_title', 'top_content', 'language_selection')
    _PAGE_PARTS = ('links', 'breadcrumbs', 'menu', 'submenu', 'panels', 'main', 'page_clearing')
    _BOTTOM_PARTS = ('bottom_bar', 'footer')
    _PART_TITLE = {
        'top':     _("Page heading"),
        'menu':    _("Main navigation"),
        'submenu': _("Local navigation"),
        'main':    _("Main content"),
        'bottom':  _("Page footer"),
        'language_selection': _("Language selection"),
    }
    # Translators: Label for language selection followed by list of languages
    _LANGUAGE_SELECTION_LABEL = _("Language:")
    _MESSAGE_TYPE_CLASS = {Request.INFO: 'info',
                           Request.WARNING: 'warning',
                           Request.ERROR: 'error'}
    _UNSAFE_CHARS = re.compile(r"[^a-zA-Z0-9_-]")

    def _safe_css_id(self, id):
        return self._UNSAFE_CHARS.sub('-', id)

    def _body_attr(self, context, **kwargs):
        onload = context.generator().js_call('new wiking.Handler')
        cls = ['page-id-' + self._safe_css_id(context.node().id().strip('/'))]
        cls.extend(['parent-page-id-' + self._safe_css_id(node.id().strip('/'))
                    for node in context.node().path()[1:-1]])
        cls.extend(['lang-%s' % context.lang(),
                    (context.node().layout() or self.Layout.DEFAULT) + '-layout'])
        if context.req().maximized():
            cls.append('maximized')
        else:
            cls.append('non-maximized')
        return super(Exporter, self)._body_attr(context, onload=onload, cls=' '.join(cls), **kwargs)

    def _body_content(self, context):
        if context.node().layout() == self.Layout.FRAME:
            return self._content(context)
        else:
            return super(Exporter, self)._body_content(context)

    def _meta(self, context):
        import wiking
        return (('generator', 'Wiking %s, LCG %s, Pytis %s' %
                 (wiking.__version__, lcg.__version__, pytis.__version__)),)

    def _node_identification(self, context):
        """Returns a string of CSS classes identifying the current node
        and its context in node hierarchy
        """

    def _wrap(self, context):
        g = self._generator
        return g.div(self._parts(context, self._WRAP_PARTS), id='wrap-layer1')
    
    def _bottom(self, context):
        return self._parts(context, self._BOTTOM_PARTS)
                           
    def _page(self, context):
        return self._parts(context, self._PAGE_PARTS)

    def _page_attr(self, context):
        node = context.node()
        cls = ''
        if context.has_menu:
            cls += ' with-menu'
        if context.has_submenu:
            cls += ' with-submenu'
        if node.panels() and context.req().show_panels():
            cls += ' with-panels'
        return dict(cls=cls)

    def _part(self, name, context):
        content = getattr(self, '_'+name)(context)
        if content is not None:
            if hasattr(self, '_'+name+'_attr'):
                attr = getattr(self, '_'+name+'_attr')(context)
            else:
                attr = {}
            if name in self._PART_TITLE:
                attr['title'] = self._PART_TITLE[name]
            return self._generator.div(content, id=name.replace('_', '-'), **attr)
        else:
            return None

    def _language_selection_image(self, context, lang):
        if wiking.cfg.language_selection_image:
            return wiking.cfg.language_selection_image % lang
        else:
            return None
    
    def _hidden(self, *text):
        return self._generator.span(text, cls="hidden")

    def _uri_node(self, context, node, lang=None):
        uri = node.id()
        if not uri.startswith('/'):
            uri = '/'+ uri
        return context.generator().uri(uri, setlang=lang)

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
        result = super(Exporter, self)._head(context)
        channels = [('<link rel="alternate" type="application/rss+xml" '
                     'title="'+ p.title() +'" href="'+ p.channel() +'">')
                    for p in context.node().panels() if p.channel() is not None]
        return lcg.concat(result, channels, separator="\n  ")
    
    def _site_title(self, context):
        g = self._generator
        title = context.application.site_title(context.req())
        subtitle = context.application.site_subtitle(context.req())
        content = g.strong(title, cls='title')
        if subtitle:
            content += g.strong(' &ndash; ', cls='separator') + g.strong(subtitle, cls='subtitle')
        return content

    def _title(self, context):
        return context.node().page_heading() +' - '+ context.application.site_title(context.req())

    def _top(self, context):
        g = self._generator
        content = self._parts(context, self._TOP_PARTS)
        return g.div(g.div(g.div(content, id='top-layer3'), id='top-layer2'), id='top-layer1')

    def _top_content(self, context):
        content = context.application.top_content(context.req())
        if content:
            return lcg.coerce(content).export(context)
        else:
            return None

    def _links(self, context):
        g = self._generator
        links = [g.a(_("Main content"), href='#main-heading', accesskey="2")]
        if context.has_menu or context.has_submenu:
            links.append(g.a(_("Main navigation"), href='#main-navigation'))
            if context.has_menu and context.has_submenu:
                links.append(g.a(_("Local navigation"), href='#local-navigation'))
        if len(context.node().variants()) > 1:
            links.append(g.a(_("Language selection"), href='#language-selection-anchor'))
        if context.req().show_panels():
            for panel in context.node().panels():
                links.append(g.a(panel.accessible_title(), href='#panel-%s-anchor ' % panel.id()))
        return _("Jump in page") + ": " + concat(links, separator=' | ')
        
    def _breadcrumbs(self, context):
        links = [lcg.link(n).export(context) for n in context.node().path()[1:]]
        # Translators: A label followed by location information in webpage navigation
        return _("You are here:") + ' ' + concat(links, separator=' / ')
        
    def _menu(self, context):
        g = self._generator
        items = [item for item in context.node().root().children() if not item.hidden()]
        if items:
            top = context.node().top()
            n = len(items)
            style = "width: %d%%" % (100/n)
            last_style = "width: %d%%" % (100 - (100 / n * (n-1)))
            first, last = items[0], items[-1]
            menu = [g.li(g.a(item.title(), href=self._uri_node(context, item),
                             title=item.descr(), accesskey=(item is first and '1' or None),
                             cls='navigation-link'+(item is top and ' current' or ''),
                             )+(item is top and self._hidden(' *') or ''),
                         style=(item is last and last_style or style))
                    for item in items]
            title = g.a(_("Main navigation")+':', name='main-navigation', accesskey="3")
            return concat(g.h(title, 3), g.ul(*menu))
        else:
            return None

    def _submenu(self, context):
        if not context.has_submenu:
            return None
        g = self._generator
        req = context.req()
        application = context.application
        if context.has_menu:
            # If there is the main menu, this is its submenu, but if the main
            # menu is empty, this menu acts as the main menu.
            heading = application.menu_panel_title(req)
            title = application.menu_panel_tooltip(req)
            name = 'local-navigation'
        else:
            title = heading = _("Main navigation")
            name = 'main-navigation'
        tree = lcg.FoldableTree(context.node().top(),
                                tooltip=_("Expand/collapse complete menu hierarchy"))
        content = tree.export(context)
        extra_content = application.menu_panel_bottom_content(req)
        if extra_content:
            content += extra_content.export(context)
        return g.div((g.h(g.a(heading, name=name, accesskey="3"), 3), content),
                     cls='menu-panel')

    def _panels(self, context):
        g = self._generator
        req = context.req()
        panels = context.node().panels()
        if not panels:
            return None
        if not req.show_panels():
            # Translators: Panels are small windows on the side of the page. This is a label
            # for a link that shows/hides the panels.
            return g.a(_("Show panels"), href="?show_panels=1", cls='panel-control show')
        result = [g.a(_("Hide panels"), href="?hide_panels=1", cls='panel-control hide')]
        for panel in panels:
            title = g.a(panel.title(), name='panel-'+panel.id()+'-anchor', tabindex=0,
                        cls='panel-anchor')
            titlebar_content = panel.titlebar_content()
            if titlebar_content:
                title += titlebar_content.export(context)
            channel = panel.channel()
            if channel:
                icon = context.resource('rss.png')
                if icon:
                    # Translators: ``RSS channel'' is terminology idiom, see Wikipedia
                    channel_title = panel.title() +' ('+ _("RSS channel") +')'
                    img = g.img(context.uri(icon), align='right', alt=channel_title)
                    link = g.a(img, href=channel, title=channel_title, type='application/rss+xml',
                               cls='feed-icon-link')
                    title = link +' '+ title
            cls = 'panel'
            if panel.id() == 'login' and req.user():
                cls += ' logged'
            content = panel.content()
            # Add a fake container to force the heading level start at 4.
            container = lcg.Container(lcg.Section('', lcg.Section('', content)))
            result.append(g.div((g.h(title, 3),
                                 g.div(content.export(context), cls='panel-content')),
                                id='panel-'+self._safe_css_id(panel.id()), cls=cls,
                                title=panel.accessible_title()))
        extra_content = context.application.right_panels_bottom_content(req)
        if extra_content:
            result.append(g.div(extra_content.export(context), cls='panels-bottom-content'))
        result.append(g.br())
        return result

    def _messages(self, context):
        messages = context.req().messages()
        if messages:
            g = self._generator
            return g.div([g.div((type == Request.WARNING and _("Warning")+': 'or '') + \
                                g.escape(message),
                                cls=self._MESSAGE_TYPE_CLASS[type])
                          for message, type in messages],
                         id='messages')
        else:
            return ''
    
    def _main(self, context):
        g = self._generator
        if context.req().maximized():
            label = g.img('/_resources/minimize.png', alt=_("Minimize"))
            tooltip = _("Exit the maximized mode.")
            href = '?maximize=0'
        else:
            label = g.img('/_resources/maximize.png', alt=_("Maximize"))
            tooltip = _("Maximize the main content to the full size of the browser window.")
            href = '?maximize=1'
        return (g.hr(cls='hidden'),
                g.div((
                    g.a(label, href=href, title=tooltip, id='maximized-mode-control'),
                    g.h(g.a(context.node().page_heading(), tabindex=0,
                            name='main-heading', id='main-heading'), 1),
                    self._messages(context),
                    super(Exporter, self)._content(context)), id='content'),
                g.div('&nbsp;', id='clearing'))

    def _page_clearing(self, context):
        return '&nbsp;'
    
    def _last_change(self, context):
        # Currently unused, left here just to have the translation.
        # Translators: Information about last change of a webpage (when and who)
	return _("Last change: %(date)s, %(user)s")

    def _bottom_bar(self, context):
        req = context.req()
        left  = context.application.bottom_bar_left_content(req)
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

    def _export_inline_image(self, context, element):
        # Load Lightbox if the image has a thumbnail.
        if element.image(context).thumbnail():
            for f in ('prototype.js', 'effects.js', 'builder.js', 'lightbox.js', 'lightbox.css'):
                context.resource(f)
        return super(Exporter, self)._export_inline_image(context, element)

class Html5Exporter(lcg.Html5Exporter, Exporter):
    pass
