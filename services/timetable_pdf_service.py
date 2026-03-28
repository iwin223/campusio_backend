"""Timetable PDF Generation Service"""
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa
from datetime import datetime
from io import BytesIO
import os
from pathlib import Path


class TimetablePDFService:
    """Service for generating timetable PDFs"""

    def __init__(self):
        # Setup Jinja2 environment
        template_dir = Path(__file__).parent.parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True
        )

    def generate_pdf(self, timetable_data: dict) -> bytes:
        """
        Generate PDF from timetable data

        Args:
            timetable_data: Dictionary containing all timetable information

        Returns:
            PDF bytes
        """
        try:
            # Render template
            template = self.env.get_template("timetable.html")
            html_content = template.render(**timetable_data)

            # Generate PDF using xhtml2pdf
            pdf_buffer = BytesIO()
            pisa_status = pisa.CreatePDF(
                html_content,
                dest=pdf_buffer,
                encoding='UTF-8'
            )

            if pisa_status.err:
                raise Exception("Failed to generate PDF: pisa error occurred")

            pdf_buffer.seek(0)
            pdf_bytes = pdf_buffer.getvalue()

            return pdf_bytes

        except Exception as e:
            raise Exception(f"PDF generation failed: {str(e)}")

    def format_timetable_for_pdf(self, timetable_data: dict) -> dict:
        """
        Format timetable data for PDF template

        Args:
            timetable_data: Raw timetable data from API

        Returns:
            Formatted data for template
        """
        # Add current date and time
        formatted_data = {
            **timetable_data,
            "generated_at": datetime.now().strftime("%B %d, %Y at %I:%M %p"),
            "academic_year": "2025/2026"  # This could be made dynamic
        }

        # Ensure schedule has all days even if empty
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        day_labels = {
            'monday': 'Monday',
            'tuesday': 'Tuesday',
            'wednesday': 'Wednesday',
            'thursday': 'Thursday',
            'friday': 'Friday'
        }

        if 'schedule' in formatted_data:
            for day in days:
                if day not in formatted_data['schedule']:
                    formatted_data['schedule'][day] = []

        formatted_data['day_labels'] = day_labels
        formatted_data['days_order'] = days

        return formatted_data