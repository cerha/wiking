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
 * The API is simple.  An instance of the Discussion class must be created
 * first and then the method 'init_reply()' must be called for each comment,
 * passing it the comment_id (to be sent with the reply text as a reference to
 * the comment being replied to.

*/

var Discussion = Class.create(wiking.Translatable, {

    initialize: function ($super, uri, field, translations, autohide) {
	$super(translations);
	this.uri = uri;
	this.field = field;
	this.autohide = (typeof(autohide) == 'undefined' ? false : autohide);
    },

    init_reply: function (element_id, comment_id, quoted) {
	var div = $(element_id).up('div.list-item');
	if (this.autohide) {
	    div.observe('mouseover', function(event) { 
		this.on_mouseover(div, comment_id, quoted);
	    }.bind(this));
	    div.observe('mouseout', function(event) { 
		this.on_mouseout(event, div);
	    }.bind(this));
	} else {
	    var button = this.create_reply_button(div, comment_id, quoted);
	    button.show();
	}
    },

    create_reply_button: function (div, comment_id, quoted) {
	var button = new Element('button', {'onclick': 'return false;'});
	button.insert(new Element('span').update(this.gettext('Reply')));
	button.observe('click', function (event) { 
	    this.on_reply(div, comment_id, quoted);
	}.bind(this));
	button_div = new Element('div', {'style': 'display: none',
					 'class': 'reply-button'}).insert(button)
	div.insert(button_div);
	return button_div;
    },

    on_mouseover: function (div, comment_id, quoted) {
	var form = div.up('div.pytis-form').down('form');
	if (!form) {
	    var button = div.down('.reply-button');
	    if (!button)
		button = this.create_reply_button(div, comment_id, quoted);
	    if (!button.visible()) {
		this.slide_down(button);
	    }
	}
    },

    on_mouseout: function (event, div) {
	// Note, the mousout event is generated also for the elements inside
	// the div, so we must find out ourselves whether the mouse really has
	// really left the div (silly, isn't it?).
	var x = event.pointerX();
	var y = event.pointerY();
	var offset = div.cumulativeOffset();
	var size = div.getDimensions();
	if (!(x > offset.left && x < offset.left+size.width &&  
	      y > offset.top  && y < offset.top+size.height)) {
	    var button = div.down('.reply-button');
	    if (button && button.visible())
		this.slide_up(button);
	}
    },

    on_reply: function (div, comment_id, quoted) {
	if (this.autohide)
            div.down('.reply-button').hide();
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
	if (!this.autohide)
	    $$('.reply-button button').each(function(button) {
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
	if (!this.autohide)
	    $$('.reply-button button').each(function(button) {
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
