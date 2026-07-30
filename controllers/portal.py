# -*- coding: utf-8 -*-
# Part of Otomater. See LICENSE file for full copyright and licensing details.
import base64

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

# Single source of truth describing how each of the 18 sections is entered
# on the portal form. Keeping this data-driven (rather than 18 near-duplicate
# templates) means the template stays generic and new sections only need an
# entry here.
#
# fields: list of (technical_name, label, type) where type is one of
#   'char' | 'text' | 'integer' | 'monetary'
SECTION_FORM_CONFIG = {
    'a': {
        'title': 'A. Revenue Contribution',
        'has_types': True, 'has_self_rating': True, 'has_evidence': True,
        'fields': [
            ('name', 'Activity', 'char'),
            ('revenue_generated', 'Revenue Generated', 'monetary'),
            ('estimated_business_impact', 'Estimated Business Impact', 'monetary'),
        ],
    },
    'b': {
        'title': 'B. Cost Reduction',
        'has_types': True, 'has_self_rating': True, 'has_evidence': True,
        'fields': [
            ('name', 'Contribution', 'char'),
            ('cost_saved', 'Estimated Annual Saving', 'monetary'),
        ],
    },
    'c': {
        'title': 'C. Digital & Marketing Contribution',
        'has_types': True, 'has_self_rating': True, 'has_evidence': True,
        'fields': [
            ('name', 'Activity', 'char'),
            ('reach', 'Reach', 'integer'),
            ('views', 'Views', 'integer'),
            ('leads_generated', 'Leads Generated', 'integer'),
            ('admissions_influenced', 'Admissions Influenced', 'integer'),
        ],
    },
    'd': {
        'title': 'D. Student Success Contribution',
        'has_types': True, 'has_self_rating': True, 'has_evidence': True,
        'fields': [
            ('name', 'Contribution', 'char'),
            ('measurable_result', 'Measurable Result', 'text'),
        ],
    },
    'e': {
        'title': 'E. Placement Contribution',
        'has_types': False, 'has_self_rating': True, 'has_evidence': True,
        'fields': [
            ('name', 'Activity / Period', 'char'),
            ('students_placed', 'Students Placed', 'integer'),
            ('recruiters_added', 'Recruiters Added', 'integer'),
            ('placement_drives', 'Placement Drives Conducted', 'integer'),
            ('highest_salary', 'Highest Salary', 'monetary'),
            ('average_salary', 'Average Salary', 'monetary'),
        ],
    },
    'f': {
        'title': 'F. Partnerships & Institutional Contribution',
        'has_types': True, 'has_self_rating': False, 'has_evidence': True,
        'fields': [
            ('name', 'Contribution', 'char'),
            ('business_impact', 'Business Impact', 'text'),
        ],
    },
    'g': {
        'title': 'G. Innovation',
        'has_types': False, 'has_self_rating': False, 'has_evidence': True,
        'intro': 'Describe one innovative idea implemented during this quarter.',
        'fields': [
            ('name', 'Innovation Idea', 'char'),
            ('problem_identified', 'Problem Identified', 'text'),
            ('action_taken', 'Solution Implemented', 'text'),
            ('business_impact', 'Business Impact', 'text'),
            ('time_saved', 'Time Saved', 'char'),
            ('cost_saved', 'Cost Saved', 'monetary'),
        ],
    },
    'h': {
        'title': 'H. Cross Department Contribution',
        'has_types': False, 'has_departments': True,
        'has_self_rating': False, 'has_evidence': False,
        'fields': [
            ('name', 'Contribution', 'char'),
            ('business_impact', 'Business Impact', 'text'),
        ],
    },
    'i': {
        'title': 'I. Process Improvement',
        'has_types': True, 'has_self_rating': False, 'has_evidence': False,
        'fields': [
            ('name', 'Improvement', 'char'),
            ('time_saved', 'Time Saved', 'char'),
        ],
    },
    'j': {
        'title': 'J. Student & Parent Satisfaction',
        'has_types': True, 'has_self_rating': False, 'has_evidence': True,
        'fields': [
            ('name', 'Description', 'char'),
        ],
    },
    'k': {
        'title': 'K. Team Development',
        'has_types': False, 'has_self_rating': False, 'has_evidence': False,
        'fields': [
            ('name', 'Description', 'char'),
            ('internal_training_count', 'Internal Training', 'integer'),
            ('staff_mentored_count', 'Staff Mentored', 'integer'),
            ('faculty_training_count', 'Faculty Training', 'integer'),
            ('process_training_count', 'Process Training', 'integer'),
        ],
    },
    'l': {
        'title': 'L. Brand Building',
        'has_types': True, 'has_self_rating': False, 'has_evidence': False,
        'fields': [
            ('name', 'Activity', 'char'),
            ('business_impact', 'Impact', 'text'),
        ],
    },
    'm': {
        'title': 'M. Risk Prevention',
        'has_types': False, 'has_self_rating': False, 'has_evidence': True,
        'intro': 'Describe any issue prevented.',
        'fields': [
            ('name', 'Title', 'char'),
            ('issue_prevented', 'Issue Prevented', 'text'),
            ('revenue_protected', 'Revenue Loss Prevented', 'monetary'),
            ('estimated_business_impact', 'Estimated Value Saved', 'monetary'),
        ],
    },
    'n': {
        'title': 'N. AI & Technology Adoption',
        'has_types': True, 'has_self_rating': False, 'has_evidence': False,
        'fields': [
            ('name', 'Contribution', 'char'),
            ('efficiency_improvement', 'Efficiency Improvement', 'char'),
        ],
    },
    'o': {
        'title': 'O. New Opportunities Identified',
        'has_types': False, 'has_self_rating': False, 'has_evidence': False,
        'fields': [
            ('name', 'Opportunity', 'char'),
            ('current_status', 'Current Status', 'char'),
        ],
    },
    'p': {
        'title': 'P. Customer Retention',
        'has_types': False, 'has_self_rating': False, 'has_evidence': False,
        'fields': [
            ('name', 'Description', 'char'),
            ('students_retained', 'Students Retained', 'integer'),
            ('parents_convinced', 'Parents Convinced', 'integer'),
            ('repeat_enrolments', 'Repeat Enrolments', 'integer'),
            ('alumni_engagements', 'Alumni Engagement', 'integer'),
        ],
    },
    'q': {
        'title': 'Q. Special Recognition',
        'has_types': True, 'has_self_rating': False, 'has_evidence': True,
        'fields': [
            ('name', 'Recognition Details', 'char'),
        ],
    },
    'r': {
        'title': 'R. Best Contribution of the Quarter',
        'has_types': False, 'has_self_rating': False, 'has_evidence': True,
        'intro': 'Describe your single biggest contribution.',
        'fields': [
            ('name', 'Biggest Contribution', 'char'),
            ('problem_identified', 'Problem', 'text'),
            ('action_taken', 'Action Taken', 'text'),
            ('result_achieved', 'Result', 'text'),
            ('business_impact', 'Business Impact', 'text'),
        ],
    },
}

