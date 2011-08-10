# -*- coding: utf-8 -*-

# Copyright (C) 2011 Brailcom, o.p.s.
#
# COPYRIGHT NOTICE
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import lcg
import wiking
from wiking.cms import CMSExtensionModule, Roles
import pytis.data as pd
from pytis.presentation import Action, Binding, Field, computer
import pytis.web as pw

_ = lcg.TranslatableTextFactory('wiking')

class CryptoNames(CMSExtensionModule):
    """Management of encryption passwords.

    This module just lists defined encryption areas.  The encryption areas are
    defined in the database by the application developer and can't be changed
    here.  The actual password managament is performed by CryptoKeys
    side-form module.

    """    
    class Spec(wiking.Specification):
        table = 'cms_crypto_names'
        title = _("Crypto Areas")
        def fields(self): return (
            Field('name', _("Name")),
            Field('description', _("Description")),
            )
        sorting = (('name', pd.ASCENDENT,),
                   )
        bindings = (Binding('keys', _("Users and Keys"), 'CryptoKeys',
                            binding_column='name'),
                    )

    RIGHTS_list = (Roles.ADMIN,)
    RIGHTS_view = (Roles.ADMIN,)
    RIGHTS_insert = ()
    RIGHTS_update = ()
    RIGHTS_delete = ()

