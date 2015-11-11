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

/*jshint browser: true */
/*jshint es3: true */
/*jshint -W097 */ // allow direct "use strict"
/*global Class */
/*global Effect */
/*global Gettext */
/*global $ */
/*global $$ */
/*global lcg */
/*global self */

"use strict";

var wiking = {
    // Offset from the top of the browser window to use for scrolling to
    // page elements (such as sections or anchors).  Normally we want to
    // scroll to get the top of the element to the top of the window, but
    // some layouts (such as when there is a fixed positioned bar at the
    // top) may need to add an offset;
    scroll_offset: 0,

    gettext: new Gettext({domain:'wiking'}),

    handler: null,

    _: function (msg) {
	return wiking.gettext.gettext(msg);
    }
};

wiking.Handler = Class.create(lcg.KeyHandler, {
    // This class is instantiated within the page onload handler.  It is the
    // main javascript interface of a Wiking application.  It creates
    // instances of other javascript classes to handle menus etc if the
    // relevant HTML objects exist..

    initialize: function ($super) {
	// Constructor (called on page load).
	$super();
	var menu = $('main-menu');
	if (menu) {
	    this._main_menu = new wiking.MainMenu(menu);
	} else {
	    this._main_menu = undefined;
	}

	// Set up global key handler.
	document.observe('keydown', this.on_key_down.bind(this));

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

	// Move focus to the main content if there is no anchor in the current URL.
	if (!self.location.hash) {
	    this.set_focus($('main-heading'));
	}

	// Force initial scroll to respect wiking.scroll_offset.
	if (self.location.hash && wiking.scroll_offset !== 0) {
	    var anchor_ = self.location.hash.substr(1);
	    var target_ = $(anchor_) || $$('a[name=' + anchor_ + ']')[0];
	    if (target_) {
		new Effect.ScrollTo(target_, {offset: -wiking.scroll_offset});
	    }
	}

	// Use smooth scrolling for in-page links.
	$$('a[href*="#"]').each(function(element) {
	    var href = element.readAttribute('href');
	    var uri = href.substr(0, href.indexOf('#'));
	    if (uri === '' || uri === self.location.pathname) {
		var anchor = href.substr(href.indexOf('#') + 1);
		if (anchor) {
		    var target = $(anchor) || $$('a[name=' + anchor + ']')[0];
		    if (target && !target.hasClassName('notebook-page')) {
			element.observe('click', function(event) {
			    new Effect.ScrollTo(target, {offset: -wiking.scroll_offset});
			    event.stop();
			});
		    }
		}
	    }
	});

	wiking.handler = this;
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
	if (submenu && submenu.getStyle('display') !== 'none') {
	    lcg.widget_instance(submenu.down('.foldable-tree-widget')).focus();
	} else {
	    var menu = $('main-menu');
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

wiking.MainMenu = Class.create(lcg.Menu, {

    _MANAGE_TABINDEX: false,

    keymap: function () {
	// Arrow keys are duplicated with Ctrl-Shift- to get them accessible to VoiceOver
	// users as VO doesn't pass single arrow keypresses to the application.
	return {
	    'Left': this.cmd_prev,
	    'Ctrl-Shift-Left': this.cmd_prev,
	    'Right': this.cmd_next,
	    'Ctrl-Shift-Right': this.cmd_next,
	    'Enter': this.cmd_activate,
	    'Space': this.cmd_activate,
	    'Down': this.cmd_submenu,
	    'Ctrl-Shift-Down': this.cmd_submenu,
	    'Escape': this.cmd_quit
	};
    },

    init_items: function ($super, ul, parent) {
	// By setting the role to 'menubar', the menubar becomes an "item"
	// in the surrounding 'navigation' element.  This disturbs VoiceOver
	// presentation and requires the user to go through two elements
	// (first "navigation, one item" and second "menubar n items")
	// where the first is redundant and misleading.  When the role is
	// left unset, the menu items become items of the 'navigation'.
	// Their number is announced correctly and they can be navigated
	// easily.
	ul.setAttribute('role', 'presentation');
	// Initialize dropdown menu management.
	this.active_dropdown = null;
	return $super(ul, parent);
    },

    init_item: function ($super, item, prev, parent) {
	$super(item, prev, parent);
	var dropdown = item.up('li').down('.menu-dropdown');
	var submenu = (item.hasClassName('current') ? $('submenu') : undefined);
	if (dropdown) {
	    // The condition below should be actually re-evaluated on every page width
	    // change (because the submenu is hidden/shown dynamically by responsive CSS),
	    // but in practice screen reader users hardly ever resize their browser
	    // window...
	    if (submenu && submenu.getStyle('display') !== 'none') {
		item.setAttribute('aria-owns', 'submenu');
	    } else {
		// Setting aria-haspopup has a strange effect in VO, it starts
		// to read the item as "local navigation link", which seems confusing.
		//item.setAttribute('aria-haspopup', 'true');
		item.setAttribute('aria-expanded', 'false');
		item.setAttribute('aria-controls',
				  dropdown.down('.foldable-tree-widget').getAttribute('id'));
	    }
	}
	this.bind_tree_menu_parent(submenu, item);
	this.bind_tree_menu_parent(dropdown, item);
	item._wiking_submenu = submenu;
	item._wiking_dropdown = dropdown;
    },

    bind_tree_menu_parent: function (element, item) {
	if (element) {
	    var tree_menu = lcg.widget_instance(element.down('.foldable-tree-widget'));
	    tree_menu.items.each(function(tree_menu_item) {
		tree_menu_item._lcg_menu_parent = item;
	    });
	}
    },

    toggle_dropdown: function (dropdown) {
	if (this.active_dropdown && this.active_dropdown !== dropdown) {
	    this.toggle_dropdown(this.active_dropdown);
	}
	var item = dropdown.up('li').down('.navigation-link');
	if (!dropdown.visible()) {
	    this.active_dropdown = dropdown;
	    // Reset the style to the initial state (when clicking too fast, the effects
	    // may overlap and leave a messy final style).
	    dropdown.setAttribute('style', 'display: none;');
	    item.addClassName('expanded');
	    item.setAttribute('aria-expanded', 'true');
	    // This solves two problems.  A. the dropdown looks odd when not wider than the item.
	    // B. the dropdown width flickers when hovering over its widest item.
	    dropdown.setStyle({width: Math.max(item.getWidth(), dropdown.getWidth()) + 'px'});
	    new Effect.SlideDown(dropdown, {duration: 0.2});
	    this.on_touchstart = function (event) { this.touch_moved = false; }.bind(this);
	    this.on_touchmove = function (event) { this.touch_moved = true; }.bind(this);
	    this.on_touchend = function (event) {
		if (!this.touch_moved) {
		    this.on_click(event);
		}
	    }.bind(this);
	    this.on_click = function (event) {
		if (dropdown && event.findElement('.menu-dropdown') !== dropdown) {
		    this.toggle_dropdown(dropdown);
		    if (!event.stopped) {
			event.stop();
		    }
		}
	    }.bind(this);
	    $(document).observe('click', this.on_click);
	    $(document).observe('touchstart', this.on_touchstart);
	    $(document).observe('touchmove', this.on_touchmove);
	    $(document).observe('touchend', this.on_touchend);
	} else {
	    $(document).stopObserving('click', this.on_click);
	    $(document).stopObserving('touchstart', this.on_touchstart);
	    $(document).stopObserving('touchmove', this.on_touchmove);
	    $(document).stopObserving('touchend', this.on_touchend);
	    this.active_dropdown = null;
	    new Effect.SlideUp(dropdown, {
		duration: 0.2,
		afterFinish: function () {
		    item.removeClassName('expanded');
		    item.setAttribute('aria-expanded', 'false');
		}
	    });
	}
    },

    cmd_submenu: function (item) {
	var submenu = item._wiking_submenu;
	var dropdown = item._wiking_dropdown;
	var menu_element;
	if (submenu && submenu.getStyle('display') !== 'none') {
	    menu_element = submenu;
	} else if (dropdown && dropdown.visible()) {
	    menu_element = dropdown;
	} else if (dropdown) {
	    this.toggle_dropdown(dropdown);
	}
	if (menu_element) {
	    var tree_menu = lcg.widget_instance(menu_element.down('.foldable-tree-widget'));
	    this.set_focus(tree_menu.items[0]);
	}
    },

    cmd_activate: function (item) {
	var dropdown = item._wiking_dropdown;
	var submenu = item._wiking_submenu;
	if (dropdown && !dropdown.visible() &&
	    (!submenu || submenu.getStyle('display') === 'none')) {
	    this.toggle_dropdown(dropdown);
	} else {
	    self.location = item.getAttribute('href');
	}
    },

    cmd_quit: function (item) {
	this.set_focus($('main-heading'));
    }

});
