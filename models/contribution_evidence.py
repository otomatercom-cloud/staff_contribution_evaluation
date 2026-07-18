# -*- coding: utf-8 -*-
# Part of Otomater. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models

from .evaluation_config import SECTION_SELECTION


class StaffContributionEvidence(models.Model):
    _name = 'staff.contribution.evidence'
    _description = 'Staff Contribution Evidence'
    _order = 'upload_date desc, id desc'

    evaluation_id = fields.Many2one(
        'staff.contribution.evaluation', string='Evaluation',
        required=True, ondelete='cascade', index=True)
    line_id = fields.Many2one(
        'staff.contribution.line', string='Contribution Record',
        ondelete='cascade', index=True,
        domain="[('evaluation_id', '=', evaluation_id)]")
    section = fields.Selection(
        SECTION_SELECTION, string='Contribution Section',
        compute='_compute_section', store=True, readonly=False,
        help="Section this evidence supports. Filled automatically when the "
             "evidence is linked to a contribution record.")
    evidence_type_id = fields.Many2one(
        'staff.evidence.type', string='Evidence Type')
    name = fields.Char(string='Description', required=True)
    attachment = fields.Binary(string='Attachment', attachment=True)
    attachment_filename = fields.Char(string='File Name')
    uploaded_by = fields.Many2one(
        'res.users', string='Uploaded By', readonly=True,
        default=lambda self: self.env.user)
    upload_date = fields.Datetime(
        string='Upload Date', readonly=True, default=fields.Datetime.now)
    company_id = fields.Many2one(
        related='evaluation_id.company_id', store=True, index=True)

    @api.depends('line_id.section')
    def _compute_section(self):
        for evidence in self:
            if evidence.line_id:
                evidence.section = evidence.line_id.section

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Keep evaluation_id consistent when created from a line.
            if vals.get('line_id') and not vals.get('evaluation_id'):
                line = self.env['staff.contribution.line'].browse(
                    vals['line_id'])
                vals['evaluation_id'] = line.evaluation_id.id
        return super().create(vals_list)
