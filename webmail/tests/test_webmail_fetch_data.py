# Copyright 2017 ACSONE SA/NV
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).


from unittest import mock

from odoo.tests.common import TransactionCase


class FakeIMAPClient:
    def login(self, login, password):
        pass

    def logout(self):
        return

    def close(self):
        return

    def list(self):
        return "OK", []


class TestWebmailBadConnexion(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.webmail_account = cls.env.ref("webmail.demo_webmail_account")
        cls.webmail_folder = cls.env.ref("webmail.demo_webmail_folder")

    def test_connexion(self):
        with mock.patch("imaplib.IMAP4_SSL", return_value=FakeIMAPClient()):
            self.webmail_account.button_test_connexion()
            self.webmail_account.button_fetch_folders()
            # TODO, create folder and check
            # TODO, create mail and check