SECTION_ORDER = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l',
                  'm', 'n', 'o', 'p', 'q', 'r']


class ContributionEvaluationPortal(CustomerPortal):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'contribution_evaluation_count' in counters:
            employee = request.env.user.employee_id
            count = 0
            if employee:
                count = request.env['staff.contribution.evaluation'].sudo().search_count(
                    [('employee_id', '=', employee.id)])
            values['contribution_evaluation_count'] = count
        return values

    def _get_own_evaluation(self, evaluation_id):
        employee = request.env.user.employee_id
        if not employee:
            raise AccessError(
                request.env._("No employee record is linked to your user."))
        evaluation = request.env['staff.contribution.evaluation'].sudo().search([
            ('id', '=', evaluation_id),
            ('employee_id', '=', employee.id),
        ], limit=1)
        if not evaluation:
            raise AccessError(
                request.env._("This evaluation is not accessible."))
        return evaluation

    def _build_sections_data(self, evaluation):
        """Pre-compute everything the template needs per section so the
        QWeb template itself stays free of dynamic attribute lookups."""
        sections_data = []
        for code in SECTION_ORDER:
            cfg = SECTION_FORM_CONFIG[code]
            lines = evaluation.line_ids.filtered(
                lambda l, code=code: l.section == code)
            cards = []
            for line in lines:
                detail_values = [
                    (label, getattr(line, fname))
                    for fname, label, ftype in cfg['fields']
                    if fname != 'name'
                ]
                cards.append({
                    'line': line,
                    'title': line.name,
                    'details': detail_values,
                })
            items = request.env['staff.contribution.type']
            item_kind = None
            if cfg.get('has_types'):
                items = request.env['staff.contribution.type'].sudo().search(
                    [('section', '=', code)])
                item_kind = 'type'
            elif cfg.get('has_departments'):
                items = request.env['hr.department'].sudo().search(
                    [('company_id', '=', evaluation.company_id.id)])
                item_kind = 'department'
            sections_data.append({
                'code': code,
                'cfg': cfg,
                'cards': cards,
                'items': items,
                'item_kind': item_kind,
            })
        return sections_data

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    @http.route(['/my/contribution-evaluations'], type='http', auth='user', website=True)
    def portal_evaluation_list(self, **kw):
        employee = request.env.user.employee_id
        evaluations = request.env['staff.contribution.evaluation']
        if employee:
            evaluations = evaluations.sudo().search(
                [('employee_id', '=', employee.id)],
                order='evaluation_year desc, quarter desc')
        return request.render(
            'staff_contribution_evaluation.portal_evaluation_list', {
                'evaluations': evaluations,
                'employee': employee,
                'page_name': 'contribution_evaluation',
            })

    @http.route(['/my/contribution-evaluations/new'], type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def portal_evaluation_new(self, quarter=None, evaluation_year=None, **kw):
        employee = request.env.user.employee_id
        if not employee:
            raise AccessError(
                request.env._("No employee record is linked to your user."))
        vals = {'employee_id': employee.id}
        if quarter:
            vals['quarter'] = quarter
        if evaluation_year:
            vals['evaluation_year'] = evaluation_year
        evaluation = request.env['staff.contribution.evaluation'].sudo().create(vals)
        return request.redirect('/my/contribution-evaluations/%d' % evaluation.id)

    @http.route(['/my/contribution-evaluations/<int:evaluation_id>'], type='http',
                auth='user', website=True)
    def portal_evaluation_form(self, evaluation_id, **kw):
        evaluation = self._get_own_evaluation(evaluation_id)
        return request.render(
            'staff_contribution_evaluation.portal_evaluation_form', {
                'evaluation': evaluation,
                'sections_data': self._build_sections_data(evaluation),
                'page_name': 'contribution_evaluation',
            })

    @http.route(['/my/contribution-evaluations/<int:evaluation_id>/line/<string:section>/add'],
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_evaluation_line_add(self, evaluation_id, section, **post):
        """Single-entry add, used only for sections with no tick list
        (E, G, K, M, O, P, R)."""
        evaluation = self._get_own_evaluation(evaluation_id)
        if evaluation.state != 'draft':
            raise UserError(
                request.env._("This evaluation can no longer be edited."))
        cfg = SECTION_FORM_CONFIG.get(section)
        if not cfg or cfg.get('has_types') or cfg.get('has_departments'):
            raise UserError(request.env._("Unknown or unsupported section."))

        vals = {'evaluation_id': evaluation.id, 'section': section}
        for fname, _label, ftype in cfg['fields']:
            raw = post.get(fname)
            if ftype == 'integer':
                vals[fname] = int(raw) if raw else 0
            elif ftype == 'monetary':
                vals[fname] = float(raw) if raw else 0.0
            else:
                vals[fname] = raw or ''

        if not vals.get('name'):
            raise UserError(
                request.env._("Please fill in the required field before saving."))

        if cfg.get('has_self_rating'):
            self_rating = post.get('self_rating')
            vals['self_rating'] = int(self_rating) if self_rating else 0

        has_evidence = post.get('has_evidence') == 'on'
        if cfg.get('has_evidence'):
            vals['has_evidence'] = has_evidence

        line = request.env['staff.contribution.line'].sudo().create(vals)

        if cfg.get('has_evidence') and has_evidence:
            upload = request.httprequest.files.get('evidence_file')
            if upload and upload.filename:
                request.env['staff.contribution.evidence'].sudo().create({
                    'evaluation_id': evaluation.id,
                    'line_id': line.id,
                    'name': upload.filename,
                    'attachment': base64.b64encode(upload.read()),
                    'attachment_filename': upload.filename,
                })

        return request.redirect(
            '/my/contribution-evaluations/%d#section-%s' % (evaluation.id, section))

    @http.route(['/my/contribution-evaluations/<int:evaluation_id>/section/<string:section>/bulk-add'],
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_evaluation_bulk_add(self, evaluation_id, section, **post):
        """Row-table add for tick-list sections (A, B, C, D, F, H, I, J, L,
        N, Q): one row per contribution type (or department for H), each
        with its own independent field values. Every ticked row becomes
        its own separate contribution entry."""
        evaluation = self._get_own_evaluation(evaluation_id)
        if evaluation.state != 'draft':
            raise UserError(
                request.env._("This evaluation can no longer be edited."))
        cfg = SECTION_FORM_CONFIG.get(section)
        if not cfg or not (cfg.get('has_types') or cfg.get('has_departments')):
            raise UserError(request.env._("Unknown or unsupported section."))

        form = request.httprequest.form
        if cfg.get('has_departments'):
            items = request.env['hr.department'].sudo().search(
                [('company_id', '=', evaluation.company_id.id)])
            item_field = 'department_id'
        else:
            items = request.env['staff.contribution.type'].sudo().search(
                [('section', '=', section)])
            item_field = 'contribution_type_id'

        vals_list = []
        for item in items:
            if form.get('include_%d' % item.id) != 'on':
                continue
            name = form.get('name_%d' % item.id)
            if not name:
                raise UserError(
                    request.env._("Please enter an Activity for every "
                                  "ticked row."))
            vals = {
                'evaluation_id': evaluation.id,
                'section': section,
                item_field: item.id,
                'name': name,
            }
            for fname, _label, ftype in cfg['fields']:
                if fname == 'name':
                    continue
                raw = form.get('%s_%d' % (fname, item.id))
                if ftype == 'integer':
                    vals[fname] = int(raw) if raw else 0
                elif ftype == 'monetary':
                    vals[fname] = float(raw) if raw else 0.0
                else:
                    vals[fname] = raw or ''
            if cfg.get('has_self_rating'):
                raw = form.get('self_rating_%d' % item.id)
                vals['self_rating'] = int(raw) if raw else 0
            if cfg.get('has_evidence'):
                vals['has_evidence'] = (
                    form.get('has_evidence_%d' % item.id) == 'on')
            vals_list.append(vals)

        if not vals_list:
            raise UserError(
                request.env._("Tick at least one row before submitting."))

        request.env['staff.contribution.line'].sudo().create(vals_list)
        return request.redirect(
            '/my/contribution-evaluations/%d#section-%s' % (evaluation.id, section))

    @http.route(['/my/contribution-evaluations/<int:evaluation_id>/line/<int:line_id>/delete'],
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_evaluation_line_delete(self, evaluation_id, line_id, **post):
        evaluation = self._get_own_evaluation(evaluation_id)
        if evaluation.state != 'draft':
            raise UserError(
                request.env._("This evaluation can no longer be edited."))
        line = request.env['staff.contribution.line'].sudo().browse(line_id)
        if line.evaluation_id != evaluation:
            raise AccessError(request.env._("This entry is not accessible."))
        section = line.section
        line.unlink()
        return request.redirect(
            '/my/contribution-evaluations/%d#section-%s' % (evaluation.id, section))

    @http.route(['/my/contribution-evaluations/<int:evaluation_id>/save-remarks'],
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_evaluation_save_remarks(self, evaluation_id, employee_remarks=None, **post):
        evaluation = self._get_own_evaluation(evaluation_id)
        if evaluation.state != 'draft':
            raise UserError(
                request.env._("This evaluation can no longer be edited."))
        evaluation.write({'employee_remarks': employee_remarks or ''})
        return request.redirect('/my/contribution-evaluations/%d' % evaluation.id)

    @http.route(['/my/contribution-evaluations/<int:evaluation_id>/submit'],
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_evaluation_submit(self, evaluation_id, **post):
        evaluation = self._get_own_evaluation(evaluation_id)
        evaluation.action_submit()
        return request.redirect('/my/contribution-evaluations/%d' % evaluation.id)
