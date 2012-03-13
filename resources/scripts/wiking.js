/* -*- coding: utf-8 -*-
 *
 * Copyright (C) 2008-2012 Brailcom, o.p.s.
 * Author: Tomas Cerha
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	 See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

var wiking = new Object();

wiking.Base = Class.create({

    initialize: function (translations) {
	this.translations = translations;
	this.keymap = this.init_keymap();
    },
      
    init_keymap: function () {
	return {};
    },

    gettext: function(text) {
	// Translations are passed to JavaScript from python when init() is called.
	translation = this.translations[text];
	if (typeof(translation) != 'undefined')
	    return translation;
	else
	    return text;
    },
    
    event_key: function (event) {
	var code = document.all ? event.keyCode : event.which;
	var map = {
	    8:  'Backspace',
	    10: 'Enter',
	    13: 'Enter',
	    27: 'Escape',
	    32: 'Space',
	    33: 'PageUp',
	    34: 'PageDown',
	    35: 'End',
	    36: 'Home',
	    37: 'Left',
	    39: 'Right',
	    38: 'Up',
	    40: 'Down'
	};
	var key = null;
	if (code >= 65 && code <= 90) key = String.fromCharCode(code).toLowerCase();
	else key = map[code];
	if (key != null) {
	    var modifiers = '';
	    if (document.all || document.getElementById) {
		if (event.ctrlKey) modifiers += 'Ctrl-';
		if (event.altKey) modifiers += 'Alt-';
		if (event.shiftKey) modifiers += 'Shift-';
	    } else if (document.layers) {
		if (event.modifiers & Event.CONTROL_MASK) modifiers += 'Ctrl-';
		if (event.modifiers & Event.ALT_MASK) modifiers += 'Alt-';
		if (event.modifiers & Event.SHIFT_MASK) modifiers += 'Shift-';
	    }
	    key = modifiers+key;
	}
	return key;
    },

    on_key_down: function (event) {
	var key_name = this.event_key(event);
	var command = this.keymap[key_name];
	if (command) {
	    var element = event.element();
	    command.bind(this)(element);
	    event.stop();
	};
    },

    set_focus: function (element) {
	if (element != null) 
	    setTimeout(function () { try { element.focus(); } catch (e) {} }, 0);
    }
    
});


wiking.Handler = Class.create(wiking.Base, {
    // This class is instantiated within the page onload handler.  It is the
    // main javascript interface of a Wiking application.  It creates
    // instances of other javascript classes to handle menus etc if the
    // relevant HTML objects exist..
    
    // Landmarks by HTML element id.
    LANDMARKS: {
	'top':         'banner',
	'menu-map':    'navigation',
	'submenu-map': 'navigation',
	'main':        'main',
	'bottom':      'contentinfo'
    },
    
    initialize: function ($super, translations) {
	// Constructor (called on page load).
	$super(translations);
	this.init_landmarks();
	var menu = $('menu');
	if (menu)
	    this.menu = new wiking.MainMenu(translations, menu);
	else
	    this.menu = null;
	var submenu = $('submenu');
	if (submenu) {
	    this.submenu = new wiking.TreeMenu(translations, submenu);
	    if (menu)
		this.menu.bind_submenu(this.submenu);
	} else {
	    this.submenu = null;
	}
	// Set up global key handler.
	document.observe('keydown', this.on_key_down.bind(this));
	// Move focus to the main content if there is no anchor in the current URL.
	if (self.location.href.match("#") == null)
	    this.set_focus($('main-heading'));
	// Update the information about browser's timezone in the cookie to let
	// the server know what is the user's time zone.  The problem is that
	// this information will not be available on the very first request, so
	// the times will show in UTC on the first request and in the users
	// time zone on upcomming request, which may be confusing.  It is also
	// not 100% accurate as we don't detect the DST change dates and let
	// the server decide what the DST change dates most likely are.
	// TODO: Maybe use http://www.pageloom.com/automatic-timezone-detection-with-javascript
	var summer_date = new Date(Date.UTC(2005, 6, 30, 0, 0, 0, 0));
	var summer_offset = -summer_date.getTimezoneOffset()
	var winter_date = new Date(Date.UTC(2005, 12, 30, 0, 0, 0, 0));
	var winter_offset = -winter_date.getTimezoneOffset();
	wiking.cookies.set('wiking_tz_offsets', summer_offset + ';' + winter_offset);
    },
    
    init_keymap: function () {
	return {
	    'Ctrl-Shift-m': this.cmd_menu,
	    'Ctrl-Shift-Up': this.cmd_menu
	};
    },

    init_landmarks: function () {
	//Initialize ARIA landmarks;
	for (var id in this.LANDMARKS) {
	    var element = $(id);
	    if (element != null)
		element.setAttribute('role', this.LANDMARKS[id]);
	}
    },
    
    cmd_menu: function (element) {
	if (this.submenu != null)
	    this.submenu.focus();
	else if (this.menu != null)
	    this.menu.focus();
    }
    
});

wiking.Menu = Class.create(wiking.Base, {
    // Initialize a hierarchical menu -- assign ARIA roles to HTML tags
    // and bind keyboard event handling to support keyboard menu traversal.
    
    initialize: function ($super, translations, node) {
	$super(translations);
	this.node = node;
	node.setAttribute('role', 'application');
	// Go through the menu and assign aria roles and key bindings.
	var ul = node.down('ul');
	this.items = this.init_items(ul, null);
	// Set the active item.
	var active = this.initially_active_item();
	if (active != null)
	    this.activate_item(active);
    },

    init_items: function (ul, parent) {
	var items = [];
	var base_id;
	if (parent == null)
	    base_id = this.node.getAttribute('id')+'-item';
	else
	    base_id = parent.getAttribute('id');
	for (var i = 0; i < ul.childNodes.length; i++) {
	    var child = $(ul.childNodes[i]);
	    if (child.nodeName =='LI') {
		var prev = (items.length == 0 ? null : items[items.length-1]);
		var id = base_id + '.' + (items.length+1);
		this.init_item(child, id, prev, parent);
		items[items.length] = child;
	    }
	}
	return items;
    },

    init_item: function (li, id, prev, parent) {
	var link = li.down('a');
	link.setAttribute('tabindex', '-1');
	li.setAttribute('role', 'presentation');
	li.setAttribute('id', id);
	li.setAttribute('tabindex', '-1');
	li._wiking_menu_prev = prev;
	li._wiking_menu_next = null;
	li._wiking_menu_parent = parent;
	li._wiking_submenu = null;
	li._wiking_menu = this;
	if (prev != null)
	    prev._wiking_menu_next = li;
	li.observe('keydown', this.on_key_down.bind(this));
    },
    
    initially_active_item: function () {
	if (this.items.length != 0) {
	    var current = this.node.down('a.current');
	    if (current)
		return current.up('li');
	    else
		return this.items[0];
	} else {
	    return null;
	}
    },
    
    active_item: function () {
	return $(this.node.getAttribute('aria-activedescendant'));
    },

    activate_item: function (item) {
	var previously_active_item = this.active_item()
	if (previously_active_item != null)
	    previously_active_item.setAttribute('tabindex', '-1');
	this.node.setAttribute('aria-activedescendant', item.getAttribute('id'));
	item.setAttribute('tabindex', '0');
    },

    focus: function () {
	var item = this.active_item();
	this.expand_item(item, true);
	this.set_focus(item);
    },
    
    expand_item: function (item, recourse) {
	return false;
    }
    
});

wiking.NotebookBase = Class.create(wiking.Menu, {

    init_items: function ($super, ul, parent) {
	ul.setAttribute('role', 'tablist');
	return $super(ul, parent);
    },

    init_item: function ($super, li, id, prev, parent) {
	$super(li, id, prev, parent);
	li.setAttribute('role', 'tab');
	li.down('a').onclick = (function() { this.cmd_activate(li); return false; }).bind(this);
    },
    
    init_keymap: function () {
	return {
	    'Left':	    this.cmd_prev,
	    'Right':	    this.cmd_next,
	    'Enter':	    this.cmd_activate,
	    'Space':	    this.cmd_activate
	};
    },

    cmd_prev: function (item) {
	this.set_focus(item._wiking_menu_prev);
    },

    cmd_next: function (item) {
	this.set_focus(item._wiking_menu_next);
    },
    
    cmd_activate: function (item) {
    }

});

wiking.Notebook = Class.create(wiking.NotebookBase, {
    // Generic notebook widget
    // There may be multiple instances on one page.
    // This is a Javascript counterpart of the `wiking.Notebook' python class.
    COOKIE: 'wiking_last_notebook_tab',

    initialize: function ($super, node_id) {
	$super({}, $(node_id));
    },

    initially_active_item: function () {
	// The active item set in the python code (marked as 'current' in HTML)
	// has the highest precedence.
	var current = this.node.down('.notebook-switcher li a.current');
	if (current)
	    return current.up('li');
	else
	    return (this.current_location_active_item() || // the tab may be referenced by anchor.
		    this.last_saved_active_item() || // the most recently active tab.
		    this.items[0]); // finally the first item is used with the lowest precedence.
    },


    init_item: function ($super, li, id, prev, parent) {
	$super(li, id, prev, parent);
	var link = li.down('a');
	var href = link.getAttribute('href'); // The href always starts with '#'.
	var tab = $('section-'+href.substr(1));
	li._wiking_notebook_tab = tab;
	tab._wiking_notebook_item = li;
	tab.down('h1,h2,h3,h4,h5,h6').hide();
	tab.hide();
    },

    current_location_active_item: function() {
	// Get the active item if the anchor is part of the current location.
	var match = self.location.href.match('#');
	if (match != null) {
	    var parts = self.location.href.split('#', 2);
	    var tab = this.node.down('#section-'+parts[1]);
	    if (tab && tab._wiking_notebook_item) {
		return tab._wiking_notebook_item;
	    }
	}
    },

    last_saved_active_item: function() {
	// Get the active item saved most recently in a browser cookie.
	//
	// We remember the last tab only for one notebook (the one which was
	// last switched) to avoid polution of cookies with too many values).
	//
	// The HTML class should identify a particular Notebook widget and
	// should not change across requests, while its id is unique on a page,
	// but may not identify a particulat widget and may change across
	// requests.  So we use the class as a part of cookie value.
	//
	var cls = this.node.getAttribute('class');
	if (cls) {
	    var cookie = wiking.cookies.get(this.COOKIE);
	    if (cookie) {
		var parts = cookie.split(':', 2);
		if (parts[0] == cls) {
		    var tab = this.node.down('#'+parts[1]);
		    if (tab && tab._wiking_notebook_item) {
			return tab._wiking_notebook_item;
		    }
		}
	    }
	}
	return null;
    },

    activate_item: function ($super, item) {
	var previously_active_item = this.active_item()
	$super(item);
	if (previously_active_item != item) {
	    if (previously_active_item) {
		previously_active_item.down('a').removeClassName('current');
		previously_active_item._wiking_notebook_tab.hide();
	    }
	    item.down('a').addClassName('current');
	    item._wiking_notebook_tab.show();
	    var cls = this.node.getAttribute('class');
	    if (cls) {
		var cookie = cls+':'+item._wiking_notebook_tab.getAttribute('id');
		wiking.cookies.set(this.COOKIE, cookie);
	    }
	}
    },

    cmd_activate: function (item) {
	this.activate_item(item);
	this.set_focus(item._wiking_notebook_tab);
    }

});


wiking.MainMenu = Class.create(wiking.NotebookBase, {
    // Specific handling of top level folders menu.
    
    init_keymap: function ($super) {
	keymap = $super();
	keymap['Down'] = this.cmd_submenu;
	keymap['Escape'] = this.cmd_quit;
	return keymap;
    },
    
    bind_submenu: function(menu) {
	// Bind given wiking.TreeMenu instance as a descendant of this menu in
	// keyboard traversal.
	var item = this.active_item();
	item._wiking_submenu = menu.items;
	menu.bind_parent(item);
    },
    
    cmd_activate: function (item) {
	self.location = item.down('a').getAttribute('href');
    },

    cmd_submenu: function (item) {
	if (item._wiking_submenu != null)
	    this.set_focus(item._wiking_submenu[0]);
    },

    cmd_quit: function (item) {
	this.set_focus($('main-heading'));
    }
    
});


wiking.TreeMenu = Class.create(wiking.Menu, {
    // Specific handling of foldable tree menu.
    
    initialize: function ($super, translations, node) {
	$super(translations, node);
	node.down('.menu-panel').setAttribute('role', 'tree');
	if (this.foldable) {
	    var b = new Element('button',
				{id: 'toggle-menu-expansion-button',
				 title: this.gettext("Expand/collapse complete menu hierarchy")});
	    node.down('ul').insert({after: b});
	    b.observe('click', this.on_toggle_expansion.bind(this));
	}
    },

    init_keymap: function () {
	return {
	    'Up':	    this.cmd_up,
	    'Down':         this.cmd_down,
	    'Shift-Up':	    this.cmd_prev,
	    'Shift-Down':   this.cmd_next,
	    'Shift-Right':  this.cmd_expand,
	    'Shift-Left':   this.cmd_collapse,
	    'Right':        this.cmd_expand,
	    'Left':         this.cmd_collapse,
	    'Escape':	    this.cmd_quit,
	    'Enter':	    this.cmd_activate,
	    'Space':	    this.cmd_activate
	};
    },
    
    init_items: function ($super, ul, parent) {
	ul.setAttribute('role', 'group');
	return $super(ul, parent);
    },
    
    init_item: function ($super, li, id, prev, parent) {
	$super(li, id, prev, parent);
	li.down('a').setAttribute('role', 'presentation');
	li.observe('click', this.on_menu_click.bind(this));
	li.setAttribute('role', 'treeitem');
	var span = li.down('span');
	if (span != null)
	    span.setAttribute('role', 'presentation');
	// Append hierarchical submenu if found.
	var submenu = li.down('ul');
	if (submenu != null) {
	    if (li.hasClassName('foldable')) {
		var hidden = (li.hasClassName('folded') ? 'true' : 'false');
		submenu.setAttribute('aria-hidden', hidden);
		var expanded = (li.hasClassName('folded') ? 'false' : 'true' );
		li.setAttribute('aria-expanded', expanded);
		this.foldable = true;
	    }
	    li._wiking_submenu = this.init_items(submenu, li);
	}
    },
    
    bind_parent: function(parent) {
	// Bind given wiking.FolderMenu item as a parent of this menu in
	// keyboard traversal.
	for (var i = 0; i < this.items.length; i++) {
	    var item = this.items[i];
	    item._wiking_menu_parent = parent;
	}
    },
    
    toggle_item_expansion: function (item) {
	if (item != null) {
	    if (this.expanded)
		this.collapse_item(item);
	    else
		this.expand_item(item);
	    if (item._wiking_submenu != null)
		this.toggle_item_expansion(item._wiking_submenu[0]);
	    this.toggle_item_expansion(item._wiking_menu_next);
	}
    },
    
    expand_item: function (item, recourse) {
	var expanded = false;
	if (item.hasClassName('folded')) {
	    item.removeClassName('folded');
	    item.down('ul').setAttribute('aria-hidden', 'false');
	    item.setAttribute('aria-expanded', 'true');
	    expanded = true;
	}
	if (recourse && item._wiking_menu_parent != null)
	    this.expand_item(item._wiking_menu_parent, true);
	return expanded;
    },
    
    collapse_item: function (item) {
	if (item.hasClassName('foldable') && !item.hasClassName('folded')) {
	    item.addClassName('folded');
	    item.down('ul').setAttribute('aria-hidden', 'true');
	    item.setAttribute('aria-expanded', 'false');
	    return true;
	}
	return false;
    },
    
    next_item: function (item) {
	// Recursively find the next item in sequence by traversing the hierarchy.
	var next;
	if (item._wiking_menu_next != null)
	    next = item._wiking_menu_next;
	else if (item._wiking_menu_parent != null
		 && item._wiking_menu_parent._wiking_menu == this)
	    next = this.next_item(item._wiking_menu_parent);
	return next;
    },
    
    cmd_up: function (item) {
	var target = null;
	if (item._wiking_menu_prev != null) {
	    target = item._wiking_menu_prev;
	    if (target._wiking_submenu != null && !target.hasClassName('folded'))
		target = target._wiking_submenu[target._wiking_submenu.length-1];
	} else {
	    target = item._wiking_menu_parent;
	}
	this.set_focus(target);
    },

    cmd_down: function (item) {
	var target = null;
	if (item._wiking_submenu != null && !item.hasClassName('folded'))
	    target = item._wiking_submenu[0];
	else
	    target = this.next_item(item);
	this.set_focus(target);
    },

    cmd_prev: function (item) {
	this.set_focus(item._wiking_menu_prev);
    },

    cmd_next: function (item) {
	this.set_focus(item._wiking_menu_next);
    },

    cmd_expand: function (item) {
	if (!this.expand_item(item) && item._wiking_submenu != null)
	    this.set_focus(item._wiking_submenu[0]);
    },

    cmd_collapse: function (item) {
	if (!this.collapse_item(item))
	    this.set_focus(item._wiking_menu_parent);
    },

    cmd_activate: function (item) {
	self.location = item.down('a').getAttribute('href');
    },

    cmd_quit: function (item) {
	this.set_focus($('main-heading'));
    },
    
    on_toggle_expansion: function (event) {
	this.toggle_item_expansion(this.items[0]);
	this.expanded = !this.expanded;
	var b = $('toggle-menu-expansion-button');
	if (this.expanded)
	    b.addClassName('expanded');
	else
	    b.removeClassName('expanded');
    },
    
    on_menu_click: function (event) {
	var element = event.element();
	if (element.nodeName == 'A' || element.nodeName == 'LI') {
	    // The inner SPAN has a left margin making space for folding controls.
	    // Then, if the user clicks inside the A or LI element, but not inside
	    // SPAN, folding controls were clicked.  The strange hack with the inner
	    // SPAN is needed to make folding work across browsers (particulartly
	    // MSIE).
	    var span = element.down('span');
	    var item = span.parentNode.parentNode;
	    if (event.pointerX() < span.cumulativeOffset().left) {
		if (item.hasClassName('folded'))
		    this.expand_item(item);
		else
		    this.collapse_item(item);
		event.stop();
	    }
	}
    }
    
});

wiking.Cookies = Class.create({
    // This class is taken from 
    // http://codeinthehole.com/writing/javascript-cookie-objects-using-prototype-and-json/
    initialize: function(path, domain) {
        this.path = path || '/';
        this.domain = domain || null;
    },
    // Sets a cookie
    set: function(key, value, days) {
        if (typeof key != 'string') throw "Invalid key";
        if (typeof value != 'string' && typeof value != 'number') throw "Invalid value";
        if (days && typeof days != 'number') throw "Invalid expiration time";
        var setValue = key+'='+escape(new String(value));
        if (days) {
            var date = new Date();
            date.setTime(date.getTime()+(days*24*60*60*1000));
            var setExpiration = "; expires="+date.toGMTString();
        } else var setExpiration = "";
        var setPath = '; path='+escape(this.path);
        var setDomain = (this.domain) ? '; domain='+escape(this.domain) : '';
        var cookieString = setValue+setExpiration+setPath+setDomain;
        document.cookie = cookieString;
    },
    // Returns a cookie value or false
    get: function(key) {
        var keyEquals = key+"=";
        var value = false;
        document.cookie.split(';').invoke('strip').each(function(s){
            if (s.startsWith(keyEquals)) {
                value = unescape(s.substring(keyEquals.length, s.length));
                throw $break;
            }
        });
        return value;
    },
    // Clears a cookie
    clear: function(key) {
        this.set(key,'',-1);
    },
    // Clears all cookies
    clearAll: function() {
        document.cookie.split(';').collect(function(s){
            return s.split('=').first().strip();
        }).each(function(key){
            this.clear(key);
        }.bind(this));
    }
});

wiking.cookies = new wiking.Cookies();
