/* -*- coding: utf-8 -*-
 *
 * Copyright (C) 2012-2017 OUI Technology Ltd.
 * Copyright (C) 2019 Tomáš Cerha <t.cerha@gmail.com>
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

/* Javascript support for inline replies in a Wiking based discussion.
 *
 * The discussion listing is supposed to be a form generated using a
 * pytis.web.form.ListView Python class.  The code here dynamically adds a
 * "Reply" button to each comment in the discussion (dynamically because the
 * button only works when JavaScript is on, so we don't want it on the page at
 * all when JavaScript is off).  The button, when pressed, inserts a form for
 * entering a reply to given comment into the page just below the comment.
 *
 * An instance of the wiking.Discussion class must be created below the exported
 * pytis form.  The new instance will automatically locate all
 * '.discussion-reply' elements in the document and bind Javascript handlers
 * to the related HTML elements of the discussion list.
 */

/*jshint browser: true */
/*jshint es3: true */
/*eslint no-unused-vars: 0 */
/*global Class */
/*global Element */
/*global Effect */
/*global $ */
/*global $$ */
/*global wiking */

"use strict";

var Discussion = Class.create({

    initialize: function (form_id, uri, field, attachment_field) {
        this.form = $(form_id);
        this.uri = uri;
        this.field = field;
        if (attachment_field === undefined) {
            attachment_field = null;
        }
        this.attachment_field = attachment_field;
        if (this.form.instance) {
            this.form.instance.on_load(this.add_reply_buttons.bind(this));
        }
    },

    add_reply_buttons: function () {
        // Dynamically add reply buttons to a
        this.form.select('.discussion-reply').each(function (div) {
            var comment_id = div.down('span.id').innerHTML;
            var quoted = decodeURIComponent(div.down('span.quoted').innerHTML);
            var item = div.up('.list-item');
            var actions = item.down('.actions');
            if (actions === null) {
                actions = new Element('div', {'class': 'actions'});
                item.insert(actions);
            }
            var button = new Element('button', {'class': 'reply'});
            button.insert(new Element('span', {'class': 'icon reply-icon'}));
            button.insert(new Element('span', {'class': 'label'}).update(wiking._("Reply")));
            button.observe('click', function (event) {
                this.on_reply(item, comment_id, quoted);
            }.bind(this));
            actions.insert({'top': button});
        }.bind(this));
    },

    on_reply: function (item, comment_id, quoted) {
        if (item.down('form.edit-form')) {
            return;
        }
        var form = new Element('form', {'action': this.uri+'/'+comment_id,
                                        'method': 'POST',
                                        'style': 'display: none',
                                        'class': 'pytis-form edit-form'});
        var field_id = 'wiking-discussion-reply-' + comment_id;
        form.insert(new Element('div').insert(
            new Element('label', {'for': field_id,
                                  'class': 'field-label id-'+this.field}).update(
                                      wiking._('Your Reply') + ':')));
        form.insert(new Element('textarea', {'class': 'fullsize',
                                             'cols': '80',
                                             'rows': '8',
                                             'name': this.field,
                                             'id': field_id,
                                             'aria-required': 'true'}));
        if (this.attachment_field !== null) {
            form.setAttribute('enctype', 'multipart/form-data');
            var attachment_field_id = field_id + 'attachment';
            var adiv = new Element('div');
            adiv.insert(new Element('label', {'for': attachment_field_id,
                                              'class': 'field-label id-' + this.attachment_field})
                        .update(wiking._('Attachment') + ':'));
            adiv.insert(new Element('input', {'type': 'file',
                                              'size': '50',
                                              'name': this.attachment_field,
                                              'id': attachment_field_id}));
            form.insert(adiv);
        }
        form.insert(new Element('input', {'type': 'hidden', 'name': 'action', 'value': 'reply'}));
        var buttons = [
            [wiking._("Submit"), 'ok-icon', {'type': 'submit', 'value': '1'},
             function (event) { return; }],
            [wiking._("Quote"), 'quote-icon', {'onclick': 'return false;'},
             function (event) { this.on_quote(form[this.field], quoted); }],
            [wiking._("Cancel"), 'remove-icon', {'onclick': 'return false;'},
             function (event) { this.on_cancel(form); }]];
        var div = new Element('div', {'class': 'submit-buttons'});
        form.insert(div);
        buttons.each(function (x) {
            var button = new Element('button', x[2]);
            button.insert(new Element('span', {'class': 'icon ' + x[1]}));
            button.insert(new Element('span', {'class': 'label'}).update(x[0]));
            button.observe('click', x[3].bind(this));
            div.insert(button);
        }.bind(this));
        item.insert({after: form});
        $$('.actions button.reply').each(function(button) {
            button.disable();
        });
        this.slide_down(form);
        var field = form[this.field];
        setTimeout(function () { field.focus(); }, 250);
    },

    on_cancel: function (form) {
        this.slide_up(form, true);
        if (Effect !== undefined) {
            setTimeout(function () { form.remove(); }, 200);
        } else {
            form.remove();
        }
        $$('.actions button.reply').each(function(button) {
            button.enable();
        });
    },

    on_quote: function (field, quoted) {
        if (field.value) {
            if (field.value.substr(field.value.length-1) !== '\n') {
                field.value += '\n';
            }
            field.value += quoted;
        } else {
            field.value = quoted;
        }
        field.focus();
    },

    slide_up: function (element, duration) {
        if (Effect !== undefined) {
            if (duration === undefined) {
                duration = 0.2;
            }
            new Effect.SlideUp(element, {duration: duration});
        } else {
            element.hide();
        }
    },

    slide_down: function (element, duration) {
        if (Effect !== undefined) {
            if (duration === undefined) {
                duration = 0.2;
            }
            new Effect.SlideDown(element, {duration: duration});
        } else {
            element.show();
        }
    }

});
