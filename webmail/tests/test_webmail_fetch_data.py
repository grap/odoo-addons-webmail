# Copyright (C) 2023 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import datetime
from unittest import mock

from markupsafe import Markup

from odoo.tests.common import TransactionCase

from .mail_data import mail_data_1


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
            b'(\\HasNoChildren) "/" "&ALI-&-&AOk-(-&AOg-_&AOcA4A-)=^$*&APk-,;:!<"',
        ]

    def select(self, arg1):
        return ("OK", [b"1"])

    def search(self, arg1, arg2):
        return ("OK", [b"1"])

    def fetch(self, arg1, arg2):
        return ("OK", [(b"2 (RFC822 {3335}", mail_data_1)])


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
            self.assertEqual(len(folders), 5)
            self.assertIn("Rangé", folders.mapped("technical_name"))
            self.assertIn("Rangé/CIE", folders.mapped("technical_name"))
            self.assertIn("Rangé/Coopaname", folders.mapped("technical_name"))
            self.assertIn("²&é(-è_çà)=^$*ù,;:!<", folders.mapped("technical_name"))

            self.assertIn("Rangé", folders.mapped("name"))
            self.assertIn("CIE", folders.mapped("name"))
            self.assertIn("Coopaname", folders.mapped("name"))

            cie_folder = self.webmail_account.folder_ids.filtered(
                lambda x: x.name == "CIE"
            )
            self.assertEqual(len(cie_folder.mail_ids), 0)
            cie_folder.button_fetch_mails()
            self.assertEqual(len(cie_folder.mail_ids), 1)
            mail = cie_folder.mail_ids
            self.assertEqual(
                mail.identifier, "<6b7ab563-d0af-455d-b2d9-1c98f5cd70d9@grap.coop>"
            )
            self.assertEqual(mail.date, datetime.datetime(2025, 3, 18, 0, 51, 33))
            self.assertEqual(mail.subject, "Test Subject")
            self.assertEqual(
                mail.from_text, '"Bob LEPONGE (GRAP)" <bob.leponge@grap.coop>'
            )
            self.assertEqual(mail.to_text, "bob.leponge@grap.coop")
            self.assertEqual(
                mail.body,
                Markup(
                    "<div>\r\n"
                    "    <p><b>Test</b> <i>Body.</i></p>\r\n"
                    "    <p><i><br>\r\n"
                    "      </i></p>\r\n"
                    "  </div>\r\n"
                ),
            )

            self.assertEqual(mail.conversation_id.subject, "Test Subject")
            self.assertEqual(mail.conversation_id.mail_qty, 1)
