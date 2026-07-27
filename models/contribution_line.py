# -*- coding: utf-8 -*-
# Part of Otomater. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .evaluation_config import SECTION_SELECTION

# Sections where the employee gives a self rating (per the paper form,
# sections A - E carry a self rating; the remaining sections are rated by
# the manager only).
SELF_RATED_SECTIONS = ('a', 'b', 'c', 'd', 'e')


class StaffContributionLine(models.Model):
    _name = 'staff.contribution.line'
    _description = 'Staff Contribution Line'
    _order = 'evaluation_id, section, sequence, id'

    # ------------------------------------------------------------------
    # Relational / core fields
    # ------------------------------------------------------------------
    evaluation_id = fields.Many2one(
        'staff.contribution.evaluation', string='Evaluation',
        required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='evaluation_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(
        related='evaluation_id.currency_id', store=True)
    employee_id = fields.Many2one(
        related='evaluation_id.employee_id', store=True, index=True)
    state = fields.Selection(related='evaluation_id.state', store=True)
    sequence = fields.Integer(default=10)
    section = fields.Selection(
        SECTION_SELECTION, required=True, index=True, default='a')
    contribution_type_ids = fields.Many2many(
        'staff.contribution.type', 'staff_contribution_line_type_rel',
        'line_id', 'contribution_type_id', string='Contribution Type(s)',
        domain="[('section', '=', section)]",
        help="Tick all contribution types that apply to this entry.")
    contribution_type_id = fields.Many2one(
        'staff.contribution.type', string='Contribution Type',
        domain="[('section', '=', section)]",
        help="Single contribution type for this entry (used by sections "
             "where each ticked type gets its own independent details).")
    name = fields.Char(
        string='Title', required=True,
        help="Short title of the contribution / activity.")
    description = fields.Text(
        string='Description',
        help="Activity description / contribution details. For Innovation "
             "this is the solution implemented; for Best Contribution this "
             "is the biggest contribution of the quarter.")
    measurable_result = fields.Text(string='Measurable Result')
    business_impact = fields.Text(string='Business Impact')
    current_status = fields.Char(
        string='Current Status',
        help="Section O: current status of the identified opportunity.")

    # Section G (Innovation) and R (Best Contribution) narrative fields
    problem_identified = fields.Text(string='Problem Identified')
    action_taken = fields.Text(string='Action Taken')
    result_achieved = fields.Text(string='Result')
    issue_prevented = fields.Text(
        string='Issue Prevented',
        help="Section M: issue / risk that was prevented.")

    # ------------------------------------------------------------------
    # Monetary KPIs
    # ------------------------------------------------------------------
    revenue_generated = fields.Monetary(
        string='Revenue Generated', currency_field='currency_id')
    revenue_protected = fields.Monetary(
        string='Revenue Loss Prevented', currency_field='currency_id',
        help="Section M: estimated revenue loss prevented / value saved.")
    estimated_business_impact = fields.Monetary(
        string='Estimated Business Impact (Value)',
        currency_field='currency_id')
    estimated_business_potential = fields.Monetary(
        string='Estimated Business Potential', currency_field='currency_id',
        help="Section O: estimated business potential of the opportunity.")
    cost_saved = fields.Monetary(
        string='Cost Saved / Annual Saving', currency_field='currency_id',
        help="Estimated annual saving (Section B) or cost saved "
             "(Sections G / N).")
    highest_salary = fields.Monetary(
        string='Highest Salary', currency_field='currency_id')
    average_salary = fields.Monetary(
        string='Average Salary', currency_field='currency_id')
    time_saved = fields.Char(
        string='Time Saved',
        help="Estimated time saved, e.g. '4 hours / week'.")
    efficiency_improvement = fields.Char(
        string='Efficiency Improvement',
        help="Section N: efficiency improvement achieved.")

    # ------------------------------------------------------------------
    # Count / reach KPIs
    # ------------------------------------------------------------------
    reach = fields.Integer(string='Reach')
    views = fields.Integer(string='Views')
    leads_generated = fields.Integer(string='Leads Generated')
    admissions_influenced = fields.Integer(string='Admissions Influenced')
    students_placed = fields.Integer(string='Students Placed')
    recruiters_added = fields.Integer(string='Recruiters Added')
    placement_drives = fields.Integer(string='Placement Drives Conducted')
    students_retained = fields.Integer(string='Students Retained')
    parents_convinced = fields.Integer(string='Parents Convinced')
    repeat_enrolments = fields.Integer(string='Repeat Enrolments')
    alumni_engagements = fields.Integer(string='Alumni Engagements')
    activity_count = fields.Integer(
        string='Activity Count',
        help="Section K: number of trainings / mentoring activities.")
    internal_training_count = fields.Integer(
        string='Internal Training',
        help="Section K: number of internal training sessions conducted.")
    staff_mentored_count = fields.Integer(
        string='Staff Mentored',
        help="Section K: number of staff mentored.")
    faculty_training_count = fields.Integer(
        string='Faculty Training',
        help="Section K: number of faculty training sessions conducted.")
    process_training_count = fields.Integer(
        string='Process Training',
        help="Section K: number of process training sessions conducted.")

    # Section H: departments benefited
    department_ids = fields.Many2many(
        'hr.department', 'staff_contribution_line_department_rel',
        'line_id', 'department_id', string='Departments Benefited')

    # ------------------------------------------------------------------
    # Ratings
    # ------------------------------------------------------------------
    self_rating = fields.Integer(
        string='Self Rating (0-5)',
        help="Employee self rating on a 0 to 5 scale.")
    manager_rating = fields.Integer(
        string='Manager Rating (0-5)', tracking=False,
        help="Reporting Manager rating on a 0 to 5 scale.")
    hr_rating = fields.Integer(
        string='HR Rating (0-5)', tracking=False,
        help="HR rating on a 0 to 5 scale, entered independently of the "
             "Reporting Manager's rating.")
    has_self_rating = fields.Boolean(
        compute='_compute_has_self_rating',
        help="Technical: whether this section carries a self rating.")

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------
    evidence_ids = fields.One2many(
        'staff.contribution.evidence', 'line_id', string='Evidence')
    evidence_count = fields.Integer(compute='_compute_evidence_count')
    has_evidence = fields.Boolean(
        string='Supporting Evidence Attached',
        help="Tick Yes if you are attaching supporting evidence for this "
             "contribution.")

    # ------------------------------------------------------------------
    # Compute / constraints
    # ------------------------------------------------------------------
    @api.depends('section')
    def _compute_has_self_rating(self):
        for line in self:
            line.has_self_rating = line.section in SELF_RATED_SECTIONS

    @api.depends('evidence_ids')
    def _compute_evidence_count(self):
        for line in self:
            line.evidence_count = len(line.evidence_ids)

    @api.constrains('self_rating', 'manager_rating', 'hr_rating')
    def _check_ratings(self):
        for line in self:
            if line.self_rating < 0 or line.self_rating > 5:
                raise ValidationError(
                    self.env._("Self rating must be between 0 and 5."))
            if line.manager_rating < 0 or line.manager_rating > 5:
                raise ValidationError(
                    self.env._("Manager rating must be between 0 and 5."))
            if line.hr_rating < 0 or line.hr_rating > 5:
                raise ValidationError(
                    self.env._("HR rating must be between 0 and 5."))

    @api.constrains('section', 'contribution_type_ids', 'contribution_type_id')
    def _check_type_section(self):
        for line in self:
            mismatched = line.contribution_type_ids.filtered(
                lambda t: t.section != line.section)
            if mismatched:
                raise ValidationError(
                    self.env._("The contribution type(s) %s do not belong "
                               "to section '%s'.",
                               ', '.join(mismatched.mapped('name')),
                               dict(SECTION_SELECTION).get(line.section)))
            if (line.contribution_type_id
                    and line.contribution_type_id.section != line.section):
                raise ValidationError(
                    self.env._("The contribution type '%s' does not belong "
                               "to section '%s'.",
                               line.contribution_type_id.name,
                               dict(SECTION_SELECTION).get(line.section)))

    @api.onchange('evidence_ids')
    def _onchange_evidence_ids(self):
        if self.evidence_ids:
            self.has_evidence = True

    @api.onchange('section')
    def _onchange_section(self):
        self.contribution_type_ids = self.contribution_type_ids.filtered(
            lambda t: t.section == self.section)
        if (self.contribution_type_id
                and self.contribution_type_id.section != self.section):
            self.contribution_type_id = False

    # ------------------------------------------------------------------
    # Server side protection of manager ratings
    # ------------------------------------------------------------------
    def _check_manager_rating_access(self, vals):
        """Only manager-level users may set / change manager ratings."""
        if 'manager_rating' in vals and not self.env.user.has_group(
                'staff_contribution_evaluation.group_contribution_manager'):
            raise UserError(
                self.env._("Only the Reporting Manager (or above) can enter "
                           "manager ratings."))

    def _check_hr_rating_access(self, vals):
        """Only HR-level users may set / change HR ratings."""
        if 'hr_rating' in vals and not self.env.user.has_group(
                'staff_contribution_evaluation.group_contribution_hr'):
            raise UserError(
                self.env._("Only HR (or above) can enter HR ratings."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('manager_rating'):
                self._check_manager_rating_access(vals)
            if vals.get('hr_rating'):
                self._check_hr_rating_access(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._check_manager_rating_access(vals)
        self._check_hr_rating_access(vals)
        for line in self:
            line.evaluation_id._check_editable()
        return super().write(vals)

    def unlink(self):
        for line in self:
            line.evaluation_id._check_editable()
        return super().unlink()

    @api.depends('name', 'section')
    def _compute_display_name(self):
        section_labels = dict(SECTION_SELECTION)
        for line in self:
            label = section_labels.get(line.section, '')
            code = label.split('.')[0] if label else ''
            line.display_name = (
                "[%s] %s" % (code, line.name) if code else line.name)
