# Copyright (C) 2025 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import datetime
import logging
import re

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WebmailConversation(models.Model):
    _name = "webmail.conversation"
    _description = "Webmail Conversation"
    _rec_name = "subject"
    _order = "last_mail_date desc, subject"

    subject = fields.Char(compute="_compute_subject", store=True)

    mail_ids = fields.One2many(
        comodel_name="webmail.mail", inverse_name="conversation_id", readonly=True
    )

    mail_qty = fields.Integer(compute="_compute_mail_qty", store=True)

    first_mail_date = fields.Datetime(compute="_compute_dates", store=True)

    last_mail_date = fields.Datetime(compute="_compute_dates", store=True)

    last_mail_date_pretty = fields.Char(compute="_compute_last_mail_date_pretty")

    interlocutor_ids = fields.Many2many(
        comodel_name="webmail.contact", compute="_compute_interlocutor_ids"
    )

    content = fields.Html("Contents", compute="_compute_content")

    pending_answer = fields.Boolean(readonly=True)

    answer = fields.Html()

    unread = fields.Boolean()

    answer_contact_ids = fields.Many2many(comodel_name="webmail.contact")

    def button_write_answer(self):
        self.write({"pending_answer": True})

    def button_drop_answer(self):
        self.write({"pending_answer": False, "answer": False})

    @api.depends("mail_ids.content")
    def _compute_content(self):
        for conversation in self:
            conversation.content = "<hr/>".join(conversation.mapped("mail_ids.content"))

    @api.depends("mail_ids.author_contact_id")
    def _compute_interlocutor_ids(self):
        for conversation in self:
            conversation.interlocutor_ids = conversation.mapped(
                "mail_ids.author_contact_id"
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

    @api.depends("mail_ids.subject")
    def _compute_subject(self):
        for conversation in self.filtered(lambda x: x.subject is False):
            subjects = conversation.mapped("mail_ids.subject")
            subjects = [x for x in subjects if x]
            if not subjects:
                conversation.subject = _("No Subject")
            else:
                conversation.subject = self._clean_subject(subjects[0])

    @api.model
    def _clean_subject(self, subject):
        return re.sub(r"(((RE)|(Re)|(Fwd)|(TR)): )+", "", subject)

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

    def action_view_mails(self):
        mails = self.mapped("mail_ids")
        action = self.env["ir.actions.actions"]._for_xml_id(
            "webmail.action_webmail_mail"
        )
        action["domain"] = [("id", "in", mails.ids)]
        return action

    def button_merge(self):
        self._merge()

    def _merge(self):
        if len(self) <= 1:
            raise UserError(_("Merge conversation requires many conversation"))

        # Get the first
        first_conversation = self[-1:]
        other_conversations = self[:-1]

        # Move the mails
        other_conversations.mail_ids.conversation_id = first_conversation
        other_conversations.unlink()
        return first_conversation
