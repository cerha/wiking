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
	 this.menu = null;
	 this.foldable_submenu = false;
	 this.menu_expanded = false;
	 this.toggle_menu_expansion_button = null;
      },

      init: function (translations) {
	 // Initialize the loaded page (called from document body onload event).
	 this.translations = translations;
	 this.init_landmarks();
	 this.init_menus();
	 // Set up global key handler.
	 var global_key_handler = (document.all ? document.body : window);
	 global_key_handler.onkeydown = this.on_key_down.bind(this);
	 // Move focus to the main content if there is no anchor in the current URL.
	 if (window.location.href.match("#") == null)
	    this.set_focus($('main-heading'));
      },

      gettext: function(text) {
	 translation = this.translations[text];
	 if (typeof(translation) != 'undefined')
	    return translation;
	 else
	    return text;
      },

      init_landmarks: function () {
	 //Initialize ARIA landmarks;
	 for (var id in this.LANDMARKS) {
	    var element = $(id);
	    if (element != null)
	       element.setAttribute('role', this.LANDMARKS[id]);
	 }
      },

      init_menus: function () {
	 // Initialize the menus -- assign ARIA roles to HTML tags and bind
	 // keyboard event handling to support hierarchical keyboard traversal.
	 var menu = $('menu');
	 var submenu = $('submenu');
	 if (menu == null)
	    // If the main menu is not present, add submenu as the root menu.
	    menu = $('submenu');
	 if (menu != null) {
	    this.menu = menu;
	    var items = this.init_menu(menu.down('ul'), null);
	    var active = $(menu.getAttribute('aria-activedescendant'));
	    if (menu != submenu && submenu != null && active != null) {
	       // Add submenu as a child menu of the current main menu item.
	       this.init_menu(submenu.down('ul'), active);
	       menu.setAttribute('aria-owns', 'submenu');
	       submenu.setAttribute('role', 'application');
	    }
	    //var map = menu.down('map');
	    menu.setAttribute('role', 'application');
	    //menu.setAttribute('tabindex', '0');
	    // If a submenu item is active, the active item may now be different from above.
	    var active = $(menu.getAttribute('aria-activedescendant'));
	    if (active == null && items.length != 0) {
	       active = items[0];
	       menu.setAttribute('aria-activedescendant', active.getAttribute('id'));
	    }
	    active.setAttribute('tabindex', '0');
	    if (this.foldable_submenu) {
	       var b = new Element('button',
				   {id: 'toggle-menu-expansion-button',
				    onclick: 'return wiking_handler.toggle_menu_expansion();',
				    title: this.gettext("Expand all")});
	       submenu.down('ul').insert({after: b});
	    }
	 }
      },

      init_menu: function (ul, parent) {
	 //ul.setAttribute('role', 'menu');
	 var items = [];
	 var base_id = (parent != null ? parent.getAttribute('id') : 'wiking-menu');
	 for (var i = 0; i < ul.childNodes.length; i++) {
	    var li = $(ul.childNodes[i]);
	    if (li.nodeName =='LI') {
	       li.observe('click', this.on_menu_click.bind(this));
	       var item = li.down('a');
	       var id = base_id + '.' + i;
	       item.setAttribute('id', id);
	       // Note: tabindex makes the items unroutable when ARIA is not correctly supported.
	       item.setAttribute('tabindex', '-1');
	       //item.setAttribute('title', item.innerHTML);
	       //item.setAttribute('role', 'menuitem');
	       if (item.hasClassName('current'))
		  this.menu.setAttribute('aria-activedescendant', id);
	       var prev = (items.length == 0 ? null : items[items.length-1]);
	       var map = {};
	       map[this.CMD_PARENT] = parent;
	       map[this.CMD_CHILD] = null;
	       map[this.CMD_PREV] = prev;
	       map[this.CMD_NEXT] = null;
	       item._menu_navigation_target = map;
	       if (prev != null)
		  prev._menu_navigation_target[this.CMD_NEXT] = item;
	       if (parent != null && items.length == 0)
		  parent._menu_navigation_target[this.CMD_CHILD] = item;
	       item.onkeydown = this.on_menu_keydown.bind(this);
	       items[items.length] = item;
	       // Append hierarchical submenu if found.
	       var submenu = li.down('ul');
	       if (submenu != null) {
		  if (li.hasClassName('foldable')) {
		     var hidden = (li.hasClassName('folded')?'true':'false');
		     submenu.setAttribute('aria-hidden', hidden);
		     // ? submenu.setAttribute('aria-expanded', hidden);
		     this.foldable_submenu = true;
		  }
		  this.init_menu(submenu, item);
	       }
	    }
	 }
	 return items;
      },

      toggle_menu_expansion: function () {
	 this.toggle_item_expansion(this.menu.down('ul').down('a'));
	 //this.set_focus(item);
	 this.menu_expanded = !this.menu_expanded;
	 var b = $('toggle-menu-expansion-button');
	 if (this.menu_expanded) {
	    b.addClassName('expanded');
	    b.setAttribute('title', this.gettext("Collapse all"));
	 } else {
	    b.removeClassName('expanded');
	    b.setAttribute('title', this.gettext("Expand all"));
	 }
      },

      toggle_item_expansion: function (item) {
	 if (item != null) {
	    var parent = item.parentNode;
	    if (this.menu_expanded)
	       this.collapse_item(item);
	    else
	       this.expand_item(item);
	    var map = item._menu_navigation_target;
	    this.toggle_item_expansion(map[this.CMD_CHILD]);
	    this.toggle_item_expansion(map[this.CMD_NEXT]);

	 }
      },

      expand_item: function (item, recourse) {
	 var li = item.parentNode;
	 if (li.hasClassName('folded')) {
	    li.removeClassName('folded');
	    li.down('ul').setAttribute('aria-hidden', 'false');
	 }
	 if (recourse) {
	    var parent = item._menu_navigation_target[this.CMD_PARENT];
	    if (parent != null)
	       this.expand_item(parent, true);
	 }
      },

      collapse_item: function (item) {
	 var li = item.parentNode;
	 if (li.hasClassName('foldable') && !li.hasClassName('folded')) {
	    li.addClassName('folded');
	    li.down('ul').setAttribute('aria-hidden', 'true');
	 }
      },

      on_key_down: function (event) {
	 // Handle global Wiking keyboard shortcuts.
	 // Not all browsers invoke onkeypress for arrow keys, so keys must be
	 // handled in onkeydown.
	 var cmd = this.KEYMAP[this.event_key(event)];
	 if (cmd == this.CMD_MENU) {
	    var item = $(this.menu.getAttribute('aria-activedescendant'));
	    this.expand_item(item, true);
	    this.set_focus(item);
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
	       if (cmd == this.CMD_CHILD)
		  this.expand_item(element);
	       else if (cmd == this.CMD_PARENT)
		  this.collapse_item(target);
	       // This is commented out since it seems better not to change the
	       // active item item to change during menu navigation.  It is
	       // only changed when the item is activated and the page
	       // reloaded.
	       //element.setAttribute('tabindex', '-1');
	       //target.setAttribute('tabindex', '0');
	       //this.menu.setAttribute('aria-activedescendant', target.getAttribute('id'));
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
	    var item = span.parentNode;
	    if (event.pointerX() < span.cumulativeOffset().left) {
	       if (item.parentNode.hasClassName('folded'))
		  this.expand_item(item);
	       else
		  this.collapse_item(item);
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
