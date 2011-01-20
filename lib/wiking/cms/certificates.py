# -*- coding: utf-8 -*-
# Copyright (C) 2006-2010 Brailcom, o.p.s.
# Author: Milan Zamazal
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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Support for certificate administration and authentication.

This code is currently unused.  If it is ever needed again, it is necessary to re-inregrate it into
Wiking CMS.  It was taken out from cms.py on 2009-05-07, so the other related changes can be found
in the version control system history.

"""

from wiking.cms import *

import cStringIO
import os
import subprocess
import mx.DateTime

import pytis.data
from pytis.presentation import computer, Computer, Fields, Field
from lcg import log as debug

ONCE = pp.Editable.ONCE
NEVER = pp.Editable.NEVER
ALWAYS = pp.Editable.ALWAYS
ASC = pd.ASCENDENT
DESC = pd.DESCENDANT

# Strings for this domain will not be translated until this module is unused.
_ = lcg.TranslatableTextFactory('wiking-cms-certificates') 


def _certificate_mail_info(record):
    text = _("To generate the request, you can use the OpenSSL package "
             "and the attached OpenSSL configuration file.\n"
             "In such a case use the following command to generate the certificate "
             "request, assuming your private key is stored in a file named `key.pem':")
    text += ("\n\n"
             "  openssl req -utf8 -new -key key.pem -out request.pem -config openssl.cnf\n\n")
    text += ("If you don't have a private key, you can generate one together with the "
             "certificate request using the following command:\n\n"
             "  openssl req -utf8 -newkey rsa:2048 -keyout key.pem -out request.pem"
             " -config openssl.cnf\n\n")
    attachment = "openssl.cnf"
    user_name = '%s %s' % (record['firstname'].value(), record['surname'].value(),)
    user_email = record['email'].value()
    attachment_stream = cStringIO.StringIO(str (
                '''[ req ]
distinguished_name  = req_distinguished_name
attributes          = req_attributes
x509_extensions     = v3_ca
prompt              = no
string_mask         = utf8only
[ req_distinguished_name ]
CN                  = %s
emailAddress       = %s
[ req_attributes ]
[ usr_cert ]
[ v3_req ]
basicConstraints   = CA:FALSE
nsCertType        = client
keyUsage           = keyEncipherment
[ v3_ca ]

[ crl_ext ]
''' % (user_name, user_email,)))
    return text, attachment, attachment_stream


class Certificates(CMSModule):
    """Base class of classes handling various kinds of certificates."""

    class UniType(pytis.data.Type):
        """Universal type able to contain any value.

        This is just a utility type for internal use within 'Certificates'
        class, without implementing any of the 'Type' methods.

        """

    class Spec(Specification):

        def __init__(self, *args, **kwargs):
            Specification.__init__(self, *args, **kwargs)
            self._ca_x509 = None

        _ID_COLUMN = 'certificates_id'
        
        def fields(self): return (
            Field(self._ID_COLUMN, width=8, editable=NEVER),
            Field('file', _("PEM file"), virtual=True, editable=ALWAYS,
                  type=pytis.data.Binary(not_null=True, maxlen=10000),
                  descr=_("Upload a PEM file containing the certificate")),
            Field('certificate', _("Certificate"), width=60, height=20, editable=NEVER,
                  computer=Computer(self._certificate_computer, depends=('file',))),
            Field('x509', _("X509 structure"), virtual=True, editable=NEVER, type=Certificates.UniType(),
                  computer=Computer(self._x509_computer, depends=('certificate',))),
            Field('serial_number', _("Serial number"), editable=NEVER,
                  computer=self._make_x509_computer(self._serial_number_computer)),
            Field('text', _("Certificate"), width=60, height=20, editable=NEVER,
                  computer=self._make_x509_computer(self._text_computer)),
            Field('issuer', _("Certification Authority"), width=32, editable=NEVER,
                  computer=self._make_x509_computer(self._issuer_computer)),
            Field('valid_from', _("Valid from"), editable=NEVER,
                  computer=self._make_x509_computer(self._valid_from_computer)),
            Field('valid_until', _("Valid until"), editable=NEVER,
                  computer=self._make_x509_computer(self._valid_until_computer)),
            Field('trusted', _("Trusted"), default=False,
                  descr=_("When this is checked, certificates signed by this root certificate are considered valid.")),
            )
        
        columns = ('issuer', 'valid_from', 'valid_until', 'trusted',)
        sorting = (('issuer', ASC,), ('valid_until', ASC,))
        layout = ('trusted', 'issuer', 'valid_from', 'valid_until', 'text',)

        def _certificate_computation(self, buffer):
            return str(buffer)
        def _certificate_computer(self, record):
            file_value = record['file'].value()
            if file_value is None: # new record form
                return None
            certificate = self._certificate_computation(file_value.buffer())
            return certificate
        def _x509_computer(self, record):
            import gnutls.crypto
            if self._ca_x509 is None:
                self._ca_x509 = gnutls.crypto.X509Certificate(open(cfg.ca_certificate_file).read())
            certificate = record['certificate'].value()
            if certificate is None: # new record form
                return None
            try:
                x509 = gnutls.crypto.X509Certificate(certificate)
            except Exception, e:
                raise Exception(_("Invalid certificate"), e)
            if not x509.has_issuer(x509) and not x509.has_issuer(self._ca_x509):
                x509 = None
            return x509
        def _make_x509_computer(self, function):
            def func(record):
                x509 = record['x509'].value()
                if x509 is None:
                    return None
                return function(x509)
            return Computer(func, depends=('x509',))
        def _serial_number_computer(self, x509):
            number = int(x509.serial_number)
            if not isinstance(number, int): # it may be long
                raise Exception(_("Unprocessable serial number"))
            return number
        def _issuer_computer(self, x509):
            return unicode(x509.issuer)
        def _valid_from_computer(self, x509):
            return self._convert_x509_timestamp(x509.activation_time)
        def _valid_until_computer(self, x509):
            return self._convert_x509_timestamp(x509.expiration_time)
        def _text_computer(self, x509):
            return ('Subject: %s\nIssuer: %s\nSerial number: %s\nVersion: %s\nValid from: %s\nValid until: %s\n' %
                    (x509.subject, x509.issuer, x509.serial_number, x509.version, time.ctime(x509.activation_time), time.ctime(x509.expiration_time),))
        def _convert_x509_timestamp(self, timestamp):
            time_tuple = time.gmtime(timestamp)
            mx_time = mx.DateTime.DateTime(*time_tuple[:6])
            return mx_time
            
        def check(self, record):
            x509 = record['x509'].value()
            if x509 is None:
                return ('file', _("The certificate is not valid"),)
                
    RIGHTS_view = (Roles.ADMIN,)
    RIGHTS_list = (Roles.ADMIN,)
    RIGHTS_rss  = (Roles.ADMIN,)
    RIGHTS_insert = (Roles.ADMIN,)
    RIGHTS_update = (Roles.ADMIN,)
    RIGHTS_delete = (Roles.ADMIN,)
        
    _LAYOUT = {'insert': ('file',)}

class CACertificates(Certificates):
    """Management of root certificates."""
    
    class Spec(Certificates.Spec):
        
        _ID_COLUMN = 'cacertificates_id'

        table = 'cacertificates'
        title = _("CA Certificates")
        help = _("Manage trusted root certificates.")
        
        def check(self, record):
            error = Certificates.Spec.check(self, record)
            if error is not None:
                return error
            x509 = record['x509'].value()
            if x509.check_ca() != 1:
                return ('file', _("This is not a CA certificate."))
        
    _LAYOUT = {'insert': ('file',)}

    
class UserCertificates(Certificates):
    """Management of user certificates, especially for the purpose of authentication."""

    class Spec(Certificates.Spec):
        
        title = _("User Certificates")
        help = _("Manage user and other kinds of certificates.")
        table = 'certificates'
        
        _PURPOSE_AUTHENTICATION = 1

        def fields(self):
            fields = Certificates.Spec.fields(self)
            fields = fields + (Field('subject', _("Subject"), virtual=True, editable=NEVER, type=Certificates.UniType(),
                                     computer=self._make_x509_computer(self._subject_computer)),
                               Field('common_name', _("Name"), editable=NEVER,
                                     computer=Computer(self._common_name_computer, depends=('subject',))),
                               Field('email', _("E-mail"), editable=NEVER,
                                     computer=Computer(self._email_computer, depends=('subject',))),
                               Field('uid', not_null=True),
                               Field('purpose', not_null=True),
                               )
            return fields

        _OWNER_COLUMN = 'uid'
        columns = ('common_name', 'valid_from', 'valid_until', 'trusted',)
        layout = ('trusted', 'common_name', 'email', 'issuer', 'valid_from', 'valid_until', 'text',)

        def _subject_computer(self, x509):
            return x509.subject
        def _common_name_computer(self, record):
            subject = record['subject'].value()
            if subject is None:
                return ''
            return subject.common_name
        def _email_computer(self, record):
            subject = record['subject'].value()
            if subject is None:
                return ''
            return subject.email

    def authentication_certificate(self, uid):
        """Return authentication certificate row of the given user.

        The return value is the corresponding 'pytis.data.Row' instance.  If
        the user doesn't have authentication certificate assigned, return
        'None'.

        This method considers only authentication certificates.  Certificates
        present for other purposes are ignored.

        Arguments:

          uid -- user id as an integer

        """
        data = self._data
        uid_value = pd.Value(data.find_column('uid').type(), uid)
        purpose_value = pd.Value(data.find_column('purpose').type(), self.Spec._PURPOSE_AUTHENTICATION)
        try:
            self._data.select(pd.AND(pd.EQ('uid', uid_value), pd.EQ('purpose', purpose_value)))
            row = self._data.fetchone()
        finally:
            try:
                self._data.close()
            except:
                pass
        return row

    def certificate_user(self, req, certificate):
        """Return user corresponding to 'certificate' and request 'req'.

        If there is no such user, return 'None'.

        The method assumes the certificate has already been verified by site CA
        certificate, so no verification is performed.

        Arguments:

          req -- 'Request' instance to provide for construction of the user object
          certificate -- PEM encoded certificate verified against the site's CA
            certificate, a string
        
        """
        user = None
        import gnutls.crypto
        x509 = gnutls.crypto.X509Certificate(certificate)
        serial_number = int(x509.serial_number)
        row = self._data.get_row(serial_number=serial_number)
        if row is not None:
            uid = row['uid'].value()
            user_module = self._module('Users')
            user_record = user_module.find_user(req, uid)
            user = user_module.user(req, user_record['login'].value())
        return user

class CertificateRequest(UserCertificates):

    class Spec(UserCertificates.Spec):
        # This is a *public* method.  But it has to begin with underscore
        # otherwise it would be handled in a special way by Wiking, causing
        # failure.
        # Comment by TC: This is not a good practice.  Specification shouldnt care about DB
        # connection.  The code that needs it should be defined at the module level.
        def _set_dbconnection(self, dbconnection):
            self._serial_number_counter = pd.DBCounterDefault('certificate_serial_number', dbconnection)
            
        def fields(self):
            fields = pp.Fields(UserCertificates.Spec.fields(self))
            overridden = [Field(inherit=fields['file'], descr=_("Upload a PEM file containing the certificate request")),
                          Field(inherit=fields['purpose'], default=self._PURPOSE_AUTHENTICATION)]
            # We add some fields to propagate last form values to the new request
            extra = [Field('regcode', type=pytis.data.String(), virtual=True)]
            return fields.fields(override=overridden) + extra            

        def _certificate_computation(self, buffer):
            serial_number = self._serial_number_counter.next()
            working_dir = os.path.join(cfg.storage, 'certificate-%d' % (serial_number,))
            request_file = os.path.join(working_dir, 'request')
            certificate_file = os.path.join(working_dir, 'certificate.pem')
            log_file = os.path.join(working_dir, 'log')
            template_file = os.path.join(working_dir, 'certtool.cfg')
            os.mkdir(working_dir)
            try:
                stdout = open(log_file, 'w')
                open(request_file, 'w').write(str(buffer))
                open(template_file, 'w').write('serial = %s\nexpiration_days = %s\ntls_www_client\n' %
                                               (serial_number, cfg.certificate_expiration_days,))
                return_code = subprocess.call(('/usr/bin/certtool', '--generate-certificate',
                                               '--load-request', request_file,
                                               '--outfile', certificate_file,
                                               '--load-ca-certificate', cfg.ca_certificate_file, '--load-ca-privkey', cfg.ca_key_file,
                                               '--template', template_file,),
                                              stdout=stdout, stderr=stdout)
                if return_code != 0:
                    raise Exception(_("Certificate request could not be processed"), open(log_file).read())
                certificate = open(certificate_file).read()
            finally:
                for file_name in os.listdir(working_dir):
                    os.remove(os.path.join(working_dir, file_name))
                os.rmdir(working_dir)
            return certificate
    
    def _spec(self, resolver):
        spec = super(CertificateRequest, self)._spec(resolver)
        spec._set_dbconnection(self._dbconnection)
        return spec

    def _layout(self, req, action, record=None):
        # This is necessary to propagate `uid' given in the form to the actual
        # data row
        if action == 'insert' and req.param('submit'):
            return ('uid', 'file',)
        else:
            return super(CertificateRequest, self)._layout(req, action, record)

    def _document_title(self, req, record):
        return _("Certificate upload")


# Related configuration options:
    #class _Option_certificate_expiration_days(pc.NumericOption, pc.HiddenOption):
    #    _DESCR = "Number of days to make signed certificates valid."
    #    _DOC = ("User authentication certificates signed by our local certificate authority "
    #            "will be made valid for that number of days.")
    #    _DEFAULT = 5*365
    # 
    #class _Option_ca_certificate_file(pc.StringOption, pc.HiddenOption):
    #    _DESCR = "Name of the file containing the local certification authority certificate."
    #    _DOC = ("This certificate is used to sign users' certificates used for authentication to the application.")
    #    _DEFAULT = '/etc/wiking/ca-cert.pem'
    # 
    #class _Option_ca_key_file(pc.StringOption, pc.HiddenOption):
    #    _DESCR = "Name of the file containing the key corresponding to the local certification authority certificate."
    #    _DOC = ("This is the secret certificate private key.")
    #    _DEFAULT = '/etc/wiking/ca-key.pem'
    # 
    #class _Option_certificate_authentication(pc.BooleanOption, pc.HiddenOption):
    #    _DESCR = "Whether certificate authentication is enabled."
    #    def default(self):
    #        ca_certificate_file = self._configuration.ca_certificate_file
    #        return ca_certificate_file and os.path.exists(ca_certificate_file)
    
