# Copyright (C) 2023 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from freezegun import freeze_time

from odoo.tests.common import TransactionCase


class TestMailDataAnalysis(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.mail_1 = cls.env.ref("webmail.demo_webmail_mail_1")
        cls.conversation = cls.mail_1.conversation_id

    def test_last_mail_date_pretty(self):
        self.conversation.mail_ids.write({"date": "2025-04-01 09:44:00"})
        freezer = freeze_time("2025-04-01 13:55:00")
        freezer.start()
        self.conversation._compute_last_mail_date_pretty()
        self.assertEqual(self.conversation.last_mail_date_pretty, "11:44")
        freezer.stop()

        freezer = freeze_time("2025-04-02 12:00:00")
        freezer.start()
        self.conversation._compute_last_mail_date_pretty()
        self.assertIn(self.conversation.last_mail_date_pretty, ["1 avril", "1 April"])
        freezer.stop()

        freezer = freeze_time("2025-07-01 00:00:00")
        freezer.start()
        self.conversation._compute_last_mail_date_pretty()
        self.assertEqual(self.conversation.last_mail_date_pretty, "01/04/2025")
        freezer.stop()
