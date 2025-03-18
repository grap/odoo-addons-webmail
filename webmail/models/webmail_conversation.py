# Copyright (C) 2025 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WebmailConversation(models.Model):
    _name = "webmail.conversation"
    _description = "Webmail Conversation"
    _rec_name = "subject"
    _order = "date desc, subject"

    subject = fields.Char(compute="_compute_subject", store=True)

    mail_ids = fields.One2many(
        comodel_name="webmail.mail", inverse_name="conversation_id", readonly=True
    )

    mail_qty = fields.Integer(compute="_compute_mail_qty", store=True)

    date = fields.Datetime(compute="_compute_dates", store=True)

    last_answer_date = fields.Datetime(compute="_compute_dates", store=True)

    @api.depends("mail_ids.subject")
    def _compute_subject(self):
        for conversation in self.filtered(lambda x: x.subject is False):
            re_prefixes = r"(((Re)|(Fwd)|(TR)): )+"
            subjects = conversation.mapped("mail_ids.subject")
            subjects = [x for x in subjects if x]
            if not subjects:
                conversation.subject = _("No Subject")
            else:
                conversation.subject = re.sub(re_prefixes, "", subjects[0])

    @api.depends("mail_ids.date")
    def _compute_dates(self):
        for conversation in self:
            dates = conversation.mapped("mail_ids.date")
            conversation.date = min(dates)
            conversation.last_answer_date = min(dates)

    @api.depends("mail_ids.conversation_id")
    def _compute_mail_qty(self):
        for conversation in self:
            conversation.mail_qty = len(conversation.mail_ids)

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
