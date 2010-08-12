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

var WikingBase = Class.create({

      initialize: function (keymap, translations) {
	 this.keymap = keymap;
	 this.translations = translations;
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

      command: function (event) {
	 return this.keymap[this.event_key(event)];
      },

      set_focus: function (element) {
	 if (element != null) 
	    setTimeout(function () { try { element.focus(); } catch (e) {} }, 0);
      }

   });


var WikingHandler = Class.create(WikingBase, {
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
	 this.CMD_MENU = 'menu';
	 keymap = {
	    'Ctrl-Shift-m': this.CMD_MENU
	 };
	 $super(keymap, translations);
	 this.init_landmarks();
	 var menu = $('menu');
	 if (menu)
	    this.menu = new WikingFoldersMenu(translations, menu);
	 else
	    this.menu = null;
	 var submenu = $('submenu');
	 if (submenu) {
	    this.submenu = new WikingTreeMenu(translations, submenu);
	    if (menu)
	       this.menu.bind_submenu(this.submenu);
	 } else {
	    this.submenu = null;
	 }
	 // Set up global key handler.
	 document.observe('keydown', this.on_keydown.bind(this));
	 // Move focus to the main content if there is no anchor in the current URL.
	 if (window.location.href.match("#") == null)
	    this.set_focus($('main-heading'));
      },

      init_landmarks: function () {
	 //Initialize ARIA landmarks;
	 for (var id in this.LANDMARKS) {
	    var element = $(id);
	    if (element != null)
	       element.setAttribute('role', this.LANDMARKS[id]);
	 }
      },

      on_keydown: function (event) {
	 // Handle global Wiking keyboard shortcuts.
	 var cmd = this.command(event);
	 if (cmd == this.CMD_MENU) {
	    if (this.submenu != null)
	       this.submenu.focus();
	    else if (this.menu != null)
	       this.menu.focus();
	    event.stop();
	 }
      }

   });

var WikingMenu = Class.create(WikingBase, {
      // Initialize a hierarchical menu -- assign ARIA roles to HTML tags
      // and bind keyboard event handling to support keyboard menu traversal.
      
      initialize: function ($super, keymap, translations, node) {
	 $super(keymap, translations);
	 this.node = node;
	 node.setAttribute('role', 'application');
	 // Go through the menu and assign aria roles and key bindings.
	 var ul = node.down('ul');
	 this.items = this.init_items(ul, null);
	 // Set the active item.
	 var active = $(node.getAttribute('aria-activedescendant'));
	 if (active == null && this.items.length != 0) {
	    active = this.items[0];
	    node.setAttribute('aria-activedescendant', active.getAttribute('id'));
	 }
	 active.setAttribute('tabindex', '0');
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
	       var item = this.init_item(child, id, prev, parent);
	       items[items.length] = item;
	    }
	 }
	 return items;
      },

      init_item: function (li, id, prev, parent) {
	 li.setAttribute('role', 'presentation');
	 var item = li.down('a');
	 item.setAttribute('id', id);
	 // Note: tabindex makes the items unroutable when ARIA is not correctly supported.
	 item.setAttribute('tabindex', '-1');
	 if (item.hasClassName('current'))
	    this.node.setAttribute('aria-activedescendant', id);
	 item._wiking_menu_prev = prev;
	 item._wiking_menu_next = null;
	 item._wiking_menu_parent = parent;
	 item._wiking_submenu = null;
	 item._wiking_menu = this;
	 if (prev != null)
	    prev._wiking_menu_next = item;
	 item.observe('keydown', this.on_menu_keydown.bind(this));
	 return item;
      },

      on_menu_keydown: function (event) {
	 // Must be implemented in derived classes.
      },

      focus: function () {
	 var item = $(this.node.getAttribute('aria-activedescendant'));
	 this.expand_item(item, true);
	 this.set_focus(item);
      },

      expand_item: function (item, recourse) {
	 return false;
      }

   });


