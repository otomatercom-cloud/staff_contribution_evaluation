# -*- coding: utf-8 -*-
# Part of Otomater. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Single source of truth for contribution sections (A - R).
SECTION_SELECTION = [
    ('a', 'A. Revenue Contribution'),
    ('b', 'B. Cost Reduction'),
    ('c', 'C. Digital & Marketing Contribution'),
    ('d', 'D. Student Success Contribution'),
    ('e', 'E. Placement Contribution'),
    ('f', 'F. Partnerships & Institutional Contribution'),
    ('g', 'G. Innovation'),
    ('h', 'H. Cross Department Contribution'),
    ('i', 'I. Process Improvement'),
    ('j', 'J. Student & Parent Satisfaction'),
    ('k', 'K. Team Development'),
    ('l', 'L. Brand Building'),
    ('m', 'M. Risk Prevention'),
    ('n', 'N. AI & Technology Adoption'),
    ('o', 'O. New Opportunities Identified'),
    ('p', 'P. Customer Retention'),
    ('q', 'Q. Special Recognition'),
    ('r', 'R. Best Contribution of the Quarter'),
]


class StaffContributionType(models.Model):
    _name = 'staff.contribution.type'
    _description = 'Staff Contribution Type'
    _order = 'section, sequence, id'

    name = fields.Char(required=True, translate=True)
    section = fields.Selection(
        SECTION_SELECTION, required=True, index=True,
        help="Contribution section of the quarterly evaluation form this "
             "type belongs to.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()

    _sql_constraints = [
        ('name_section_uniq', 'unique(name, section)',
         'A contribution type with this name already exists in this section.'),
    ]


class StaffEvidenceType(models.Model):
    _name = 'staff.evidence.type'
    _description = 'Staff Contribution Evidence Type'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'This evidence type already exists.'),
    ]


class StaffEvaluationCriteria(models.Model):
    _name = 'staff.evaluation.criteria'
    _description = 'Staff Evaluation Scorecard Criteria'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    weight = fields.Float(
        required=True, default=0.0,
        help="Weight of this criterion in percent. All active criteria "
             "should total 100%.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(
        help="Explain to managers what this criterion measures and how the "
             "0-100 score should be assigned.")
    mapped_sections = fields.Char(
        string='Auto-Calculate From Sections',
        help="Comma-separated contribution section codes (e.g. \"a,b,f\") "
             "whose entries feed this criterion's auto-calculated score, "
             "based on the average Manager/HR Rating (0-5) of contributions "
             "in those sections, scaled to 0-100. Leave blank to enter this "
             "criterion's score manually with no auto-suggestion. Section "
             "codes: a=Revenue, b=Cost Reduction, c=Digital & Marketing, "
             "d=Student Success, e=Placement, f=Partnerships, g=Innovation, "
             "h=Cross Department, i=Process Improvement, j=Satisfaction, "
             "k=Team Development, l=Brand Building, m=Risk Prevention, "
             "n=AI & Technology, o=Opportunities, p=Retention, "
             "q=Recognition, r=Best Contribution.")

    def _get_mapped_section_codes(self):
        self.ensure_one()
        if not self.mapped_sections:
            return []
        return [c.strip() for c in self.mapped_sections.split(',') if c.strip()]

    @api.constrains('weight')
    def _check_weight(self):
        for criteria in self:
            if criteria.weight < 0 or criteria.weight > 100:
                raise ValidationError(
                    self.env._("The weight of an evaluation criterion must be "
                               "between 0 and 100."))
