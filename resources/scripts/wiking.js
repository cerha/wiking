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

wiking.gettext = new Gettext({domain:'wiking'});
wiking._ = function (msg){ return wiking.gettext.gettext(msg); };

wiking.Handler = Class.create(lcg.KeyHandler, {
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
    
    initialize: function ($super) {
	// Constructor (called on page load).
	$super();
	var menu = $('menu');
	if (menu) {
	    var main_menu = new wiking.MainMenu(menu);
	    var submenu = $('submenu');
	    if (submenu) {
		var tree_menu = lcg.widget_instance(submenu.down('.foldable-tree-widget'));
		// Bind given lcg.TreeMenu instance as a descendant of this menu in
		// keyboard traversal.
		var parent_item = main_menu.active_item();
		parent_item._lcg_submenu = tree_menu.items;
		for (var i = 0; i < tree_menu.items.length; i++) {
		    var item = tree_menu.items[i];
		    item._lcg_menu_parent = parent_item;
		}
	    }
	}
	this.init_landmarks();
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
	lcg.cookies.set('wiking_tz_offsets', summer_offset + ';' + winter_offset);
    },
    
    keymap: function () {
	return {
	    'Ctrl-Shift-m': this.cmd_menu,
	    'Ctrl-Shift-Up': this.cmd_menu,
	    'Ctrl-Shift-Down': this.cmd_notebook
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
	// Move focus to the menu (the current menu item).
	var menu = $('menu');
	var submenu = $('submenu');
	if (submenu) {
	    lcg.widget_instance(submenu.down('.foldable-tree-widget')).focus();
	} else {
	    var menu = $('menu');
	    if (menu)
		lcg.widget_instance(menu).focus();
	}
    },
    
    cmd_notebook: function (element) {
	// Move focus to the first Notebook widget on the page.
	var nb = document.body.down('div.notebook-widget');
	if (nb != null) {
	    var item = $(nb.getAttribute('aria-activedescendant'));
	    this.set_focus(item);
	}
    }
    
});

wiking.MainMenu = Class.create(lcg.NotebookMenu, {
    
    keymap: function ($super) {
	keymap = $super();
	keymap['Down'] = this.cmd_submenu;
	keymap['Escape'] = this.cmd_quit;
	return keymap;
    },
    
    cmd_submenu: function (item) {
	if (item._lcg_submenu != null)
	    this.set_focus(item._lcg_submenu[0]);
    },

    cmd_quit: function (item) {
	this.set_focus($('main-heading'));
    }
    
});




