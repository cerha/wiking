/* -*- coding: utf-8 -*-
 *
 * Copyright (C) 2012-2017 OUI Technology Ltd.
 * Copyright (C) 2019, 2022 Tomáš Cerha <t.cerha@gmail.com>
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

"use strict";

wiking.Discussion = class {

    constructor(form_id, uri, field_name, attachment_field_name) {
        this._form_id = form_id
        this._uri = uri
        this._field_name = field_name
        this._attachment_field_name = attachment_field_name
        let form = lcg.widget_instance(form_id)
        if (form) {
            form.on_load(() => this._add_reply_buttons(form))
        }
    }

    _add_reply_buttons(form) {
        // Dynamically add reply buttons to a
        for (let div of form.element.find('.discussion-reply')) {
            let item = $(div).parents('.list-item')
            if (!item.find('.actions').length) {
                item.append('<div class="actions">')
            }
            item.find('.actions').prepend(
                $('<button class="reply">')
                    .on('click', event => this._on_reply(
                        item,
                        $(div).find('.id').text(), // comment_id
                        decodeURIComponent($(div).find('.quoted').text()),
                    ))
                    .append($('<span class="icon reply-icon">'))
                    .append($('<span class="label">').text(wiking._("Reply")))
            )
        }
    }

    _on_reply(item, comment_id, quoted) {
        if (item.find('form.edit-form').length) {
            return
        }
        let field_id = 'wiking-discussion-reply-' + comment_id
        let form = $(`<form action="${this._uri}/${comment_id}" method="POST" class="pytis-form edit-form">`)
            .append($('<div>')
                    .append($(`<label for=${field_id} class="field-label id-${this._field_name}">`)
                            .text(wiking._('Your Reply') + ':')))
            .append($(`<textarea class="fullsize" cols="80" rows="8" name="${this._field_name}"` +
                      ` id="${field_id}" aria-required="true">`))
            .hide()
        if (this._attachment_field_name) {
            form.attr('enctype', 'multipart/form-data').append(
                $('<div>').append([
                    $(`<label for="${field_id}-attachment" `+
                      ` class="field-label id-${this._attachment_field_name}">`)
                        .text(wiking._('Attachment') + ':'),
                    $(`<input type="file" size="50" name="${this._attachment_field_name}" ` +
                      ` id="${field_id}-attachment">`)
                ])
            )
        }
        form.append('<input type="hidden" name="action" value="reply">')
        let div = $('<div class="submit-buttons">')
        form.append(div)
        let buttons = [
            ['<button type="submit" value="1">', wiking._("Submit"), 'ok-icon', e => true],
            ['<button>', wiking._("Quote"), 'quote-icon', e => this._on_quote(form, quoted)],
            ['<button>', wiking._("Cancel"), 'remove-icon', e => this._on_cancel(form)],
        ]
        for (let [button, label, icon, callback] of buttons) {
            div.append($(button)
                       .append(`<span class="icon ${icon}">`)
                       .append($('<span class="label">').text(label))
                       .on('click', callback))
        }
        form.insertAfter(item)
        $('.actions button.reply').prop('disabled', true)
        form.slideDown({
            duration: 250,
            complete: () => form.find(`textarea[name="${this._field_name}"]`).focus(),
        })
    }

    _on_cancel(form) {
        form.slideUp({duration: 250, complete: () => form.remove()})
        $('.actions button.reply').prop('disabled', false)
        return false
    }

    _on_quote(form, quoted) {
        let field = form.find(`[name=${this._field_name}]`)
        let value = field.val()
        if (value) {
            if (value.substr(value.length - 1) !== '\n') {
                value += '\n'
            }
            value += quoted
        } else {
            value = quoted
        }
        field.val(value)
        field.focus()
        return false
    }

}
