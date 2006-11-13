# -*- coding: iso-8859-2 -*-
# Copyright (C) 2005, 2006 Tomáš Cerha.
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

import time, re, os

DBG = pytis.util.DEBUG
EVT = pytis.util.EVENT
OPR = pytis.util.OPERATIONAL
log = pytis.util.StreamLogger(sys.stderr).log

_ = lcg.TranslatableTextFactory('wiking')

from lcg import _html
concat = lcg.concat

def timeit(func, *args, **kwargs):
    # measure process time
    t1, t2 = time.clock(), time.time()
    result = func(*args, **kwargs)
    return result,  time.clock() - t1, time.time() - t2

def get_module(name):
    try:
        from mod_python.apache import import_module
        modules = import_module('wiking.modules', log=True)
    except ImportError:
        import wiking.modules as modules
    return getattr(modules, name)

_CAMEL_CASE_WORD = re.compile(r'[A-Z][a-z\d]+')
def split_camel_case(string):
    """Return a lowercase string using 'separator' to concatenate words."""
    return _CAMEL_CASE_WORD.findall(string)

def camel_case_to_lower(string, separator='-'):
    """Return a lowercase string using 'separator' to concatenate words."""
    return separator.join([w.lower() for w in split_camel_case(string)])

def rss(title, url, items, descr=None):
    result = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>%s</title>
    <link>%s</link>''' % (title, url) + (descr and '''
    <description>%s</description>''' % descr or '') + '''
    %s
  </channel>
