/* -*- coding: utf-8 -*-
 *
 * Copyright (C) 2008, 2009 Brailcom, o.p.s.
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
var WIKING_KEYMAP = {
   'Ctrl-Shift-Up':    CMD_PREV,
   'Ctrl-Shift-Down':  CMD_NEXT,
   'Ctrl-Shift-Left':  CMD_PARENT,
   'Ctrl-Shift-Right': CMD_CHILD,
   'Ctrl-Shift-m':     CMD_MENU,
   'Escape':           CMD_QUIT
};

var WIKING_LANDMARKS = {
   'top':     'banner',
   'menu':    'navigation',
   'submenu': 'navigation',
   'main':    'main',
   'bottom':  'contentinfo'
};

var _current_main_menu_item = null;
var _first_menu_item = null;
var _main_heading = null;

function wiking_init() {
   _main_heading = document.getElementById('main-heading');
   // Initialize the menus -- assign ARIA roles to HTML tags and bind keyboard event handling to
   // support hierarchical keyboard traversal.
   var items = [];
   append_menu(items, document.getElementById('menu'), null);
   if (items.length == 0)
      // The main menu is not present.
      append_menu(items, document.getElementById('submenu'), null);
   append_panels_menu(items);
   append_language_selection_menu(items);
   _first_menu_item = items[0];
   //Initialize ARIA landmarks;
   for (var id in WIKING_LANDMARKS) {
      var element = document.getElementById(id);
      if (element != null)
	 element.setAttribute('role', WIKING_LANDMARKS[id]);
   }
   // Set up global key handler.
   if (document.all)
      document.body.onkeydown = wiking_onkeydown;
   else
      window.onkeydown = wiking_onkeydown;
   // Move focus to the main content if there is no anchor in the current URL.
   if (window.location.href.match("#") == null)
      set_focus(_main_heading);
}

function wiking_onkeydown(event) {
   // Handle global Wiking keyboard shortcuts.
   // Not all browsers invoke onkeypress for arrow keys, so keys must be handled in onkeydown.
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

function append_menu(items, node, parent) {
   if (node != null) {
      var ul = node.getElementsByTagName('ul')[0];
      if (ul != null) { // && ul.parentNode == node) {
	 //ul.setAttribute('role', 'menu');
	 for (var i = 0; i < ul.childNodes.length; i++) {
	    var li = ul.childNodes[i];
	    if (li.nodeName =='LI') {
	       var link = li.getElementsByTagName('a')[0];
	       var item = link;
	       //item.setAttribute('role', 'menuitem');
	       //item.setAttribute('tabindex', '-1');
	       //item.setAttribute('title', link.innerHTML);
	       var subitems = [];
	       append_menu(subitems, li, item);
	       if (subitems.length == 0 && parent == null) {
		  var cls = link.getAttribute(document.all?'className':'class');
		  if (cls && cls.match('(\^\|\\s)current(\\s\|\$)') != null) {
		     _current_main_menu_item = item;
		     append_menu(subitems, document.getElementById('submenu'), item);
		  }
	       }
	       var child = null;
	       if (subitems.length != 0)
		  //item.setAttribute('aria-haspopup', 'true');
		  child = subitems[0];
	       append_menu_item(items, item, parent, child);
	    }
	 }
      }
   }
}

function append_panels_menu(items) {
   var node = document.getElementById('panels');
   if (node != null) {
      var login_panel = null;
      var headings = node.getElementsByTagName('h3');
      for (var i = 0; i < headings.length; i++) {
	 var heading = headings[i];
	 var panel = heading.parentNode;
	 panel.setAttribute('role', 'supplementary');
	 var item = heading.getElementsByTagName('a')[0];
	 if (item != null)
	    if (panel.getAttribute('id') == 'panel-login')
	       // Append login panel as the last panel in navigation order.
	       login_panel = item
	    else
	       append_menu_item(items, item, null, null);
      }
      if (login_panel != null)
	 append_menu_item(items, login_panel, null, null);
   }
}

function append_language_selection_menu(items) {
   var node = document.getElementById('language-selection');
   var item = document.getElementById('language-selection-anchor');
   if (node != null && item != null) {
      node.setAttribute('role', 'supplementary');
      item.setAttribute('tabindex', '-1');
      var languages = [];
      var links = node.getElementsByTagName('a');
      for (var i = 1; i < links.length; i++)
	 append_menu_item(languages, links[i], item, null);
      append_menu_item(items, item, null, languages[0]);
   }
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

function add_on_load(func) {
   if(window.addEventListener) {
      window.addEventListener("load", func, false);
   } else {
      window.attachEvent('onload', func);
   }
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
