# Copyright (C) 2025 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import datetime
import imaplib
import logging
from time import time

from dateutil.relativedelta import relativedelta

from odoo import Command, _, api, fields, models, tools
from odoo.exceptions import UserError

from .tools import clean_subject

_logger = logging.getLogger(__name__)


# "mail.thread",
class WebmailConversation(models.Model):
    _name = "webmail.conversation"
    _inherit = ["mail.thread.main.attachment"]
    _description = "Webmail Conversation"
    _rec_name = "subject"
    _order = "last_mail_date desc, subject"

    account_id = fields.Many2one(
        comodel_name="webmail.account",
        ondelete="cascade",
        required=True,
        default=lambda x: x._default_account_id(),
    )

    mail_ids = fields.One2many(
        comodel_name="webmail.mail", inverse_name="conversation_id", readonly=True
    )

    mail_qty = fields.Integer(compute="_compute_mail_qty", store=True)

    tag_ids = fields.Many2many(string="Tags", comodel_name="webmail.tag")

    active = fields.Boolean(default=True)

    subject = fields.Char(compute="_compute_subject", store=True)

    first_mail_date = fields.Datetime(compute="_compute_dates", store=True)

    last_mail_date = fields.Datetime(compute="_compute_dates", store=True)

    last_mail_date_pretty = fields.Char(compute="_compute_last_mail_date_pretty")

    author_ids = fields.Many2many(
        string="Authors",
        comodel_name="webmail.contact",
        compute="_compute_author_ids",
        relation="webmail_conversation_contact_author_rel",
        store=True,
    )

    contact_ids = fields.Many2many(
        string="Interlocutors",
        comodel_name="webmail.contact",
        compute="_compute_contact_ids",
        relation="webmail_conversation_contact_contact_rel",
        store=True,
    )

    content = fields.Html("Contents", compute="_compute_content")

    message_state = fields.Selection(
        selection=[
            ("no", "No Message"),
            ("draft_message", "Draft Message"),
            ("draft_reply", "Draft Reply"),
            ("draft_forward", "Draft Forward"),
        ],
        default="draft_message",
        readonly=True,
    )

    message_subject = fields.Char()

    message_body = fields.Html()

    message_attachment_ids = fields.One2many(
        comodel_name="ir.attachment",
        inverse_name="res_id",
        domain=[("res_model", "=", "webmail.conversation")],
        string="Attachments",
    )

    message_nb_attachment = fields.Integer(
        string="Number of Attachments", compute="_compute_message_nb_attachment"
    )

    has_been_read = fields.Boolean(
        compute="_compute_has_been_read", store=True, inverse="_inverse_has_been_read"
    )

    to_contact_ids = fields.Many2many(
        comodel_name="webmail.contact",
        relation="webmail_conversation_webmail_contact_to_rel",
    )

    cc_contact_ids = fields.Many2many(
        comodel_name="webmail.contact",
        relation="webmail_conversation_webmail_contact_cc_rel",
    )

    read_me = fields.Boolean(
        prefetch=False,
        compute="_compute_read_me",
        help="Technical field, use to mark the conversation as read.",
    )

    # ###########################
    # Default Section
    # ###########################
    def _default_account_id(self):
        accounts = self.env["webmail.account"].search([])
        if len(accounts) == 1:
            return accounts[0]

    # ###########################
    # Overload Section
    # ###########################
    def write(self, vals):
        if "account_id" in vals:
            raise UserError(
                _("Unable to change 'Account' field on existing conversation.")
            )
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _on_delete(self):
        if self.env.context.get("erase_mail"):
            self.mapped("mail_ids").unlink()

    # ###########################
    # Compute & Inverse Section
    # ###########################
    def _compute_message_nb_attachment(self):
        attachment_data = self.env["ir.attachment"]._read_group(
            [("res_model", "=", "webmail.conversation"), ("res_id", "in", self.ids)],
            ["res_id"],
            ["__count"],
        )
        attachment = dict(attachment_data)
        for conversation in self:
            conversation.message_nb_attachment = attachment.get(
                conversation._origin.id, 0
            )

    def _compute_read_me(self):
        # Fake compute section
        # the field read me is computed only when conversation
        # form view is displayed.
        # we so "auto-mark-as-read" the conversation once it has been
        # opened
        for conversation in self:
            conversation.read_me = True
            conversation.has_been_read = True

    @api.depends("mail_ids.has_been_read")
    def _compute_has_been_read(self):
        for conversation in self:
            conversation.has_been_read = all(
                conversation.mapped("mail_ids.has_been_read")
            )

    def _inverse_has_been_read(self):
        for conversation in self:
            conversation.mapped("mail_ids").write(
                {"has_been_read": conversation.has_been_read}
            )

    @api.depends("mail_ids.date")
    def _compute_dates(self):
        for conversation in self:
            dates = conversation.mapped("mail_ids.date")
            conversation.first_mail_date = dates and min(dates) or False
            conversation.last_mail_date = dates and max(dates) or False

    @api.depends("mail_ids.conversation_id")
    def _compute_mail_qty(self):
        for conversation in self:
            conversation.mail_qty = len(conversation.mail_ids)

    @api.depends("mail_ids.body")
    def _compute_content(self):
        for conversation in self:
            conversation.content = "<hr/>".join(conversation.mapped("mail_ids.body"))

    @api.depends("mail_ids.author_contact_id")
    def _compute_author_ids(self):
        for conversation in self:
            conversation.author_ids = conversation.mapped("mail_ids.author_contact_id")

    @api.depends(
        "mail_ids.author_contact_id",
        "mail_ids.to_contact_ids",
        "mail_ids.cc_contact_ids",
    )
    def _compute_contact_ids(self):
        for conversation in self:
            conversation.contact_ids = (
                conversation.mapped("mail_ids.author_contact_id")
                | conversation.mapped("mail_ids.to_contact_ids")
                | conversation.mapped("mail_ids.cc_contact_ids")
            )

    @api.depends("last_mail_date")
    def _compute_last_mail_date_pretty(self):
        ctx_today = fields.Datetime.context_timestamp(
            self, fields.Datetime.from_string(datetime.datetime.today())
        )
        for conversation in self:
            if not conversation.last_mail_date:
                conversation.last_mail_date_pretty = ""
                continue

            ctx_date = fields.Datetime.context_timestamp(
                self, fields.Datetime.from_string(conversation.last_mail_date)
            )
            # last answer has been done today, displaying 'HH:MM'
            if (
                ctx_today.day == ctx_date.day
                and ctx_today.month == ctx_date.month
                and ctx_today.year == ctx_date.year
            ):
                conversation.last_mail_date_pretty = ctx_date.strftime("%H:%M")
                continue

            ctx_3m_date = fields.Datetime.context_timestamp(
                self,
                datetime.datetime(ctx_today.year, ctx_today.month, 1)
                + relativedelta(months=-2),
            )

            # last answer has been done in the 3 last monthes, displaying "DD month"
            if ctx_3m_date < ctx_date:
                conversation.last_mail_date_pretty = ctx_date.strftime("%-d %B")
                continue

            # last answer is old. displaying classic date
            conversation.last_mail_date_pretty = ctx_date.strftime("%d/%m/%Y")

    @api.depends("mail_ids.subject", "mail_qty", "message_subject")
    def _compute_subject(self):
        for conversation in self.filtered(lambda x: not x.mail_qty):
            # Conversation comes from mail we wrote
            conversation.subject = conversation.message_subject

        for conversation in self.filtered(lambda x: x.subject is False and x.mail_qty):
            # Conversation comes from external mails
            subjects = conversation.mapped("mail_ids.subject")
            subjects = [x for x in subjects if x]
            if not subjects:
                conversation.subject = _("No Subject")
            else:
                conversation.subject = clean_subject(subjects[0])

    # ###########################
    # Button and Action section
    # ###########################
    def button_mark_as_read(self):
        self.write({"has_been_read": True})

    def button_mark_as_unread(self):
        self.write({"has_been_unread": False})

    def button_merge(self):
        self._merge()

    def button_write_message(self):
        self.write(
            {
                "draft_message": True,
                "to_contact_ids": [],
                "cc_contact_ids": [],
                "message_subject": "",
            }
        )

    def button_answer_single(self):
        default_subject = False
        last_mail = self.mail_ids[0]
        if last_mail.author_contact_id.email != self.account_id.login:
            # Answer to a user that wrote a mail
            to_contacts = last_mail.author_contact_id
        else:
            # Send again mail to same people
            to_contacts = last_mail.to_contact_ids
        default_subject = last_mail.subject
        if not default_subject.lower().startswith("re: "):
            default_subject = f"Re: {default_subject}"
        self.write(
            {
                "draft_message": True,
                "to_contact_ids": [Command.set(to_contacts.ids)],
                "cc_contact_ids": [],
                "message_subject": default_subject,
            }
        )

    def button_answer_multi(self):
        self.button_answer_single()
        last_mail = self.mail_ids[0]
        cc_contacts = last_mail.to_contact_ids | last_mail.cc_contact_ids
        cc_contact_ids = [
            x.id
            for x in cc_contacts
            if x.email != self.account_id.login and x.id not in self.to_contact_ids.ids
        ]
        self.write(
            {
                "cc_contact_ids": [Command.set(cc_contact_ids)],
            }
        )

    def button_drop_draft_message(self):
        self.write(
            {
                "draft_message": False,
                "message_body": False,
                "to_contact_ids": [Command.clear()],
                "cc_contact_ids": [Command.clear()],
            }
        )

    def button_send_message(self):
        for conversation in self:
            conversation._send_message()
            conversation.button_drop_draft_message()

    def attach_document(self, **kwargs):
        """Code comes from hr.expense model"""
        self._message_set_main_attachment_id(
            self.env["ir.attachment"].browse(kwargs["attachment_ids"][-1:]), force=True
        )

    def action_view_mails(self):
        mails = self.mapped("mail_ids")
        action = self.env["ir.actions.actions"]._for_xml_id(
            "webmail.action_webmail_mail"
        )
        action["domain"] = [("id", "in", mails.ids)]
        return action

    # ###########################
    # Private section
    # ###########################
    def _merge(self, enable=False):
        if len(self) <= 1:
            raise UserError(_("Merge conversation requires many conversation"))

        # Get the first
        first_conversation = self[-1:]
        other_conversations = self[:-1]

        # Move the mails
        other_conversations.mail_ids.conversation_id = first_conversation
        first_conversation_vals = self._prepare_first_conversation_vals(
            first_conversation, other_conversations, enable=enable
        )
        other_conversations.unlink()
        if first_conversation_vals:
            first_conversation.write(first_conversation_vals)
        return first_conversation

    @api.model
    def _prepare_first_conversation_vals(
        self, first_conversation, other_conversations, enable=False
    ):
        vals = {}
        if not first_conversation.active:
            if enable or any(other_conversations.mapped("active")):
                vals.update({"active": True})
        extra_tag_ids = [
            x
            for x in other_conversations.mapped("tag_ids").ids
            if x not in first_conversation.tag_ids.ids
        ]
        if extra_tag_ids:
            vals.update({"tag_ids": [Command.link(tag_id) for tag_id in extra_tag_ids]})
        return vals

    def _send_message(self):
        self.ensure_one()
        if not self.message_subject:
            raise UserError(_("The field 'Subject' is required to send an email."))
        if not self.to_contact_ids:
            raise UserError(_("The field 'To' is required to send an email."))
        if not tools.html2plaintext(self.message_body):
            raise UserError(_("The field 'Body' is required to send an email."))

        attachments = [
            (a["name"], a["raw"], a["mimetype"])
            for a in self.message_attachment_ids.sudo().read(
                ["name", "raw", "mimetype"]
            )
            if a["raw"] is not False
        ]

        IrMailServer = self.env["ir.mail_server"]
        msg = IrMailServer.build_email(
            email_from=self.account_id.login,
            email_to=self.mapped("to_contact_ids.formatted_address"),
            email_cc=self.mapped("cc_contact_ids.formatted_address"),
            subject=self.message_subject,
            body=self.message_body,
            attachments=attachments,
            subtype="html",
        )
        if self.mail_qty:
            msg["In-Reply-To"] = self.mail_ids[-1].identifier
        # Send the email
        IrMailServer.send_email(
            msg,
            smtp_server=self.account_id.smtp_url,
            smtp_port=self.account_id.smtp_port,
            smtp_user=self.account_id.login,
            smtp_password=self.account_id.password,
            smtp_encryption="ssl",
        )
        # Store the email in the 'Sent' folder Locally
        sent_folder = self.env["webmail.folder"].search(
            [
                ("account_id", "=", self.account_id.id),
                ("technical_name", "=", "Sent"),
            ]
        )
        self.env["webmail.mail"]._create_or_update_mail(
            sent_folder, msg, conversation=self
        )

        # Store the email in the 'Sent' folder of the folder
        client = self.account_id._get_imap_client_connected()
        client.append(
            "Sent", "", imaplib.Time2Internaldate(time()), str(msg).encode("utf-8")
        )
        client.logout()
