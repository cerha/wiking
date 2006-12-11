# Copyright (C) 2006 Brailcom, o.p.s.
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
from lcg import _html, concat

_ = lcg.TranslatableTextFactory('wiking')

class Exporter(lcg.HtmlExporter):

    _BODY_PARTS = ('wrapper',)
    _LANGUAGE_SELECTION_LABEL = _("Language:")

    t = lcg.Link.ExternalTarget
    
    def _node_uri(self, node, lang=None):
        uri = '/'+ node.id()
        if lang is not None:
            uri += '?lang=%s;keep_language=1' % lang
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
        return _html.div(part, id=name)
    
    def _head(self, node):
        styles = ['<link rel="stylesheet" type="text/css" href="%s">' % \
                  stylesheet for stylesheet in node.stylesheets()]
        x = "\n".join(styles)
        return concat(super(Exporter, self)._head(node), x, separator='\n  ')
    
    def _top(self, node):
        config = node.config()
        title = config.site_title
        if config.site_subtitle:
            title += ' &ndash; ' + config.site_subtitle
        t = _html.div(_html.strong(title), id='site-title')
        return _html.div(_html.div(_html.div(t, id='top-layer3'),
                                   id='top-layer2'), id='top-layer1')

    def _menu(self, node):
        links = [_html.link(item.title() + (cur and hidden(' *') or ''),
                            self._node_uri(item),
                            hotkey=(item.id() == 'index' and "1" or None),
                            cls=("navigation-link"+(cur and " current" or "")))
                 for item, cur in
                 [(item, self._is_current(node, item)) for item in node.menu()]]
        if node.panels():
            skip_target = '#panel-%s ' % node.panels()[0].id()
        else:
            skip_target = '#content-heading'
        skip_lnk = hidden(" (", _html.link(_("skip"), skip_target),")")
        l = _html.link(_("Main navigation"), None, name='main-navigation',
                       hotkey="3")
        label = _html.strong(concat(l, skip_lnk, ":"), cls='label')
        sep = " "+hidden("|")+"\n"
        skip_all = hidden(_html.link(_("Skip all repetitive content"),
                                     '#content-heading', hotkey="2"))
        return (skip_all,
                _html.map(_html.div((label, concat(links, separator=sep)),
                                    id="navigation-bar"),
                          title=_("Main navigation"), name="main-navigation"))

    def _page(self, node):
        return self._parts(node, ('menu', 'language_selection',
                                  'panels', 'content', 'clearing'))
    
    def _panels(self, node):
        panels = node.panels()
        if panels and not node.config().show_panels:
            return _html.div(_html.link(_("Show panels"), "?show_panels=1"),
                             cls="panel-control show")
        result = []
        for i, panel in enumerate(panels):
            id = panel.id()
            content = panel.content()
            if isinstance(content, lcg.Content):
                content = content.export(self)
            try:
                next = '#panel-%s ' % panels[i+1].id()
            except IndexError:
                next = '#content-heading'
            title = _html.link(panel.title(), None, name="panel-%s" % id)
            h = _html.div((_html.strong(title),
                           hidden(" (", _html.link(_("skip"), next), ")")),
                          cls='title')
            c = _html.div(content, cls="panel-content")
            result.append(_html.div((_html.hr(cls="hidden"), h, c),
                                    cls="panel panel-"+id))
        if panels:
            ctrl = _html.div(_html.link(_("Hide panels"), "?hide_panels=1"),
                             cls="panel-control hide")
            result.extend((_html.hr(cls="hidden"), ctrl))
        return result


    def _content(self, node):
        h = _html.h(_html.link(node.title(), None, name='content-heading'), 1)
        content = (h, super(Exporter, self)._content(node))
        return _html.div(content, cls='node-id-'+node.id())

    def _clearing(self, node):
        return '&nbsp;'
    
    def _bottom(self, node):
        return self._parts(node, ('wiking_bar', 'last_change', 'footer'))
                           
    def _wiking_bar(self, node):
        import wiking
	result = (_html.hr(),)
        ctrls = (hidden("["),)
        if node.edit_label():
            ctrls += (_html.link(node.edit_label(), "?action=edit"), "|")
        if node.config().wmi:
            ctrl = _html.link(_("Leave the Management Interface"), '/',
                              hotkey="9")
        elif node.config().doc:
            ctrl = _html.link(_("Leave the Help System"), '/')
        else:
            ctrl = _html.link(_("Manage this site"), '/_wmi/',
                              title=_("Enter the Wiking Management Interface"),
                              hotkey="9")
        ctrls += (ctrl, hidden("]"))
        result += (_html.span(concat(ctrls, separator="\n"), cls="controls"),)
        result += (_html.span(_("Powered by %s %s",
                                _html.link("Wiking",
                                           "http://www.freebsoft.org/wiking"),
                                wiking.__version__)),)
        return result
        

    def _last_change(self, node):
        return None
	return _("Last change: %s, %s")

    def _footer(self, node):
        links = [_html.link(label, uri, title=title) + ','
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
        p = _html.p
        contact = node.config().webmaster_addr
        return (_html.hr(),
                p(_("This site conforms to the following standards:"), *links),
                p(_("This site can be viewed in ANY browser."),
                  _html.link(_("Accessibility Statement"),
                             '/_doc/accessibility?display=inline', hotkey='0')),
                p(_("Contact:"), _html.link(contact, "mailto:"+contact)))
    

def hidden(*text):
    return _html.span(text, cls="hidden")
    
#     menu = "\r\n".join(["<ul>"] +
#                        ["<li>%s</li>" % p['identifier'].value()
#                         for p in self._get_rows(parent=None)] +
#                        ["</ul>"])

