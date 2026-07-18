"""Report Card PDF Generation Service"""
from jinja2 import Environment, FileSystemLoader, Template
from xhtml2pdf import pisa
from datetime import datetime
from io import BytesIO
import os
import re
from pathlib import Path


class ReportCardPDFService:
    """Service for generating report card PDFs"""
    
    def __init__(self):
        # Setup Jinja2 environment for file-based templates
        template_dir = Path(__file__).parent.parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True
        )
        self.default_template_name = "report_card.html"
    
    def render_html(self, report_data: dict, template_html: str = None) -> str:
        """
        Render report card as HTML (for preview in modal)
        
        Args:
            report_data: Dictionary containing all report card information
            template_html: Custom HTML template (Jinja2) string. If None, uses default file
            
        Returns:
            Rendered HTML string
        """
        try:
            if template_html:
                # Log the available keys for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Available template variables: {list(report_data.keys())}")
                
                template = Template(template_html, autoescape=False)
                html_content = template.render(**report_data)
            else:
                template = self.env.get_template(self.default_template_name)
                html_content = template.render(**report_data)
            
            return html_content
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Template rendering failed: {str(e)}")
            logger.error(f"Available data keys: {list(report_data.keys()) if report_data else 'Empty data'}")
            raise Exception(f"Failed to render report card HTML: {str(e)}")
    
    def generate_pdf(self, report_data: dict, template_html: str = None) -> bytes:
        """
        Generate PDF from report card data
        
        Args:
            report_data: Dictionary containing all report card information
            template_html: Custom HTML template (Jinja2) string. If None, uses default file
            
        Returns:
            PDF bytes
        """
        try:
            # Render HTML first
            html_content = self.render_html(report_data, template_html=template_html)
            
            # Ensure proper XHTML structure for xhtml2pdf
            html_content = self._ensure_xhtml_compliance(html_content)
            
            # Generate PDF using xhtml2pdf
            pdf_buffer = BytesIO()
            pisa_status = pisa.CreatePDF(
                html_content,
                dest=pdf_buffer,
                encoding='UTF-8'
            )
            
            if pisa_status.err:
                raise Exception(f"PDF generation error: {pisa_status.err}")
            
            pdf_buffer.seek(0)
            pdf_bytes = pdf_buffer.getvalue()
            
            if not pdf_bytes:
                raise Exception("PDF generation produced empty output")
            
            return pdf_bytes
        except Exception as e:
            raise Exception(f"Failed to generate report card PDF: {str(e)}")
    
    @staticmethod
    def _ensure_xhtml_compliance(html_content: str) -> str:
        """
        Ensure HTML is XHTML-compliant for xhtml2pdf
        xhtml2pdf requires proper XHTML structure
        """
        # Add DOCTYPE if missing
        if '<!DOCTYPE' not in html_content and '<html' in html_content:
            html_content = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n' + html_content
        
        # Ensure <html> tag has proper attributes
        if '<html>' in html_content:
            html_content = html_content.replace('<html>', '<html xmlns="http://www.w3.org/1999/xhtml">')
        
        # Fix unclosed img, br, hr tags for XHTML
        import re
        html_content = re.sub(r'<img([^>]*)>', r'<img\1 />', html_content)
        html_content = re.sub(r'<br>', r'<br />', html_content)
        html_content = re.sub(r'<hr>', r'<hr />', html_content)
        
        # Wrap content in proper HTML structure if missing
        if '<html' not in html_content.lower():
            html_content = f'<html><head><meta charset="UTF-8"/></head><body>{html_content}</body></html>'
        
        return html_content
    
    @staticmethod
    def format_grade_data(report_card, grades, subjects_map, student, academic_term_name: str = None) -> dict:
        """
        Format report card and grades into template data
        
        Args:
            report_card: ReportCard model instance
            grades: List of Grade model instances
            subjects_map: Dictionary of subject_id -> Subject model
            student: Student model instance or dictionary with student data
            academic_term_name: Name of the academic term
            
        Returns:
            Dictionary ready for template rendering
        """
        from datetime import datetime
        
        # Helper function to get values from object or dict
        def get_value(obj, key, default):
            if isinstance(obj, dict):
                return obj.get(key, default)
            else:
                return getattr(obj, key, default)
        
        # ── GES SBA split ────────────────────────────────────────────────────
        # Termly reports follow the GES School Based Assessment format:
        # CLASS SCORE (SBA: classwork/homework/quiz/mid-term/project) scaled to
        # 50%, EXAM SCORE (end-of-term) scaled to 50%, TOTAL out of 100 graded
        # on the 1-9 GES scale.
        EXAM_TYPES = {"end_of_term"}

        subjects_data = {}
        for grade in grades:
            subject = subjects_map.get(grade.subject_id)
            subject_name = subject.name if subject else "Unknown"
            subject_code = subject.code if subject and hasattr(subject, 'code') else "N/A"

            if subject_name not in subjects_data:
                subjects_data[subject_name] = {
                    "subject_id": grade.subject_id,
                    "subject_code": subject_code,
                    "subject_name": subject_name,
                    "sba_score": 0.0, "sba_max": 0.0,
                    "exam_score": 0.0, "exam_max": 0.0,
                }

            atype = grade.assessment_type.value if hasattr(grade.assessment_type, 'value') else str(grade.assessment_type)
            bucket = subjects_data[subject_name]
            if atype in EXAM_TYPES:
                bucket["exam_score"] += grade.score
                bucket["exam_max"] += grade.max_score
            else:
                bucket["sba_score"] += grade.score
                bucket["sba_max"] += grade.max_score

        subjects_list = []
        subject_totals = []
        for subject_name, data in sorted(subjects_data.items()):
            class_score_50 = round((data["sba_score"] / data["sba_max"]) * 50, 1) if data["sba_max"] > 0 else 0.0
            exam_score_50 = round((data["exam_score"] / data["exam_max"]) * 50, 1) if data["exam_max"] > 0 else 0.0
            total_100 = round(class_score_50 + exam_score_50, 1)
            grade_info = ReportCardPDFService._get_letter_grade(total_100)
            subject_totals.append(total_100)

            subjects_list.append({
                "subject_name": subject_name,
                "subject_code": data["subject_code"],
                "class_score": class_score_50,     # out of 50
                "exam_score": exam_score_50,       # out of 50
                "total_score": total_100,          # out of 100
                "grade": grade_info["grade"],      # GES 1-9
                "remarks": grade_info["description"],
            })

        overall_percentage = round(sum(subject_totals) / len(subject_totals), 1) if subject_totals else 0
        overall_grade_info = ReportCardPDFService._get_letter_grade(overall_percentage)

        # Attendance: prefer explicit day counts (GES format shows "x out of y")
        days_present = get_value(report_card, 'days_present', None)
        days_total = get_value(report_card, 'days_total', None)
        if days_present is not None and days_total:
            attendance_display = f"{days_present} out of {days_total}"
        else:
            pct = get_value(report_card, 'attendance_percentage', None)
            attendance_display = f"{pct}%" if pct is not None else "Not Recorded"

        return {
            "school_name": get_value(student, 'school_name', 'School Name Not Available'),
            "student_name": get_value(student, 'first_name', 'Name not Available'),
            "student_id": get_value(student, 'id', 'Id not Available'),
            "class_name": get_value(student, 'class_name', 'Not Assigned'),
            "academic_term": academic_term_name or "Term 1, 2026",
            "generated_date": datetime.utcnow().strftime("%d %B %Y"),
            "attendance_display": attendance_display,
            "attendance_percentage": get_value(report_card, 'attendance_percentage', 'Not Available'),
            "class_size": get_value(report_card, 'class_size', 'Not Available'),
            "position": get_value(report_card, 'position', 'Not Available'),
            "overall_average": overall_percentage,
            "overall_grade": overall_grade_info["grade"],
            "overall_description": overall_grade_info["description"],
            "subjects": subjects_list,
            "class_teacher_remarks": get_value(report_card, 'class_teacher_remarks', None) or "",
            "head_teacher_remarks": get_value(report_card, 'head_teacher_remarks', None) or "",
            # GES SBA footer blocks
            "attitude": get_value(report_card, 'attitude', None) or "",
            "conduct": get_value(report_card, 'conduct', None) or "",
            "interest": get_value(report_card, 'interest', None) or "",
            "vacation_date": get_value(report_card, 'vacation_date', None) or "",
            "reopening_date": get_value(report_card, 'reopening_date', None) or "",
            "promoted_to": get_value(report_card, 'promoted_to', None) or "",
        }
    
    @staticmethod
    def _get_letter_grade(percentage: float) -> dict:
        """Convert percentage to GES grade"""
        GES_GRADE_SCALE = [
            {"grade": "1", "min_score": 80, "max_score": 100, "description": "Excellent", "gpa_point": 1.0},
            {"grade": "2", "min_score": 70, "max_score": 79, "description": "Very Good", "gpa_point": 2.0},
            {"grade": "3", "min_score": 60, "max_score": 69, "description": "Good", "gpa_point": 3.0},
            {"grade": "4", "min_score": 55, "max_score": 59, "description": "Credit", "gpa_point": 4.0},
            {"grade": "5", "min_score": 50, "max_score": 54, "description": "Pass", "gpa_point": 5.0},
            {"grade": "6", "min_score": 45, "max_score": 49, "description": "Weak Pass", "gpa_point": 6.0},
            {"grade": "7", "min_score": 40, "max_score": 44, "description": "Very Weak", "gpa_point": 7.0},
            {"grade": "8", "min_score": 35, "max_score": 39, "description": "Poor", "gpa_point": 8.0},
            {"grade": "9", "min_score": 0, "max_score": 34, "description": "Fail", "gpa_point": 9.0},
        ]
        
        for grade in GES_GRADE_SCALE:
            if grade["min_score"] <= percentage <= grade["max_score"]:
                return grade
        return GES_GRADE_SCALE[-1]  # Return fail grade if below 0
