/* -*- coding: utf-8 -*-
 *
 * Copyright (C) 2014-2016 OUI Technology Ltd.
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

/* global Class, Element, Gettext, $, wiking */

"use strict";

wiking.cms = {};
wiking.cms.gettext = new Gettext({domain: 'wiking-cms'});
wiking.cms._ = function (msg) { return wiking.cms.gettext.gettext(msg); };

wiking.cms.PublicationExportForm = Class.create({
    initialize: function (form_id) {
        var form = $(form_id);
        this._form = form;
        this._braille_options = form.down('.label-braille-export-options');
        this._epub_options = form.down('.label-epub-export-options');
        this._pdf_options = form.down('.label-pdf-export-options');
        var format = form.down('input:checked[name="format"]').value;
        this._show_options(format);
        form.on('change', 'input[name="format"]', this._on_format_change.bind(this));
        form.down('select[name="printer"] option[value=""]').remove();
        var test_button = form.down('button[type="submit"][name="test"]');
        if (test_button) {
            test_button.on('click', this._on_test_button.bind(this));
            form.down('button[type="submit"][name=""]').disable();
        }
    },

    _on_format_change: function (event, element) {
        this._show_options(event.element().value);
    },

    _show_options: function (format) {
        if (format != 'epub') {
            this._epub_options.hide();
        }
        if (format != 'braille') {
            this._braille_options.hide();
        }
        if (format != 'pdf') {
            this._pdf_options.hide ();
        }
        if (format === 'epub') {
            this._epub_options.show();
        } else if (format === 'braille') {
            this._braille_options.show();
        } else if (format === 'pdf') {
            this._pdf_options.show();
        }
    },

    _on_test_button: function (event) {
        document.body.style.cursor = "wait";
        this._form.down('form').request({parameters: {submit: 'test'},
                                        onSuccess: this._on_test_result.bind(this)});
        var container = this._form.down('div.export-progress-log');
        container.select('div').each(function (e) { e.remove(); });
        this._form.select('.export-progress-summary').each(function (e) { e.remove(); });
        container.insert(
            new Element('div', {'class': 'info-msg'}).update(wiking.cms._("Export started..."))
        );
        event.stop();
    },

    _on_test_result: function(response) {
        // Show test results in reaction to previously sent AJAX request.
        try {
            var data = response.responseJSON;
            var container = this._form.down('div.export-progress-log');
            if (data.messages) {
                var labels = {WARNING: wiking.cms._("Warning"),
                              ERROR: wiking.cms._("Error")};
                data.messages.each(function(msg) {
                    var kind = msg[0], message = msg[1];
                    var label = labels[kind];
                    var div = new Element('div', {'class': kind.toLowerCase() + '-msg'});
                    if (label) {
                        div.insert(new Element('span', {'class': 'label'}).update(label+':'));
                        div.insert(' ');
                    }
                    div.insert(message);
                    container.insert(div);
                });
            }
            if (data.summary) {
                var div = new Element('div', {'class': 'export-progress-summary'});
                div.insert(new Element('span', {'class': 'label'}).update(wiking.cms._("Summary")+':'));
                div.insert(' ' + data.summary);
                container.up().insert(div, {after: container});
            }
            container.insert(
                new Element('div', {'class': 'info-msg'}).update(wiking.cms._("Export finished."))
            );
            this._form.down('button[type="submit"][name=""]').enable();
        } catch (e) {
            // Errors in asynchronous handlers are otherwise silently ignored.
            console.log(e);
        }
        document.body.style.cursor = "default";
    }

});
