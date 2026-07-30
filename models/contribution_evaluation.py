# -*- coding: utf-8 -*-
# Part of Otomater. See LICENSE file for full copyright and licensing details.
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

QUARTER_SELECTION = [
    ('q1', 'Q1 (Jan - Mar)'),
    ('q2', 'Q2 (Apr - Jun)'),
    ('q3', 'Q3 (Jul - Sep)'),
    ('q4', 'Q4 (Oct - Dec)'),
]

QUARTER_MONTHS = {
    'q1': (1, 3),
    'q2': (4, 6),
    'q3': (7, 9),
    'q4': (10, 12),
}

RATING_SELECTION = [
    ('outstanding', 'Outstanding'),
    ('exceeds', 'Exceeds Expectations'),
    ('very_good', 'Very Good'),
    ('good', 'Good'),
    ('needs_improvement', 'Needs Improvement'),
    ('unsatisfactory', 'Unsatisfactory'),
]

# Fields the employee remains allowed to touch even in later states
# (workflow buttons write 'state'; chatter writes are on other models).
WORKFLOW_FIELDS = {
    'state', 'date_submitted', 'employee_remarks', 'manager_remarks',
    'hr_remarks', 'director_remarks',
}


class StaffEvaluationScore(models.Model):
    _name = 'staff.evaluation.score'
    _description = 'Staff Evaluation Scorecard Line'
    _order = 'sequence, id'

    evaluation_id = fields.Many2one(
        'staff.contribution.evaluation', string='Evaluation',
        required=True, ondelete='cascade', index=True)
    criteria_id = fields.Many2one(
        'staff.evaluation.criteria', string='Evaluation Criteria',
        required=True)
    sequence = fields.Integer(related='criteria_id.sequence', store=True)
    weight = fields.Float(
        string='Weight (%)', required=True,
        help="Weight snapshot taken from the criteria configuration when "
             "the scorecard was generated.")
    score = fields.Float(
        string='Manager Score (0-100)',
        help="Manager score for this criterion on a 0-100 scale. Can be "
             "entered manually or set via 'Auto-Calculate from Contributions'.")
    weighted_score = fields.Float(
        string='Weighted Score', compute='_compute_weighted_score',
        store=True, help="Score x Weight / 100")
    hr_score = fields.Float(
        string='HR Score (0-100)',
        help="HR score for this criterion on a 0-100 scale, entered "
             "independently of the Manager score. Can be entered manually "
             "or set via 'Auto-Calculate from Contributions'.")
    hr_weighted_score = fields.Float(
        string='HR Weighted Score', compute='_compute_hr_weighted_score',
        store=True, help="HR Score x Weight / 100")
    auto_score = fields.Float(
        string='Auto Score (Manager)', compute='_compute_auto_scores',
        help="What the Manager Score would be if calculated automatically "
             "from the Manager Rating of contributions in this criterion's "
             "mapped sections. Not saved to Score until applied.")
    auto_hr_score = fields.Float(
        string='Auto Score (HR)', compute='_compute_auto_scores',
        help="What the HR Score would be if calculated automatically from "
             "the HR Rating of contributions in this criterion's mapped "
             "sections. Not saved to HR Score until applied.")
    company_id = fields.Many2one(
        related='evaluation_id.company_id', store=True, index=True)

    _sql_constraints = [
        ('evaluation_criteria_uniq', 'unique(evaluation_id, criteria_id)',
         'Each criterion can appear only once on an evaluation scorecard.'),
    ]

    @api.depends('score', 'weight')
    def _compute_weighted_score(self):
        for line in self:
            line.weighted_score = line.score * line.weight / 100.0

    @api.depends('hr_score', 'weight')
    def _compute_hr_weighted_score(self):
        for line in self:
            line.hr_weighted_score = line.hr_score * line.weight / 100.0

    @api.depends('criteria_id.mapped_sections',
                 'evaluation_id.line_ids.section',
                 'evaluation_id.line_ids.manager_rating',
                 'evaluation_id.line_ids.hr_rating')
    def _compute_auto_scores(self):
        for line in self:
            codes = line.criteria_id._get_mapped_section_codes()
            mapped_lines = line.evaluation_id.line_ids.filtered(
                lambda l, codes=codes: l.section in codes) if codes else (
                    line.evaluation_id.line_ids.browse())
            if mapped_lines:
                count = len(mapped_lines)
                line.auto_score = (
                    sum(mapped_lines.mapped('manager_rating')) / count * 20)
                line.auto_hr_score = (
                    sum(mapped_lines.mapped('hr_rating')) / count * 20)
            else:
                line.auto_score = 0.0
                line.auto_hr_score = 0.0

    @api.constrains('score')
    def _check_score(self):
        for line in self:
            if line.score < 0 or line.score > 100:
                raise ValidationError(
                    self.env._("Scorecard scores must be between 0 and 100."))

    @api.constrains('hr_score')
    def _check_hr_score(self):
        for line in self:
            if line.hr_score < 0 or line.hr_score > 100:
                raise ValidationError(
                    self.env._("Scorecard HR scores must be between 0 and "
                               "100."))

    @api.constrains('weight')
    def _check_weight(self):
        for line in self:
            if line.weight < 0 or line.weight > 100:
                raise ValidationError(
                    self.env._("Scorecard weights must be between 0 and "
                               "100."))

    def write(self, vals):
        if 'hr_score' in vals and not self.env.user.has_group(
                'staff_contribution_evaluation.group_contribution_hr'):
            raise UserError(
                self.env._("Only HR (or above) can enter the HR Score."))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('hr_score') and not self.env.user.has_group(
                    'staff_contribution_evaluation.group_contribution_hr'):
                raise UserError(
                    self.env._("Only HR (or above) can enter the HR Score."))
        return super().create(vals_list)


