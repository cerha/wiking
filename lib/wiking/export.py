# Copyright (C) 2006, 2007 Brailcom, o.p.s.
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

class Exporter(lcg.HtmlExporter):

    _BODY_PARTS = ('wrap',)
    _WRAP_PARTS = ('top', 'page', 'bottom')
    _PAGE_PARTS = ('links', 'breadcrumbs', 'language_selection',
                   'menu', 'submenu', 'panels', 'content', 'clearing')
    _BOTTOM_PARTS = ('wiking_bar', 'last_change', 'footer')
    _LANGUAGE_SELECTION_LABEL = _("Language:")

    def _wrap(self, node):
        return self._parts(node, self._WRAP_PARTS)
    
    def _bottom(self, node):
        return self._parts(node, self._BOTTOM_PARTS)
                           
    def _page(self, node):
        node.state().has_submenu = bool([n for n in node.top().children() if not n.hidden()])
        return self._parts(node, self._PAGE_PARTS)

    def _page_cls(self, node):
        state = node.state()
        cls = cls='node-id-%s' % node.id()
        if state.has_submenu:
            cls += ' with-submenu'
        if node.panels() and state.show_panels:
            cls += ' with-panels'
        return cls

    def _part(self, name, node):
        content = getattr(self, '_'+name)(node)
        if content is not None:
            if hasattr(self, '_'+name+'_cls'):
                cls = getattr(self, '_'+name+'_cls')(node)
            else:
                cls = None
            return self._generator.div(content, id=name.replace('_', '-'), cls=cls)
        else:
            return None
    
    def _node_uri(self, node, lang=None):
        uri = '/'+ node.id()
        if lang is not None:
            uri += '?setlang=%s' % lang
        return uri
    
    def _site_title(self, node, full=False):
        state = node.state()
        if state.wmi:
            title = _("Wiking Management Interface")
        elif state.modname == 'Documentation' and not state.inline:
            title = _("Wiking Help System")
        else:
            title = cfg.site_title
            if full and cfg.site_subtitle:
                title += ' &ndash; ' + cfg.site_subtitle
        return title
    
    def _title(self, node):
        return self._site_title(node) + ' - ' + node.heading()

    def _hidden(self, *text):
        return self._generator.span(text, cls="hidden")

    #def _head(self, node):
    #    result = super(Exporter, self)._head(node)
    #    rss = node.state().rss
    #    if rss:
    #        result = concat(result, '<link rel="alternate" '
    #                        'type="application/rss+xml" title="%s" href="%s"/>'
    #                        % (node.title(), rss), separator='\n  ')
    #    return result
    
    def _top(self, node):
        g = self._generator
        title = self._site_title(node, full=True)
        return g.div(g.div(g.div(g.div(g.strong(title), id='site-title'),
                                 id='top-layer3'), id='top-layer2'), id='top-layer1')

    def _links(self, node):
        g = self._generator
        state = node.state()
        links = [g.link(_("Content"), '#content-heading', hotkey="2"),
                 g.link(_("Main navigation"), '#main-navigation')]
        if state.has_submenu:
            links.append(g.link(_("Local navigation"), '#local-navigation'))
        if len(node.language_variants()) > 1:
            links.append(g.link(_("Language selection"), '#language-selection'))
        if state.show_panels:
            for panel in node.panels():
                links.append(g.link(panel.title(), '#panel-%s ' % panel.id()))
        return self._hidden(_("Jump in page") + ": " + concat(links, separator=' | '))
        
    def _breadcrumbs(self, node):
        g = self._generator
        links = [lcg.link(n).export(self) for n in node.path()[1:]]
        return _("You are here:") + ' ' + concat(links, separator=' / ')
        
    def _menu(self, node):
        g = self._generator
        links = []
        for item in node.root().children():
            if not item.hidden():
                cls = "navigation-link"
                sign = ''
                if item is node.top():
                    cls += " current"
                    sign = self._hidden(' *')
                links.append(g.link(item.title(), self._node_uri(item), title=item.descr(),
                                    hotkey=(item.id() == 'index' and "1" or None), cls=cls) + sign)
        title = g.h(g.link(_("Main navigation"), None, name='main-navigation', hotkey="3"), 3)
        return g.map(g.div((title, g.list(links)), id="main-menu"),
                     title=_("Main navigation"))

    def _submenu(self, node):
        g = self._generator
        state = node.state()
        if not state.has_submenu:
            return None
        menu = lcg.NodeIndex(node=node.top(), depth=99)
        menu.set_parent(node)
        title = g.h(g.link(_("In this section:"), None, name='local-navigation', hotkey="3"), 3)
        return g.map(g.div((title, menu.export(self)), id='submenu-frame'),
                     title=_("Local navigation"))
    
    def _panels(self, node):
        g = self._generator
        panels = node.panels()
        if not panels:
            return None
        if not node.state().show_panels:
            return g.link(_("Show panels"), "?show_panels=1", cls='panel-control show')
        result = [g.link(_("Hide panels"), "?hide_panels=1", cls='panel-control hide')]
        for panel in panels:
            content = panel.content()
            if isinstance(content, lcg.Content):
                content = content.export(self)
            result.append(g.div((g.h(g.link(panel.title(), None, name="panel-"+panel.id()), 3),
                                 g.div(content, cls="panel-content")),
                                cls="panel panel-"+panel.id()))
        return result

    def _content(self, node):
        g = self._generator
        return (g.h(g.link(node.heading(), None, name='content-heading'), 1),
                super(Exporter, self)._content(node),
                g.div('&nbsp;', id='content-clearing'))

    def _clearing(self, node):
        return '&nbsp;'
    
    def _wiking_bar(self, node):
        import wiking
        g = self._generator
        state = node.state()
	result = (g.hr(),)
        ctrl = ''
        #if state.edit_label:
        #    ctrl += (g.link(state.edit_label, "?action=edit"), "|")
        if cfg.allow_login_ctrl and (state.wmi or not cfg.allow_login_panel):
            user = state.user
            if user:
                username = user.name()
                cmd, label = ('logout', _("log out"))
            else:
                username = _("not logged")
                cmd, label = ('login', _("log in"))
            lctrl = g.link(label, '?command=%s' % cmd, cls='login-ctrl')
            ctrl += concat(_("Login"), ': ', username, ' (', lctrl, ') | ')
        if state.wmi:
            ctrl += g.link(_("Leave the Management Interface"), '/', hotkey="9")
        elif state.modname == 'Documentation' and not state.inline:
            ctrl += g.link(_("Leave the Help System"), '/')
        elif cfg.allow_wmi_link:
            modname = state.modname or ''
            if modname == 'WikingManagementInterface':
                modname = ''
            ctrl += g.link(_("Manage this site"), '/_wmi/'+modname, hotkey="9",
                           title=_("Enter the Wiking Management Interface"))
        if ctrl:
            ctrls = concat(self._hidden("["), ctrl, self._hidden("]"))
            result += (g.span(ctrls, cls="controls"),)
        result += (g.span(_("Powered by %(wiking)s %(version)s",
                            wiking=g.link("Wiking",
                                          "http://www.freebsoft.org/wiking"),
                            version=wiking.__version__)),)
        return result
        

    def _last_change(self, node):
        return None
	return _("Last change: %(date)s, %(user)s")

    def _footer(self, node):
        g = self._generator
        links = [g.link(label, uri, title=title) + ','
                 for label, uri, title in
                 (("HTML 4.01",
                   "http://validator.w3.org/check/referer",
                   None),
                  ("CSS2",
                   "http://jigsaw.w3.org/css-validator/check/referer",
                   None),
                  ("WCAG 1.0",
                   "http://www.w3.org/WAI/WCAG1AAA-Conformance",
                   "W3C-WAI Web Content Accessibility Guidelines."),
                  ("Section 508",
                   "http://www.section508.gov",
                   _("US Government Section 508 Accessibility Guidelines.")))]
        contact = cfg.webmaster_addr
        if contact is None:
            domain = node.state().server_hostname
            if domain.startswith('www.'):
                domain = domain[4:]
            contact = 'webmaster@' + domain
        return (g.hr(),
                g.p(_("This site conforms to the following standards:"),
                    *links),
                g.p(_("This site can be viewed in ANY browser."),
                    g.link(_("Accessibility Statement"),
                           '/_doc/accessibility?display=inline', hotkey='0')),
                g.p(_("Contact:"), g.link(contact, "mailto:"+contact)))
    


