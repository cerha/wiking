/* -*- coding: utf-8 -*-
 *
 * Copyright (C) 2014-2016 OUI Technology Ltd.
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

"use strict"

wiking.cms = {
    _: lcg.gettext('wiking-cms'),
}

wiking.cms.PublicationExportForm = class extends lcg.Widget {
    constructor(element_id) {
        super(element_id)
        this.element.find('select[name="printer"] option[value=""]').remove()
        this.element.find('input[name="format"]').on('change', e => this._update_options())
        let test_button = this.element.find('button[type="submit"][name="test"]')
        if (test_button.length) {
            test_button.on('click', this._start_test_export.bind(this))
            this.element.find('button[type="submit"]:not([name="test"])').prop('disabled', true)
        }
        this._update_options()
    }

    _update_options() {
        let options = {
            braille: this.element.find('.label-braille-export-options'),
            epub: this.element.find('.label-epub-export-options'),
            pdf: this.element.find('.label-pdf-export-options'),
        }
        let format = this.element.find('input:checked[name="format"]').val()
        if (format === 'epub') {
            options.braille.hide()
            options.pdf.hide ()
            options.epub.show()
        } else if (format === 'braille') {
            options.pdf.hide ()
            options.epub.hide()
            options.braille.show()
        } else if (format === 'pdf') {
            options.braille.hide()
            options.epub.hide()
            options.pdf.show()
        }
    }

    _start_test_export(event) {
        this.element.find('.export-progress-summary').remove()
        this.element.find('div.export-progress-log')
            .empty()
            .append($('<div class="info-msg">').text(wiking.cms._("Export started...")))
        this._ajax({
            form: this.element.find('form'),
            data: {submit: 'test'},
        }, this._on_test_result.bind(this))
        return false
    }

    _on_test_result(data, status, xhr) {
        // Show test results in reaction to previously sent AJAX request.
        let log = this.element.find('div.export-progress-log')
        if (data.messages) {
            let labels = {WARNING: wiking.cms._("Warning"),
                          ERROR: wiking.cms._("Error")}
            for (let [kind, message] of data.messages) {
                let div = $(`<div class="${kind.toLowerCase()}-msg">`)
                let label = labels[kind]
                if (label) {
                    div.append($('<span class="label">').text(label + ':'))
                    div.append(' ')
                }
                div.append(message)
                log.append(div)
            }
        }
        if (data.summary) {
            $('<div class="export-progress-summary">')
                .append($('<span class="label">').text(wiking.cms._("Summary") + ':'))
                .append(' ' + data.summary)
                .insertAfter(log)
        }
        log.append($('<div class="info-msg">').text(wiking.cms._("Export finished.")))
        this.element.find('button[type="submit"]:not([name="test"])').prop('disabled', false)
    }

}
