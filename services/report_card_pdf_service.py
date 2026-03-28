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
        
        # Group grades by subject
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
                    "grades": [],
                    "total_score": 0,
                    "total_max": 0,
                }
            
            # Calculate percentage and letter grade
            percentage = round(grade.score / grade.max_score * 100, 1) if grade.max_score > 0 else 0
            letter_grade = ReportCardPDFService._get_letter_grade(percentage)
            
            subjects_data[subject_name]["grades"].append({
                "assessment_type": grade.assessment_type.value if hasattr(grade.assessment_type, 'value') else str(grade.assessment_type),
                "score": grade.score,
                "max_score": grade.max_score,
                "percentage": percentage,
                "grade": letter_grade["grade"],
                "description": letter_grade["description"],
                "date_display": grade.created_at.strftime("%d %b %Y") if hasattr(grade.created_at, 'strftime') else str(grade.created_at)
            })
            
            subjects_data[subject_name]["total_score"] += grade.score
            subjects_data[subject_name]["total_max"] += grade.max_score
        
        # Calculate averages for each subject
        subjects_list = []
        for subject_name, data in subjects_data.items():
            avg_percentage = round((data["total_score"] / data["total_max"] * 100) if data["total_max"] > 0 else 0, 1)
            avg_grade = ReportCardPDFService._get_letter_grade(avg_percentage)
            
            subjects_list.append({
                "subject_name": subject_name,
                "subject_code": data["subject_code"],
                "grades": data["grades"],
                "total_score": data["total_score"],
                "total_max": data["total_max"],
                "average_percentage": avg_percentage,
                "average_grade": avg_grade["grade"],
                "average_description": avg_grade["description"]
            })
        
        # Calculate overall performance
        if grades:
            total_score = sum(g.score for g in grades)
            total_max = sum(g.max_score for g in grades)
            overall_percentage = round((total_score / total_max * 100) if total_max > 0 else 0, 1)
        else:
            total_score = 0
            total_max = 0
            overall_percentage = 0
        
        overall_grade_info = ReportCardPDFService._get_letter_grade(overall_percentage)
        
        return {
            "school_name": get_value(student, 'school_name', 'School Name Not Available'),
            "student_name": get_value(student, 'first_name', 'Name not Available'),
            "student_id": get_value(student, 'id', 'Id not Available'),
            "class_name": get_value(student, 'class_name', 'Not Assigned'),
            "academic_term": academic_term_name or "Term 1, 2026",
            "generated_date": datetime.utcnow().strftime("%d %B %Y"),
            "attendance_percentage": get_value(report_card, 'attendance_percentage', 'Not Available'),
            "class_size": get_value(report_card, 'class_size', 'Not Available'),
            "position": get_value(report_card, 'position', 'Not Available'),
            "overall_average": overall_percentage,
            "overall_grade": overall_grade_info["grade"],
            "overall_description": overall_grade_info["description"],
            "subjects": subjects_list,
            "class_teacher_remarks": get_value(report_card, 'class_teacher_remarks', 'Not Available'),
            "head_teacher_remarks": get_value(report_card, 'head_teacher_remarks', 'Not Available'),
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
