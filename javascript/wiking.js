/* -*- coding: utf-8 -*-
 *
 * Copyright (C) 2008-2018 OUI Technology Ltd.
 * Copyright (C) 2019-2025 Tomáš Cerha <t.cerha@gmail.com>
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
/* global $, lcg, wiking */

"use strict"

window.wiking = {
    handler: null,
    _: lcg.gettext('wiking'),
}

wiking.Handler = class extends lcg.KeyHandler {
    // This class is instantiated within the page onload handler.  It is the
    // main javascript interface of a Wiking application.  It creates
    // instances of other javascript classes to handle menus etc if the
    // relevant HTML objects exist..

    constructor() {
        // Constructor (called on page load).
        super()

        // Set up global key handler.
        $(document).on('keydown', this._on_key_down.bind(this))

        // Update the information about browser's timezone in the cookie to let
        // the server know what is the user's time zone.  The problem is that
        // this information will not be available on the very first request, so
        // the times will show in UTC on the first request and in the users
        // time zone on upcomming request, which may be confusing.  It is also
        // not 100% accurate as we don't detect the DST change dates and let
        // the server decide what the DST change dates most likely are.
        // TODO: Maybe use http://www.pageloom.com/automatic-timezone-detection-with-javascript
        let summer_date = new Date(Date.UTC(2005, 6, 30, 0, 0, 0, 0))
        let summer_offset = -summer_date.getTimezoneOffset()
        let winter_date = new Date(Date.UTC(2005, 12, 30, 0, 0, 0, 0))
        let winter_offset = -winter_date.getTimezoneOffset()
        lcg.cookies.set('wiking_tz_offsets', summer_offset + ';' + winter_offset)

        // Use smooth scrolling for in-page links.
        $('a[href*="#"]').each((i, element) => {
            let link = $(element)
            if (link.closest('.foldable-tree-widget').length == 0) {
                let href = $(element).attr('href')
                let uri = href.substr(0, href.indexOf('#'))
                if (uri === '' || uri === self.location.pathname) {
                    let anchor = href.substr(href.indexOf('#') + 1)
                    if (anchor) {
                        let target = $('#' + anchor.replace(/\./g, '\\.'))
                    if (!target.length) {
                        target = $('a[name=' + anchor + ']')
                    }
                        if (target.length && !target.hasClass('notebook-page')) {
                            link.on('click', function(event) {
                                $('html,body').animate({scrollTop: target.offset().top}, 300);
                                return false
                            })
                        }
                    }
                }
            }
        })

        // These links have role='button' so they should behave like buttons (invoke on Space).
        $('a.login-button, .maximized-mode-control a').on('keydown', event => {
            if (this._event_key(event) === 'Space') {
                self.location = $(event.target).attr('href')
                return false
            }
        })

        $('.login-control .password-expiration-warning, .login-control .ctrl-icon')
            .on('click', event => {
                let info = $(event.target).closest('.login-control').find('.password-expiration-warning .info')
                if (!info.is(':visible')) {
                    info.show()
                    this._dismiss_handler = e => {
                        info.hide()
                        $(document).off('click', this._dismiss_handler)
                        return false
                    }
                    $(document).on('click', this._dismiss_handler)
                }
                return false
            })

        wiking.handler = this
    }

    _define_keymap() {
        // None of the shortcuts defined here are essential.  Most users
        // will not know about them, but they may improve the experience
        // for "expert" screen reader users.
        return {
            'Ctrl-Shift-m': this._cmd_menu,
            // These shortcuts (up/down) don't work on Windows, but make
            // a pleasant convenience on Linux and Mac OS.
            'Ctrl-Shift-Up': this._cmd_top_controls,
            'Ctrl-Shift-Down': this._cmd_notebook,
        }
    }

    _cmd_menu(event, element) {
        // Move focus to the menu (the current menu item).
        let submenu = $('#submenu')
        if (submenu.length && submenu.css('display') !== 'none') {
            lcg.widget_instance(submenu.find('.foldable-tree-widget')).focus()
        } else {
            let menu = $('#main-menu')
            if (menu.length) {
                lcg.widget_instance(menu).focus()
            }
        }
    }

    _cmd_top_controls(event, element) {
        // Move focus to the top bar.
        let controls = $('#top-controls')
        if (controls.length) {
            let item = controls.find('a, [tabindex=0]').first()
            if (item.length) {
                item.focus()
            }
        }
    }

    _cmd_notebook(event, element) {
        // Move focus to the first Notebook widget on the page.
        let nb = $('div.notebook-widget').first()
        if (nb.length) {
            let item = $('#' + nb.attr('aria-activedescendant'))
            this._set_focus(item)
        }
    }

}