var WikingFoldersMenu = Class.create(WikingMenu, {
      // Specific handling of top level folders menu.

      initialize: function ($super, translations, node) {
	 // Definition of available commands.
	 this.CMD_PREV = 'prev'; // Go to the next item at the same level of hierarchy.
	 this.CMD_NEXT = 'next'; // Go to the previous item at the same level of hierarchy.
	 this.CMD_SUBMENU = 'submenu'; // Go to the submenu.
	 this.CMD_ACTIVATE = 'activate';
	 this.CMD_QUIT = 'quit';
	 // Menu navigation keyboard shortcuts mapping to available command identifiers.
	 keymap = {
	    'Left':	    this.CMD_PREV,
	    'Right':        this.CMD_NEXT,
	    'Down':         this.CMD_SUBMENU,
	    'Escape':	    this.CMD_QUIT,
	    'Enter':	    this.CMD_ACTIVATE,
	    'Space':	    this.CMD_ACTIVATE
	 };
	 $super(keymap, translations, node);
      },

      init_items: function ($super, ul, parent) {
	 ul.setAttribute('role', 'tablist');
	 return $super(ul, parent);
      },

      init_item: function ($super, li, id, prev, parent) {
	 var item = $super(li, id, prev, parent);
	 item.setAttribute('role', 'tab');
	 return item;
      },

      bind_submenu: function(menu) {
	 // Bind given WikingTreeMenu instance as a descendant of this menu in
	 // keyboard traversal.
	 var item = $(this.node.getAttribute('aria-activedescendant'));
	 item._wiking_submenu = menu.items;
	 menu.bind_parent(item);
      },

      on_menu_keydown: function (event) {
	 var item = event.element();
	 var cmd = this.command(event);
	 if (cmd == this.CMD_PREV) {
	    this.set_focus(item._wiking_menu_prev);
	    event.stop();
	 } else if (cmd == this.CMD_NEXT) {
	    this.set_focus(item._wiking_menu_next);
	    event.stop();
	 } else if (cmd == this.CMD_SUBMENU) {
	    if (item._wiking_submenu != null)
	       this.set_focus(item._wiking_submenu[0]);
	    event.stop();
	 } else if (cmd == this.CMD_ACTIVATE) {
	    self.location = item.getAttribute('href');
	    event.stop();
	 } else if (cmd == this.CMD_QUIT) {
	    this.set_focus($('main-heading'));
	    event.stop();
	 }
      }

   });


