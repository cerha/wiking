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

/* Menu navigation keyboard shortcuts */
MENU_KEY       = 'Ctrl-Alt-m';
MENU_KEY_UP    = 'Shift-Up';
MENU_KEY_DOWN  = 'Shift-Down';
MENU_KEY_LEFT  = 'Shift-Left';
MENU_KEY_RIGHT = 'Shift-Right';

var _current_main_menu_item = null;

function wiking_init() {
   // Not all browsers invoke onkeypress for arrow keys, so keys must be handled in onkeydown.
   init_menu('main-menu', null);
   if (document.all)
      document.body.onkeydown = wiking_onkeydown;
   else
      window.onkeydown = wiking_onkeydown;
   set_focus(document.getElementById('content-heading'));
}

function wiking_onkeydown(event) {
   // Handle global Wiking keyboard shortcuts.
   switch (event_key(event)) {
   case MENU_KEY: // Set focus to the first menu item.
      set_focus(_current_main_menu_item); return false;
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
      if (parent == null)
	 menu.setAttribute('role', 'menubar');
      return init_menu_items(menu.getElementsByTagName('ul')[0], parent);
   } else {
      return null;
   }
}

function init_menu_items(ul, parent) {
   ul.setAttribute('role', 'menu');
   var items = [];
   for (var i = 0; i < ul.childNodes.length; i++) {
      var node = ul.childNodes[i];
      if (node.nodeName =='LI') {
	 node.setAttribute('role', 'menuitem');
	 var link = node.getElementsByTagName('a')[0];
	 var child = null;
	 if (parent == null) {
	    var cls = link.getAttribute(document.all?'className':'class');
	    if (cls && cls.match('(\^\|\\s)current(\\s\|\$)') != null) {
	       _current_main_menu_item = link;
	       child = init_menu('submenu-frame', link);
	    }
	 } else {
	    var submenu = node.getElementsByTagName('ul')[0];
	    if (submenu != null && submenu.parentNode == node)
	       child = init_menu_items(submenu, link);
	 }
	 append_menu_item(items, link, parent, child);
      }
   }
   if (parent == null) {
      append_panels_menu(items);
      append_language_selection_menu(items);
      append_wmi_menu(items);
   }
   return items[0];
}

function append_panels_menu(items) {
   var panels = [];
   var node = document.getElementById('panels');
   var item = document.getElementById('panels-menu-item');
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

function append_menu_item(items, node, parent, child) {
   var parent_key, child_key, prev_key, next_key;
   if (parent == null) {
      // This is the main menubar.
      parent_key = MENU_KEY_UP;
      child_key  = MENU_KEY_DOWN;
      prev_key   = MENU_KEY_LEFT;
      next_key   = MENU_KEY_RIGHT;
   } else {
      // This is the local (sub)menu.
      parent_key = MENU_KEY_LEFT;
      child_key  = MENU_KEY_RIGHT;
      prev_key   = MENU_KEY_UP;
      next_key   = MENU_KEY_DOWN;
   }
   var prev = null;
   if (items.length > 0)
      prev = items[items.length-1];
   var map = {};
   map[parent_key] = parent;
   map[child_key]  = child;
   map[prev_key]   = prev;
   map[next_key]   = null;
   node._menu_navigation_target = map;
   if (prev != null)
      prev._menu_navigation_target[next_key] = node;
   node.onkeydown = function(event) { return on_menu_keydown(event, this); };
   items[items.length] = node;
}

function on_menu_keydown(event, link) {
   var key = event_key(event);
   if (key==MENU_KEY_UP || key==MENU_KEY_DOWN || key==MENU_KEY_RIGHT || key==MENU_KEY_LEFT) {
      var target = link._menu_navigation_target[key];
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
   var map = {37: 'Left',  // left arrow
	      39: 'Right', // right arrow
	      38: 'Up',    // up arrow
	      40: 'Down',  // down arrow
	      77: 'm'}
   var key = map[code];
   if (key != null) {
      if (event.shiftKey) key = 'Shift-'+key;
      if (event.altKey) key = 'Alt-'+key;
      if (event.ctrlKey) key = 'Ctrl-'+key;
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
