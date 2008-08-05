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

var _first_menu_item = null;

function wiking_init() {
   // Not all browsers invoke onkeypress for arrow keys, so keys must be handled in onkeydown.
   _first_menu_item = init_menu('main-menu', true, null);
   if (document.all)
      document.body.onkeydown = wiking_onkeydown;
   else
      window.onkeydown = wiking_onkeydown;
}

function wiking_onkeydown(event) {
   // Handle global Wiking keyboard shortcuts.
   //alert(event_key(event));
   switch (event_key(event)) {
   case 'Ctrl-Shift-m': // Set focus to the first menu item.
      set_focus(_first_menu_item); return false;
   }
   return true;
}

function init_menu(menu_id, horizontal, parent) {
   // Initialize given menu and its items.
   //
   // The initialization mainly consists of assigning ARIA roles to HTML tags and
   // binding keyboard event handling to menu items to support hierarchical
   // keyboard menu traversal.
   //
   var menu = document.getElementById(menu_id);
   if (menu != null) {
      if (horizontal)
	 menu.setAttribute('role', 'menubar');
      return init_menu_items(menu.getElementsByTagName('ul')[0], horizontal, parent);
   } else {
      return null;
   }
}

function init_menu_items(ul, horizontal, parent) {
   ul.setAttribute('role', 'menu');
   var items = [];
   var n = 0;
   for (var i = 0; i < ul.childNodes.length; i++) {
      var node = ul.childNodes[i];
      if (node.nodeName =='LI') {
	 node.setAttribute('role', 'menuitem');
	 var link = node.getElementsByTagName('a')[0];
	 items[n++] = link;
	 var child = null;
	 if (horizontal) {
	    var cls = link.getAttribute(document.all?'className':'class');
	    if (cls && cls.match('(\^\|\\s)current(\\s\|\$)') != null)
	       child = init_menu('submenu-frame', false, link);
	 } else {
	    var submenu = node.getElementsByTagName('ul')[0];
	    if (submenu != null && submenu.parentNode == node)
	       child = init_menu_items(submenu, false, link, null);
	 }
	 var prev = n > 1 ? items[n-2] : null;
	 var parent_key, child_key, prev_key, next_key;
	 if (horizontal) {
	    // This is the main menubar.
	    parent_key = 'Up';
	    child_key  = 'Down';
	    prev_key   = 'Left';
	    next_key   = 'Right';
	 } else {
	    // This is the local (sub)menu.
	    parent_key = 'Left';
	    child_key  = 'Right';
	    prev_key   = 'Up';
	    next_key   = 'Down';
	 }
	 var map = {};
	 map[parent_key] = parent;
	 map[child_key]  = child;
	 map[prev_key]   = prev;
	 map[next_key]   = null;
	 link._menu_navigation_target = map;
	 if (prev != null)
	    prev._menu_navigation_target[next_key] = link;
	 link.onkeydown = function(event) { return on_menu_keydown(event, this); };
      }
   }
   return items[0];
}

function on_menu_keydown(event, link) {
   var key = event_key(event);
   if (key == 'Up' || key == 'Down' || key == 'Right' || key == 'Left') {
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

