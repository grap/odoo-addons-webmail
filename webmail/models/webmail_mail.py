# Copyright (C) 2023 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import datetime
import email
import hashlib
import logging

import imap_tools

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
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

    to_contact_ids = fields.Many2many(
        relation="webmail_contact_webmail_mail_to_rel",
        comodel_name="webmail.contact",
        compute="_compute_to_contacts",
        store=True,
    )
    to_contact_qty = fields.Integer(compute="_compute_to_contacts", store=True)

    cc_contact_ids = fields.Many2many(
        relation="webmail_contact_webmail_mail_cc_rel",
        comodel_name="webmail.contact",
        compute="_compute_cc_contacts",
        store=True,
    )

    cc_contact_qty = fields.Integer(compute="_compute_cc_contacts", store=True)

    author_avatar_256 = fields.Image(related="author_contact_id.avatar_256")

    to_text = fields.Char(readonly=True)

    cc_text = fields.Char(readonly=True)

    body = fields.Html(readonly=True, sanitize_style=True)

    has_been_read = fields.Boolean()

    counter_text = fields.Char(compute="_compute_counter_text")

    contact_qty = fields.Integer(compute="_compute_contact_qty", store=True)

    # #######################
    # Compute Section
    # #######################
    @api.depends("conversation_id.mail_ids")
    def _compute_counter_text(self):
        for mail in self:
            total = mail.conversation_id.mail_qty
            counter = total - mail.conversation_id.mail_ids.ids.index(mail.id)
            mail.counter_text = f"{counter} / {total}"

    @api.depends("from_text", "original_from_text")
    def _compute_author_contact_id(self):
        for mail in self:
            mail.author_contact_id = self.env["webmail.contact"]._get_or_create(
                mail.original_from_text or mail.from_text
            )

    @api.depends("to_text")
    def _compute_to_contacts(self):
        for mail in self.filtered(lambda x: x.to_text):
            contacts = self.env["webmail.contact"]
            for string in email_split_and_format(mail.to_text):
                contacts |= self.env["webmail.contact"]._get_or_create(string)
            mail.to_contact_ids = [Command.set(contacts.ids)]
            mail.to_contact_qty = len(mail.to_contact_ids)

    @api.depends("cc_text")
    def _compute_cc_contacts(self):
        for mail in self.filtered(lambda x: x.cc_text):
            contacts = self.env["webmail.contact"]
            for string in email_split_and_format(mail.cc_text):
                contacts |= self.env["webmail.contact"]._get_or_create(string)
            mail.cc_contact_ids = [Command.set(contacts.ids)]
            mail.cc_contact_qty = len(mail.cc_contact_ids)

    @api.depends("author_contact_id", "to_contact_ids", "cc_contact_ids")
    def _compute_contact_qty(self):
        for mail in self:
            mail.contact_qty = len(
                set(
                    (
                        mail.author_contact_id
                        | mail.to_contact_ids
                        | mail.cc_contact_ids
                    ).ids
                )
            )

    @api.depends("reply_identifier")
    def _compute_origin_mail_id(self):
        for mail in self:
            origin_mail = self.search([("identifier", "=", mail.reply_identifier)])
            mail.origin_mail_id = origin_mail.id

    @api.depends("identifier", "reply_identifier")
    def _compute_conversation_id(self):
        for mail in self.filtered(lambda x: not x.conversation_id):
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
                    .create(mail._prepare_conversation())
                    .id
                )

            elif len(existing_conversations) == 1:
                _logger.info(
                    f"[ANALYZE] subject: {mail.subject}. Found existing conversation."
                )
                mail.conversation_id = other_mails.mapped("conversation_id")[0].id
                if not mail.conversation_id.active:
                    mail.conversation_id.active = True
            else:
                _logger.info(
                    f"[ANALYZE] subject: {mail.subject}. Found many conversations."
                )
                mail.conversation_id = existing_conversations._merge(enable=True).id

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

    @api.ondelete(at_uninstall=False)
    def _on_delete(self):
        original_contacts = (
            self.mapped("author_contact_id")
            | self.mapped("cc_contact_ids")
            | self.mapped("to_contact_ids")
        )
        if self.env.context.get("erase_mail"):
            self._erase_mail()
        to_delete_contacts = original_contacts.filtered(
            lambda x: x.author_mail_qty == 0
        )
        if to_delete_contacts:
            _logger.info(f"Deleting {len(to_delete_contacts)} unused contacts ...")
            to_delete_contacts.unlink()

    # #######################
    # Private Section
    # #######################
    def _create_or_update_mail(self, webmail_folder, email_message, conversation=False):
        identifier = self._get_identifier_from_message(email_message)
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
            "data": email_message.as_string(),
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

        if conversation:
            vals["conversation_id"] = conversation.id
        else:
            webmail_folder.account_id.user_id.notify_info(
                title="New mail",
                message=f"<b>Subject</b><br />{message_dict.get('subject')}",
                sticky=True,
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
    def _get_identifier_from_message(self, email_message):
        """Extract Message-ID field from message data.
        This field is like a unique ID for email systems.
        In rare case, this fields is not set. In that case,
        we generate a unique text, based on an hash of the email data."""
        identifier = email_message.get("Message-ID")
        if not identifier:
            identifier = hashlib.sha256(email_message.as_string()).hexdigest()
        return identifier

    def _prepare_conversation(self):
        self.ensure_one()
        return {
            "account_id": self.account_id.id,
            "draft_message": False,
        }

    def _erase_mail(self):
        if len(self.mapped("account_id")) > 1:
            raise UserError(
                _("Unable to erase mail in many imap accounts in the same time.")
            )
        client = self.mapped("account_id")._get_imap_client_connected()
        for mail in self:
            num = mail._find_mail(client)
            if num:
                client.store(num, "+FLAGS", "\\Deleted")
            else:
                mail.account_id.user_id.notify_danger(
                    _(
                        f"Mail {mail.subject}. ({mail.identifier}"
                        f" not found in the folder {mail.folder_id.complete_name})"
                    ),
                    sticky=True,
                )
        client.expunge()
        client.close()
        client.logout()

    def _find_mail(self, client):
        """Find an email in the distant imap folder and return then 'num'
        of the email, or False if not found."""
        self.ensure_one()
        client.select(self.folder_id.technical_name)

        # First, look by Message-ID
        status, search_result = client.search(
            None, f'(HEADER Message-ID "{self.identifier}")'
        )
        if status == "OK" and len(search_result) == 1 and search_result[0] != b"":
            return search_result[0]

        mail_date = datetime.date(self.date.year, self.date.month, self.date.day)

        domain = str(
            imap_tools.AND(
                date_gte=mail_date + datetime.timedelta(days=-1),
                date_lt=mail_date + datetime.timedelta(days=+1),
            )
        )
        client.search(None, domain)
        status, search_result = client.search(None, domain)

        if status == "OK":
            num_list = search_result[0].split()
            for num in num_list:
                status, mail_data = client.fetch(
                    num, "(BODY[HEADER.FIELDS (MESSAGE-ID)])"
                )
                email_message = email.message_from_bytes(
                    mail_data[0][1], policy=email.policy.default
                )
                if email_message.get("Message-ID") == self.identifier:
                    return num

        return False
