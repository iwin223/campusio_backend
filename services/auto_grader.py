"""Auto-grading service for assignment submissions"""
import json
from typing import Dict, Optional, Tuple
from difflib import SequenceMatcher
import re


class AutoGrader:
    """
    Service for automatically grading student submissions based on question types.
    Supports: Multiple Choice, Short Answer, and Matching questions.
    Essays require manual grading.
    """
    
    def __init__(self):
        self.SHORT_ANSWER_THRESHOLD = 0.75  # 75% similarity for full marks
        
    async def auto_grade_submission(
        self,
        submission_text: Optional[str],
        assignment_questions: list,
        assignment_points: float
    ) -> Dict:
        """
        Auto-grade a submission based on question answers.
        
        Args:
            submission_text: JSON string of student answers: {"q_id": answer}
            assignment_questions: List of AssignmentQuestion objects
            assignment_points: Max points for assignment
            
        Returns:
            {
                "total_score": float,
                "max_score": float,
                "percentage": float,
                "question_scores": {question_id: {"score": float, "max": float, "auto_gradable": bool}},
                "can_full_auto_grade": bool,  # True if no essays
                "feedback": str
            }
        """
        try:
            if not submission_text:
                return {
                    "total_score": 0,
                    "max_score": assignment_points,
                    "percentage": 0,
                    "question_scores": {},
                    "can_full_auto_grade": False,
                    "feedback": "No submission text provided"
                }
            
            # Parse student answers
            try:
                student_answers = json.loads(submission_text)
            except json.JSONDecodeError:
                return {
                    "total_score": 0,
                    "max_score": assignment_points,
                    "percentage": 0,
                    "question_scores": {},
                    "can_full_auto_grade": False,
                    "feedback": "Invalid answer format"
                }
            
            total_score = 0.0
            question_scores = {}
            has_essay = False
            grading_details = []
            
            # Grade each question
            for question in assignment_questions:
                question_id = str(question.id)
                question_points = float(question.points or 1.0)
                student_answer = student_answers.get(question_id)
                
                if question.question_type == "multipleChoice":
                    score, is_correct, details = await self._grade_multiple_choice(
                        student_answer, question
                    )
                    question_scores[question_id] = {
                        "score": score * question_points,
                        "max": question_points,
                        "auto_gradable": True,
                        "is_correct": is_correct,
                        "type": "multipleChoice"
                    }
                    total_score += score * question_points
                    grading_details.append(f"Q: {details}")
                    
                elif question.question_type == "shortAnswer":
                    score_pct, similarity, details = await self._grade_short_answer(
                        student_answer, question
                    )
                    question_scores[question_id] = {
                        "score": (score_pct / 100.0) * question_points,
                        "max": question_points,
                        "auto_gradable": True,
                        "similarity": round(similarity, 2),
                        "type": "shortAnswer"
                    }
                    total_score += (score_pct / 100.0) * question_points
                    grading_details.append(f"Q: {details}")
                    
                elif question.question_type == "matching":
                    score, is_correct, details = await self._grade_matching(
                        student_answer, question
                    )
                    question_scores[question_id] = {
                        "score": score * question_points,
                        "max": question_points,
                        "auto_gradable": True,
                        "is_correct": is_correct,
                        "type": "matching"
                    }
                    total_score += score * question_points
                    grading_details.append(f"Q: {details}")
                    
                elif question.question_type == "essay":
                    # Essays get 0 points in auto-grading
                    question_scores[question_id] = {
                        "score": 0,
                        "max": question_points,
                        "auto_gradable": False,
                        "type": "essay"
                    }
                    has_essay = True
                    grading_details.append(f"Q (Essay): Requires manual grading - {question_points} points available")
                    
                else:
                    # Unknown type, mark as not auto-gradable
                    question_scores[question_id] = {
                        "score": 0,
                        "max": question_points,
                        "auto_gradable": False,
                        "type": question.question_type
                    }
            
            # Calculate percentage
            percentage = (total_score / assignment_points * 100) if assignment_points > 0 else 0
            
            # Build feedback
            feedback = "; ".join(grading_details)
            if has_essay:
                feedback += "; Essay questions require manual grading by teacher"
            
            return {
                "total_score": round(total_score, 2),
                "max_score": assignment_points,
                "percentage": round(percentage, 2),
                "question_scores": question_scores,
                "can_full_auto_grade": not has_essay,
                "feedback": feedback
            }
            
        except Exception as e:
            return {
                "total_score": 0,
                "max_score": assignment_points,
                "percentage": 0,
                "question_scores": {},
                "can_full_auto_grade": False,
                "feedback": f"Grading error: {str(e)}"
            }
    
    async def _grade_multiple_choice(
        self,
        student_answer: Optional[str],
        question
    ) -> Tuple[float, bool, str]:
        """
        Grade a multiple choice question.
        Correct if student selected the right option ID.
        
        Returns: (score_multiplier [0-1], is_correct, details)
        """
        if not student_answer:
            return (0.0, False, "No answer provided")
        
        correct_answer = question.correct_answer
        if not correct_answer:
            return (1.0, True, "Cannot grade - no answer key")
        
        # Direct comparison
        is_correct = str(student_answer).strip() == str(correct_answer).strip()
        
        if is_correct:
            return (1.0, True, "Correct")
        else:
            return (0.0, False, f"Incorrect (selected: {student_answer}, correct: {correct_answer})")
    
    async def _grade_short_answer(
        self,
        student_answer: Optional[str],
        question
    ) -> Tuple[float, float, str]:
        """
        Grade a short answer question using fuzzy matching.
        
        Strategy:
        1. Normalize both strings (lowercase, remove extra whitespace)
        2. Calculate similarity score
        3. Award points based on threshold
        
        Returns: (score_percentage [0-100], similarity [0-1], details)
        """
        if not student_answer:
            return (0, 0, "No answer provided")
        
        correct_answer = question.correct_answer
        if not correct_answer:
            return (100, 1.0, "Cannot grade - no answer key")
        
        # Normalize answers
        student_ans_norm = self._normalize_text(student_answer)
        correct_ans_norm = self._normalize_text(correct_answer)
        
        # Calculate similarity
        similarity = SequenceMatcher(None, student_ans_norm, correct_ans_norm).ratio()
        
        # Scoring based on similarity
        if similarity >= self.SHORT_ANSWER_THRESHOLD:
            return (100, similarity, f"Correct (similarity: {similarity*100:.0f}%)")
        elif similarity >= 0.6:
            return (75, similarity, f"Partially correct (similarity: {similarity*100:.0f}%)")
        elif similarity >= 0.4:
            return (50, similarity, f"Partial credit (similarity: {similarity*100:.0f}%)")
        else:
            return (0, similarity, f"Incorrect (similarity: {similarity*100:.0f}%)")
    
    async def _grade_matching(
        self,
        student_answers: Optional[Dict],
        question
    ) -> Tuple[float, bool, str]:
        """
        Grade a matching question.
        Student answer format: {"option_id": "item_id", ...}
        Correct answer format: {"option_id": "item_id", ...}
        
        Returns: (score_multiplier [0-1], all_correct, details)
        """
        if not student_answers:
            return (0.0, False, "No answer provided")
        
        correct_answer = question.correct_answer
        if not correct_answer:
            return (1.0, True, "Cannot grade - no answer key")
        
        try:
            # Parse correct answer if it's a string
            if isinstance(correct_answer, str):
                correct_ans_dict = json.loads(correct_answer)
            else:
                correct_ans_dict = correct_answer
            
            # Parse student answer if it's a string
            if isinstance(student_answers, str):
                try:
                    student_ans_dict = json.loads(student_answers)
                except:
                    return (0.0, False, "Invalid answer format")
            else:
                student_ans_dict = student_answers or {}
            
            # Count correct matches
            total_pairs = len(correct_ans_dict)
            correct_pairs = 0
            
            for option_id, correct_item_id in correct_ans_dict.items():
                student_item_id = student_ans_dict.get(str(option_id))
                if str(student_item_id) == str(correct_item_id):
                    correct_pairs += 1
            
            score = correct_pairs / total_pairs if total_pairs > 0 else 0.0
            all_correct = score == 1.0
            
            return (
                score,
                all_correct,
                f"Matched {correct_pairs}/{total_pairs} pairs correctly"
            )
            
        except Exception as e:
            return (0.0, False, f"Grading error: {str(e)}")
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison:
        - Convert to lowercase
        - Remove extra whitespace
        - Remove common punctuation
        - Keep alphanumeric and spaces only
        """
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove common punctuation but keep alphanumeric and spaces
        text = re.sub(r'[^\w\s]', '', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text
