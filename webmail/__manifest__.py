# Copyright (C) 2023 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Webmail",
    "summary": "Odoo as a Webmail",
    "version": "18.0.1.2.0",
    "category": "R&D",
    "author": "GRAP, OaaFS",
    "maintainers": ["legalsylvain"],
    "website": "https://github.com/grap/odoo-addons-webmail",
    "license": "AGPL-3",
    "depends": [
        "mail",
        # OCA
        "queue_job",
        "web_notify",
    ],
    "external_dependencies": {"python": ["imapclient", "beautifulsoup4", "imap-tools"]},
    "data": [
        "security/ir_module_category.xml",
        "security/ir_rule.xml",
        "security/res_groups.xml",
        "security/ir.model.access.csv",
        "data/webmail_provider.xml",
        "views/menu.xml",
        "views/view_webmail_account.xml",
        "views/view_webmail_provider.xml",
        "views/view_webmail_tag.xml",
        "views/view_webmail_folder.xml",
        "views/view_webmail_mail.xml",
        "views/view_webmail_conversation.xml",
        "views/view_webmail_contact.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "webmail/static/src/css/webmail.scss",
        ],
    },
    "demo": [
        "demo/webmail_account.xml",
        "demo/webmail_folder.xml",
    ],
}
