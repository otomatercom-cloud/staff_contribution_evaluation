# -*- coding: utf-8 -*-
# Part of Otomater. See LICENSE file for full copyright and licensing details.
{
    'name': 'Staff Contribution Evaluation',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Appraisal',
    'summary': 'Quarterly Significant Contribution Evaluation for employees',
    'description': """
Staff Contribution Evaluation
=============================
Digitally manages the Quarterly Significant Contribution Evaluation process:

* Employee submits quarterly contributions (18 sections A-R) with evidence
* Reporting Manager reviews, rates and completes the weighted scorecard
* HR reviews and forwards to Director
* Director approves / finalizes
* KPI summary, weighted final score, overall performance rating
* Role based security, record rules, activities and mail notifications
* Printable QWeb evaluation reports
    """,
    'author': 'Otomater',
    'website': 'https://otomater.com',
    'license': 'OPL-1',
    'depends': [
        'base',
        'mail',
        'hr',
        'portal',
    ],
    'data': [
        # Security (groups first, then ACLs / record rules)
        'security/security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/sequence.xml',
        'data/contribution_type_data.xml',
        'data/evidence_type_data.xml',
        'data/evaluation_criteria_data.xml',
        'data/mail_template_data.xml',
        'data/cron_data.xml',
        # Views
        'views/evaluation_config_views.xml',
        'views/contribution_line_views.xml',
        'views/quick_entry_wizard_views.xml',
        'views/contribution_evaluation_views.xml',
        'views/reporting_views.xml',
        # Reports
        'report/evaluation_report.xml',
        'report/evaluation_report_template.xml',
        # Portal
        'views/portal_templates.xml',
        # Menus last (they reference actions above)
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'assets': {
        'web.assets_frontend': [
            'staff_contribution_evaluation/static/src/css/portal_style.css',
        ],
    },
}
