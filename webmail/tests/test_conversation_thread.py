# Copyright (C) 2025 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestConversationThread(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.webmail_account = cls.env.ref("webmail.demo_webmail_account")
        cls.folder_inbox = cls.env.ref("webmail.demo_folder_inbox")
        cls.WebmailConversation = cls.env["webmail.conversation"]
        cls.WebmailMail = cls.env["webmail.mail"]

    def _create_mail(self, identifier, reply_identifier):
        return self.WebmailMail.create(
            {
                "date": fields.Datetime.now() - timedelta(days=20 - int(identifier)),
                "subject": f"Subject {identifier}",
                "identifier": identifier,
                "reply_identifier": reply_identifier,
                "folder_id": self.folder_inbox.id,
                "from_text": "from@test.fr",
            }
        )

    def _getConversations(self):
        return self.WebmailConversation.search([])

    def test_conversation_creation(self):
        self.assertEqual(
            len(self._getConversations()),
            0,
            "Without any action, No conversation should be created.",
        )

        # ############
        # Create the Mail "10"
        # ############
        mail_10 = self._create_mail("10", "9")
        conv_A = self._getConversations()
        self.assertEqual(
            len(conv_A), 1, "Create a New mail should create a Conversation"
        )
        self.assertIn(
            mail_10.id,
            conv_A.mail_ids.ids,
            "The first mail should be part of the created conversation",
        )
        self.assertEqual(
            conv_A.subject,
            "Subject 10",
            "The first mail should give the name to the conversation",
        )

        # ############
        # Create a mail "11" as an answer of the Mail "10"
        # ############
        mail_11 = self._create_mail("11", "10")
        self.assertIn(
            mail_11.id,
            conv_A.mail_ids.ids,
            "A direct answer should joint the original conversation",
        )
        self.assertEqual(
            conv_A.subject,
            "Subject 10",
            "Next mail should not give the name to the conversation",
        )

        # ############
        # Create a mail "9" that is the original mail of the first mail "10"
        # ############
        mail_9 = self._create_mail("9", "8")
        self.assertIn(
            mail_9.id,
            conv_A.mail_ids.ids,
            "Direct original mail created after should join the original conversation",
        )
        self.assertEqual(
            conv_A.subject,
            "Subject 10",
            "Previous mail should not give the name to the conversation",
        )

        # ############
        # Create a mail "7" that is in the same conversation,
        # but system can not know it at this step, because mail "8"
        # doesn't exist.
        # ############
        mail_7 = self._create_mail("7", "6")
        conv_B = mail_7.conversation_id
        self.assertNotEqual(
            conv_A,
            conv_B,
            "Create a mail that breaks thread should create a new conversation.",
        )
        self.assertEqual(
            len(conv_B.mail_ids),
            1,
            "The new conversation should contain only the new mail.",
        )
        self.assertEqual(
            conv_B.subject,
            "Subject 7",
            "Next mail should not give the name to the conversation",
        )

        # ############
        # Create a mail "8" that is in the same conversation,
        # System should now merge the two conversations.
        # ############
        mail_7 = self._create_mail("8", "7")
        conv_MERGED = self._getConversations()
        self.assertEqual(
            len(conv_MERGED),
            1,
            "The two previous conversations should be merged.",
        )
        self.assertEqual(
            len(conv_MERGED.mail_ids),
            5,
            "the new conversation should contains all the previous mails.",
        )
        self.assertEqual(
            conv_MERGED.subject,
            "Subject 7",
            "The merged conversation should have the subject of the older mail.",
        )
