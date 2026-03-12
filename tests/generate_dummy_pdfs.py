"""
Generate dummy PDF documents for testing the Intelli-Credit pipeline.

Creates 6 mandatory + 2 optional PDF documents with realistic credit data
for a Steel Manufacturing company: "Rajesh Steel Industries Pvt Ltd"
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.units import inch
import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "test_docs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

styles = getSampleStyleSheet()
title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=18, spaceAfter=20)
heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14, spaceAfter=12, spaceBefore=18)
body_style = ParagraphStyle('CustomBody', parent=styles['Normal'], fontSize=10, spaceAfter=8, alignment=TA_JUSTIFY, leading=14)
small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=8, textColor=colors.grey)


def make_table(data, col_widths=None):
    """Create a styled table."""
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5c5c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f8f8')]),
    ]))
    return t


def create_annual_report():
    """W1 — Annual Report for Rajesh Steel Industries Pvt Ltd."""
    path = os.path.join(OUTPUT_DIR, "annual_report_rajesh_steel_fy2025.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=50, bottomMargin=50)
    story = []

    story.append(Paragraph("RAJESH STEEL INDUSTRIES PVT LTD", title_style))
    story.append(Paragraph("Annual Report — Financial Year 2024-25", styles['Heading3']))
    story.append(Paragraph("CIN: L27100MH2005PTC198765 | Registered Office: Plot 42, MIDC Bhiwandi, Maharashtra 421302", small_style))
    story.append(Spacer(1, 20))

    # Director's Report
    story.append(Paragraph("DIRECTOR'S REPORT", heading_style))
    story.append(Paragraph(
        "Dear Shareholders, Your directors present the 20th Annual Report along with the audited financial "
        "statements of Rajesh Steel Industries Pvt Ltd for the financial year ended March 31, 2025. "
        "The company has achieved a revenue of Rs 312.4 crore during FY2025, representing a growth of 8.2% "
        "over FY2024 revenue of Rs 288.7 crore. The EBITDA margin improved to 13.6% at Rs 42.6 crore. "
        "The company's PAT stood at Rs 15.1 crore, compared to Rs 13.2 crore in the previous year.", body_style))
    story.append(Spacer(1, 10))

    # Financial Summary
    story.append(Paragraph("FINANCIAL HIGHLIGHTS", heading_style))
    fin_data = [
        ['Particulars (Rs Crore)', 'FY2025', 'FY2024', 'FY2023'],
        ['Revenue from Operations', '312.4', '288.7', '261.2'],
        ['Cost of Materials', '198.5', '186.3', '170.8'],
        ['Employee Costs', '28.4', '25.9', '23.1'],
        ['EBITDA', '42.6', '38.2', '33.8'],
        ['Depreciation', '12.8', '11.5', '10.2'],
        ['Interest Cost', '9.8', '9.1', '8.4'],
        ['PBT', '20.0', '17.6', '15.2'],
        ['Tax', '4.9', '4.4', '3.8'],
        ['PAT', '15.1', '13.2', '11.4'],
        ['Total Debt', '142.3', '128.5', '115.0'],
        ['Net Worth', '78.2', '67.1', '58.9'],
        ['Debt/Equity Ratio', '1.82x', '1.91x', '1.95x'],
    ]
    story.append(make_table(fin_data, col_widths=[200, 80, 80, 80]))
    story.append(Spacer(1, 15))

    # Related Party Transactions
    story.append(Paragraph("RELATED PARTY TRANSACTIONS", heading_style))
    story.append(Paragraph(
        "The company has entered into the following related party transactions during the year, "
        "all conducted at arm's length basis as per applicable regulations:", body_style))
    rpt_data = [
        ['Party', 'Nature', 'Amount (Rs Cr)', 'Relationship'],
        ['Agarwal Holdings Pvt Ltd', 'Raw Material Purchases', '6.1', 'Promoter Group Entity'],
        ['Priya Trading Company', 'Logistics Services', '2.8', 'Director Interest'],
        ['Green Energy Solutions', 'Power Supply Agreement', '1.5', 'KMP Relative Entity'],
        ['Rajesh Family Trust', 'CSR Donations', '0.4', 'Promoter Trust'],
        ['MegaSteel Suppliers Inc', 'Steel Scrap Imports', '4.2', 'Common Director'],
    ]
    story.append(make_table(rpt_data, col_widths=[140, 115, 80, 130]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "NOTE: The transaction with Agarwal Holdings Pvt Ltd of Rs 6.1 crore for raw material purchases "
        "was not disclosed in the previous year's related party schedule. This was identified during the "
        "current year audit and is being reported for the first time.", body_style))

    story.append(PageBreak())

    # Auditor's Report
    story.append(Paragraph("INDEPENDENT AUDITOR'S REPORT", heading_style))
    story.append(Paragraph(
        "To the Members of Rajesh Steel Industries Pvt Ltd,", body_style))
    story.append(Paragraph(
        "Opinion: We have audited the financial statements of the Company. In our opinion, the financial "
        "statements give a true and fair view, subject to the following qualifications:", body_style))
    story.append(Paragraph(
        "Emphasis of Matter: Without qualifying our opinion, we draw attention to Note 12 regarding "
        "the inventory valuation methodology where the company has changed its method from FIFO to "
        "weighted average, resulting in an increase of Rs 3.2 crore in closing inventory value. "
        "Additionally, Note 18 describes a pending NCLT matter involving the promoter group entity "
        "Agarwal Holdings, with a contingent liability of Rs 8.5 crore. The auditors also note that "
        "certain related party transactions totaling Rs 6.1 crore were not reported in the prior year.", body_style))
    story.append(Spacer(1, 15))

    # Litigation
    story.append(Paragraph("LITIGATION AND CONTINGENT LIABILITIES", heading_style))
    lit_data = [
        ['Case', 'Forum', 'Amount (Rs Cr)', 'Status'],
        ['Income Tax Dispute FY2022', 'ITAT Mumbai', '3.2', 'Pending Appeal'],
        ['Commercial Dispute - ABC Corp', 'NCLT Mumbai', '8.5', 'Pending Hearing'],
        ['GST Demand FY2023', 'GST Appellate', '1.8', 'Show Cause Reply Filed'],
    ]
    story.append(make_table(lit_data, col_widths=[160, 100, 80, 120]))
    story.append(Spacer(1, 15))

    # Board Composition
    story.append(Paragraph("BOARD OF DIRECTORS", heading_style))
    dir_data = [
        ['Name', 'Designation', 'DIN'],
        ['Rajesh Kumar Agarwal', 'Managing Director & Promoter', '00198765'],
        ['Priya Agarwal', 'Whole-time Director', '00198766'],
        ['Vikram Agarwal', 'Executive Director (Operations)', '00198767'],
        ['Suresh Iyer', 'Independent Director', '02345678'],
        ['Dr. Meera Krishnan', 'Independent Director', '03456789'],
        ['Anil Patel (CFO)', 'Chief Financial Officer', 'N/A'],
    ]
    story.append(make_table(dir_data, col_widths=[160, 170, 80]))

    doc.build(story)
    print(f"  ✅ Annual Report: {path}")
    return path


def create_bank_statement():
    """W2 — Bank Statement for 12 months."""
    path = os.path.join(OUTPUT_DIR, "bank_statement_rajesh_steel_12m.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=50, bottomMargin=50)
    story = []

    story.append(Paragraph("STATE BANK OF INDIA", title_style))
    story.append(Paragraph("Current Account Statement — Account No. 39876543210", styles['Heading3']))
    story.append(Paragraph("Account Holder: Rajesh Steel Industries Pvt Ltd | Branch: MIDC Bhiwandi", small_style))
    story.append(Paragraph("Period: April 2024 to March 2025", small_style))
    story.append(Spacer(1, 20))

    # Monthly Summary
    story.append(Paragraph("MONTHLY CASH FLOW SUMMARY", heading_style))
    monthly_data = [
        ['Month', 'Credit (Rs Cr)', 'Debit (Rs Cr)', 'Closing Bal (Rs Cr)'],
        ['Apr-2024', '24.8', '23.1', '8.2'],
        ['May-2024', '26.1', '25.8', '8.5'],
        ['Jun-2024', '25.5', '24.2', '9.8'],
        ['Jul-2024', '28.3', '27.9', '10.2'],
        ['Aug-2024', '27.1', '26.5', '10.8'],
        ['Sep-2024', '29.4', '28.8', '11.4'],
        ['Oct-2024', '30.2', '29.5', '12.1'],
        ['Nov-2024', '26.8', '25.9', '13.0'],
        ['Dec-2024', '25.9', '26.8', '12.1'],
        ['Jan-2025', '27.5', '26.2', '13.4'],
        ['Feb-2025', '28.8', '27.1', '15.1'],
        ['Mar-2025', '31.2', '28.9', '17.4'],
    ]
    story.append(make_table(monthly_data, col_widths=[80, 110, 110, 120]))
    story.append(Spacer(1, 15))

    story.append(Paragraph("ACCOUNT SUMMARY", heading_style))
    summary_data = [
        ['Metric', 'Value'],
        ['Total Credits (12 months)', 'Rs 331.6 Crore'],
        ['Total Debits (12 months)', 'Rs 320.7 Crore'],
        ['Average Monthly Balance', 'Rs 11.83 Crore'],
        ['Peak Balance', 'Rs 17.4 Crore (Mar 2025)'],
        ['Lowest Balance', 'Rs 8.2 Crore (Apr 2024)'],
        ['Cheque Return Count', '2 (May 2024, Dec 2024)'],
        ['Inward Cheque Returns', '0'],
        ['EMI Regularity', '12/12 months on time'],
        ['Term Loan EMI (Monthly)', 'Rs 1.85 Crore'],
        ['Working Capital Utilization', '78% average (Limit: Rs 42 Crore)'],
    ]
    story.append(make_table(summary_data, col_widths=[180, 280]))

    story.append(Spacer(1, 15))
    story.append(Paragraph(
        "Note: Two outward cheque returns were observed — Rs 18.5 lakh in May 2024 (insufficient funds, "
        "cleared on re-presentation) and Rs 12.3 lakh in December 2024 (technical mismatch, cleared same day). "
        "Both were resolved within 24 hours.", body_style))

    doc.build(story)
    print(f"  ✅ Bank Statement: {path}")
    return path


def create_gst_returns():
    """W3 — GST Returns (GSTR-3B & 2A comparison)."""
    path = os.path.join(OUTPUT_DIR, "gst_returns_rajesh_steel_fy2025.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=50, bottomMargin=50)
    story = []

    story.append(Paragraph("GST RETURN SUMMARY — GSTR-3B", title_style))
    story.append(Paragraph("GSTIN: 27AABCR1234M1ZQ | Rajesh Steel Industries Pvt Ltd", styles['Heading3']))
    story.append(Paragraph("Financial Year: 2024-25", small_style))
    story.append(Spacer(1, 20))

    story.append(Paragraph("MONTHLY GSTR-3B FILINGS", heading_style))
    gst_data = [
        ['Month', 'Taxable Value (Rs Cr)', 'CGST (Rs Lakh)', 'SGST (Rs Lakh)', 'IGST (Rs Lakh)', 'ITC Claimed (Rs Lakh)'],
        ['Apr-2024', '24.2', '108.9', '108.9', '72.6', '245.2'],
        ['May-2024', '25.8', '116.1', '116.1', '77.4', '261.3'],
        ['Jun-2024', '24.9', '112.1', '112.1', '74.7', '252.4'],
        ['Jul-2024', '27.6', '124.2', '124.2', '82.8', '279.8'],
        ['Aug-2024', '26.5', '119.3', '119.3', '79.5', '268.5'],
        ['Sep-2024', '28.8', '129.6', '129.6', '86.4', '292.1'],
        ['Oct-2024', '29.5', '132.8', '132.8', '88.5', '299.3'],
        ['Nov-2024', '26.1', '117.5', '117.5', '78.3', '264.7'],
        ['Dec-2024', '25.3', '113.9', '113.9', '75.9', '256.8'],
        ['Jan-2025', '26.8', '120.6', '120.6', '80.4', '271.9'],
        ['Feb-2025', '28.1', '126.5', '126.5', '84.3', '285.4'],
        ['Mar-2025', '30.5', '137.3', '137.3', '91.5', '308.7'],
    ]
    story.append(make_table(gst_data, col_widths=[55, 95, 70, 70, 70, 90]))
    story.append(Spacer(1, 15))

    story.append(Paragraph("GSTR-2A vs GSTR-3B RECONCILIATION", heading_style))
    story.append(Paragraph(
        "ITC Claimed in GSTR-3B (FY2025): Rs 3,286.1 Lakh. "
        "ITC as per GSTR-2A (FY2025): Rs 3,044.8 Lakh. "
        "MISMATCH: Rs 241.3 Lakh (7.3% excess ITC claimed). "
        "This mismatch is primarily attributable to timing differences in vendor return filings "
        "and one disputed invoice from MegaSteel Suppliers worth Rs 98.4 Lakh where the supplier "
        "filed returns under a different GSTIN.", body_style))

    story.append(Paragraph(
        "Reported Revenue in GSTR-3B: Rs 324.1 Crore. "
        "Revenue as per Books: Rs 312.4 Crore. "
        "DIFFERENCE: Rs 11.7 Crore — arising from advance receipts (Rs 8.2 Cr) and job work invoices (Rs 3.5 Cr).", body_style))

    doc.build(story)
    print(f"  ✅ GST Returns: {path}")
    return path


def create_itr():
    """W4 — Income Tax Returns."""
    path = os.path.join(OUTPUT_DIR, "itr_rajesh_steel_ay2025.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=50, bottomMargin=50)
    story = []

    story.append(Paragraph("INCOME TAX RETURN — ITR-6", title_style))
    story.append(Paragraph("Assessment Year: 2025-26 (FY 2024-25)", styles['Heading3']))
    story.append(Paragraph("PAN: AABCR1234M | Rajesh Steel Industries Pvt Ltd", small_style))
    story.append(Spacer(1, 20))

    story.append(Paragraph("COMPUTATION OF INCOME", heading_style))
    itr_data = [
        ['Particulars', 'Amount (Rs Crore)'],
        ['Revenue from Operations', '310.1'],
        ['Other Income', '2.3'],
        ['Total Income', '312.4'],
        ['Cost of Materials Consumed', '198.5'],
        ['Employee Benefit Expenses', '28.4'],
        ['Depreciation (as per IT Act)', '14.2'],
        ['Interest on Borrowings', '9.8'],
        ['Other Expenses', '42.9'],
        ['Total Expenditure', '293.8'],
        ['Profit Before Tax', '18.6'],
        ['Tax @ 25.168%', '4.7'],
        ['Net Profit After Tax', '13.9'],
        ['MAT Credit Utilized', '0.8'],
        ['Tax Paid (Advance + SA)', '5.2'],
        ['Refund Due / (Payable)', '(0.3)'],
    ]
    story.append(make_table(itr_data, col_widths=[280, 150]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("NOTE ON REVENUE RECONCILIATION", heading_style))
    story.append(Paragraph(
        "Revenue as per ITR: Rs 310.1 Crore. Revenue as per Annual Report: Rs 312.4 Crore. "
        "Difference of Rs 2.3 Crore on account of revenue recognition timing for contracts "
        "spanning across financial years (AS-7 / Ind AS 115 adjustments). "
        "Revenue as per GST Returns: Rs 324.1 Crore — difference of Rs 14.0 Crore includes "
        "advance receipts and job work invoicing.", body_style))

    doc.build(story)
    print(f"  ✅ ITR: {path}")
    return path


def create_board_minutes():
    """W6 — Board Minutes."""
    path = os.path.join(OUTPUT_DIR, "board_minutes_rajesh_steel_fy2025.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=50, bottomMargin=50)
    story = []

    story.append(Paragraph("BOARD MEETING MINUTES", title_style))
    story.append(Paragraph("Rajesh Steel Industries Pvt Ltd", styles['Heading3']))
    story.append(Paragraph("Minutes of Board Meeting held on 15 January 2025 at Registered Office", small_style))
    story.append(Spacer(1, 20))

    story.append(Paragraph("ATTENDANCE", heading_style))
    story.append(Paragraph(
        "Present: Mr. Rajesh Kumar Agarwal (MD), Mrs. Priya Agarwal (WTD), Mr. Vikram Agarwal (ED), "
        "Mr. Suresh Iyer (ID), Dr. Meera Krishnan (ID), Mr. Anil Patel (CFO). "
        "Quorum: Present. Chair: Mr. Rajesh Kumar Agarwal.", body_style))

    story.append(Paragraph("AGENDA ITEM 1: APPROVAL OF FINANCIAL RESULTS", heading_style))
    story.append(Paragraph(
        "The Board reviewed and approved the unaudited financial results for Q3 FY2025. "
        "Revenue for Q3 stood at Rs 82.3 crore with PAT of Rs 4.1 crore.", body_style))

    story.append(Paragraph("AGENDA ITEM 2: RELATED PARTY TRANSACTION APPROVAL", heading_style))
    story.append(Paragraph(
        "RESOLVED that the Board approves the Related Party Transactions with Agarwal Holdings Pvt Ltd "
        "for the supply of raw materials at arm's length pricing. The value for FY2025 is estimated at "
        "Rs 6.1 crore. Mr. Rajesh Kumar Agarwal abstained from voting as an interested director. "
        "The Audit Committee had previously reviewed and recommended this transaction.", body_style))
    story.append(Paragraph(
        "NOTE: Independent Director Mr. Suresh Iyer raised a concern regarding the lack of disclosure "
        "of this RPT in the FY2024 annual report. The CFO explained that it was inadvertently omitted "
        "and assured that corrective measures have been implemented.", body_style))

    story.append(Paragraph("AGENDA ITEM 3: BORROWING LIMITS", heading_style))
    story.append(Paragraph(
        "RESOLVED that the Board approves enhancement of borrowing limits from Rs 120 crore to "
        "Rs 180 crore to fund the new rolling mill expansion project at MIDC Bhiwandi Phase-2. "
        "The proposed loan of Rs 50 crore from State Bank of India will be secured against the "
        "factory land and plant & machinery at MIDC Bhiwandi.", body_style))

    story.append(Paragraph("AGENDA ITEM 4: NCLT MATTER UPDATE", heading_style))
    story.append(Paragraph(
        "The Company Secretary updated the Board on the pending NCLT matter (Case No. NCLT/MUM/2024/5678) "
        "involving Agarwal Holdings. The next hearing is scheduled for March 2025. Total contingent "
        "liability exposure stands at Rs 8.5 crore. The Board noted the update.", body_style))

    doc.build(story)
    print(f"  ✅ Board Minutes: {path}")
    return path


def create_shareholding():
    """W7 — Shareholding Pattern."""
    path = os.path.join(OUTPUT_DIR, "shareholding_rajesh_steel_fy2025.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=50, bottomMargin=50)
    story = []

    story.append(Paragraph("SHAREHOLDING PATTERN", title_style))
    story.append(Paragraph("Rajesh Steel Industries Pvt Ltd — As on 31 March 2025", styles['Heading3']))
    story.append(Paragraph("Authorized Capital: Rs 25 Crore | Paid-up Capital: Rs 18.5 Crore", small_style))
    story.append(Spacer(1, 20))

    story.append(Paragraph("PROMOTER AND PROMOTER GROUP HOLDING", heading_style))
    promo_data = [
        ['Shareholder', 'Shares', '% Holding', 'Pledge Status'],
        ['Rajesh Kumar Agarwal', '55,50,000', '30.0%', '18.5% pledged with SBI'],
        ['Priya Agarwal', '27,75,000', '15.0%', 'Nil'],
        ['Vikram Agarwal', '18,50,000', '10.0%', 'Nil'],
        ['Agarwal Holdings Pvt Ltd', '37,00,000', '20.0%', '12.0% pledged with ICICI'],
        ['Rajesh Family Trust', '9,25,000', '5.0%', 'Nil'],
        ['TOTAL PROMOTER', '1,48,00,000', '80.0%', '30.5% of promoter shares pledged'],
    ]
    story.append(make_table(promo_data, col_widths=[145, 80, 70, 160]))
    story.append(Spacer(1, 15))

    story.append(Paragraph("NON-PROMOTER HOLDING", heading_style))
    nonpromo_data = [
        ['Category', 'Shares', '% Holding'],
        ['Institutional Investors', '14,80,000', '8.0%'],
        ['Bodies Corporate', '11,10,000', '6.0%'],
        ['NRIs', '5,55,000', '3.0%'],
        ['Public / Individual', '5,55,000', '3.0%'],
        ['TOTAL NON-PROMOTER', '37,00,000', '20.0%'],
    ]
    story.append(make_table(nonpromo_data, col_widths=[180, 100, 100]))
    story.append(Spacer(1, 15))

    story.append(Paragraph("PLEDGE OF PROMOTER SHARES", heading_style))
    story.append(Paragraph(
        "Total promoter shares pledged: 45,17,500 shares (30.5% of promoter holding). "
        "This represents 24.4% of total paid-up capital. The pledged shares serve as additional "
        "collateral for the company's term loan facilities. The RBI prudential norms require "
        "monitoring of promoter pledge levels above 20%.", body_style))

    doc.build(story)
    print(f"  ✅ Shareholding: {path}")
    return path


def create_legal_notice():
    """W5 — Legal Notices (Optional)."""
    path = os.path.join(OUTPUT_DIR, "legal_notices_rajesh_steel.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=50, bottomMargin=50)
    story = []

    story.append(Paragraph("LEGAL NOTICES & REGULATORY ORDERS", title_style))
    story.append(Paragraph("Rajesh Steel Industries Pvt Ltd", styles['Heading3']))
    story.append(Spacer(1, 20))

    story.append(Paragraph("1. NCLT MATTER — CASE NO. NCLT/MUM/2024/5678", heading_style))
    story.append(Paragraph(
        "An application has been filed before the National Company Law Tribunal, Mumbai Bench "
        "by ABC Trading Corporation against Agarwal Holdings Pvt Ltd (promoter group entity) "
        "for recovery of dues amounting to Rs 8.5 crore. The applicant claims that Agarwal Holdings "
        "has defaulted on payment for steel supplies. Rajesh Steel Industries has been made a "
        "co-respondent due to common directorship. Next hearing: March 28, 2025.", body_style))

    story.append(Paragraph("2. INCOME TAX DEMAND — AY 2022-23", heading_style))
    story.append(Paragraph(
        "The Income Tax Department has raised a demand of Rs 3.2 crore for Assessment Year 2022-23 "
        "relating to disallowance of certain deductions claimed under Section 35AD. The company "
        "has filed an appeal before ITAT Mumbai. Stay of demand has been granted pending appeal.", body_style))

    story.append(Paragraph("3. GST SHOW CAUSE NOTICE", heading_style))
    story.append(Paragraph(
        "A show cause notice under Section 74 of CGST Act 2017 has been issued for FY2022-23 "
        "regarding excess ITC claimed amounting to Rs 1.8 crore. The company has filed a detailed "
        "reply with supporting documentation on 15 November 2024.", body_style))

    story.append(Paragraph("4. RBI DEFAULTER LIST CHECK", heading_style))
    story.append(Paragraph(
        "As per verification on 01 March 2025: Neither the company nor any of its directors "
        "appear on the RBI Wilful Defaulter List or CIBIL SMA-2 list. However, Agarwal Holdings "
        "Pvt Ltd (promoter group) was classified as SMA-1 by ICICI Bank in November 2024 "
        "before the account was regularized in January 2025.", body_style))

    doc.build(story)
    print(f"  ✅ Legal Notices: {path}")
    return path


def create_rating_report():
    """W8 — Credit Rating Report (Optional)."""
    path = os.path.join(OUTPUT_DIR, "rating_report_rajesh_steel.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=50, bottomMargin=50)
    story = []

    story.append(Paragraph("CREDIT RATING REPORT", title_style))
    story.append(Paragraph("CRISIL — Rajesh Steel Industries Pvt Ltd", styles['Heading3']))
    story.append(Paragraph("Date of Rating: 15 February 2025 | Rating Valid Until: 14 February 2026", small_style))
    story.append(Spacer(1, 20))

    story.append(Paragraph("RATING SUMMARY", heading_style))
    rating_data = [
        ['Facility', 'Amount (Rs Cr)', 'Rating', 'Outlook'],
        ['Long Term Bank Loan', '90.0', 'CRISIL BBB+', 'Stable'],
        ['Working Capital Limits', '42.0', 'CRISIL A3+', 'N/A'],
        ['Proposed Term Loan', '50.0', 'CRISIL BBB+', 'Stable'],
    ]
    story.append(make_table(rating_data, col_widths=[150, 100, 100, 80]))
    story.append(Spacer(1, 15))

    story.append(Paragraph("KEY RATING DRIVERS", heading_style))
    story.append(Paragraph("STRENGTHS:", styles['Heading4']))
    story.append(Paragraph(
        "• Established track record of 20 years in steel manufacturing. "
        "• Diversified product portfolio with long-rolled, flat, and value-added steel products. "
        "• Healthy revenue growth of 8.2% CAGR over 3 years. "
        "• Adequate working capital management with 78% utilization.", body_style))
    story.append(Paragraph("WEAKNESSES:", styles['Heading4']))
    story.append(Paragraph(
        "• Elevated leverage with D/E ratio of 1.82x (sector average: 1.5x). "
        "• Significant related party transaction exposure (Rs 15.0 crore total RPTs). "
        "• Pending NCLT matter involving promoter group entity. "
        "• High promoter share pledge at 30.5% of promoter holding.", body_style))

    story.append(Paragraph("RATING RATIONALE", heading_style))
    story.append(Paragraph(
        "The rating reflects the company's established market position in the steel sector and "
        "consistent revenue growth. However, the rating is constrained by the above-average leverage, "
        "pending litigation matters, and the undisclosed RPT amount of Rs 6.1 crore identified during "
        "the current year audit. The rating outlook is 'Stable' reflecting our expectation that the "
        "company will maintain its business risk profile and gradually deleverage.", body_style))

    doc.build(story)
    print(f"  ✅ Rating Report: {path}")
    return path


if __name__ == "__main__":
    print("\n🔨 Generating dummy PDFs for Intelli-Credit pipeline testing...\n")
    paths = {}
    paths['annual_report'] = create_annual_report()
    paths['bank_statement'] = create_bank_statement()
    paths['gst_returns'] = create_gst_returns()
    paths['itr'] = create_itr()
    paths['board_minutes'] = create_board_minutes()
    paths['shareholding_pattern'] = create_shareholding()
    paths['legal_notice'] = create_legal_notice()
    paths['rating_report'] = create_rating_report()

    print(f"\n✅ All 8 PDFs generated in: {os.path.abspath(OUTPUT_DIR)}")
    print("\nFiles:")
    for name, path in paths.items():
        size_kb = os.path.getsize(path) / 1024
        print(f"  {name}: {os.path.basename(path)} ({size_kb:.1f} KB)")
