/* -*- coding: utf-8 -*-
 *
 * Copyright (C) 2008-2018 OUI Technology Ltd.
 * Copyright (C) 2019, 2025 Tomáš Cerha <t.cerha@gmail.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

/* eslint no-unused-vars: 0 */
/* global Prototype, Class, Effect, Gettext, $, $$, lcg, self */

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

        // Set up global key handler.
        document.observe('keydown', this._on_key_down.bind(this));

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

        // Move focus to the main content if there is no anchor in the current URL
        // to improve the experience for screen reader users.  Don't do it in MSIE
        // as it scrolls the current viewport so that the left side menu column is
        // not visible.
        if (!self.location.hash && !Prototype.Browser.IE && !document.body.down('*[autofocus]')) {
            $('main-heading').up().focus();
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
            if (!element.up('.foldable-tree-widget')) {
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
            }
        });

        // These links have role='button' so they should behave like buttons (invoke on Space).
        $$('a.login-button, a.maximized-mode-button').each(function(element) {
            element.observe('keydown', function(event) {
                if (this._event_key(event) === 'Space') {
                    self.location = element.getAttribute('href');
                    event.stop();
                }
            }.bind(this));
        }.bind(this));

        $$('.login-control .password-expiration-warning, .login-control .ctrl-icon')
            .each(function(element) {
            var info = element.up('.login-control').down('.password-expiration-warning .info');
            if (info) {
                info._dismiss_handler = function (event) {
                    if (info._ignore_next_click) {
                        info._ignore_next_click = false;
                    } else {
                        if (event.findElement('.info') !== info) {
                            info.hide();
                            $(document).stopObserving('click', info._dismiss_handler);
                        }
                    }
                };
                element.observe('click', function(event) {
                    if (!info.visible()) {
                        info.show();
                        info._ignore_next_click = true;
                        $(document).observe('click', info._dismiss_handler);
                    }
                });
            }
        });

        // Bind submenu with the main menu so that Arrow-up on a top
        // level sumenu item navigates to the current main menu item.
        var submenu = $('submenu');
        if (submenu) {
            var tree_menu = lcg.widget_instance(submenu.down('.foldable-tree-widget'));
            $$('#menu ul.level-1 > li.in-path > a').each(function(item) {
                tree_menu.items.each(function(x) {
                    x._lcg_menu_parent = item;
                });
            });
        }

        wiking.handler = this;
    },

    _define_keymap: function () {
        // None of the shortcuts defined here are essential.  Most users
        // will not know about them, but they may improve the experience
        // for "expert" screen reader users.
        return {
            'Ctrl-Shift-m': this._cmd_menu,
            // These shortcuts (up/down) don't work on Windows, but make
            // a pleasant convenience on Linux and Mac OS.
            'Ctrl-Shift-Up': this._cmd_top_controls,
            'Ctrl-Shift-Down': this._cmd_notebook
        };
    },

    _cmd_menu: function (event, element) {
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

    _cmd_top_controls: function (event, element) {
        // Move focus to the top bar.
        var controls = $('top-controls');
        if (controls) {
            var item = controls.down('a, [tabindex=0]');
            if (item) {
                item.focus();
            }
        }
    },

    _cmd_notebook: function (event, element) {
        // Move focus to the first Notebook widget on the page.
        var nb = document.body.down('div.notebook-widget');
        if (nb) {
            var item = $(nb.getAttribute('aria-activedescendant'));
            this._set_focus(item);
        }
    }

});

