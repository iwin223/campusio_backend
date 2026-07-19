"""Free, rule-based report card comment generator.

Generates class-teacher and headteacher remarks from a student's computed
grade data (GES 1-9 scale, see report_card_pdf_service.py). No external
calls, no cost — this is the default path for every school. The optional
AI path (BYOK) lives in ai_comment_service.py and is never invoked unless
a school explicitly configures its own provider key.
"""
import random


# Keyed by GES grade string ("1".."9"), matching
# ReportCardPDFService._get_letter_grade()'s "grade" field.
CLASS_TEACHER_TEMPLATES = {
    "1": [
        "{name} has performed excellently this term, consistently producing outstanding work across all subjects.",
        "An excellent term for {name}, with sustained hard work and a strong grasp of the material.",
        "{name} continues to excel, showing real mastery of this term's work. Keep it up.",
    ],
    "2": [
        "{name} had a very good term, showing consistent effort and a sound understanding of the work.",
        "A strong performance from {name} this term, with a very good grasp of most subjects.",
        "{name} is performing very well and should keep up the good work.",
    ],
    "3": [
        "{name} had a good term overall, with room to push further in a few subjects.",
        "A solid term for {name}, good effort with some areas that could still improve.",
        "{name} is doing well and is encouraged to aim even higher next term.",
    ],
    "4": [
        "{name} put in fair effort this term; more consistent revision would raise the results.",
        "{name}'s performance was satisfactory, but there is clear room for improvement.",
        "With more focused effort, {name} can achieve better results next term.",
    ],
    "5": [
        "{name} passed this term but needs to work harder to strengthen understanding of the work.",
        "{name}'s results this term were average; extra practice at home is recommended.",
        "{name} should devote more time to study in order to improve next term.",
    ],
    "6": [
        "{name}'s performance this term was below expectation; closer attention to studies is needed.",
        "{name} needs to put in significantly more effort to improve.",
        "More consistent homework and revision will help {name} improve.",
    ],
    "7": [
        "{name} struggled this term and needs additional support to catch up.",
        "{name}'s results are a concern; extra help at home is strongly recommended.",
        "{name} requires close monitoring and extra support to improve.",
    ],
    "8": [
        "{name} struggled this term and needs additional support to catch up.",
        "{name}'s results are a concern; extra help at home is strongly recommended.",
        "{name} requires close monitoring and extra support to improve.",
    ],
    "9": [
        "{name} had a very difficult term academically and needs urgent intervention and support.",
        "{name}'s results this term are well below expectation; please arrange extra tuition or support.",
        "Immediate additional support is recommended to help {name} catch up with the class.",
    ],
}

HEAD_TEACHER_TEMPLATES = {
    "1": ["Excellent result. Keep it up.", "A commendable performance. Well done.", "Outstanding effort this term."],
    "2": ["Very good result. Keep working hard.", "A very good term's work.", "Good effort, aim even higher."],
    "3": ["Good result. Can do better.", "Satisfactory progress this term.", "Encouraging effort shown."],
    "4": ["Fair result. More effort needed.", "Average performance, needs improvement.", "Must work harder next term."],
    "5": ["Fair result. More effort needed.", "Average performance, needs improvement.", "Must work harder next term."],
    "6": ["Below average. Needs serious attention.", "Weak performance, extra effort required.", "Must improve significantly."],
    "7": ["Below average. Needs serious attention.", "Weak performance, extra effort required.", "Must improve significantly."],
    "8": ["Poor result. Needs urgent improvement.", "Serious concern, please see class teacher.", "Requires immediate remedial attention."],
    "9": ["Poor result. Needs urgent improvement.", "Serious concern, please see class teacher.", "Requires immediate remedial attention."],
}


def generate_template_remarks(student_first_name: str, report_data: dict) -> dict:
    """Build class-teacher and headteacher remarks from computed report data.

    Args:
        student_first_name: first name to interpolate into the comment
        report_data: the dict returned by ReportCardPDFService.format_grade_data
            (must contain overall_grade, subjects, attendance_percentage)

    Returns:
        {"class_teacher_remarks": str, "head_teacher_remarks": str}
    """
    name = student_first_name or "The student"
    grade = str(report_data.get("overall_grade") or "5")
    if grade not in CLASS_TEACHER_TEMPLATES:
        grade = "5"

    class_remark = random.choice(CLASS_TEACHER_TEMPLATES[grade]).format(name=name)
    head_remark = random.choice(HEAD_TEACHER_TEMPLATES[grade])

    subjects = report_data.get("subjects") or []
    if len(subjects) >= 2:
        best = max(subjects, key=lambda s: s.get("total_score", 0))
        worst = min(subjects, key=lambda s: s.get("total_score", 0))
        if best["subject_name"] != worst["subject_name"]:
            if best.get("total_score", 0) >= 70:
                class_remark += f" {name} performed particularly well in {best['subject_name']}."
            if worst.get("total_score", 100) < 50:
                class_remark += f" More support is needed in {worst['subject_name']}."

    attendance_pct = report_data.get("attendance_percentage")
    if isinstance(attendance_pct, (int, float)):
        if attendance_pct < 75:
            class_remark += " Poor attendance was a significant factor this term and must improve."
        elif attendance_pct < 90:
            class_remark += " Attendance also needs attention."

    return {
        "class_teacher_remarks": class_remark,
        "head_teacher_remarks": head_remark,
    }
