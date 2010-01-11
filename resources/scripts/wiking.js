/* -*- coding: utf-8 -*-
 *
 * Copyright (C) 2008, 2009, 2010 Brailcom, o.p.s.
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

var WikingHandler = Class.create({
      initialize: function () {
	 // WikingHandler constructor (called when the script is loaded).
	 // Definition of available commands.
	 this.CMD_PARENT = 'parent'; // Go up in the hierarchy.
	 this.CMD_CHILD	= 'child';  // Go down in the hierarchy.
	 this.CMD_PREV = 'prev'; // Go to the next item at the same level.
	 this.CMD_NEXT = 'next'; // Go to the previous item at the same level.
	 this.CMD_MENU = 'menu';
	 this.CMD_ACTIVATE = 'activate';
	 this.CMD_QUIT = 'quit';
	 // Menu navigation keyboard shortcuts mapping to available command identifiers.
	 this.KEYMAP = {
	    'Up':	    this.CMD_PREV,
	    'Down':         this.CMD_NEXT,
	    'Left':         this.CMD_PARENT,
	    'Right':        this.CMD_CHILD,
	    'Ctrl-Shift-m': this.CMD_MENU,
	    'Escape':	    this.CMD_QUIT,
	    'Enter':	    this.CMD_ACTIVATE,
	    'Space':	    this.CMD_ACTIVATE
	 };
	 // Landmark by HTML element id.
	 this.LANDMARKS = {
	    'top':     'banner',
	    'menu':    'navigation',
	    'submenu': 'navigation',
	    'main':    'main',
	    'bottom':  'contentinfo'
	 };
	 // Other (private) attributes. 
	 this.menu = [];
	 this.active_menu_item = null;
      },

      init: function () {
	 // Initialize the loaded page (called from document body onload event).
	 // First initialize the menus -- assign ARIA roles to HTML tags and bind
	 // keyboard event handling to support hierarchical keyboard traversal.
	 this.append_menu(this.menu, $('menu'), null);
	 if (this.menu.length == 0)
	    // The main menu is not present.
	    this.append_menu(this.menu, $('submenu'), null);
	 //Initialize ARIA landmarks;
	 for (var id in this.LANDMARKS) {
	    var element = $(id);
	    if (element != null)
	       element.setAttribute('role', this.LANDMARKS[id]);
	 }
	 // Set up global key handler.
	 var global_key_handler = (document.all ? document.body : window);
	 global_key_handler.onkeydown = this.on_key_down.bind(this);
	 // Move focus to the main content if there is no anchor in the current URL.
	 if (window.location.href.match("#") == null)
	    this.set_focus($('main-heading'));
      },

      append_menu: function (items, node, parent) {
	 if (node != null) {
	    var map = $(node).down('map');
	    if (map != null) {
	       // Main menu or top level of submenu.
	       map.setAttribute('role', 'application');
	       map.setAttribute('tabindex', '0');
	    }
	    var ul = $(node).down('ul');
	    if (ul != null) {
	       //ul.setAttribute('role', 'menu');
	       for (var i = 0; i < ul.childNodes.length; i++) {
		  var li = $(ul.childNodes[i]);
		  if (li.nodeName =='LI') {
		     var item = li.down('a');
		     li.observe('click', this.on_menu_click.bind(this));
		     //item.setAttribute('role', 'menuitem');
		     //item.setAttribute('tabindex', '-1');
		     //item.setAttribute('title', item.innerHTML);
		     var subitems = [];
		     if (item.hasClassName('current'))
			this.active_menu_item = item;
		     this.append_menu(subitems, li, item);
		     if (subitems.length == 0 && parent == null && item.hasClassName('current')) {
			// Add submenu as a child menu of the current main menu item.
			this.append_menu(subitems, $('submenu'), item);
		     }
		     var child = null;
		     if (subitems.length != 0)
			child = subitems[0];
		     //item.setAttribute('aria-haspopup', 'true');
		     if (li.hasClassName('foldable')) {
			var hidden = (li.hasClassName('folded')?'true':'false');
			var submenu = li.down('ul');
			submenu.setAttribute('aria-hidden', hidden);
		     }
		     this.append_menu_item(items, item, parent, child);
		  }
	       }
	    }
	 }
      },

      append_menu_item: function (items, item, parent, child) {
	 var prev = null;
	 if (items.length > 0)
	    prev = items[items.length-1];
	 //item.setAttribute('role', '');
	 // Makes the items unroutable when ARIA is not correctly supported.
	 //item.setAttribute('tabindex', '-1');
	 var map = {};
	 map[this.CMD_PARENT] = parent;
	 map[this.CMD_CHILD] = child;
	 map[this.CMD_PREV] = prev;
	 map[this.CMD_NEXT] = null;
	 item._menu_navigation_target = map;
	 if (prev != null)
	    prev._menu_navigation_target[this.CMD_NEXT] = item;
	 item.onkeydown = this.on_menu_keydown.bind(this);
	 items[items.length] = item;
      },

      on_key_down: function (event) {
	 // Handle global Wiking keyboard shortcuts.
	 // Not all browsers invoke onkeypress for arrow keys, so keys must be
	 // handled in onkeydown.
	 var cmd = this.KEYMAP[this.event_key(event)];
	 if (cmd == this.CMD_MENU) {
	    this.set_focus(this.active_menu_item);
	    return false;
	 }
	 return true;
      },
      
      on_menu_keydown: function (event) {
	 var element = event.element();
	 var key = this.event_key(event);
	 var cmd = this.KEYMAP[key];
	 if (cmd == null)
	    return true;
	 if (cmd == this.CMD_QUIT) {
	    this.set_focus($('main-heading'));
	 } else if (cmd == this.CMD_ACTIVATE) {
	    self.location = element.getAttribute('href');
	 } else {
	    var target = element._menu_navigation_target[cmd];
	    if (target != null) {
	       var p1 = element.parentNode;
	       var p2 = target.parentNode;
	       if (cmd == this.CMD_CHILD && p1.hasClassName('folded')) {
		  p1.removeClassName('folded');
		  p1.down('ul').setAttribute('aria-hidden', 'false');
	       }
	       if (cmd == this.CMD_PARENT &&
		   p2.hasClassName('foldable') && !p2.hasClassName('folded')) {
		  p2.addClassName('folded');
		  p2.down('ul').setAttribute('aria-hidden', 'true');
	       }
	       this.set_focus(target);
	    }
	 }
	 return false;
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
	    if (event.pointerX() < span.cumulativeOffset().left) {
	       var li = span.parentNode.parentNode;
	       if (li.hasClassName('foldable')) {
		  if (li.hasClassName('folded')) {
		     li.removeClassName('folded');
		     li.down('ul').setAttribute('aria-hidden', 'false');
		  } else {
		     li.addClassName('folded');
		     li.down('ul').setAttribute('aria-hidden', 'true');
		  }
	       }
	       event.stop();
	    }
	 }
      },

      event_key: function (event) {
	 if (document.all) event = window.event;
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

      set_focus: function (element) {
	 if (element != null) 
	    setTimeout(function () { try { element.focus(); } catch (e) {} }, 0);
      }
      
   });

// Instantiate the handler and register calling `init()' on page load.
var wiking_handler = new WikingHandler();
if (window.addEventListener)
   window.addEventListener("load", wiking_handler.init.bind(wiking_handler), false);
else
   window.attachEvent('onload', wiking_handler.init.bind(wiking_handler));

