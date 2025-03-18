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
        return "OK", [
            b'(\\HasChildren \\UnMarked) "/" Rang&AOk-',
            b'(\\HasNoChildren \\UnMarked) "/" Rang&AOk-/CIE',
            b'(\\HasNoChildren \\UnMarked) "/" Rang&AOk-/Coopaname',
        ]


class TestWebmailFetchData(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.webmail_account = cls.env.ref("webmail.demo_webmail_account")
        cls.webmail_folder = cls.env.ref("webmail.demo_webmail_folder")

    def test_connexion(self):
        with mock.patch("imaplib.IMAP4_SSL", return_value=FakeIMAPClient()):
            # Check Connexion
            self.webmail_account.button_test_connexion()
            self.assertEqual(len(self.webmail_account.folder_ids), 1)

            # Check Fetch Folders
            self.webmail_account.button_fetch_folders()
            folders = self.webmail_account.folder_ids
            self.assertEqual(len(folders), 4)
            self.assertIn("Rangé", folders.mapped("technical_name"))
            self.assertIn("Rangé/CIE", folders.mapped("technical_name"))
            self.assertIn("Rangé/Coopaname", folders.mapped("technical_name"))

            self.assertIn("Rangé", folders.mapped("name"))
            self.assertIn("CIE", folders.mapped("name"))
            self.assertIn("Coopaname", folders.mapped("name"))

            # Check Fetch Mails
            # TODO
