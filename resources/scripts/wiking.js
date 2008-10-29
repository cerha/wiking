/* -*- coding: utf-8 -*-
 *
 * Copyright (C) 2008 Brailcom, o.p.s.
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

/* Definition of available commands */
var CMD_PARENT = 'parent'; // Go up in the hierarchy.
var CMD_CHILD  = 'child';  // Go down in the hierarchy.
var CMD_PREV = 'prev'; // Go to the next item at the same level.
var CMD_NEXT = 'next'; // Go to the previous item at the same level.
var CMD_MENU = 'menu'; 
var CMD_QUIT = 'quit';

/* Menu navigation keyboard shortcuts */
var WIKING_KEYMAP = {'Ctrl-Alt-i': CMD_PREV,
		     'Ctrl-Alt-k': CMD_NEXT,
		     'Ctrl-Alt-j': CMD_PARENT,
		     'Ctrl-Alt-l': CMD_CHILD,
		     'Ctrl-Shift-Up':    CMD_PREV,
		     'Ctrl-Shift-Down':  CMD_NEXT,
		     'Ctrl-Shift-Left':  CMD_PARENT,
		     'Ctrl-Shift-Right': CMD_CHILD,
		     'Ctrl-Shift-m': CMD_MENU,
		     'Ctrl-Alt-m':   CMD_MENU,
		     'Escape': CMD_QUIT};

var _current_main_menu_item = null;
var _first_menu_item = null;
var _main_heading = null;

function wiking_init() {
   // Not all browsers invoke onkeypress for arrow keys, so keys must be handled in onkeydown.
   _main_heading = document.getElementById('main-heading')
   init_menu('menu', null);
   if (document.all)
      document.body.onkeydown = wiking_onkeydown;
   else
      window.onkeydown = wiking_onkeydown;
   if (window.location.href.match("#") == null)
      set_focus(_main_heading);
}

function wiking_onkeydown(event) {
   // Handle global Wiking keyboard shortcuts.
   switch (WIKING_KEYMAP[event_key(event)]) {
   case CMD_MENU: // Set focus to the first menu item.
      if (_current_main_menu_item != null)
	 set_focus(_current_main_menu_item);
      else
	 set_focus(_first_menu_item);
      return false;
   }
   return true;
}

function init_menu(menu_id, parent) {
   // Initialize given menu and its items.
   //
   // The initialization mainly consists of assigning ARIA roles to HTML tags and
   // binding keyboard event handling to menu items to support hierarchical
   // keyboard menu traversal.
   //
   var menu = document.getElementById(menu_id);
   if (menu != null) {
      var ul = menu.getElementsByTagName('ul')[0];
      if (ul)
	 return init_menu_items(ul, parent);
   }
   return null;
}

function init_menu_items(ul, parent) {
   if (parent == null)
      ul.setAttribute('role', 'menubar');
   else
      ul.setAttribute('role', 'menu');
   var items = [];
   for (var i = 0; i < ul.childNodes.length; i++) {
      var node = ul.childNodes[i];
      if (node.nodeName =='LI') {
	 var child = null;
	 var link = node.getElementsByTagName('a')[0];
	 var item = link;
	 item.setAttribute('role', 'menuitem');
	 //item.setAttribute('tabindex', '-1');
	 //item.setAttribute('title', link.innerHTML);
	 if (parent == null) {
	    var cls = link.getAttribute(document.all?'className':'class');
	    if (cls && cls.match('(\^\|\\s)current(\\s\|\$)') != null) {
	       _current_main_menu_item = item;
	       child = init_menu('submenu', item);
	    }
	 } else {
	    var submenu = node.getElementsByTagName('ul')[0];
	    if (submenu != null && submenu.parentNode == node) {
	       child = init_menu_items(submenu, item);
	       //item.setAttribute('aria-haspopup', 'true');
	    }
	 }
	 append_menu_item(items, item, parent, child);
      }
   }
   if (parent == null) {
      append_panels_menu(items);
      append_language_selection_menu(items);
      append_wmi_menu(items);
   }
   _first_menu_item = items[0];
   return items[0];
}

function append_panels_menu(items) {
   var panels = [];
   var node = document.getElementById('panels');
   var item = document.getElementById('panels-menu-item');
   //var item = node;
   if (node != null && item != null) {
      var headings = node.getElementsByTagName('h3');
      for (var i = 0; i < headings.length; i++) {
	 var link = headings[i].getElementsByTagName('a')[0];
	 if (link != null)
	    append_menu_item(panels, link, item, null);
      }
      append_menu_item(items, item, null, panels[0]);
   }
}

function append_language_selection_menu(items) {
   var languages = [];
   var node = document.getElementById('language-selection');
   var item = document.getElementById('language-selection-anchor');
   if (node != null && item != null) {
      var links = node.getElementsByTagName('a');
      for (var i = 1; i < links.length; i++)
	 append_menu_item(languages, links[i], item, null);
      append_menu_item(items, item, null, languages[0]);
   }
}

function append_wmi_menu(items) {
   var item = document.getElementById('wmi-link');
   if (item != null)
      append_menu_item(items, item, null, null);
}

function append_menu_item(items, item, parent, child) {
   var prev = null;
   if (items.length > 0)
      prev = items[items.length-1];
   var map = {};
   map[CMD_PARENT] = parent;
   map[CMD_CHILD] = child;
   map[CMD_PREV] = prev;
   map[CMD_NEXT] = null;
   map[CMD_QUIT] = _main_heading;
   item._menu_navigation_target = map;
   if (prev != null)
      prev._menu_navigation_target[CMD_NEXT] = item;
   item.onkeydown = function(event) { return on_menu_keydown(event, this); };
   items[items.length] = item;
}

function on_menu_keydown(event, link) {
   var cmd = WIKING_KEYMAP[event_key(event)];
   if (cmd != null) {
      var target = link._menu_navigation_target[cmd];
      if (target != null)
	 set_focus(target);
      return false;
   } else {
      return true;
   }
}

function event_key(event) {
   if (document.all) event = window.event;
   var code = document.all ? event.keyCode : event.which;
   var map = {8:  'Backspace',
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
	      40: 'Down'};
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
      //alert(code+': '+key);
   }
   return key;
}

function set_focus(element) {
   if (element != null) 
      setTimeout(function () { try { element.focus(); } catch (e) {} }, 0);
}

function debug(message) {
   if (!debug.window_ || debug.window_.closed) {
      var win = window.open("", null, "width=400, height=200, scrollbars=yes, resizable=yes, " +
			    "status=no, location=no, menubar=no, toolbar=no");
      if (!win) return;
      var doc = win.document;
      doc.write("<html><head><title>Debug Log</title></head><body></body></html>");
      doc.close();
      debug.window_ = win;
   }
   var line = debug.window_.document.createElement("div");
   line.appendChild(debug.window_.document.createTextNode(message));
   debug.window_.document.body.appendChild(line);
}