class StaffContributionEvaluation(models.Model):
    _name = 'staff.contribution.evaluation'
    _description = 'Staff Contribution Evaluation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'evaluation_year desc, quarter desc, id desc'
    _check_company_auto = True

    # ------------------------------------------------------------------
    # Header / employee information
    # ------------------------------------------------------------------
    name = fields.Char(
        string='Evaluation Number', required=True, copy=False,
        readonly=True, index=True, default=lambda self: self.env._('New'))
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        tracking=True, check_company=True,
        default=lambda self: self.env.user.employee_id)
    employee_code = fields.Char(
        related='employee_id.barcode', string='Employee ID', store=True)
    department_id = fields.Many2one(
        related='employee_id.department_id', string='Department',
        store=True, index=True)
    job_id = fields.Many2one(
        related='employee_id.job_id', string='Designation', store=True)
    work_location_id = fields.Many2one(
        related='employee_id.work_location_id', string='Branch',
        store=True)
    manager_id = fields.Many2one(
        'hr.employee', string='Reporting Manager', index=True, tracking=True,
        compute='_compute_manager_id', store=True, readonly=False,
        check_company=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', string='Currency')
    user_id = fields.Many2one(
        'res.users', string='Created By User', readonly=True,
        default=lambda self: self.env.user)

    quarter = fields.Selection(
        QUARTER_SELECTION, required=True, tracking=True,
        default=lambda self: self._default_quarter())
    evaluation_year = fields.Char(
        string='Evaluation Year', required=True, size=4, tracking=True,
        default=lambda self: str(fields.Date.context_today(self).year))
    date_from = fields.Date(
        string='Evaluation Period From', compute='_compute_period',
        store=True, readonly=False)
    date_to = fields.Date(
        string='Evaluation Period To', compute='_compute_period',
        store=True, readonly=False)
    date_submitted = fields.Date(
        string='Date of Submission', readonly=True, copy=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('manager_review', 'Manager Review'),
        ('hr_review', 'HR Review'),
        ('director_review', 'Director Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Evaluation Status', default='draft', required=True,
        tracking=True, copy=False, index=True)

    # ------------------------------------------------------------------
    # Contribution lines (per section, domain-filtered on one model)
    # ------------------------------------------------------------------
    line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='All Contributions')
    line_count = fields.Integer(compute='_compute_counts')

    revenue_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Revenue Contributions', domain=[('section', '=', 'a')])
    cost_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Cost Reductions', domain=[('section', '=', 'b')])
    marketing_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Digital & Marketing', domain=[('section', '=', 'c')])
    student_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Student Success', domain=[('section', '=', 'd')])
    placement_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Placement', domain=[('section', '=', 'e')])
    partnership_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Partnerships & Institutional', domain=[('section', '=', 'f')])
    innovation_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Innovation', domain=[('section', '=', 'g')])
    crossdept_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Cross Department', domain=[('section', '=', 'h')])
    process_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Process Improvement', domain=[('section', '=', 'i')])
    satisfaction_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Student & Parent Satisfaction',
        domain=[('section', '=', 'j')])
    team_dev_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Team Development', domain=[('section', '=', 'k')])
    brand_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Brand Building', domain=[('section', '=', 'l')])
    risk_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Risk Prevention', domain=[('section', '=', 'm')])
    ai_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='AI & Technology Adoption', domain=[('section', '=', 'n')])
    opportunity_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='New Opportunities', domain=[('section', '=', 'o')])
    retention_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Customer Retention', domain=[('section', '=', 'p')])
    recognition_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Special Recognition', domain=[('section', '=', 'q')])
    best_line_ids = fields.One2many(
        'staff.contribution.line', 'evaluation_id',
        string='Best Contribution of the Quarter',
        domain=[('section', '=', 'r')])

    evidence_ids = fields.One2many(
        'staff.contribution.evidence', 'evaluation_id', string='Evidence')
    evidence_count = fields.Integer(compute='_compute_counts')

    # ------------------------------------------------------------------
    # KPI Summary - calculated from contribution lines
    # ------------------------------------------------------------------
    kpi_revenue_generated = fields.Monetary(
        string='Revenue Generated', currency_field='currency_id',
        compute='_compute_kpi_summary', store=True)
    kpi_revenue_protected = fields.Monetary(
        string='Revenue Protected', currency_field='currency_id',
        compute='_compute_kpi_summary', store=True)
    kpi_cost_saved = fields.Monetary(
        string='Cost Saved', currency_field='currency_id',
        compute='_compute_kpi_summary', store=True)
    kpi_admissions_influenced = fields.Integer(
        string='Admissions Influenced',
        compute='_compute_kpi_summary', store=True)
    kpi_leads_generated = fields.Integer(
        string='Leads Generated', compute='_compute_kpi_summary', store=True)
    kpi_campaign_reach = fields.Integer(
        string='Campaign Reach', compute='_compute_kpi_summary', store=True)
    kpi_campaign_views = fields.Integer(
        string='Campaign Views', compute='_compute_kpi_summary', store=True)
    kpi_students_placed = fields.Integer(
        string='Students Placed', compute='_compute_kpi_summary', store=True)
    kpi_recruiters_added = fields.Integer(
        string='Recruiters Added', compute='_compute_kpi_summary', store=True)
    kpi_partnership_count = fields.Integer(
        string='Partnerships', compute='_compute_kpi_summary', store=True)
    kpi_ai_initiative_count = fields.Integer(
        string='AI Initiatives', compute='_compute_kpi_summary', store=True)
    kpi_process_improvement_count = fields.Integer(
        string='Process Improvements',
        compute='_compute_kpi_summary', store=True)
    kpi_students_retained = fields.Integer(
        string='Students Retained', compute='_compute_kpi_summary',
        store=True)

    # KPI Summary - manual entries (cannot be derived from lines)
    kpi_achievement = fields.Float(
        string='KPI Achievement (%)',
        help="Manual entry: overall KPI achievement for the quarter, "
             "entered by the manager or HR.")
    kpi_student_satisfaction = fields.Float(
        string='Student Satisfaction',
        help="Manual entry: student satisfaction score for the quarter.")
    kpi_google_reviews = fields.Integer(
        string='Google Reviews',
        help="Manual entry: number of Google reviews attributable to the "
             "employee this quarter.")
    kpi_manual_notes = fields.Text(
        string='Manual KPI Notes',
        help="Explain the source of manually entered KPI values.")

    # ------------------------------------------------------------------
    # Manager evaluation scorecard
    # ------------------------------------------------------------------
    score_line_ids = fields.One2many(
        'staff.evaluation.score', 'evaluation_id', string='Scorecard')
    total_weight = fields.Float(
        compute='_compute_final_score', string='Total Weight (%)')
    scorecard_score = fields.Float(
        string='Manager Scorecard Score', compute='_compute_final_score',
        store=True,
        help="Weighted score from the Manager Evaluation Scorecard's "
             "Manager Score column (0-100).")
    hr_scorecard_score = fields.Float(
        string='HR Scorecard Score', compute='_compute_final_score',
        store=True,
        help="Weighted score from the Manager Evaluation Scorecard's HR "
             "Score column (0-100).")
    final_score = fields.Float(
        string='Final Score', compute='_compute_final_score', store=True,
        tracking=True, aggregator='avg')
    overall_rating = fields.Selection(
        RATING_SELECTION, string='Overall Performance Rating',
        compute='_compute_overall_rating', store=True, tracking=True)

    # ------------------------------------------------------------------
    # Consolidated per-contribution Manager / HR marks (informational —
    # a quick overview of raw ratings; the Final Score itself is driven by
    # the weighted Manager/HR Scorecard columns above).
    # ------------------------------------------------------------------
    consolidated_manager_marks_sum = fields.Integer(
        string='Manager Marks (Sum)', compute='_compute_consolidated_marks',
        store=True,
        help="Sum of the Manager Rating (0-5) entered on every individual "
             "contribution across all sections. Informational only.")
    consolidated_manager_marks_avg = fields.Float(
        string='Manager Marks (Average)', compute='_compute_consolidated_marks',
        store=True,
        help="Average of the Manager Rating (0-5) across every individual "
             "contribution across all sections. Informational only.")
    consolidated_hr_marks_sum = fields.Integer(
        string='HR Marks (Sum)', compute='_compute_consolidated_marks',
        store=True,
        help="Sum of the HR Rating (0-5) entered on every individual "
             "contribution across all sections. Informational only.")
    consolidated_hr_marks_avg = fields.Float(
        string='HR Marks (Average)', compute='_compute_consolidated_marks',
        store=True,
        help="Average of the HR Rating (0-5) across every individual "
             "contribution across all sections. Informational only.")
    consolidated_marks_weight = fields.Float(
        string='HR Scorecard Weight (%)', default=30.0,
        help="What percentage of the Final Score comes from the HR "
             "Scorecard Score. The remaining percentage comes from the "
             "Manager Scorecard Score. E.g. 30 means Final Score = Manager "
             "Scorecard Score x 70% + HR Scorecard Score x 30%.")

    # ------------------------------------------------------------------
    # Remarks
    # ------------------------------------------------------------------
    employee_remarks = fields.Text(string='Employee Remarks')
    manager_remarks = fields.Text(string='Reporting Manager Remarks')
    hr_remarks = fields.Text(string='Human Resource Remarks')
    director_remarks = fields.Text(string='Director Remarks')

    # ==================================================================
    # Defaults / computes
    # ==================================================================
    @api.model
    def _default_quarter(self):
        month = fields.Date.context_today(self).month
        return 'q%d' % ((month - 1) // 3 + 1)

    @api.depends('employee_id')
    def _compute_manager_id(self):
        for evaluation in self:
            if evaluation.employee_id.parent_id:
                evaluation.manager_id = evaluation.employee_id.parent_id

    @api.depends('quarter', 'evaluation_year')
    def _compute_period(self):
        for evaluation in self:
            if not (evaluation.quarter and evaluation.evaluation_year
                    and evaluation.evaluation_year.isdigit()):
                continue
            year = int(evaluation.evaluation_year)
            month_from, month_to = QUARTER_MONTHS[evaluation.quarter]
            evaluation.date_from = date(year, month_from, 1)
            if month_to == 12:
                evaluation.date_to = date(year, 12, 31)
            else:
                evaluation.date_to = (
                    date(year, month_to + 1, 1) - relativedelta(days=1))

    @api.depends('line_ids', 'evidence_ids')
    def _compute_counts(self):
        for evaluation in self:
            evaluation.line_count = len(evaluation.line_ids)
            evaluation.evidence_count = len(evaluation.evidence_ids)

    @api.depends(
        'line_ids.section', 'line_ids.revenue_generated',
        'line_ids.revenue_protected', 'line_ids.cost_saved',
        'line_ids.admissions_influenced', 'line_ids.leads_generated',
        'line_ids.reach', 'line_ids.views', 'line_ids.students_placed',
        'line_ids.recruiters_added', 'line_ids.students_retained')
    def _compute_kpi_summary(self):
        for evaluation in self:
            lines = evaluation.line_ids
            evaluation.kpi_revenue_generated = sum(
                lines.mapped('revenue_generated'))
            evaluation.kpi_revenue_protected = sum(
                lines.mapped('revenue_protected'))
            evaluation.kpi_cost_saved = sum(lines.mapped('cost_saved'))
            evaluation.kpi_admissions_influenced = sum(
                lines.mapped('admissions_influenced'))
            evaluation.kpi_leads_generated = sum(
                lines.mapped('leads_generated'))
            evaluation.kpi_campaign_reach = sum(lines.mapped('reach'))
            evaluation.kpi_campaign_views = sum(lines.mapped('views'))
            evaluation.kpi_students_placed = sum(
                lines.mapped('students_placed'))
            evaluation.kpi_recruiters_added = sum(
                lines.mapped('recruiters_added'))
            evaluation.kpi_students_retained = sum(
                lines.mapped('students_retained'))
            evaluation.kpi_partnership_count = len(
                lines.filtered(lambda l: l.section == 'f'))
            evaluation.kpi_ai_initiative_count = len(
                lines.filtered(lambda l: l.section == 'n'))
            evaluation.kpi_process_improvement_count = len(
                lines.filtered(lambda l: l.section == 'i'))

    @api.depends('line_ids.manager_rating', 'line_ids.hr_rating')
    def _compute_consolidated_marks(self):
        for evaluation in self:
            lines = evaluation.line_ids
            count = len(lines)
            manager_sum = sum(lines.mapped('manager_rating'))
            hr_sum = sum(lines.mapped('hr_rating'))
            evaluation.consolidated_manager_marks_sum = manager_sum
            evaluation.consolidated_hr_marks_sum = hr_sum
            evaluation.consolidated_manager_marks_avg = (
                manager_sum / count if count else 0.0)
            evaluation.consolidated_hr_marks_avg = (
                hr_sum / count if count else 0.0)

    @api.depends('score_line_ids.weighted_score', 'score_line_ids.weight',
                 'score_line_ids.hr_weighted_score', 'consolidated_marks_weight')
    def _compute_final_score(self):
        for evaluation in self:
            evaluation.total_weight = sum(
                evaluation.score_line_ids.mapped('weight'))
            evaluation.scorecard_score = sum(
                evaluation.score_line_ids.mapped('weighted_score'))
            evaluation.hr_scorecard_score = sum(
                evaluation.score_line_ids.mapped('hr_weighted_score'))
            hr_share = max(
                0.0, min(100.0, evaluation.consolidated_marks_weight)) / 100.0
            evaluation.final_score = (
                evaluation.scorecard_score * (1 - hr_share)
                + evaluation.hr_scorecard_score * hr_share)

    @api.depends('final_score')
    def _compute_overall_rating(self):
        for evaluation in self:
            score = evaluation.final_score
            if not evaluation.score_line_ids and not evaluation.line_ids:
                evaluation.overall_rating = False
            elif score >= 90:
                evaluation.overall_rating = 'outstanding'
            elif score >= 80:
                evaluation.overall_rating = 'exceeds'
            elif score >= 70:
                evaluation.overall_rating = 'very_good'
            elif score >= 60:
                evaluation.overall_rating = 'good'
            elif score >= 50:
                evaluation.overall_rating = 'needs_improvement'
            else:
                evaluation.overall_rating = 'unsatisfactory'

    @api.depends('employee_id', 'quarter', 'evaluation_year')
    def _compute_display_name(self):
        for evaluation in self:
            parts = [evaluation.name or self.env._('New')]
            if evaluation.employee_id:
                parts.append(evaluation.employee_id.name)
            if evaluation.quarter and evaluation.evaluation_year:
                parts.append("%s/%s" % (
                    evaluation.quarter.upper(), evaluation.evaluation_year))
            evaluation.display_name = " - ".join(parts)

    # ==================================================================
    # Constraints
    # ==================================================================
    @api.constrains('evaluation_year')
    def _check_year(self):
        for evaluation in self:
            if (not evaluation.evaluation_year.isdigit()
                    or len(evaluation.evaluation_year) != 4):
                raise ValidationError(
                    self.env._("The evaluation year must be a 4 digit year, "
                               "e.g. 2026."))

    @api.constrains('employee_id', 'quarter', 'evaluation_year',
                    'company_id', 'state')
    def _check_unique_quarter(self):
        for evaluation in self:
            if evaluation.state in ('cancelled', 'rejected'):
                continue
            duplicate = self.search_count([
                ('id', '!=', evaluation.id),
                ('employee_id', '=', evaluation.employee_id.id),
                ('quarter', '=', evaluation.quarter),
                ('evaluation_year', '=', evaluation.evaluation_year),
                ('company_id', '=', evaluation.company_id.id),
                ('state', 'not in', ('cancelled', 'rejected')),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    self.env._("An evaluation already exists for %(employee)s "
                               "for %(quarter)s %(year)s.",
                               employee=evaluation.employee_id.name,
                               quarter=evaluation.quarter.upper(),
                               year=evaluation.evaluation_year))

    @api.constrains('date_from', 'date_to')
    def _check_period(self):
        for evaluation in self:
            if (evaluation.date_from and evaluation.date_to
                    and evaluation.date_from > evaluation.date_to):
                raise ValidationError(
                    self.env._("The evaluation period start date must be "
                               "before the end date."))

    @api.constrains('consolidated_marks_weight')
    def _check_consolidated_marks_weight(self):
        for evaluation in self:
            if (evaluation.consolidated_marks_weight < 0
                    or evaluation.consolidated_marks_weight > 100):
                raise ValidationError(
                    self.env._("Consolidated Marks Weight must be between "
                               "0 and 100."))

    # ==================================================================
    # CRUD / server side security
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', self.env._('New')) == self.env._('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'staff.contribution.evaluation') or self.env._('New')
        return super().create(vals_list)

    def _is_privileged_user(self):
        return (self.env.user.has_group(
            'staff_contribution_evaluation.group_contribution_hr')
            or self.env.user.has_group(
                'staff_contribution_evaluation.group_contribution_admin'))

    def _check_editable(self):
        """Approved / cancelled evaluations become read-only except for
        HR / administrators. Called from lines and evidence too."""
        for evaluation in self:
            if (evaluation.state in ('approved', 'cancelled')
                    and not evaluation._is_privileged_user()):
                raise UserError(
                    self.env._("Evaluation %s is finalized and can only be "
                               "modified by HR / administrators.",
                               evaluation.name))

    def _check_remarks_access(self, vals):
        remark_groups = {
            'manager_remarks':
                'staff_contribution_evaluation.group_contribution_manager',
            'hr_remarks':
                'staff_contribution_evaluation.group_contribution_hr',
            'director_remarks':
                'staff_contribution_evaluation.group_contribution_director',
        }
        for field_name, group in remark_groups.items():
            if field_name in vals and not self.env.user.has_group(group):
                raise UserError(
                    self.env._("You do not have the rights to edit the field "
                               "'%s'.", self._fields[field_name].string))
        # Manual KPI values and scorecard-related header data are for
        # manager level and above.
        protected = {'kpi_achievement', 'kpi_student_satisfaction',
                     'kpi_google_reviews', 'kpi_manual_notes',
                     'consolidated_marks_weight'}
        if protected & set(vals) and not self.env.user.has_group(
                'staff_contribution_evaluation.group_contribution_manager'):
            raise UserError(
                self.env._("Manual KPI values can only be entered by the "
                           "Reporting Manager, HR or administrators."))

    def write(self, vals):
        self._check_remarks_access(vals)
        if not set(vals) <= WORKFLOW_FIELDS:
            self._check_editable()
        return super().write(vals)

    def unlink(self):
        for evaluation in self:
            if evaluation.state != 'draft' and not self.env.user.has_group(
                    'staff_contribution_evaluation.group_contribution_admin'):
                raise UserError(
                    self.env._("Only draft evaluations can be deleted."))
        return super().unlink()

    # ==================================================================
    # Scorecard helpers
    # ==================================================================
    def action_load_scorecard(self):
        """Populate scorecard lines from the active criteria
        configuration (weight snapshot)."""
        criteria = self.env['staff.evaluation.criteria'].search([])
        for evaluation in self:
            existing = evaluation.score_line_ids.mapped('criteria_id')
            lines = [
                {'evaluation_id': evaluation.id,
                 'criteria_id': criterion.id,
                 'weight': criterion.weight}
                for criterion in criteria if criterion not in existing
            ]
            if lines:
                self.env['staff.evaluation.score'].create(lines)
        return True

    def action_apply_auto_manager_scores(self):
        """Copy each scorecard line's auto-calculated Manager Score into
        the actual Score field, for criteria that have mapped sections
        configured. Criteria left unmapped are skipped so any
        manually-entered score there is preserved."""
        for evaluation in self:
            for score_line in evaluation.score_line_ids:
                if not score_line.criteria_id._get_mapped_section_codes():
                    continue
                score_line.write({'score': score_line.auto_score})
        return True

    def action_apply_auto_hr_scores(self):
        """Copy each scorecard line's auto-calculated HR Score into the
        actual HR Score field, for criteria that have mapped sections
        configured. Criteria left unmapped are skipped so any
        manually-entered score there is preserved."""
        for evaluation in self:
            for score_line in evaluation.score_line_ids:
                if not score_line.criteria_id._get_mapped_section_codes():
                    continue
                score_line.write({'hr_score': score_line.auto_hr_score})
        return True

    # ==================================================================
    # Workflow
    # ==================================================================
    def _notify_next_actor(self, template_xmlid, users, summary):
        """Send the mail template and schedule an activity for the users
        responsible for the next workflow step."""
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        for evaluation in self:
            if template:
                template.send_mail(evaluation.id)
            for user in users.filtered(lambda u: not u.share):
                evaluation.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=user.id,
                    summary=summary,
                    note=self.env._(
                        "Evaluation %(name)s of %(employee)s "
                        "(%(quarter)s %(year)s) requires your action.",
                        name=evaluation.name,
                        employee=evaluation.employee_id.name,
                        quarter=evaluation.quarter.upper(),
                        year=evaluation.evaluation_year))

    def _group_users(self, group_xmlid):
        group = self.env.ref(group_xmlid, raise_if_not_found=False)
        if not group:
            return self.env['res.users']
        return group.all_user_ids.filtered(
            lambda u: u.active and not u.share
            and self.company_id in u.company_ids)

    def action_submit(self):
        for evaluation in self:
            if evaluation.state != 'draft':
                raise UserError(
                    self.env._("Only draft evaluations can be submitted."))
            if not evaluation.line_ids:
                raise UserError(
                    self.env._("Add at least one contribution before "
                               "submitting the evaluation."))
            if not evaluation.manager_id:
                raise UserError(
                    self.env._("A Reporting Manager is required before "
                               "submission."))
        self.write({
            'state': 'submitted',
            'date_submitted': fields.Date.context_today(self),
        })
        for evaluation in self:
            evaluation.activity_feedback(['mail.mail_activity_data_todo'])
            manager_user = evaluation.manager_id.user_id
            evaluation._notify_next_actor(
                'staff_contribution_evaluation.mail_template_submitted',
                manager_user or self.env['res.users'],
                self.env._('Contribution evaluation to review'))
        return True

    def action_start_manager_review(self):
        self._check_state_transition(('submitted',), 'manager_review')
        self.action_load_scorecard()
        return True

    def action_manager_submit_hr(self):
        for evaluation in self:
            if evaluation.state not in ('submitted', 'manager_review'):
                raise UserError(
                    self.env._("The evaluation must be under manager review "
                               "before it can be sent to HR."))
            missing = evaluation.score_line_ids.filtered(
                lambda s: not s.score)
            if not evaluation.score_line_ids:
                raise UserError(
                    self.env._("Load and complete the manager scorecard "
                               "before submitting to HR."))
            if missing and len(missing) == len(evaluation.score_line_ids):
                raise UserError(
                    self.env._("Enter the scorecard scores before submitting "
                               "to HR."))
        self.write({'state': 'hr_review'})
        for evaluation in self:
            evaluation.activity_feedback(['mail.mail_activity_data_todo'])
            evaluation._notify_next_actor(
                'staff_contribution_evaluation.mail_template_hr_review',
                evaluation._group_users(
                    'staff_contribution_evaluation.group_contribution_hr'),
                self.env._('Contribution evaluation - HR review'))
        return True

    def action_return_to_employee(self):
        for evaluation in self:
            if evaluation.state not in (
                    'submitted', 'manager_review', 'hr_review'):
                raise UserError(
                    self.env._("This evaluation cannot be returned from its "
                               "current state."))
        self.write({'state': 'draft'})
        for evaluation in self:
            evaluation.activity_feedback(['mail.mail_activity_data_todo'])
            employee_user = evaluation.employee_id.user_id
            evaluation._notify_next_actor(
                'staff_contribution_evaluation.mail_template_returned',
                employee_user or self.env['res.users'],
                self.env._('Contribution evaluation returned - please '
                           'update and resubmit'))
        return True

    def action_hr_submit_director(self):
        self._check_state_transition(('hr_review',), 'director_review')
        for evaluation in self:
            evaluation.activity_feedback(['mail.mail_activity_data_todo'])
            evaluation._notify_next_actor(
                'staff_contribution_evaluation.mail_template_director_review',
                evaluation._group_users(
                    'staff_contribution_evaluation.'
                    'group_contribution_director'),
                self.env._('Contribution evaluation - Director review'))
        return True

    def action_hr_return(self):
        self._check_state_transition(('hr_review',), 'manager_review')
        for evaluation in self:
            evaluation.activity_feedback(['mail.mail_activity_data_todo'])
            manager_user = evaluation.manager_id.user_id
            evaluation._notify_next_actor(
                'staff_contribution_evaluation.mail_template_returned',
                manager_user or self.env['res.users'],
                self.env._('Contribution evaluation returned by HR'))
        return True

    def action_director_return(self):
        self._check_state_transition(('director_review',), 'hr_review')
        for evaluation in self:
            evaluation.activity_feedback(['mail.mail_activity_data_todo'])
            evaluation._notify_next_actor(
                'staff_contribution_evaluation.mail_template_hr_review',
                evaluation._group_users(
                    'staff_contribution_evaluation.group_contribution_hr'),
                self.env._('Contribution evaluation returned by Director'))
        return True

    def action_director_approve(self):
        self._check_state_transition(('director_review',), 'approved')
        for evaluation in self:
            evaluation.activity_feedback(['mail.mail_activity_data_todo'])
            template = self.env.ref(
                'staff_contribution_evaluation.mail_template_approved',
                raise_if_not_found=False)
            if template:
                template.send_mail(evaluation.id)
        return True

    def action_reject(self):
        for evaluation in self:
            if evaluation.state in ('approved', 'rejected', 'cancelled'):
                raise UserError(
                    self.env._("This evaluation can no longer be rejected."))
        self.write({'state': 'rejected'})
        for evaluation in self:
            evaluation.activity_feedback(['mail.mail_activity_data_todo'])
            template = self.env.ref(
                'staff_contribution_evaluation.mail_template_rejected',
                raise_if_not_found=False)
            if template:
                template.send_mail(evaluation.id)
        return True

    def action_cancel(self):
        for evaluation in self:
            if evaluation.state == 'approved':
                raise UserError(
                    self.env._("Approved evaluations cannot be cancelled."))
        self.write({'state': 'cancelled'})
        return True

    def action_reset_to_draft(self):
        if not self._is_privileged_user():
            raise UserError(
                self.env._("Only HR / administrators can reset an evaluation "
                           "to draft."))
        self.write({'state': 'draft'})
        return True

    def _check_state_transition(self, allowed_states, new_state):
        for evaluation in self:
            if evaluation.state not in allowed_states:
                raise UserError(
                    self.env._("Invalid workflow transition for evaluation "
                               "%s.", evaluation.name))
        self.write({'state': new_state})
        return True

    # ==================================================================
    # Smart button actions
    # ==================================================================
    def action_view_evidence(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Evidence'),
            'res_model': 'staff.contribution.evidence',
            'view_mode': 'list,form',
            'domain': [('evaluation_id', '=', self.id)],
            'context': {'default_evaluation_id': self.id},
        }

    def action_view_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Contributions'),
            'res_model': 'staff.contribution.line',
            'view_mode': 'list,form',
            'domain': [('evaluation_id', '=', self.id)],
            'context': {'default_evaluation_id': self.id},
        }

    def action_quick_add(self):
        """Open the tick-multiple quick-add wizard for the section passed
        via the calling button's context (quick_add_section)."""
        self.ensure_one()
        section = self.env.context.get('quick_add_section')
        if not section:
            raise UserError(self.env._("No section specified."))
        if section == 'h':
            departments = self.env['hr.department'].search(
                [('company_id', '=', self.company_id.id)])
            row_vals = [(0, 0, {'department_id': d.id}) for d in departments]
        else:
            types = self.env['staff.contribution.type'].search(
                [('section', '=', section)])
            row_vals = [(0, 0, {'contribution_type_id': t.id}) for t in types]
        wizard = self.env['staff.contribution.quick.entry.wizard'].create({
            'evaluation_id': self.id,
            'section': section,
            'line_ids': row_vals,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Quick Add — Tick Multiple'),
            'res_model': 'staff.contribution.quick.entry.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    # ==================================================================
    # Cron: automatic quarterly evaluation creation
    # ==================================================================
    @api.model
    def cron_generate_quarterly_evaluations(self):
        """Create draft quarterly evaluations for all active employees of
        every company, skipping duplicates. Disabled by default."""
        today = fields.Date.context_today(self)
        quarter = 'q%d' % ((today.month - 1) // 3 + 1)
        year = str(today.year)
        for company in self.env['res.company'].search([]):
            employees = self.env['hr.employee'].search([
                ('company_id', '=', company.id),
                ('active', '=', True),
            ])
            existing = self.search([
                ('company_id', '=', company.id),
                ('quarter', '=', quarter),
                ('evaluation_year', '=', year),
                ('state', 'not in', ('cancelled', 'rejected')),
            ]).mapped('employee_id')
            vals_list = [{
                'employee_id': employee.id,
                'company_id': company.id,
                'quarter': quarter,
                'evaluation_year': year,
            } for employee in employees - existing]
            if vals_list:
                self.sudo().create(vals_list)
        return True
