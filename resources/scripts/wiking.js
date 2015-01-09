/* -*- coding: utf-8 -*-
 *
 * Copyright (C) 2008-2013, 2015 Brailcom, o.p.s.
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

/*jslint browser: true */
/*jslint unparam: true */
/*jslint todo: true */
/*global Class */
/*global Effect */
/*global Gettext */
/*global $ */
/*global $$ */
/*global lcg */
/*global self */

"use strict";

var wiking = new Object();

wiking.gettext = new Gettext({domain:'wiking'});
wiking._ = function (msg){ return wiking.gettext.gettext(msg); };

wiking.Handler = Class.create(lcg.KeyHandler, {
    // This class is instantiated within the page onload handler.  It is the
    // main javascript interface of a Wiking application.  It creates
    // instances of other javascript classes to handle menus etc if the
    // relevant HTML objects exist..
        
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
		var i, item;
		parent_item._lcg_submenu = tree_menu.items;
		for (i = 0; i < tree_menu.items.length; i++) {
		    item = tree_menu.items[i];
		    item._lcg_menu_parent = parent_item;
		}
	    }
	}
	// Set up global key handler.
	document.observe('keydown', this.on_key_down.bind(this));
	// Move focus to the main content if there is no anchor in the current URL.
	if (self.location.href.match("#") === null) {
	    this.set_focus($('main-heading'));
	}
	// Update the information about browser's timezone in the cookie to let
	// the server know what is the user's time zone.  The problem is that
	// this information will not be available on the very first request, so
	// the times will show in UTC on the first request and in the users
	// time zone on upcomming request, which may be confusing.  It is also
	// not 100% accurate as we don't detect the DST change dates and let
	// the server decide what the DST change dates most likely are.
	// TODO: Maybe use http://www.pageloom.com/automatic-timezone-detection-with-javascript
	var summer_date = new Date(Date.UTC(2005, 6, 30, 0, 0, 0, 0));
	var summer_offset = -summer_date.getTimezoneOffset();
	var winter_date = new Date(Date.UTC(2005, 12, 30, 0, 0, 0, 0));
	var winter_offset = -winter_date.getTimezoneOffset();
	lcg.cookies.set('wiking_tz_offsets', summer_offset + ';' + winter_offset);
	$$('a').each(function(element) {
	    // Use smooth scrolling for in-page links.
	    var href = element.readAttribute('href');
	    if (href && href[0] == '#' && href.substr(1, 8) != 'binding-') {
		var name = href.substr(1, href.length);
		var target = $(name) || $$('a[name='+name+']')[0];
		if (target) {
		    element.observe('click', function(event) {
			Effect.ScrollTo(target);
			return false;
		    });
		}
	    }
	});
    },
    
    keymap: function () {
	return {
	    'Ctrl-Shift-m': this.cmd_menu,
	    'Ctrl-Shift-Up': this.cmd_menu,
	    'Ctrl-Shift-Down': this.cmd_notebook
	};
    },

    cmd_menu: function (element) {
	// Move focus to the menu (the current menu item).
	var submenu = $('submenu');
	if (submenu) {
	    lcg.widget_instance(submenu.down('.foldable-tree-widget')).focus();
	} else {
	    var menu = $('menu');
	    if (menu) {
		lcg.widget_instance(menu).focus();
	    }
	}
    },
    
    cmd_notebook: function (element) {
	// Move focus to the first Notebook widget on the page.
	var nb = document.body.down('div.notebook-widget');
	if (nb !== null) {
	    var item = $(nb.getAttribute('aria-activedescendant'));
	    this.set_focus(item);
	}
    }
    
});

wiking.MainMenu = Class.create(lcg.NotebookMenu, {
    
    keymap: function ($super) {
	var keymap = $super();
	keymap.Down = this.cmd_submenu;
	keymap.Escape = this.cmd_quit;
	return keymap;
    },
    
    cmd_submenu: function (item) {
	if (item._lcg_submenu !== null) {
	    this.set_focus(item._lcg_submenu[0]);
	}
    },

    cmd_quit: function (item) {
	this.set_focus($('main-heading'));
    }
    
});