class CryptoKeys(CMSExtensionModule):
    """Management of keys and users.

    It uses a special set of actions that resemble standard editing actions but
    are different from them:

    - Insert new key: This creates initial key for an encryption area.  This
      can be done only once for each of the areas.  The inserted keys can be
      given to other users using copy action.

    - Copy key: Copy an existing key to another user.

    - Change password: Change password of the key for the given user.

    - Delete key: Remove a user from the given key.  This can be only done if
      another copy of the key exists.

    All the actions are performed using special database functions.
    
    """
    class Spec(wiking.Specification):
        table = 'cms_crypto_keys'
        title = _("Users and Encryption Keys")
        def fields(self): return (
            Field('key_id', _("Id")),
            Field('name', _("Name")),
            Field('uid', _("User"), codebook='Users'),
            Field('new_uid', _("User"), codebook='Users', virtual=True),
            Field('key', _("Key")),
            Field('remove', _("Action"), virtual=True,
                  computer=computer(lambda r: _("Remove"))),
            Field('old_password', _("Current password"),
                  type=pd.Password, virtual=True),
            Field('new_password', _("New password"),
                  type=pd.Password, virtual=True),
            )
        sorting = (('uid', pd.ASCENDENT,),
                   )
        columns = ('uid',)

    _DB_FUNCTIONS = dict(CMSExtensionModule._DB_FUNCTIONS,
                         cms_crypto_delete_key=(('name_', pd.String(),),
                                                ('uid_', pd.Integer(),),
                                                ('force', pd.Boolean(),),),
                         cms_crypto_insert_key=(('name_', pd.String(),),
                                                ('uid_', pd.Integer(),),
                                                ('key_', pd.String(),),
                                                ('psw', pd.String(),),),
                         cms_crypto_copy_key=(('name_', pd.String(),),
                                              ('from_uid', pd.Integer(),),
                                              ('to_uid', pd.Integer(),),
                                              ('from_psw', pd.String(),),
                                              ('to_psw', pd.String(),),),
                         cms_crypto_change_password=(('id_', pd.Integer(),),
                                                     ('old_psw', pd.String(),),
                                                     ('new_psw', pd.String(),),),
                         )
    
    _ACTIONS = (wiking.Action(_("Create key"), 'insert_key', descr=_("Create new key")),
                wiking.Action(_("Add user"), 'copy_key', descr=_("Add another user of the key")),
                wiking.Action(_("Remove user"), 'delete_key', descr=_("Delete the key from the user")),
                wiking.Action(_("Change password"), 'change_password', descr=_("Change key password")),
                )

    _OWNER_COLUMN = 'uid'

    RIGHTS_list = (Roles.ADMIN,)
    RIGHTS_view = (Roles.ADMIN,)
    RIGHTS_insert = ()
    RIGHTS_update = ()
    RIGHTS_delete = ()
    RIGHTS_insert_key = (Roles.ADMIN,)
    RIGHTS_copy_key = (Roles.ADMIN,)
    RIGHTS_delete_key = (Roles.ADMIN,)
    RIGHTS_change_password = (Roles.OWNER,)

    def _layout(self, req, action, record=None):
        if action == 'insert_key':
            layout = ('name', 'uid', 'new_password',)
        elif action == 'copy_key':
            layout = ('name', 'uid', 'new_uid', 'old_password', 'new_password',)
        elif action == 'change_password':
            layout = ('name', 'uid', 'old_password', 'new_password',)
        else:
            layout = ('name', 'uid',)
        return layout
        
    def action_insert_key(self, req, record):
        if req.param('submit'):
            try:
                result = self._insert_key(req, record['name'], record['uid'], record['new_password'])
            except pd.DBException, e:
                req.message(self._error_message(*self._analyze_exception(e)), type=req.ERROR)
            else:
                if result:
                    message = _("Key inserted.")
                else:
                    message = _("Key already inserted, use copy action to add users.")
                req.message(message)
                raise wiking.Redirect(self._current_base_uri(req, record))
        form = self._form(pw.EditForm, req, record=record,
                          layout=('key_id', 'name', 'uid', 'new_password',))
        actions = (Action('insert_key', _("Insert"), submit=1),)
        action_menu = self._action_menu(req, record, actions)
        return self._document(req, [form, action_menu], record,
                              subtitle=self._action_subtitle(req, 'insert', record))

    def _insert_key(self, req, name, uid, new_password):
        key = self._module('Session').session_key(length=128)
        return self._call_db_function('cms_crypto_insert_key', name.value(), uid.value(), key,
                                      new_password.value())
        
    def action_copy_key(self, req, record):
        if req.param('submit'):
            try:
                result = self._copy_key(req, record['name'], record['uid'], record['to_uid'],
                                        record['old_password'], record['new_password'])
            except pd.DBException, e:
                req.message(self._error_message(*self._analyze_exception(e)), type=req.ERROR)
            else:
                if result:
                    message = _("Key copied.")
                else:
                    message = _("Copy failed.")
                req.message(message)
                raise wiking.Redirect(self._current_base_uri(req, record))
        form = self._form(pw.EditForm, req, record=record,
                          layout=('key_id', 'name', 'uid', 'to_uid', 'old_password', 'new_password',))
        actions = (Action('copy_key', _("Copy"), submit=1),)
        action_menu = self._action_menu(req, record, actions)
        return self._document(req, [form, action_menu], record,
                              subtitle=self._action_subtitle(req, 'copy', record))

    def _copy_key(self, req, name, uid, to_uid, old_password, new_password):
        return self._call_db_function('cms_crypto_copy_key', name.value(),
                                      uid.value(), to_uid.value(),
                                      old_password.value(), new_password.value())

    def action_delete_key(self, req, record):
        if req.param('submit'):
            try:
                result = self._delete_key(req, record['name'], record['uid'])
            except pd.DBException, e:
                req.message(self._error_message(*self._analyze_exception(e)), type=req.ERROR)
            else:
                if result:
                    message = _("User removed.")
                else:
                    message = _("This is the last key occurrence, user not removed.")
                req.message(message)
                raise wiking.Redirect(self._current_base_uri(req, record))
        form = self._form(pw.ShowForm, req, record=record,
                          layout=('key_id', 'name', 'uid',))
        req.message(_("Please, confirm user removal."))
        actions = (Action('delete_key', _("Remove"), submit=1),)
        action_menu = self._action_menu(req, record, actions)
        return self._document(req, [form, action_menu], record,
                              subtitle=self._action_subtitle(req, 'delete', record))

    def _delete_key(self, req, name, uid):
        return self._call_db_function('cms_crypto_delete_key', name.value(), uid.value(), False)

    def action_change_password(self, req, record):
        if req.param('submit'):
            try:
                result = self._change_password(req, record['key_id'],
                                               record['old_password'], record['new_password'])
            except pd.DBException, e:
                req.message(self._error_message(*self._analyze_exception(e)), type=req.ERROR)
            else:
                if result:
                    message = _("Password changed.")
                else:
                    message = _("Password change failed.")
                req.message(message)
                raise wiking.Redirect(self._current_base_uri(req, record))
        form = self._form(pw.EditForm, req, record=record,
                          layout=('key_id', 'name', 'uid', 'old_password', 'new_password',))
        actions = (Action('change_password', _("Change password"), submit=1),)
        action_menu = self._action_menu(req, record, actions)
        return self._document(req, [form, action_menu], record,
                              subtitle=self._action_subtitle(req, 'change_password', record))

    def _change_password(self, req, id_, old_password, new_password):
        return self._call_db_function('cms_crypto_change_password', id_.value(),
                                      old_password.value(), new_password.value())