var WikingTreeMenu = Class.create(WikingMenu, {
      // Specific handling of foldable tree menu.

      initialize: function ($super, translations, node) {
	 // Definition of available commands.
	 this.CMD_EXPAND = 'expand'; // Unfold the subtree.
	 this.CMD_COLLAPSE = 'collapse';  // Fold the subtree.
	 this.CMD_UP = 'up'; // Go to the next item.
	 this.CMD_DOWN = 'down'; // Go to the previous item.
	 this.CMD_PREV = 'prev'; // Go to the next item at the same level of hierarchy.
	 this.CMD_NEXT = 'next'; // Go to the previous item at the same level of hierarchy.
	 this.CMD_ACTIVATE = 'activate';
	 this.CMD_QUIT = 'quit';
	 // Menu navigation keyboard shortcuts mapping to available command identifiers.
	 keymap = {
	    'Up':	    this.CMD_UP,
	    'Down':         this.CMD_DOWN,
	    'Shift-Up':	    this.CMD_PREV,
	    'Shift-Down':   this.CMD_NEXT,
	    'Shift-Right':  this.CMD_EXPAND,
	    'Shift-Left':   this.CMD_COLLAPSE,
	    'Right':        this.CMD_EXPAND,
	    'Left':         this.CMD_COLLAPSE,
	    'Escape':	    this.CMD_QUIT,
	    'Enter':	    this.CMD_ACTIVATE,
	    'Space':	    this.CMD_ACTIVATE
	 };
	 $super(keymap, translations, node);
	 node.down('.menu-panel').setAttribute('role', 'tree');
	 if (this.foldable) {
	    var b = new Element('button',
				{id: 'toggle-menu-expansion-button',
				 title: this.gettext("Expand/collapse complete menu hierarchy")});
	    node.down('ul').insert({after: b});
	    b.observe('click', this.on_toggle_expansion.bind(this));
	 }
      },

      init_items: function ($super, ul, parent) {
	 ul.setAttribute('role', 'group');
	 return $super(ul, parent);
      },

      init_item: function ($super, li, id, prev, parent) {
	 li.observe('click', this.on_menu_click.bind(this));
	 var item = $super(li, id, prev, parent);
	 //item.setAttribute('title', item.innerHTML);
	 item.setAttribute('role', 'treeitem');
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
	       item.setAttribute('aria-expanded', expanded);
	       this.foldable = true;
	    }
	    item._wiking_submenu = this.init_items(submenu, item);
	 }
	 return item;
      },

      bind_parent: function(parent) {
	 // Bind given WikingFolderMenu item as a parent of this menu in
	 // keyboard traversal.
	 for (var i = 0; i < this.items.length; i++) {
	    var item = this.items[i];
	    item._wiking_menu_parent = parent;
	 }
      },

      toggle_item_expansion: function (item) {
	 if (item != null) {
	    var parent = item.parentNode;
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
	 var li = item.parentNode;
	 var expanded = false;
	 if (li.hasClassName('folded')) {
	    li.removeClassName('folded');
	    li.down('ul').setAttribute('aria-hidden', 'false');
	    item.setAttribute('aria-expanded', 'true');
	    expanded = true;
	 }
	 if (recourse && item._wiking_menu_parent != null)
	    this.expand_item(item._wiking_menu_parent, true);
	 return expanded;
      },

      collapse_item: function (item) {
	 var li = item.parentNode;
	 if (li.hasClassName('foldable') && !li.hasClassName('folded')) {
	    li.addClassName('folded');
	    li.down('ul').setAttribute('aria-hidden', 'true');
	    item.setAttribute('aria-expanded', 'false');
	    return true;
	 }
	 return false;
      },

      next_item: function (item) {
	 // Recursively find the next item in sequence by traversing the hierarchy.
	 if (item._wiking_menu_next != null)
	    next = item._wiking_menu_next;
	 else if (item._wiking_menu_parent != null
		  && item._wiking_menu_parent._wiking_menu == this)
	    next = this.next_item(item._wiking_menu_parent);
	 return next;
      },

      on_menu_keydown: function (event) {
	 var item = event.element();
	 var cmd = this.command(event);
	 if (cmd == this.CMD_UP) {
	    var target = null;
	    if (item._wiking_menu_prev != null) {
	       target = item._wiking_menu_prev;
	       if (target._wiking_submenu != null && !target.parentNode.hasClassName('folded'))
		  target = target._wiking_submenu[target._wiking_submenu.length-1];
	    } else {
	       target = item._wiking_menu_parent;
	    }
	    this.set_focus(target);
	    event.stop();
	 } else if (cmd == this.CMD_DOWN) {
	    var target = null;
	    if (item._wiking_submenu != null && !item.parentNode.hasClassName('folded'))
	       target = item._wiking_submenu[0];
	    else
	       target = this.next_item(item);
	    this.set_focus(target);
	    event.stop();
	 } else if (cmd == this.CMD_PREV) {
	    this.set_focus(item._wiking_menu_prev);
	    event.stop();
	 } else if (cmd == this.CMD_NEXT) {
	    this.set_focus(item._wiking_menu_next);
	    event.stop();
	 } else if (cmd == this.CMD_EXPAND) {
	    if (!this.expand_item(item) && item._wiking_submenu != null)
	       this.set_focus(item._wiking_submenu[0]);
	    event.stop();
	 } else if (cmd == this.CMD_COLLAPSE) {
	    if (!this.collapse_item(item))
	       this.set_focus(item._wiking_menu_parent);
	    event.stop();
	 } else if (cmd == this.CMD_ACTIVATE) {
	    self.location = item.getAttribute('href');
	    event.stop();
	 } else if (cmd == this.CMD_QUIT) {
	    this.set_focus($('main-heading'));
	    event.stop();
	 }
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
	    var item = span.parentNode;
	    if (event.pointerX() < span.cumulativeOffset().left) {
	       if (item.parentNode.hasClassName('folded'))
		  this.expand_item(item);
	       else
		  this.collapse_item(item);
	       event.stop();
	    }
	 }
      }

   });