wiking.MainMenu = class extends lcg.FoldableTree {
    /* The Wiking main menu behaves as a horizontal menu bar on wide screens
     * and degrades to a vertical foldable tree on narrow screens.  The
     * parent class behavior applies in vertical mode, while different rules
     * apply in horizontal mode for the top level menu items (the submenus
     * appear as dropdowns with separate foldable trees inside them).
     */

    constructor(element_id, toggle_button_tooltip) {
        super(element_id, toggle_button_tooltip)
        this._menu_button = this.element.parent().find('.menu-button')
            .attr('role', 'button')
            .attr('aria-expanded', 'false')
            .on('click', this._on_toggle_main_menu.bind(this))
        this.element.addClass('collapsed')
            .attr('role', 'presentation')
        this._MANAGE_TABINDEX = false
    }

    _init_item(item, prev, parent) {
        super._init_item(item, prev, parent)
        let li = item.closest('li')
        if (li.parent().hasClass('level-1')) {
            // The attribute 'aria-selected' is not allowed on a pure link element
            // (see _init_items() for a reason why we are using pure links), so we
            // unset 'aria-selected' to be standards compliant (the attribute is
            // allowed only for certain ARIA roles).  The question is how to announce
            // the current main menu item to the screen reader user.
            item.attr('role', null)
            item.attr('aria-selected', null)
            if (li.hasClass('foldable')) {
                this._update_item(item, false)
            }
        }
    }

    _init_items(ul, parent) {
        let items = super._init_items(ul, parent)
        if (ul.hasClass('level-1')) {
            // By setting the role to 'menubar', the menubar becomes an "item"
            // in the surrounding 'navigation' element.  This disturbs VoiceOver
            // presentation and requires the user to go through two elements
            // (first "navigation, one item" and second "menubar n items")
            // where the first is redundant and misleading.  When the role is
            // left unset, the menu items become items of the 'navigation'.
            // Their number is announced correctly and they can be navigated
            // easily.
            ul.attr('role', 'presentation')
        } else if (ul.hasClass('level-2')) {
            ul.attr('role', 'group')
            ul.attr('aria-hidden', 'true')
        }
        return items
    }

    _on_toggle_main_menu(event) {
        let menu = this.element
        if (!menu.hasClass('expanded')) {
            menu.css({display: 'none'})
            menu.addClass('expanded')
            menu.slideDown({
                duration: 300,
                complete: () => {
                    this._menu_button.attr('aria-expanded', 'true')
                    this._set_focus(lcg.widget_instance(menu).items[0])
                }
            })
        } else {
            menu.slideUp({
                duration: 300,
                complete: () => {
                    menu.removeClass('expanded')
                    menu.attr('style', null)
                    this._menu_button.attr('aria-expanded', 'false')
                },
            })
        }
    }

    _horizontal(item) {
        /* Return true if given item is a top level item and the menu is currently
         * in the horizontal menu bar mode (see class documentation for details). */
        return (item.closest('ul').hasClass('level-1') &&
                this._menu_button.css('display') === 'none')
    }

    _on_item_click(event, item) {
        if (this._horizontal(item)) {
            this._cmd_activate(event, item)
            return false
        } else {
            return super._on_item_click(event, item)
        }
    }

    _cmd_activate(event, item) {
        let li = item.closest('li')
        //console.log('--', this._horizontal(item), li.hasClass('foldable'))
        if (this._horizontal(item) && li.hasClass('foldable')) {
            let dropdown = li.children('ul')
            if (dropdown.length && dropdown.css('display') === 'none') {
                this._expand_item(item)
                return
            }
        }
        super._cmd_activate(event, item)
    }

    _expand_item(item, recourse) {
        let li = item.closest('li')
        if (this._horizontal(item) && !li.hasClass('expanded')) {
            this.items.forEach(x => {
                if (x.closest('li').hasClass('expanded')) {
                    this._collapse_item(x)
                }
            })
            let dropdown = li.children('ul')
            // Setting min-width solves two problems.  A. the dropdown looks visually
            // odd when not wider than the item.  B. the dropdown width flickers when
            // hovering over its widest item.
            // Also resetting the style here prevents messy final state when
            // clicking too fast so that the slideDown effects overlap.
            dropdown.css({
                minWidth: Math.max(item.width(), dropdown.width() + 10) + 'px',
                boxSizing: 'border-box',
                display: 'none'
            })
            li.removeClass('collapsed')
            li.addClass('expanded')
            /* The current item has the class 'expanded' to work well in vertical mode
               (on narrow screen), but it must be hidden even in the expanded state by
               the CSS when in horizontal mode (on a wide screen) because the submenu
               is a drop-down there.  The class
               'script-expanded' works around this.
             */
            li.addClass('script-expanded')
            this._update_item(item, true)
            dropdown.slideDown({duration: 250})
            this._on_touchstart = function (event) { this._touch_moved = false }.bind(this)
            this._on_touchmove = function (event) { this._touch_moved = true }.bind(this)
            this._on_touchend = function (event) {
                if (!this._touch_moved) {
                    this._on_click(event)
                }
            }.bind(this)
            this._on_click = event => {
                let element = $(event.target);
                if (!element.closest('ul.level-2').is(dropdown) &&
                    !element.closest('ul.level-1 > li').is(li)) {
                    this._collapse_item(item)
                    return false
                }
            }
            $(document)
                .on('click', this._on_click)
                .on('touchstart', this._on_touchstart)
                .on('touchmove', this._on_touchmove)
                .on('touchend', this._on_touchend)
            return true
        }
        return super._expand_item(item, recourse)
    }

    _collapse_item(item) {
        if (item.closest('ul').hasClass('level-1')) {
            $(document)
                .off('click', this._on_click)
                .off('touchstart', this._on_touchstart)
                .off('touchmove', this._on_touchmove)
                .off('touchend', this._on_touchend)
        }
        super._collapse_item(item)
        item.closest('li').removeClass('script-expanded')
    }

}

wiking.MainMenuOrig = class extends lcg.Menu {

    _cmd_quit(event, item) {
        this._set_focus($('#main-heading'))
    }

}
