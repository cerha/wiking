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

    _BODY_PARTS = ('wrapper',)
    _LANGUAGE_SELECTION_LABEL = _("Language:")

    def _node_uri(self, node, lang=None):
        uri = '/'+ node.id()
        if lang is not None:
            uri += '?setlang=%s' % lang
        return uri
    
    def _title(self, node):
        config = node.config()
        return config.site_title + ' - ' + node.title()

    def _is_current(self, node, item):
        nid, iid = (node.id(), item.id())
        return iid == nid or nid.startswith(iid+'/')
    
    def _wrapper(self, node):
        return self._parts(node, ('top', 'page', 'bottom'))
    
    def _part(self, part, name):
        return self._generator.div(part, id=name)
    
    #def _head(self, node):
    #    result = super(Exporter, self)._head(node)
    #    rss = node.config().rss
    #    if rss:
    #        result = concat(result, '<link rel="alternate" '
    #                        'type="application/rss+xml" title="%s" href="%s"/>'
    #                        % (node.title(), rss), separator='\n  ')
    #    return result
    
    def _top(self, node):
        g = self._generator
        config = node.config()
        title = config.site_title
        if config.site_subtitle:
            title += ' &ndash; ' + config.site_subtitle
        return g.div(g.div(g.div(g.div(g.strong(title), id='site-title'),
                                 id='top-layer3'), id='top-layer2'),
                     id='top-layer1')

    def _hidden(self, *text):
        return self._generator.span(text, cls="hidden")

    def _menu(self, node):
        g = self._generator
        links = [g.link(item.title() + (cur and self._hidden(' *') or ''),
                        self._node_uri(item), title=item.descr(),
                        hotkey=(item.id() == 'index' and "1" or None),
                        cls=("navigation-link"+(cur and " current" or "")))
                 for item, cur in [(item, self._is_current(node, item))
                                   for item in node.menu()]]
        if node.panels():
            skip_target = '#panel-%s ' % node.panels()[0].id()
        else:
            skip_target = '#content-heading'
        skip_lnk = self._hidden(" (", g.link(_("skip"), skip_target),")")
        l = g.link(_("Main navigation"), None, name='main-navigation',
                   hotkey="3")
        label = g.strong(concat(l, skip_lnk, ":"), cls='label')
        sep = " "+ self._hidden("|") +"\n"
        skip_all = self._hidden(g.link(_("Skip all repetitive content"),
                                 '#content-heading', hotkey="2"))
        return (skip_all, g.map(g.div((label, concat(links, separator=sep)),
                                      id="navigation-bar"),
                                title=_("Main navigation")))

    def _page(self, node):
        return self._parts(node, ('menu', 'language_selection',
                                  'panels', 'content', 'clearing'))

    def _login_ctrl(self, node):
        user = node.config().user
        if user:
            u, l, cmd = (user['user'].value(), _("log out"), 'logout')
        else:
            u, l, cmd = (_("not logged"), _("log in"), 'login')
        return (u, self._generator.link(l, '?command=%s' % cmd,
                                        cls='login-ctrl'))
    
    def _panels(self, node):
        g = self._generator
        panels = node.panels()
        config = node.config()
        if not panels:
            return None
        if not config.show_panels:
            return g.link(_("Show panels"), "?show_panels=1",
                          cls='panel-control show')
        result = [g.link(_("Hide panels"), "?hide_panels=1",
                         cls='panel-control hide'),
                  g.hr(cls="hidden")]
        if config.login_panel:
            user, ctrl = self._login_ctrl(node)
            content = (g.p(concat(user, ' ', self._hidden('['), ctrl,
                                  self._hidden(']'))),)
            if config.register and not config.user:
                content += (g.div(g.link(_("New user registration"),
                                         config.register),
                                  cls='register'),)
            panels.insert(0, Panel('login', _("Login"), content))
        for i, panel in enumerate(panels):
            id = panel.id()
            content = panel.content()
            if isinstance(content, lcg.Content):
                content = content.export(self)
            try:
                next = '#panel-%s ' % panels[i+1].id()
            except IndexError:
                next = '#content-heading'
            title = g.link(panel.title(), None, name="panel-%s" % id)
            h = g.div((g.strong(title),
                       self._hidden(" (", g.link(_("skip"), next), ")")),
                      cls='title')
            c = g.div(content, cls="panel-content")
            result.append(g.div((h, c, g.hr(cls="hidden")),
                                cls="panel panel-"+id))
        return result

    def _content(self, node):
        g = self._generator
        content = (
            g.h(g.link(node.title(), None, name='content-heading'), 1),
            super(Exporter, self)._content(node))
        return g.div(content, cls='node-id-'+node.id())

    def _clearing(self, node):
        return '&nbsp;'
    
    def _bottom(self, node):
        return self._parts(node, ('wiking_bar', 'last_change', 'footer'))
                           
    def _wiking_bar(self, node):
        import wiking
        g = self._generator
        config = node.config()
	result = (g.hr(),)
        ctrl = ''
        #if config.edit_label:
        #    ctrl += (g.link(config.edit_label, "?action=edit"), "|")
        if config.wmi or not config.login_panel:
            user, lctrl = self._login_ctrl(node)
            ctrl += concat(_("Login"), ': ', user, ' (', lctrl, ') | ')
        if config.wmi:
            ctrl += g.link(_("Leave the Management Interface"), '/', hotkey="9")
        elif config.doc:
            ctrl += g.link(_("Leave the Help System"), '/')
        elif config.allow_wmi_link:
            modname = config.modname or ''
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
        contact = node.config().webmaster_addr
        return (g.hr(),
                g.p(_("This site conforms to the following standards:"),
                    *links),
                g.p(_("This site can be viewed in ANY browser."),
                    g.link(_("Accessibility Statement"),
                           '/_doc/accessibility?display=inline', hotkey='0')),
                g.p(_("Contact:"), g.link(contact, "mailto:"+contact)))
    

#     menu = "\r\n".join(["<ul>"] +
#                        ["<li>%s</li>" % p['identifier'].value()
#                         for p in self._get_rows(parent=None)] +
#                        ["</ul>"])