wiking.MainMenu = Class.create(lcg.FoldableTree, {
    /* The Wiking main menu behaves as a horizontal menu bar on wide screens
     * and degrades to a vertical foldable tree on narrow screens.  The
     * parent class behavior applies in vertical mode, while different rules
     * apply in horizontal mode for the top level menu items (the submenus
     * appear as dropdowns with separate foldable trees inside them).
     */

    _MANAGE_TABINDEX: false,

    initialize: function ($super, element_id, toggle_button_tooltip) {
        $super(element_id, toggle_button_tooltip);
        this._menu_button = this.element.parentNode.down('.menu-button');
        this._menu_button.on('click', this._on_toggle_main_menu.bind(this));
        this._menu_button.setAttribute('role', 'button');
        this._menu_button.setAttribute('aria-expanded', 'false');
        this.element.addClassName('collapsed');
        this.element.setAttribute('role', 'presentation');
    },

    _init_item: function ($super, item, prev, parent) {
        $super(item, prev, parent);
        var li = item.up('li');
        if (li.parentNode.hasClassName('level-1')) {
            // The attribute 'aria-selected' is not allowed on a pure link element
            // (see _init_items() for a reason why we are using pure links), so we
            // unset 'aria-selected' to be standards compliant (the attribute is
            // allowed only for certain ARIA roles).  The question is how to announce
            // the current main menu item to the screen reader user.
            item.removeAttribute('role');
            item.removeAttribute('aria-selected');
            if (li.hasClassName('foldable')) {
                this._update_item(item, false);
            }
        }
    },

    _init_items: function ($super, ul, parent) {
        var items = $super(ul, parent);
        if (ul.hasClassName('level-1')) {
            // By setting the role to 'menubar', the menubar becomes an "item"
            // in the surrounding 'navigation' element.  This disturbs VoiceOver
            // presentation and requires the user to go through two elements
            // (first "navigation, one item" and second "menubar n items")
            // where the first is redundant and misleading.  When the role is
            // left unset, the menu items become items of the 'navigation'.
            // Their number is announced correctly and they can be navigated
            // easily.
            ul.setAttribute('role', 'presentation');
        } else if (ul.hasClassName('level-2')) {
            ul.setAttribute('role', 'group');
            ul.setAttribute('aria-hidden', 'true');
        }
        return items;
    },

    _on_toggle_main_menu: function(event) {
        var menu = this.element;
        if (!menu.hasClassName('expanded')) {
            menu.setStyle({display: 'none'});
            menu.addClassName('expanded');
            menu.slideDown({
                duration: 0.3,
                afterFinish: function () {
                    this._menu_button.setAttribute('aria-expanded', 'true');
                    this._set_focus(lcg.widget_instance(menu).items[0]);
                }.bind(this)
            });
        } else {
            menu.slideUp({
                duration: 0.3,
                afterFinish: function () {
                    menu.removeClassName('expanded');
                    menu.removeAttribute('style');
                    this._menu_button.setAttribute('aria-expanded', 'false');
                }.bind(this)
            });
        }
    },

    _horizontal: function (item) {
        /* Return true if given item is a top level item and the menu is currently
         * in the horizontal menu bar mode (see class documentation for details). */
        return (item.up('ul').hasClassName('level-1') &&
                this._menu_button.getStyle('display') === 'none');
    },

    _on_item_click: function ($super, event, item) {
        if (this._horizontal(item)) {
            this._cmd_activate(event, item);
            event.stop();
        } else {
            $super(event, item);
        }
    },

    _cmd_activate: function ($super, event, item) {
        var li = item.up('li');
        if (this._horizontal(item) && li.hasClassName('foldable')) {
            var dropdown = li.down('ul');
            if (dropdown && dropdown.getStyle('display') === 'none') {
                this._expand_item(item);
                return;
            }
        }
        $super(event, item);
    },

    _expand_item: function ($super, item, recourse) {
        var li = item.up('li');
        if (this._horizontal(item) && !li.hasClassName('expanded')) {
            this.items.each(function(x) {
                if (x.up('li').hasClassName('expanded')) {
                    this._collapse_item(x);
                }
            }.bind(this));
            var dropdown = li.down('ul');
            // Setting min-width solves two problems.  A. the dropdown looks visually
            // odd when not wider than the item.  B. the dropdown width flickers when
            // hovering over its widest item.
            // Also resetting the style here prevents messy final state when
            // clicking too fast so that the slideDown effects overlap.
            dropdown.setStyle({
                minWidth: Math.max(item.getWidth(), dropdown.getWidth() + 10) + 'px',
                boxSizing: 'border-box',
                display: 'none'
            });
            li.removeClassName('collapsed');
            li.addClassName('expanded');
            /* The current item has the class 'expanded' to work well in vertical mode
               (on narrow screen), but it must be hidden even in the expanded state by
               the CSS when in horizontal mode (on a wide screen) because the submenu
               is a drop-down there.  The class
               'script-expanded' works around this.
             */
            li.addClassName('script-expanded');
            this._update_item(item, true);
            dropdown.slideDown({duration: 0.25});
            this._on_touchstart = function (event) { this._touch_moved = false; }.bind(this);
            this._on_touchmove = function (event) { this._touch_moved = true; }.bind(this);
            this._on_touchend = function (event) {
                if (!this._touch_moved) {
                    this._on_click(event);
                }
            }.bind(this);
            this._on_click = function (event) {
                if (event.findElement('ul.level-2') !== dropdown
                    && event.findElement('ul.level-1 > li') !== li) {
                    this._collapse_item(item);
                    if (!event.stopped) {
                        event.stop();
                    }
                }
            }.bind(this);
            $(document).observe('click', this._on_click);
            $(document).observe('touchstart', this._on_touchstart);
            $(document).observe('touchmove', this._on_touchmove);
            $(document).observe('touchend', this._on_touchend);
            return true;
        }
        return $super(item, recourse);
    },

    _collapse_item: function ($super, item) {
        if (item.up('ul').hasClassName('level-1')) {
            $(document).stopObserving('click', this._on_click);
            $(document).stopObserving('touchstart', this._on_touchstart);
            $(document).stopObserving('touchmove', this._on_touchmove);
            $(document).stopObserving('touchend', this._on_touchend);
        }
        $super(item);
        item.up('li').removeClassName('script-expanded');
    }

});

wiking.MainMenuOrig = Class.create(lcg.Menu, {

    _cmd_quit: function (event, item) {
        this._set_focus($('main-heading'));
    }

});
