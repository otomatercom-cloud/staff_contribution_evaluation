# -*- coding: utf-8 -*-
# Part of Otomater. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import UserError

from .evaluation_config import SECTION_SELECTION

# Sections where the wizard row is keyed by a single contribution type
# (radio-select UX on the real model). Section 'h' is keyed by a single
# department instead (see DEPARTMENT_SECTION below). Every ticked row
# becomes its own separate staff.contribution.line record either way.
SINGLE_TYPE_SECTIONS = {'a', 'b', 'c', 'd', 'f', 'i', 'j', 'l', 'n', 'q'}
DEPARTMENT_SECTION = 'h'


class StaffContributionQuickEntryWizard(models.TransientModel):
    _name = 'staff.contribution.quick.entry.wizard'
    _description = 'Quick Add Contributions (Tick Multiple)'

    evaluation_id = fields.Many2one(
        'staff.contribution.evaluation', required=True, ondelete='cascade')
    section = fields.Selection(SECTION_SELECTION, required=True)
    company_id = fields.Many2one(related='evaluation_id.company_id')
    currency_id = fields.Many2one(related='evaluation_id.currency_id')
    line_ids = fields.One2many(
        'staff.contribution.quick.entry.line', 'wizard_id', string='Rows')

    def action_confirm(self):
        self.ensure_one()
        included = self.line_ids.filtered('include')
        if not included:
            raise UserError(
                self.env._("Tick at least one row before confirming."))
        if included.filtered(lambda l: not l.name):
            raise UserError(
                self.env._("Please enter an Activity for every ticked row."))

        vals_list = []
        for line in included:
            vals = {
                'evaluation_id': self.evaluation_id.id,
                'section': self.section,
                'name': line.name,
                'revenue_generated': line.revenue_generated,
                'estimated_business_impact': line.estimated_business_impact,
                'cost_saved': line.cost_saved,
                'reach': line.reach,
                'views': line.views,
                'leads_generated': line.leads_generated,
                'admissions_influenced': line.admissions_influenced,
                'measurable_result': line.measurable_result,
                'business_impact': line.business_impact,
                'time_saved': line.time_saved,
                'efficiency_improvement': line.efficiency_improvement,
                'self_rating': line.self_rating,
                'has_evidence': line.has_evidence,
            }
            if self.section == DEPARTMENT_SECTION:
                vals['department_id'] = line.department_id.id
            elif self.section in SINGLE_TYPE_SECTIONS:
                vals['contribution_type_id'] = line.contribution_type_id.id
            vals_list.append(vals)

        self.env['staff.contribution.line'].create(vals_list)
        return {'type': 'ir.actions.act_window_close'}


class StaffContributionQuickEntryLine(models.TransientModel):
    _name = 'staff.contribution.quick.entry.line'
    _description = 'Quick Add Contribution Line'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'staff.contribution.quick.entry.wizard', required=True,
        ondelete='cascade')
    sequence = fields.Integer(default=10)
    contribution_type_id = fields.Many2one(
        'staff.contribution.type', readonly=True)
    department_id = fields.Many2one(
        'hr.department', readonly=True)
    include = fields.Boolean(string='Include')
    name = fields.Char(string='Activity')

    revenue_generated = fields.Float(string='Revenue Generated')
    estimated_business_impact = fields.Float(
        string='Estimated Business Impact')
    cost_saved = fields.Float(string='Cost Saved / Estimated Annual Saving')
    reach = fields.Integer(string='Reach')
    views = fields.Integer(string='Views')
    leads_generated = fields.Integer(string='Leads Generated')
    admissions_influenced = fields.Integer(string='Admissions Influenced')
    measurable_result = fields.Char(string='Measurable Result')
    business_impact = fields.Char(string='Business Impact')
    time_saved = fields.Char(string='Time Saved')
    efficiency_improvement = fields.Char(string='Efficiency Improvement')
    self_rating = fields.Integer(string='Self-Rating (0-5)')
    has_evidence = fields.Boolean(string='Evidence')

    @api.onchange('include')
    def _onchange_include(self):
        if self.include and not self.name:
            self.name = (self.contribution_type_id.name
                         or self.department_id.name)
