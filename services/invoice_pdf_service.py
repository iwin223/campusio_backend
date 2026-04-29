"""Invoice PDF Generation Service"""
from jinja2 import Template
from xhtml2pdf import pisa
from datetime import datetime
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


class InvoicePDFService:
    """Service for generating subscription invoice PDFs"""

    INVOICE_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            * { margin: 0; padding: 0; }
            body { font-family: Arial, sans-serif; color: #333; background: white; }
            .invoice-container { max-width: 800px; margin: 0 auto; padding: 20px; }
            .invoice-header { border-bottom: 2px solid #3b82f6; padding-bottom: 20px; margin-bottom: 30px; }
            .header-row { display: flex; justify-content: space-between; align-items: start; }
            .school-info h1 { font-size: 28px; color: #1e3a8a; margin-bottom: 5px; }
            .school-info p { color: #666; font-size: 13px; }
            .invoice-meta { text-align: right; }
            .invoice-meta p { margin: 5px 0; font-size: 13px; }
            .invoice-title { font-size: 20px; font-weight: bold; color: #1e3a8a; margin-bottom: 5px; }
            .invoice-number { color: #666; font-size: 13px; }
            
            .details-section { margin-bottom: 30px; }
            .section-title { font-size: 14px; font-weight: bold; margin-bottom: 10px; text-transform: uppercase; color: #1e3a8a; }
            .details-row { display: flex; margin: 8px 0; font-size: 13px; }
            .details-label { width: 40%; font-weight: bold; color: #475569; }
            .details-value { width: 60%; color: #1e293b; }
            
            .items-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
            .items-table th { 
                background: #f1f5f9; 
                padding: 12px; 
                text-align: left; 
                font-weight: bold;
                font-size: 13px;
                border-bottom: 2px solid #e2e8f0;
                color: #1e293b;
            }
            .items-table td { 
                padding: 12px; 
                border-bottom: 1px solid #e2e8f0;
                font-size: 13px;
            }
            .items-table tr:last-child td { border-bottom: 2px solid #e2e8f0; }
            
            .amount-column { text-align: right; }
            .amount-cell { font-weight: bold; color: #1e293b; }
            
            .summary-section { margin: 30px 0; }
            .summary-row { display: flex; justify-content: flex-end; margin: 8px 0; font-size: 13px; }
            .summary-label { width: 200px; text-align: right; padding-right: 20px; }
            .summary-value { width: 120px; text-align: right; font-weight: bold; }
            
            .summary-row.total { 
                border-top: 2px solid #3b82f6; 
                border-bottom: 2px solid #3b82f6;
                padding: 10px 0;
                margin: 15px 0;
                font-size: 16px;
            }
            .summary-row.total .summary-value { color: #1e3a8a; }
            
            .payment-status { 
                margin: 20px 0; 
                padding: 15px; 
                background: #f0fdf4; 
                border-left: 4px solid #22c55e;
                font-size: 13px;
            }
            .payment-status.partial { 
                background: #fffbeb; 
                border-left-color: #f59e0b;
            }
            .payment-status.pending { 
                background: #fef2f2; 
                border-left-color: #ef4444;
            }
            
            .footer { 
                margin-top: 40px; 
                padding-top: 20px; 
                border-top: 1px solid #e2e8f0;
                text-align: center;
                font-size: 12px;
                color: #666;
            }
            .footer p { margin: 5px 0; }
            
            .status-badge { 
                display: inline-block;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                text-transform: uppercase;
            }
            .status-badge.paid { background: #dcfce7; color: #166534; }
            .status-badge.partial { background: #fef3c7; color: #b45309; }
            .status-badge.issued { background: #fee2e2; color: #991b1b; }
            
            .note { 
                background: #f8fafc;
                padding: 15px;
                border-radius: 4px;
                margin: 20px 0;
                font-size: 12px;
                color: #475569;
            }
        </style>
    </head>
    <body>
        <div class="invoice-container">
            <!-- Header -->
            <div class="invoice-header">
                <div class="header-row">
                    <div class="school-info">
                        <h1>{{ school_name }}</h1>
                        <p>School ERP Platform Subscription Invoice</p>
                    </div>
                    <div class="invoice-meta">
                        <div class="invoice-title">INVOICE</div>
                        <div class="invoice-number">#{{ invoice_number }}</div>
                        <p><strong>Date:</strong> {{ issued_date }}</p>
                        <p><strong>Due Date:</strong> {{ due_date }}</p>
                    </div>
                </div>
            </div>

            <!-- Invoice Details -->
            <div class="details-section">
                <div class="section-title">Invoice Details</div>
                <div class="details-row">
                    <div class="details-label">Academic Year:</div>
                    <div class="details-value">{{ academic_year }}</div>
                </div>
                <div class="details-row">
                    <div class="details-label">Term:</div>
                    <div class="details-value">{{ term }}</div>
                </div>
                <div class="details-row">
                    <div class="details-label">Billing Period:</div>
                    <div class="details-value">{{ academic_year }} - {{ term }}</div>
                </div>
                <div class="details-row">
                    <div class="details-label">Invoice Status:</div>
                    <div class="details-value"><span class="status-badge {{ status_class }}">{{ status }}</span></div>
                </div>
            </div>

            <!-- Items Table -->
            <table class="items-table">
                <thead>
                    <tr>
                        <th>Description</th>
                        <th>Student Count</th>
                        <th>Unit Price</th>
                        <th class="amount-column">Amount</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Platform Subscription Fee</td>
                        <td>{{ student_count }}</td>
                        <td>GHS {{ unit_price }}</td>
                        <td class="amount-column"><span class="amount-cell">GHS {{ subtotal }}</span></td>
                    </tr>
                </tbody>
            </table>

            <!-- Summary -->
            <div class="summary-section">
                <div class="summary-row">
                    <div class="summary-label">Subtotal:</div>
                    <div class="summary-value">GHS {{ subtotal }}</div>
                </div>
                {% if tax_amount > 0 %}
                <div class="summary-row">
                    <div class="summary-label">Tax (0%):</div>
                    <div class="summary-value">GHS {{ tax_amount }}</div>
                </div>
                {% endif %}
                <div class="summary-row total">
                    <div class="summary-label">Total Amount Due:</div>
                    <div class="summary-value">GHS {{ total_amount }}</div>
                </div>
                <div class="summary-row">
                    <div class="summary-label">Amount Paid:</div>
                    <div class="summary-value" style="color: #22c55e;">GHS {{ amount_paid }}</div>
                </div>
                <div class="summary-row">
                    <div class="summary-label">Outstanding Balance:</div>
                    <div class="summary-value" style="color: #ef4444;">GHS {{ outstanding_balance }}</div>
                </div>
            </div>

            <!-- Payment Status -->
            {% if status == 'PAID' %}
            <div class="payment-status">
                <strong>✓ Payment Status: FULLY PAID</strong><br>
                Thank you for your payment. This invoice has been settled in full.
                {% if paid_date %}
                Payment received on: {{ paid_date }}
                {% endif %}
            </div>
            {% elif status == 'PARTIAL' %}
            <div class="payment-status partial">
                <strong>⚠ Payment Status: PARTIALLY PAID</strong><br>
                Outstanding balance of GHS {{ outstanding_balance }} remains due. Please settle by {{ due_date }}.
            </div>
            {% else %}
            <div class="payment-status pending">
                <strong>⚠ Payment Status: OUTSTANDING</strong><br>
                Payment of GHS {{ total_amount }} is due by {{ due_date }}.
            </div>
            {% endif %}

            <!-- Note -->
            <div class="note">
                <strong>Payment Instructions:</strong><br>
                Please remit payment through our secure payment portal using Mobile Money (MTN, Vodafone, AirtelTigo) 
                or Debit/Credit Card. Reference your invoice number {{ invoice_number }} when making payment.
            </div>

            <!-- Footer -->
            <div class="footer">
                <p><strong>School ERP Platform</strong></p>
                <p>For payment inquiries: info@campusio.online | +233 53 448 4781</p>
                <p>Generated on {{ generated_date }}</p>
            </div>
        </div>
    </body>
    </html>
    """

    @staticmethod
    def format_invoice_data(invoice: dict, school_name: str) -> dict:
        """Format invoice data for PDF template"""
        issued_date = invoice.get("issued_at")
        if isinstance(issued_date, str):
            issued_date = datetime.fromisoformat(issued_date.replace("Z", "+00:00"))

        due_date = invoice.get("due_date")
        if isinstance(due_date, str):
            due_date = datetime.fromisoformat(due_date.replace("Z", "+00:00"))

        paid_date = invoice.get("paid_at")
        if paid_date and isinstance(paid_date, str):
            paid_date = datetime.fromisoformat(paid_date.replace("Z", "+00:00"))

        status = invoice.get("status", "ISSUED")
        outstanding = invoice.get("total_amount", 0) - invoice.get("amount_paid", 0)

        status_class = {
            "PAID": "paid",
            "PARTIAL": "partial",
            "ISSUED": "issued",
            "DRAFT": "issued"
        }.get(status, "issued")

        return {
            "invoice_number": invoice.get("invoice_number", "N/A"),
            "school_name": school_name,
            "academic_year": invoice.get("academic_year", "N/A"),
            "term": invoice.get("term", "").capitalize(),
            "student_count": invoice.get("student_count", 0),
            "unit_price": f"{invoice.get('unit_price', 0):.2f}",
            "subtotal": f"{invoice.get('subtotal', invoice.get('total_amount', 0)):.2f}",
            "tax_amount": f"{invoice.get('tax_amount', 0):.2f}",
            "total_amount": f"{invoice.get('total_amount', 0):.2f}",
            "amount_paid": f"{invoice.get('amount_paid', 0):.2f}",
            "outstanding_balance": f"{outstanding:.2f}",
            "status": status,
            "status_class": status_class,
            "issued_date": issued_date.strftime("%B %d, %Y") if issued_date else "N/A",
            "due_date": due_date.strftime("%B %d, %Y") if due_date else "N/A",
            "paid_date": paid_date.strftime("%B %d, %Y") if paid_date else None,
            "generated_date": datetime.now().strftime("%B %d, %Y at %I:%M %p"),
        }

    @classmethod
    def generate_pdf(cls, invoice: dict, school_name: str) -> bytes:
        """
        Generate PDF from invoice data

        Args:
            invoice: Invoice dictionary with all required fields
            school_name: Name of the school

        Returns:
            PDF bytes
        """
        try:
            # Format data for template
            invoice_data = cls.format_invoice_data(invoice, school_name)

            # Render HTML
            template = Template(cls.INVOICE_TEMPLATE)
            html_content = template.render(**invoice_data)

            # Generate PDF
            pdf_buffer = BytesIO()
            pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer, encoding="UTF-8")

            if pisa_status.err:
                raise Exception(f"PDF generation error: {pisa_status.err}")

            pdf_buffer.seek(0)
            pdf_bytes = pdf_buffer.getvalue()

            if not pdf_bytes or len(pdf_bytes) == 0:
                raise Exception("PDF generation produced empty output")

            return pdf_bytes

        except Exception as e:
            logger.error(f"Failed to generate invoice PDF: {str(e)}")
            raise Exception(f"Failed to generate invoice PDF: {str(e)}")