</rss>''' % '\n    '.join(['''<item>
       <title>%s</title>
       <link>%s</link>''' % (title, url) + (descr and '''
       <description>%s</description>''' % descr or '') + '''
    </item>''' for title, url, descr in items])
    return result

def send_mail (sender, addr, subject, text, html, smtp_server='localhost'):
    """Create a mime e-mail message with text and HTML version."""
    import MimeWriter
    import mimetools
    import cStringIO
    import time
    
    out = cStringIO.StringIO() # output buffer for our message 
    htmlin = cStringIO.StringIO(html)
    txtin = cStringIO.StringIO(text)

    writer = MimeWriter.MimeWriter(out)
    #
    # set up some basic headers... we put subject here
    # because smtplib.sendmail expects it to be in the
    # message body
    #
    writer.addheader("From", sender)
    writer.addheader("To", addr)
    writer.addheader("Subject", subject)
    writer.addheader("Date", time.strftime("%a, %d %b %Y %H:%M:%S",
                                           time.localtime(time.time())))
    writer.addheader("MIME-Version", "1.0")
    #
    # start the multipart section of the message
    # multipart/alternative seems to work better
    # on some MUAs than multipart/mixed
    #
    writer.startmultipartbody("alternative")
    writer.flushheaders()
    #
    # the plain text section
    #
    subpart = writer.nextpart()
    subpart.addheader("Content-Transfer-Encoding", "quoted-printable")
    pout = subpart.startbody("text/plain", [("charset", 'utf-8')])
    mimetools.encode(txtin, pout, 'quoted-printable')
    txtin.close()
    #
    # start the html subpart of the message
    #
    subpart = writer.nextpart()
    subpart.addheader("Content-Transfer-Encoding", "quoted-printable")
    #
    # returns us a file-ish object we can write to
    #
    pout = subpart.startbody("text/html", [("charset", 'utf-8')])
    mimetools.encode(htmlin, pout, 'quoted-printable')
    htmlin.close()
    #
    # Now that we're done, close our writer and
    # return the message body
    #
    writer.lastpart()
    import smtplib
    server = smtplib.SMTP(smtp_server)
    try:
        server.sendmail(sender, addr, out.getvalue())
    finally:
        out.close()
        server.quit()




# ============================================================================

class HttpError(Exception):
    ERROR_CODE = None
    def name(self):
        name = " ".join(split_camel_case(self.__class__.__name__))
        return _("Error %d: %s", self.ERROR_CODE, name)
    def msg(self, req):
        pass


class NotFound(HttpError):
    ERROR_CODE = 404
    
    def msg(self, req):
        msg = (_("The item '%s' does not exist on this server or cannot be "
                 "served.", req.uri),
               _("If you are sure the web address is correct, "
                 "but are encountering this error, please send "
                 "an e-mail to the webmaster."),
               _("Thank you"))
        return lcg.concat([lcg.concat("<p>", p, "</p>\n\n") for p in msg])

    
class NotAcceptable(HttpError):
    ERROR_CODE = 406
    
    def __init__(self, available):
        self._available = tuple(available)

    def available(self):
        return self._available
        
    def msg(self, req):
        from lcg import _html
        prefered = [lcg.language_name(l) for l in req.prefered_languages()]
        msg = (_("The resource '%s' is not available in either of "
                 "the requested languages.", req.uri),
               lcg.concat(_("Your browser is configured to accept only the "
                            "following languages:"), ' ',
                          lcg.concat(prefered, separator=', ')))
        if self._available:
            available = [_html.link(lcg.language_name(l),
                                    "%s?lang=%s;keep_language=1" % (req.uri, l))
                         for l in self._available]
            msg += (lcg.concat(_("The available variants are:"), ' ',
                               lcg.concat(available, separator=', ')),
                    _("If you want to accept other languages permanently, "
                      "setup the language preferences in your browser "
                      "or contact your system administrator."))
        return lcg.concat([lcg.concat("<p>", p, "</p>\n\n") for p in msg])
    
# ============================================================================

class MenuItem(object):
    def __init__(self, id, title):
        self._id = id
        self._title = title
    def id(self):
        return self._id
    def title(self):
        return self._title


class Panel(object):
    def __init__(self, id, title, content):
        self._id = id
        self._title = title
        self._content = content
    def id(self):
        return self._id
    def title(self):
        return self._title
    def content(self):
        return self._content


class Document(object):
    """Independent document description."""
    
    def __init__(self, title, content, descr=None, lang=None, variants=(),
                 edit_label=None):
        self._title = title
        if isinstance(content, (list, tuple)):
            content = lcg.SectionContainer([c for c in content if c],
                                           toc_depth=0)
        self._content = content
        self._descr = descr
        self._lang = lang
        self._variants = variants
        self._edit_label = edit_label

    def lang(self):
        return self._lang
    
    def mknode(self, id, config, menu, panels, stylesheets):
        return WikingNode(id, config, title=self._title, content=self._content,
                          lang=self._lang, variants=self._variants or (),
                          descr=self._descr, menu=menu, panels=panels,
                          stylesheets=stylesheets, edit_label=self._edit_label)

    
# ============================================================================
# Classes derived from LCG components
# ============================================================================

class WikingNode(lcg.ContentNode):
    
    def __init__(self, id, config, menu=(), panels=(), stylesheets=(),
                 edit_label=None, lang=None, variants=(), **kwargs):
        self._config = config
        self._menu = menu
        self._panels = panels
        self._stylesheets = stylesheets
        for panel in panels:
            panel.content().set_parent(self)
        self._edit_label = edit_label
        super(WikingNode, self).__init__(None, id, language=lang,
                                         language_variants=variants, **kwargs)
        
    def config(self):
        return self._config
    
    def menu(self):
        return self._menu
    
    def panels(self):
        return self._panels
               
    def stylesheets(self):
        return self._stylesheets
               
    def edit_label(self):
        return self._edit_label

    
class ActionMenu(lcg.Content):
    
    def __init__(self, uri, actions, data=None, row=None):
        super(ActionMenu, self).__init__()
        assert isinstance(uri, str), uri
        assert isinstance(actions, (tuple, list)), actions
        assert data is None or isinstance(data, pytis.data.Data), data
        assert row is None or isinstance(row, pytis.data.Row), row
        self._uri = uri
        self._data = data
        self._row = row
        self._actions = actions

    def _export_item(self, action):
        if action.context() is not None:
            key = dict([(c.id(), self._row[c.id()].export())
                        for c in self._data.key()])
        else:
            key = {}
        target = _html.uri(self._uri, action=action.name(), **key)
        return _html.link(action.title(), target)
        
    def export(self, exporter):
        # Only Wiking's Actions are considered, not `pytis.presentation.Action'.
        items = concat([self._export_item(a) for a in self._actions
                        if isinstance(a, Action)],
                       separator=_html.span(" |\n", cls="hidden"))
        return _html.p(concat(_("Actions:"), items, separator="\n"),
                       cls="actions")
          

class PanelItem(lcg.Content):
    def __init__(self, data, row, columns, link_provider, base_uri):
        self._data = data
        self._row = row
        self._columns = columns
        self._link_provider = link_provider
        self._base_uri = base_uri

    def _export_field(self, col):
        value = self._row[col.id()].export()
        if self._link_provider:
            uri = self._link_provider(self._row, col, self._base_uri)
            if uri:
                value = _html.link(value, uri)
        return _html.span(value, cls="panel-field-"+col.id())
        
    def export(self, exporter):
        items = [self._export_field(col) for col in self._columns]
        return _html.div(items, cls="item")
        
    
class Message(lcg.TextContent):
    _CLASS = "message"
    
    def export(self, exporter):
        return _html.p(_html.escape(self._text), cls=self._CLASS) + "\n"

  
class ErrorMessage(Message):
    _CLASS = "error"
    
    
# ============================================================================
# Classes derived from Pytis components
# ============================================================================

class Action(pytis.presentation.Action):
    def __init__(self, title, name, handler=None, **kwargs):
        # name determines the Wiking's method (and the 'action' argument.
        self._name = name
        if not handler:
            handler = lambda r: None
        super(Action, self).__init__(title, handler, **kwargs)
        
    def name(self):
        return self._name
    

class Field(pp.FieldSpec):
    
    def __init__(self, id, label='', virtual=False, dbcolumn=None, type=None,
                 codebook=None, **kwargs):
        if virtual and type is None:
            type = pd.String()
        self._virtal = virtual
        self._dbcolumn = dbcolumn or id
        self._dbcolumn_kwargs = {}
        for arg in ('not_null', 'value_column', 'validity_column',
                    'validity_condition'):
            if kwargs.has_key(arg):
                self._dbcolumn_kwargs[arg] = kwargs[arg]
                del kwargs[arg]
        super(Field, self).__init__(id, label, type_=type, codebook=codebook,
                                    **kwargs)

    def virtual(self):
        return self._virtal
    
    def dbcolumn(self):
        return self._dbcolumn
    
    def dbcolumn_kwargs(self):
        return self._dbcolumn_kwargs
    

class Data(pd.DBDataDefault):

    def _row_data(self, **kwargs):
        return [(k, pd.Value(self.find_column(k).type(), v))
                for k, v in kwargs.items()]
    
    def get_rows(self, skip=None, limit=None, sorting=(), **kwargs):
        self.select(pd.AND(*[pd.EQ(k,v) for k,v in self._row_data(**kwargs)]),
                    sort=sorting)
        rows = []
        if skip:
            self.skip(skip)
        while True:
            row = self.fetchone()
            if row is None:
                break
            rows.append(row)
            if limit is not None and len(rows) > limit:
                break
        self.close()
        return rows

    def get_row(self, **kwargs):
        rows = self.get_rows(**kwargs)
        if len(rows) == 0:
            return None
        else:
            return rows[0]

    def make_row(self, **kwargs):
        return pd.Row(self._row_data(**kwargs))

    
class WikingResolver(pytis.util.Resolver):
    """A custom resolver of Wiking modules."""
    
    def __init__(self, assistant=None):
        assert assistant is None or isinstance(assistant, pytis.util.Resolver)
        self._assistant = assistant
    
    def get(self, name, spec):
        try:
            cls = get_module(name)
        except AttributeError, e:
            if self._assistant:
                return self._assistant.get(name, spec)
            else:
                raise pytis.util.ResolverModuleError(name, str(e))
        try:
            method = getattr(cls, spec)
        except AttributeError:
            raise pytis.util.ResolverSpecError(name, spec)
        return method()

# ============================================================================

class DirectData(object):
    """Direct data access with psycopg.  Currently unused..."""
    def __init__(self, opt):
        import psycopg
        self._connection = psycopg.connect("dbname=%s" % opt['dbname'])

    def raw_select(self, table, columns, **kwargs):
        q = 'SELECT %s FROM %s WHERE %s' % \
            (', '.join(['"%s"' % col for col in columns]), table,
             ' AND '.join(['"%s" = %%s' % col for col in kwargs.keys()]))
        cr = self._connection.cursor()
        cr.execute(q, kwargs.values())
        return cr.fetchall()

    def select(self, table, columns, **kwargs):
        return [dict(zip(columns, row))
                for row in self.raw_select(table, columns, **kwargs)]
