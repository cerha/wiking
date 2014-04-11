/* -*- coding: utf-8 -*-
 *
 * Copyright (C) 2014 Brailcom, o.p.s.
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

/*jslint browser: true */
/*jslint unparam: true */
/*global Class */
/*global Element */
/*global Effect */
/*global $ */
/*global wiking */

"use strict";

wiking.cms = {};

wiking.cms.PublicationExportForm = Class.create({
    initialize: function (form_id) {
	var form = $(form_id);
	var select = form.down('select[name="format"]');
	this.form = form;
	this.braille_options = form.down('.label-braille-export-options');
	select.down('option[value=""]').remove();
	if (select.value !== 'braille') {
	    this.braille_options.hide();
	}
	select.observe('change', this.on_format_change.bind(this));
	form.down('select[name="printer"]').down('option[value=""]').remove();
    },

    on_format_change: function (event) {
	if (event.element().value === 'braille') {
	    // The effect seems strange because the fieldset label moves beyond the box...
	    //if (Effect !== undefined) {
	    //    new Effect.SlideDown(this.braille_options, {duration: 0.2});
	    //} else {
	    this.braille_options.show();
	    //}
	} else {
	    //if (Effect !== undefined) {
	    //	new Effect.SlideUp(this.braille_options, {duration: 0.2});
	    //} else {
	    this.braille_options.hide();
	    //}
	}
    }
});
