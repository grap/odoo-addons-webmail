# Copyright (C) 2023 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import email
import hashlib
import logging

from odoo import api, fields, models
from odoo.osv import expression
from odoo.tools.mail import decode_message_header, email_split_and_format

_logger = logging.getLogger(__name__)


class WebmailMail(models.Model):
    _name = "webmail.mail"
    _inherit = ["mail.thread"]
    _description = "Webmail Mail"
    _order = "date desc"
    _rec_name = "subject"

    folder_id = fields.Many2one(
        comodel_name="webmail.folder",
        ondelete="cascade",
        required=True,
        readonly=True,
    )

    account_id = fields.Many2one(
        comodel_name="webmail.account",
        related="folder_id.account_id",
        ondelete="cascade",
        readonly=True,
        store=True,
    )

    conversation_id = fields.Many2one(
        compute="_compute_conversation_id",
        comodel_name="webmail.conversation",
        store=True,
        readonly=True,
    )

    user_id = fields.Many2one(
        comodel_name="res.users",
        related="folder_id.user_id",
        store=True,
        readonly=True,
    )

    identifier = fields.Char(required=True, readonly=True)

    reply_identifier = fields.Char(readonly=True)

    origin_mail_id = fields.Many2one(
        comodel_name="webmail.mail",
        compute="_compute_origin_mail_id",
        store=True,
        precompute=True,
    )
    data = fields.Text(readonly=True)

    # Extra Mail Fields
    date = fields.Datetime(required=True, readonly=True)

    subject = fields.Char(readonly=True)

    from_text = fields.Char(readonly=True)

    original_from_text = fields.Char(readonly=True)

    author_contact_id = fields.Many2one(
        comodel_name="webmail.contact",
        compute="_compute_author_contact_id",
        store=True,
        ondelete="set null",
    )

    to_text = fields.Char(readonly=True)

    cc_text = fields.Char(readonly=True)

    body = fields.Html(readonly=True, sanitize_style=True)

    content = fields.Html(compute="_compute_content")

    has_been_read = fields.Boolean()

    # #######################
    # Compute Section
    # #######################
    @api.depends("body")
    def _compute_content(self):
        for mail in self:
            mail.content = mail.body

    @api.depends("from_text", "original_from_text")
    def _compute_author_contact_id(self):
        for mail in self:
            mail.author_contact_id = self.env["webmail.contact"]._get_or_create(
                mail.original_from_text or mail.from_text
            )

    @api.depends("reply_identifier")
    def _compute_origin_mail_id(self):
        for mail in self:
            origin_mail = self.search([("identifier", "=", mail.reply_identifier)])
            mail.origin_mail_id = origin_mail.id

    @api.depends("identifier", "reply_identifier")
    def _compute_conversation_id(self):
        for mail in self:
            domain = expression.OR(
                [
                    [("identifier", "=", mail.reply_identifier)],
                    [("reply_identifier", "=", mail.identifier)],
                ]
            )
            if mail.reply_identifier:
                domain = expression.OR(
                    [
                        domain,
                        [("reply_identifier", "=", mail.reply_identifier)],
                    ]
                )

            domain = expression.AND([domain, [("account_id", "=", mail.account_id.id)]])

            other_mails = self.search(domain)
            existing_conversations = other_mails.mapped("conversation_id")
            if len(existing_conversations) == 0:
                # That's a new thread, creating a new conversation
                _logger.info(
                    f"[ANALYZE] subject: {mail.subject}. Creating new conversation."
                )
                mail.conversation_id = (
                    self.env["webmail.conversation"]
                    .create({mail._prepare_conversation()})
                    .id
                )

            elif len(existing_conversations) == 1:
                _logger.info(
                    f"[ANALYZE] subject: {mail.subject}. Found existing conversation."
                )
                mail.conversation_id = other_mails.mapped("conversation_id")[0].id
            else:
                _logger.info(
                    f"[ANALYZE] subject: {mail.subject}. Found many conversations."
                )
                mail.conversation_id = existing_conversations._merge().id

    # #######################
    # Overload Section
    # #######################
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for mail in records:
            other_mails = self.search([("reply_identifier", "=", mail.identifier)])
            if other_mails:
                other_mails.write({"origin_mail_id": mail.id})
        return records

    # #######################
    # Private Section
    # #######################
    def _create_or_update_mail(self, webmail_folder, mail_data):
        email_message = email.message_from_bytes(mail_data, policy=email.policy.default)
        data = email_message.as_string()

        identifier = self._get_identifier_from_message(email_message, mail_data)
        existing_mail = self.search([("identifier", "=", identifier)])
        if existing_mail:
            # If mail exists, we just handle the use case where the mail
            # has moved from a folder to another, in the Mailbox.
            if existing_mail.folder_id != webmail_folder:
                existing_mail.write({"folder_id": webmail_folder.id})
            return existing_mail

        message_dict = self.env["mail.thread"].message_parse(email_message)

        if "X-Original-From" in email_message.keys():
            message_dict["x_original_from"] = email_split_and_format(
                decode_message_header(email_message, "X-Original-From", separator=",")
            )

        # Check if mail exists in Odoo
        vals = {
            "identifier": identifier,
            "reply_identifier": email_message["In-Reply-To"],
            "date": message_dict["date"],
            "data": data,
            "folder_id": webmail_folder.id,
            "subject": message_dict.get("subject"),
            "original_from_text": message_dict.get("x_original_from"),
            "from_text": message_dict["from"],
            "to_text": message_dict["to"],
            "cc_text": message_dict["cc"],
            "body": message_dict["body"],
        }

        _logger.debug(
            f"[FETCH] {webmail_folder.account_id.login} /"
            f" {webmail_folder.technical_name}:"
            f" Creation of mail {identifier}."
        )
        webmail_folder.account_id.user_id.notify_info(
            title="New mail", message=f"<b>Subject</b>{message_dict.get('subject')}"
        )
        mail = self.create(vals)
        if message_dict["attachments"]:
            res = self.env["mail.thread"]._process_attachments_for_post(
                message_dict["attachments"],
                [],
                {"model": "webmail.mail", "res_id": mail.id, "body": vals["body"]},
            )
            if "body" in res and res["body"] != vals["body"]:
                mail.write({"body": res["body"]})
        return mail

    @api.model
    def _get_identifier_from_message(self, email_message, message_bytes):
        """Extract Message-ID field from message data.
        This field is like a unique ID for email systems.
        In rare case, this fields is not set. In that case,
        we generate a unique text, based on an hash of the email data."""
        identifier = email_message["Message-ID"]
        if not identifier:
            identifier = hashlib.sha256(message_bytes).hexdigest()
        return identifier

    def _prepare_conversation(self):
        self.ensure_one()
        return {
            "account_id": self.account_id.id,
        }
