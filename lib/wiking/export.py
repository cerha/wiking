# Copyright (C) 2006, 2007, 2008 Brailcom, o.p.s.
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

class Exporter(lcg.StyledHtmlExporter, lcg.HtmlExporter):

    class Context(lcg.HtmlExporter.Context):
        def _init_kwargs(self, req=None, **kwargs):
            self._req = req
            # Some harmless hacks...
            self.has_menu = bool([n for n in self.node().root().children() if not n.hidden()])
            self.has_submenu = bool([n for n in self.node().top().children() if not n.hidden()])
            self.wmi = hasattr(req, 'wmi') and req.wmi or False
            super(Exporter.Context, self)._init_kwargs(**kwargs)

        def req(self):
            return self._req

    _BODY_PARTS = ('wrap', 'media_player')
    _WRAP_PARTS = ('top', 'page', 'bottom')
    _PAGE_PARTS = ('links', 'breadcrumbs', 'language_selection',
                   'menu', 'submenu', 'panels', 'main', 'page_clearing')
    _BOTTOM_PARTS = ('bottom_bar', 'footer')
    _LANGUAGE_SELECTION_LABEL = _("Language:")

    def _body_attr(self, context):
        return super(Exporter, self)._body_attr(context, onload='wiking_init();')

    def _wrap(self, context):
        return self._parts(context, self._WRAP_PARTS)
    
    def _bottom(self, context):
        return self._parts(context, self._BOTTOM_PARTS)
                           
    def _page(self, context):
        return self._parts(context, self._PAGE_PARTS)

    def _page_attr(self, context):
        cls = cls='node-id-%s' % context.node().id()
        if context.has_menu:
            cls += ' with-menu'
        if context.has_submenu:
            cls += ' with-submenu'
        if context.node().panels() and context.req().show_panels():
            cls += ' with-panels'
        return dict(cls=cls)

    def _part(self, name, context):
        content = getattr(self, '_'+name)(context)
        if content is not None:
            if hasattr(self, '_'+name+'_attr'):
                attr = getattr(self, '_'+name+'_attr')(context)
            else:
                attr = {}
            return self._generator.div(content, id=name.replace('_', '-'), **attr)
        else:
            return None

    def _language_selection_image(self, context, lang):
        if cfg.language_selection_image:
            return cfg.language_selection_image % lang
        else:
            return None
    
    def _hidden(self, *text):
        return self._generator.span(text, cls="hidden")

    def _uri_node(self, context, node, lang=None):
        uri = node.id()
        if not uri.startswith('/'):
            uri = context.req().uri_prefix() + '/'+ uri
        return context.generator().uri(uri, setlang=lang)

    def _resource_uri_prefix(self, context, resource):
        return context.req().application().module_uri('Resources')
    
    def _head(self, context):
        context.node().resource('wiking.js')
        result = super(Exporter, self)._head(context)
        #rss = context.rss()
        #if rss:
        #    result = concat(result, '<link rel="alternate" '
        #                    'type="application/rss+xml" title="%s" href="%s"/>'
        #                    % (context.node().title(), rss), separator='\n  ')
        return result
    
    def _site_title(self, context):
        if context.wmi:
            return _("Wiking Management Interface")
        else:
            return cfg.site_title

    def _site_subtitle(self, context):
        if context.wmi:
            return None
        else:
            return cfg.site_subtitle
    
    def _title(self, context):
        return self._site_title(context) + ' - ' + context.node().heading()

    def _top(self, context):
        g = self._generator
        title = g.strong(self._site_title(context), cls='title')
        subtitle = self._site_subtitle(context)
        if subtitle:
            title += g.strong(' &ndash; ', cls='separator') + g.strong(subtitle, cls='subtitle')
        return g.div(g.div(g.div(g.div(title, id='site-title'),
                                 id='top-layer3'), id='top-layer2'), id='top-layer1')
    

    def _links(self, context):
        g = self._generator
        links = [g.link(_("Content"), '#main-heading', hotkey="2")]
        if context.has_menu or context.has_submenu:
            links.append(g.link(_("Main navigation"), '#main-navigation'))
            if context.has_menu and context.has_submenu:
                links.append(g.link(_("Local navigation"), '#local-navigation'))
        if len(context.node().variants()) > 1:
            links.append(g.link(_("Language selection"), '#language-selection-anchor'))
        if context.req().show_panels():
            for panel in context.node().panels():
                links.append(g.link(panel.accessible_title(), '#panel-%s-anchor ' % panel.id()))
        return _("Jump in page") + ": " + concat(links, separator=' | ')
        
    def _breadcrumbs(self, context):
        links = [lcg.link(n).export(context) for n in context.node().path()[1:]]
        return _("You are here:") + ' ' + concat(links, separator=' / ')
        
    def _menu(self, context):
        g = self._generator
        top = context.node().top()
        links = [g.link(item.title(), self._uri_node(context, item),
                        title=item.descr(), hotkey=(i==0 and '1' or None),
                        cls='navigation-link' + (item is top and ' current' or ''),
                        ) + (item is top and self._hidden(' *') or '')
                 for i, item in enumerate(context.node().root().children())
                 if not item.hidden()]
        if links:
            title = g.link(_("Main navigation")+':', None, name='main-navigation', hotkey="3")
            return g.map((g.h(title, 3), g.list(links)),
                         name='menu-map', title=_("Main navigation"))
        else:
            return None

    def _submenu(self, context):
        g = self._generator
        if not context.has_submenu:
            return None
        menu = lcg.NodeIndex(node=context.node().top())
        menu.set_parent(context.node())
        if context.has_menu:
            # If there is the main menu, this is its submenu, but if the main menu is empty, this
            # menu acts as the main menu.
            title = _("Local navigation")
            heading = _("In this section:")
            name = 'local-navigation'
        else:
            title = heading = _("Main navigation")
            name = 'main-navigation'
        return g.map(g.div((g.h(g.link(heading, None, name=name, hotkey="3"), 3),
                            menu.export(context)),
                           cls='menu-panel'),
                     name='submenu-map', title=title)
    
    def _panels(self, context):
        g = self._generator
        panels = context.node().panels()
        if not panels:
            return None
        if not context.req().show_panels():
            return g.link(_("Show panels"), "?show_panels=1", cls='panel-control show')
        result = [g.link(_("Hide panels"), "?hide_panels=1", cls='panel-control hide')]
        for panel in panels:
            content = panel.content()
            # Add a fake container to force the heading level start at 4.
            container = lcg.SectionContainer(lcg.Section('', lcg.Section('', content)))
            result.append(g.div((g.h(g.link(panel.title(), None,
                                            name='panel-'+panel.id()+'-anchor', tabindex=0), 3),
                                 g.div(content.export(context), cls='panel-content')),
                                id='panel-'+panel.id(), cls='panel'))
        result.append(g.br())
        return result

    def _main(self, context):
        g = self._generator
        return (g.hr(cls='hidden'),
                g.div((g.h(g.link(context.node().heading(), None, tabindex=0,
                                  name='main-heading', id='main-heading'), 1),
                       super(Exporter, self)._content(context)), id='content'),
                g.div('&nbsp;', id='clearing'))

    def _page_clearing(self, context):
        return '&nbsp;'
    
    def _last_change(self, context):
        # Currently unused, left here just to have the translation.
	return _("Last change: %(date)s, %(user)s")

    def _bottom_bar(self, context):
        req = context.req()
        left  = req.application().bottom_bar_left_content(req)
        right = req.application().bottom_bar_right_content(req)
        if left or right:
            g = self._generator
            result = [g.hr()]
            if left:
                content = lcg.coerce(left)
                content.set_parent(context.node())
                if right:
                    result.append(g.span(content.export(context), cls="left"))
                else:
                    result.append(g.div(content.export(context), cls="left"))
            if right:
                if left:
                    result.append(self._hidden(" | "))
                content = lcg.coerce(right)
                content.set_parent(context.node())
                result.append(g.span(content.export(context)))
            return result
        else:
            return None
        
    def _footer(self, context):
        g = self._generator
        req = context.req()
        content = req.application().footer_content(req)
        if content:
            content = lcg.coerce(content)
            content.set_parent(context.node())
            return g.hr() + content.export(context)
        else:
            return None
