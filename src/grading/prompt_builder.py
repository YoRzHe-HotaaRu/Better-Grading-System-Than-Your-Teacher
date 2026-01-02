"""
Prompt builder for strict grading.

Constructs carefully engineered prompts that enforce:
- Zero tolerance for leniency
- Point-by-point evaluation
- Justification for every score
- Consistent output format
"""

from decimal import Decimal

from src.config import StrictnessMode
from src.models import Rubric


class PromptBuilder:
    """
    Builds grading prompts optimized for strict, unbiased evaluation.

    The prompts are designed to:
    1. Eliminate any possibility of favoritism
    2. Force criterion-by-criterion evaluation
    3. Require specific justifications with quotes
    4. Produce consistent JSON output
    """

    SYSTEM_PROMPT = """You are a STRICT academic grader. You are an AI with NO emotions, NO favorites, and NO leniency.

ABSOLUTE RULES - VIOLATION IS FORBIDDEN:
1. Grade EXACTLY according to the rubric. Do not interpret. Do not assume. Do not infer.
2. If a criterion requirement is not explicitly met in the answer, deduct points. No benefit of the doubt.
3. Two identical answers MUST receive IDENTICAL scores. Your grading must be perfectly reproducible.
4. You have NO knowledge of who wrote this answer. You cannot favor or disfavor anyone.
5. Writing style, politeness, formatting, or presentation do NOT affect scores unless the rubric explicitly mentions them.
6. Spelling and grammar do NOT affect scores unless the rubric explicitly scores them.

OUTPUT RULES:
- For each criterion, you MUST provide a specific quote from the student's answer as evidence.
- If deducting points, you MUST cite the exact rubric requirement that was not met.
- Your output MUST be valid JSON matching the exact format specified.
- Do not add any text before or after the JSON."""

    @staticmethod
    def build_grading_prompt(
        rubric: Rubric,
        student_answer: str,
        strictness_mode: StrictnessMode = StrictnessMode.PROPORTIONAL,
    ) -> str:
        """
        Build the user prompt for grading.

        Args:
            rubric: The parsed rubric to grade against.
            student_answer: The student's answer text.
            strictness_mode: Whether to allow partial credit.

        Returns:
            The formatted user prompt.
        """
        # Build rubric section
        rubric_text = PromptBuilder._format_rubric(rubric, strictness_mode)

        # Build the complete prompt
        prompt = f"""GRADING TASK

{rubric_text}

STUDENT ANSWER:
---BEGIN ANSWER---
{student_answer}
---END ANSWER---

INSTRUCTIONS:
1. Evaluate the answer against EACH criterion independently.
2. For each criterion, determine points awarded (0 to max_points).
3. Provide specific evidence from the answer for your scoring decision.
4. If any points are deducted, explain exactly which rubric requirement was not met.
5. Calculate the total score by summing all criterion scores.
6. Provide brief, constructive overall feedback.

OUTPUT FORMAT (respond with ONLY this JSON, no other text):
{{
  "total_score": <number>,
  "max_possible": {rubric.total_max_points},
  "criteria_results": [
    {{
      "criterion": "<exact criterion name from rubric>",
      "max_points": <number from rubric>,
      "awarded_points": <number between 0 and max_points>,
      "justification": "<specific quote or evidence from answer>",
      "deduction_reason": "<null if full points, otherwise specific rubric requirement not met>"
    }}
  ],
  "overall_feedback": "<constructive feedback for improvement>"
}}"""

        return prompt

    @staticmethod
    def _format_rubric(rubric: Rubric, strictness_mode: StrictnessMode) -> str:
        """Format the rubric for the prompt."""
        lines: list[str] = [
            f"RUBRIC: {rubric.title}",
            f"Total Possible Points: {rubric.total_max_points}",
            "",
        ]

        if strictness_mode == StrictnessMode.HARD_FAIL:
            lines.append(
                "MODE: HARD FAIL - If any part of a criterion is not fully met, "
                "award ZERO points for that criterion. No partial credit."
            )
        else:
            lines.append(
                "MODE: PROPORTIONAL - Award partial credit based on how well "
                "the criterion is met. Be precise but fair."
            )

        lines.append("")
        lines.append("CRITERIA:")

        for i, criterion in enumerate(rubric.criteria, start=1):
            partial_note = (
                ""
                if criterion.allows_partial_credit
                else " [NO PARTIAL CREDIT - either full points or zero]"
            )
            lines.append(f"{i}. {criterion.name} ({criterion.max_points} points){partial_note}")
            lines.append(f"   Description: {criterion.description}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def get_system_prompt() -> str:
        """Get the system prompt for strict grading."""
        return PromptBuilder.SYSTEM_PROMPT
