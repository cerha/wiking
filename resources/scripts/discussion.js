/* -*- coding: utf-8 -*-
 *
 * Copyright (C) 2012 Brailcom, o.p.s.
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

/* Javascript support for inline replies in a Wiking based discussion.
 *
 * The discussion listing is supposed to be a form generated using a
 * pytis.web.form.ListView Python class.  The code here dynamically adds a
 * "Reply" button to each comment in the discussion (dynamically because the
 * button only works when JavaScript is on, so we don't want it on the page at
 * all when JavaScript is off).  The button, when pressed, inserts a form for
 * entering a reply to given comment into the page just below the comment.
 * 
 * An instance of the Discussion class must be created below the exported pytis
 * form.  The new instance will automatically locate all '.discussion-reply'
 * elements in the document and bind Javascript handlers to the related HTML
 * elements of the discussion list.

*/

var Discussion = Class.create(wiking.Translatable, {

    initialize: function ($super, uri, field, translations) {
	$super(translations);
	this.uri = uri;
	this.field = field;
	$$('.discussion-reply').each(function (div) {
	    var comment_id = div.down('span.in-reply-to').innerHTML;
	    var quoted = decodeURIComponent(div.down('span.quoted').innerHTML);
	    var button = div.down('button.reply');
	    button.observe('click', function (event) { 
		this.on_reply(div, comment_id, quoted);
	    }.bind(this));
	}.bind(this));
    },

    on_reply: function (div, comment_id, quoted) {
	if (div.up('div.pytis-form').down('form'))
	    return;
        var form = new Element('form', {'action': this.uri,
					'method': 'POST',
     					'style': 'display: none',
					'class': 'pytis-form edit-form'});
	var field_id = 'wiking-discussion-reply-' + comment_id;
	var label = new Element('span', {'class': 'field-label id-'+this.field});
	label.insert(new Element('label', {'for': field_id}).update(this.gettext('Your Reply')));
	label.insert(new Element('sup', {'class': 'not-null'}).update('*'));
	label.insert(':');
	form.insert(label);
        form.insert(new Element('textarea', {'class': 'fullsize', 
     					     'cols': '80', 
     					     'rows': '8',
     					     'name': this.field,
					     'id': field_id,
     					     'aria-required': 'true'}));
        var hidden = [['action', 'insert'], 
     		      ['submit', 'submit'], 
     		      ['in_reply_to', comment_id]];
        hidden.each(function (x) {
     	    form.insert(new Element('input', {'type': 'hidden', 'name': x[0], 'value': x[1]}));
        });
	var buttons = [
	    ["Submit", {'type': 'submit', 'value': '1'}, 
	     function (event) {}],
	    ["Quote", {'onclick': 'return false;'}, 
	     function (event) { this.on_quote(form[this.field], quoted); }],
	    ["Cancel", {'onclick': 'return false;'}, 
	     function (event) { this.on_cancel(form); }]];
	var button_div = new Element('div', {'class': 'submit'});
	form.insert(button_div);
        buttons.each(function (x) {
            var button = new Element('button', x[1]).update(this.gettext(x[0]));
	    button.observe('click', x[2].bind(this));
            button_div.insert(button);
	}.bind(this));
	div.insert(form);
	$$('.discussion-reply button.reply').each(function(button) {
	    button.disable();
	});
	this.slide_down(form);
	var field = form[this.field];
	setTimeout(function () { field.focus(); }, 250);
    },

    on_cancel: function (form) {
	this.slide_up(form, true);
	if (typeof(Effect) != 'undefined')
	    setTimeout(function () { form.remove(); }, 200);
	else
	    form.remove();
	$$('.discussion-reply button.reply').each(function(button) {
	    button.enable();
	});
    },

    on_quote: function (field, quoted) {
	if (field.value) {
     	    if (field.value.substr(field.value.length-1) != '\n')
     		field.value += '\n';
     	    field.value += quoted;
        } else {
     	    field.value = quoted;
        }
        field.focus();
    },

    slide_up: function (element, duration) {
	if (typeof(Effect) != 'undefined') {
	    if (typeof(duration) == 'undefined')
		duration = 0.2;
	    new Effect.SlideUp(element, {duration: duration});
	} else {
	    element.hide();
	}
    },

    slide_down: function (element, duration) {
	if (typeof(Effect) != 'undefined') {
	    if (typeof(duration) == 'undefined')
		duration = 0.2
	    new Effect.SlideDown(element, {duration: duration});
	} else {
	    element.show();
	}
    }

});
