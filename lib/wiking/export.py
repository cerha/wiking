# Copyright (C) 2006-2015 Brailcom, o.p.s.
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

    _BODY_PARTS = ('wrap', 'media_player')
    _WRAP_PARTS = ('top', 'middle', 'bottom')
    _TOP_PARTS = ('top_content', 'login_control', 'language_selection')
    _MIDDLE_PARTS = ('page',)
    _PAGE_PARTS = ('links', 'breadcrumbs', 'menu', 'submenu', 'panels', 'main', 'page_clearing')
    _BOTTOM_PARTS = ('bottom_bar', 'footer')
    _PART_TITLE = {
        'top': _("Page heading"),
        'menu': _("Main navigation"),
        'submenu': _("Local navigation"),
        'main': _("Main content"),
        'bottom': _("Page footer"),
        'language_selection': _("Language selection"),
    }
    _PART_LABELEDBY = {
        'main': 'main-heading',
    }
    _LANDMARKS = {
        'top': 'banner',
        'menu': 'navigation',
        'submenu': 'navigation',
        'main': 'main',
        'bottom': 'contentinfo',
    }
    # Translators: Label for language selection followed by list of languages
    _LANGUAGE_SELECTION_LABEL = _("Language:")
    _MESSAGE_TYPE_CLASS = {wiking.Request.INFO: 'info',
                           wiking.Request.SUCCESS: 'success',
                           wiking.Request.WARNING: 'warning',
                           wiking.Request.ERROR: 'error'}
    _UNSAFE_CHARS = re.compile(r"[^a-zA-Z0-9_-]")

    def _safe_css_id(self, id):
        return self._UNSAFE_CHARS.sub('-', id)

    def _body_attr(self, context, **kwargs):
        onload = context.generator().js_call('new wiking.Handler')
        cls = ['page-id-' + self._safe_css_id(context.node().id().strip('/'))]
        cls.extend(['parent-page-id-' + self._safe_css_id(node.id().strip('/'))
                    for node in context.node().path()[1:-1]])
        cls.extend(('lang-%s' % context.lang(),
                    context.layout() + '-layout'))
        if context.req().maximized():
            cls.append('maximized')
        else:
            cls.append('non-maximized')
        return super(Exporter, self)._body_attr(context, onload=onload, cls=' '.join(cls), **kwargs)

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

    def _node_identification(self, context):
        """Returns a string of CSS classes identifying the current node
        and its context in node hierarchy
        """

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
        node = context.node()
        cls = ''
        if context.has_submenu:
            cls += ' with-submenu'
        if context.panels():
            cls += ' with-panels'
        return dict(cls=cls.strip() or None)

    def _part(self, name, context):
        content = getattr(self, '_' + name)(context)
        if content is not None:
            if hasattr(self, '_' + name + '_attr'):
                attr = getattr(self, '_' + name + '_attr')(context)
            else:
                attr = {}
            if name in self._PART_TITLE:
                attr['aria_label'] = self._PART_TITLE[name]
            if name in self._PART_LABELEDBY:
                attr['aria_labeledby'] = self._PART_LABELEDBY[name]
            if name in self._LANDMARKS:
                attr['role'] = self._LANDMARKS[name]
            return self._generator.div(content, id=name.replace('_', '-'), **attr)
        else:
            return None

    def _login_control(self, context):
        g = context._generator
        req = context.req()
        user = req.user()
        if user:
            username = user.name()
            uri = user.uri()
            if uri:
                username = g.a(username, href=uri)
            #g.span(_("Login") + ': ', cls='login-ctrl-label'),
            # Translators: Logout button label (verb in imperative).
            items = [
                lcg.PopupMenuItem(_("Log out"), uri=g.uri(req.uri(), command='logout')),
                lcg.PopupMenuItem(_("My User Profile"), uri=uri),
            ] + wiking.module.Application.login_control_menu_items(req)
            return g.span(
                username + lcg.PopupMenuCtrl(items, None, '.user-name').export(context),
                cls='user-name',
            )
        else:
            # Translators: Login status info.  If logged, the username is displayed instead.
            uri = req.uri()
            if uri.endswith('_registration'):
                uri = '/' # Redirect logins from the registration forms to site root
            # Translators: Login button label (verb in imperative).
            return g.a(_("Log in"), href=g.uri(uri, command='login'), cls='login-link')

    def _login_control_attr(self, context):
        user = context.req().user()
        if user:
            login, name = user.login(), user.name()
            if login != name:
                name += ' (' + login + ')'
            title = _("Logged in user:") + ' ' + name
        else:
            title = _("User not logged in")
        return dict(title=title)

    
    def _warnings(self, context):
        g = context.generator()
        req = context.req()
        user = req.user()
        appl = wiking.module.Application
        result = ''
        if user:
            if wiking.cfg.display_role_in_login_panel:
                # TODO: show only explicitly assigned roles, not special
                # roles, such as wiking.Roles.AUTHENTICATED.  Also for
                # compound roles, show only the top level role.  This
                # information is, however, currnetly not available.
                role_names = [role.name() for role in user.roles()]
                if role_names:
                    result += g.br() + '\n' + lcg.concat(role_names, separator=', ')
            expiration = user.password_expiration()
            if expiration:
                if datetime.date.today() >= expiration:
                    # Translators: Information text on login panel.
                    result += g.br() + '\n' + _("Your password expired")
                else:
                    date = lcg.LocalizableDateTime(str(expiration))
                    # Translators: Login panel info. '%(date)s' is replaced by a concrete date.
                    result += g.br() + '\n' + _("Your password expires on %(date)s", date=date)
            uri = appl.password_change_uri(req)
            if uri:
                # Translators: Link on login panel on the webpage.
                result += g.br() + '\n' + g.a(_("Change your password"), href=uri)
        else:
            uri = appl.registration_uri(req)
            if uri:
                # Translators: Login panel/dialog registration link.  Registration allows the
                # user to obtain access to the website/application by submitting his personal
                # details.
                result += g.br() + '\n' + g.a(_("New user registration"), href=uri)
        added_content = appl.login_panel_content(req)
        if added_content:
            exported = lcg.coerce(added_content).export(context)
            result += g.escape('\n') + g.div(exported, cls='login-panel-content')
        return result


    def _language_selection(self, context):
        g = context._generator
        node = context.node()
        variants = node.variants()
        if len(variants) <= 1:
            return None
        items = [lcg.PopupMenuItem(self.localizer(lang).localize(lcg.language_name(lang) or lang),
                                   uri=self._uri_node(context, node, lang=lang),
                                   #cls='lang-' + lang + ' current' if lang == context.lang() else '')
                               )
                 for lang in sorted(variants)]
        lang = context.lang()
        # The language code CS for Czech is very confusing for ordinary
        # users, while 'CZ' (which is actually a country code) seems much
        # more familiar...
        abbr = dict(cs='CZ').get(lang, lang.upper())
        return lcg.concat(
            g.a(self._LANGUAGE_SELECTION_LABEL + ' ', cls='language-selection-label'),
            g.a((g.span(lcg.language_name(lang) or abbr, cls='language-name'),
                 g.span(abbr, cls='language-abbr'),
                 lcg.PopupMenuCtrl(items, 'a').export(context)),
                cls='language-selection-ctrl',
            ),
        )
        
    def _hidden(self, *text):
        return self._generator.span(text, cls="hidden")

    def _uri_node(self, context, node, lang=None):
        uri = node.id()
        if not uri.startswith('/'):
            uri = '/' + uri
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
                g.div((g.div(self._site_title(context), id='site-title'),
                       g.div(self._parts(context, self._TOP_PARTS), id='top-controls'),
                       g.div(g.noescape('&nbsp;'), id='top-clearing')),
                      id='top-layer3'),
                id='top-layer2'),
            id='top-layer1')
        
    def _top_content(self, context):
        content = context.application.top_content(context.req())
        if content:
            return lcg.coerce(content).export(context)
        else:
            return None

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
        first = children[0]
        items = []
        for node in children:
            if not node.hidden():
                cls = ['navigation-link']
                if not all(n.hidden() for n in node.children()):
                    tree = lcg.FoldableTree(node, label=_("Hierarchical navigation menu"))
                    dropdown = g.div(tree.export(context), cls='menu-dropdown', style='display: none')
                    cls.append('with-dropdown')
                    ctrl = g.span('', cls='menu-dropdown-ctrl', role='presentation',
                                  title=_("Expand drop-down submenu of this item."))
                else:
                    dropdown = ''
                    ctrl = ''
                if node is top:
                    cls.append('current')
                items.append(g.li((g.a(node.title() + ctrl,
                                       href=self._uri_node(context, node),
                                       title=node.descr(),
                                       accesskey=(node is first and '1' or None),
                                       cls=' '.join(cls)),
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
        tree = lcg.FoldableTree(context.top_node(), label=_("Hierarchical navigation menu"),
                                tooltip=_("Expand/collapse complete menu hierarchy"))
        content = tree.export(context)
        req = context.req()
        application = context.application
        title = application.menu_panel_title(req)
        if title:
            content = lcg.concat(g.h(title, 3), content)
        bottom_content = application.menu_panel_bottom_content(req)
        if bottom_content:
            content = lcg.concat(content, bottom_content.export(context))
        return  g.div(content, cls='menu-panel')

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
                icon = context.resource('rss.png')
                if icon:
                    # Translators: ``RSS channel'' is terminology idiom, see Wikipedia
                    channel_title = panel.title() + ' (' + _("RSS channel") + ')'
                    img = g.img(context.uri(icon), align='right', alt=channel_title)
                    link = g.a(img, href=channel, title=channel_title, type='application/rss+xml',
                               cls='feed-icon-link')
                    title = link + ' ' + title
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
        return (
            g.span('', title=_("Toggle expansion of sidebar panels."), cls='expand-panels-ctrl'),
            g.div(g.div(result), id='panels-container'), # Inner div important for JS slide effects...
        )

    def _messages(self, context):
        messages = context.req().messages()
        if messages:
            g = self._generator
            return g.div([g.div((_("Warning") + ': ' if type == wiking.Request.WARNING else '') +
                                message,
                                cls=self._MESSAGE_TYPE_CLASS[type])
                          for message, type in messages],
                         id='messages')
        else:
            return ''
    
    def _main(self, context):
        g = self._generator
        if context.req().maximized():
            icon = 'minimize.png'
            label = _("Minimize")
            tooltip = _("Exit the maximized mode.")
            href = '?maximize=0'
        else:
            icon = 'maximize.png'
            label = _("Maximize")
            tooltip = _("Maximize the main content to the full size of the browser window.")
            href = '?maximize=1'
        return (g.hr(cls='hidden'),
                g.div((
                    g.a(g.img(context.uri(context.resource(icon)), alt=label),
                        href=href, title=tooltip, id='maximized-mode-control'),
                    g.h(g.a(context.node().heading().export(context), tabindex=0,
                            name='main-heading', id='main-heading'), 1),
                    self._messages(context),
                    super(Exporter, self)._content(context)), id='content'),
                g.div(g.noescape('&nbsp;'), id='clearing'))

    def _page_clearing(self, context):
        return self._generator.noescape('&nbsp;')
    
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
