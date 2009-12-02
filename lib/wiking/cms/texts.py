# -*- coding: utf-8 -*-

# Copyright (C) 2009 Brailcom, o.p.s.
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
from cms import Text

_ = lcg.TranslatableTextFactory('wiking-cms')

disabled = Text('cms.disabled',
                # Translators: Web form label (account in the meaning of user account)
                _("Information about a locked account"),
                # Translators: Text presented to a user in a web page
                _("""Your account is currently disabled.

The protected services are not available to you.
Contact the application administrator to get the account enabled."""))

unconfirmed = Text('cms.unconfirmed',
                   # Translators: Web form label
                   _("Information about an account waiting for activation code confirmation"),
                   # Translators: Text presented to a user in a web page
                   _("""Your account is unverified since
you have not yet entered the activation code sent to you.

The protected services are not available until you enter the activation
code and the administrator confirms your account."""))

unapproved = Text('cms.unapproved',
                  # Translators: Web form label
                  _("Information about an account waiting for admin approval"),
                  # Translators: Text presented to a user in a web page
                  
                  _("""Your account is waiting for approval by the administrator.
                  
The protected services are not available until the account gets approved.
If the account remains unapproved for a long time, contact the application administrator."""))
