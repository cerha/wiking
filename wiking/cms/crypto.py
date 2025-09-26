# -*- coding: utf-8 -*-
#
# Copyright (C) 2011, 2012, 2013, 2015 OUI Technology Ltd.
# Copyright (C) 2019, 2020 Tomáš Cerha <t.cerha@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
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
from pytis.presentation import Editable, Field, Action, SelectionType, computer
import pytis.web as pw

_ = lcg.TranslatableTextFactory('wiking-cms')


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

        def fields(self):
            return (
                Field('name', _("Name")),
                Field('description', _("Description")),
            )
        sorting = (('name', pd.ASCENDENT,),
                   )
        bindings = (wiking.Binding('keys', _("Users and Keys"), 'CryptoKeys', 'name',
                                   form=pw.ItemizedView),
                    )

    def _authorized(self, req, action, **kwargs):
        if action in ('view', 'list'):
            return req.check_roles(Roles.CRYPTO_ADMIN)
        else:
            return False


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

        def fields(self):
            return (
                Field('key_id', _("Id"), editable=Editable.NEVER),
                Field('name', _("Name"), not_null=True,
                      codebook='CryptoNames', editable=Editable.NEVER),
                Field('uid', _("User"), not_null=True, codebook='Users',
                      selection_type=SelectionType.CHOICE, editable=Editable.ONCE),
                Field('new_uid', _("New user"), not_null=True, codebook='Users',
                      selection_type=SelectionType.CHOICE, type=pd.Integer,
                      virtual=True, runtime_filter=computer(self._new_uid_filter)),
                Field('key', _("Key")),
                Field('remove', _("Action"), virtual=True,
                      computer=computer(lambda r: _("Remove"))),
                Field('old_password', _("Current password"),
                      type=pd.Password, verify=False, virtual=True),
                Field('new_password', _("New password"),
                      type=pd.Password, virtual=True),
                Field('delete', virtual=True, computer=computer(lambda row: _("Remove"))),
            )

        def _new_uid_filter(self, row, name):
            assigned_users = wiking.module(self._resolver).assigned_users(row['name'])
            return pd.AND(*[pd.NE('uid', u) for u in assigned_users])
        sorting = (('uid', pd.ASCENDENT,),
                   ('name', pd.ASCENDENT,),
                   )
        columns = ('uid', 'name', 'delete',)
        actions = (
            Action('password', _("Change password"), descr=_("Change key password")),
            Action('adduser', _("Copy to user"), descr=_("Add another user of the key")),
        )

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

    _TITLE_COLUMN = 'uid'
    _INSERT_LABEL = _("Create key")

    def _authorized(self, req, action, record=None, **kwargs):
        if action == 'view':
            return req.check_roles(Roles.CRYPTO_ADMIN) or self._check_uid(req, record, 'uid')
        elif action == 'password':
            return self._check_uid(req, record, 'uid')
        elif action in ('list', 'insert', 'delete', 'adduser'):
            return req.check_roles(Roles.CRYPTO_ADMIN)
        else:
            return False

    def _prefill(self, req):
        return dict(super(CryptoKeys, self)._prefill(req),
                    uid=req.user().uid())

    def _layout(self, req, action, record=None):
        if action == 'insert':
            layout = ('name', 'uid', 'new_password',)
        elif action == 'adduser':
            layout = ('key_id', 'name', 'uid', 'new_uid', 'old_password', 'new_password',)
        elif action == 'password':
            layout = ('key_id', 'name', 'uid', 'old_password', 'new_password',)
        else:
            layout = ('name', 'uid',)
        return layout

    def _columns(self, req):
        columns = super(CryptoKeys, self)._columns(req)
        if not req.has_param('_crypto_name'):
            columns = [c for c in columns if c != 'delete']
        return columns

    def _link_provider(self, req, uri, record, cid, **kwargs):
        if cid == 'delete':
            return req.make_uri(uri, key_id=record['key_id'].value(), action='delete')
        else:
            return super(CryptoKeys, self)._link_provider(req, uri, record, cid, **kwargs)

    def _list_form_kwargs(self, req, form_cls):
        kwargs = super(CryptoKeys, self)._list_form_kwargs(req, form_cls)
        if issubclass(form_cls, pw.ItemizedView) and req.check_roles(Roles.USER_ADMIN):
            kwargs['template'] = lcg.TranslatableText("%%(%s)s [%%(delete)s]" % self._TITLE_COLUMN)
        return kwargs

    def related(self, req, binding, record, uri):
        if 'name' in record:
            req.set_param('_crypto_name', record['name'])
        return super(CryptoKeys, self).related(req, binding, record, uri)

    def _actions(self, req, record):
        actions = super(CryptoKeys, self)._actions(req, record)
        if record is None and req.has_param('_crypto_name'):
            condition = pd.EQ('name', req.param('_crypto_name'))
            try:
                count = self._data.select(condition)
            finally:
                try:
                    self._data.close()
                except Exception:
                    pass
            if count > 0:
                actions = [a for a in actions if a.id() != 'insert']
        return actions

    def _insert(self, req, record, transaction):
        key = wiking.generate_random_string(256)
        if not self._call_db_function('cms_crypto_insert_key',
                                      record['name'].value(),
                                      record['uid'].value(),
                                      key,
                                      record['new_password'].value(),
                                      transaction=transaction):
            raise pd.DBException(_("New key not created. Maybe it already exists?"))

    def _update(self, req, record, transaction):
        action = req.param('action')
        if action == 'password':
            if not self._call_db_function('cms_crypto_change_password',
                                          record['key_id'].value(),
                                          record['old_password'].value(),
                                          record['new_password'].value(),
                                          transaction=transaction):
                raise pd.DBException(_("Password not changed. Maybe invalid old password?"))
        elif action == 'adduser':
            if not self._call_db_function('cms_crypto_copy_key',
                                          record['name'].value(),
                                          record['uid'].value(),
                                          record['new_uid'].value(),
                                          record['old_password'].value(),
                                          record['new_password'].value(),
                                          transaction=transaction):
                raise pd.DBException(_("User not added. Maybe invalid old password?"))
        else:
            raise Exception('Unexpected action', action)

    def _delete(self, req, record, transaction):
        if not self._call_db_function('cms_crypto_delete_key',
                                      record['name'].value(),
                                      record['uid'].value(),
                                      False,
                                      transaction=transaction):
            raise pd.DBException(_("The user couldn't be deleted. "
                                   "Maybe he is the last key holder?"))

    def action_adduser(self, req, record, action='adduser'):
        return super(CryptoKeys, self).action_update(req, record, action=action)

    def action_password(self, req, record=None):
        return self.action_update(req, record=record, action='password')

    def assigned_users(self, name):
        # Internal method for Spec class, don't use it elsewhere
        return self._data.select_map(lambda row: row['uid'], condition=pd.EQ('name', name))

    def assigned_names(self, uid):
        """Return sequence of crypto names assigned to user identified by uid.

        Arguments:

          uid -- user uid, integer

        """
        return self._data.select_map(lambda row: row['name'], condition=pd.EQ('uid', pd.ival(uid)))

    def clear_crypto_passwords(self, req, user):
        # Just a hack to allow clearing passwords on logout
        req.set_cookie(self._CRYPTO_COOKIE, None, secure=True)
        self._call_db_function('cms_crypto_lock_passwords', user.uid())
