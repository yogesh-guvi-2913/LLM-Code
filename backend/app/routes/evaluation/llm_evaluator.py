import json
import logging
import re
from typing import Dict, Any, List, Optional

from app.routes.ai.llm_router import get_llm_router

logger = logging.getLogger(__name__)

EVAL_SYSTEM_PROMPT = """You are an expert technical evaluator assessing a student's AI-assisted coding test.

You will receive:
1. The problem statement and requirements
2. The student's final code files
3. The student's chat history with the AI assistant (their prompts and AI responses)
4. Runtime results from executing the code (errors, screenshots description)

Evaluate the student across three categories. For each, provide a score (0-10) and specific feedback.

## Categories

### 1. Requirement Completion (0-10)
- Did the student's code fulfill each requirement?
- Is the application functional and usable?
- Break down each requirement with a pass/fail/partial status

### 2. Code Quality (0-10)
- Is the code clean, readable, and well-organized?
- Does it follow React best practices?
- Are components properly structured?
- Is state management appropriate?
- Are there obvious bugs or anti-patterns?

### 3. Prompt Engineering (0-10)
- How effectively did the student communicate with the AI?
- Were prompts specific and clear?
- Did the student iterate and refine their requests?
- Did they demonstrate understanding of what the AI produced?
- Were they able to guide the AI toward the desired outcome?

## Output Format
Respond with ONLY a JSON object (no markdown fences, no extra text):

{
  "overallScore": 7.5,
  "categories": [
    {
      "name": "Requirement Completion",
      "score": 8,
      "maxScore": 10,
      "feedback": "The student implemented 4 out of 5 requirements..."
    },
    {
      "name": "Code Quality",
      "score": 7,
      "maxScore": 10,
      "feedback": "Code is generally clean but..."
    },
    {
      "name": "Prompt Engineering",
      "score": 8,
      "maxScore": 10,
      "feedback": "The student wrote clear, specific prompts..."
    }
  ],
  "summary": "Overall assessment summary in 2-3 sentences.",
  "strengths": ["Specific strength 1", "Specific strength 2"],
  "improvements": ["Specific improvement 1", "Specific improvement 2"],
  "requirementBreakdown": [
    {"requirement": "Requirement text", "status": "pass|partial|fail", "notes": "Explanation"}
  ]
}"""


def build_evaluation_context(
    problem_name: str,
    problem_description: str,
    requirements: List[Any],
    files: Dict[str, Any],
    chat_history: List[Dict[str, str]],
    runtime_result: Dict[str, Any],
) -> str:
    parts = []

    parts.append(f"=== PROBLEM ===")
    parts.append(f"Name: {problem_name}")
    if problem_description:
        parts.append(f"Description: {problem_description}")

    if requirements:
        parts.append("\nRequirements:")
        for i, req in enumerate(requirements, 1):
            if isinstance(req, dict):
                parts.append(f"  {i}. {req.get('title', '')}: {req.get('description', '')}")
            else:
                parts.append(f"  {i}. {req}")

    parts.append("\n=== STUDENT CODE FILES ===")
    for path, file_info in files.items():
        content = ""
        if isinstance(file_info, dict):
            content = file_info.get("content", "")
        elif isinstance(file_info, str):
            content = file_info
        if content:
            truncated = content[:3000]
            if len(content) > 3000:
                truncated += f"\n... (truncated, {len(content)} total chars)"
            parts.append(f"\n--- {path} ---\n{truncated}")

    parts.append("\n=== CHAT HISTORY (Student <-> AI) ===")
    if chat_history:
        for msg in chat_history[-30:]:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            label = "STUDENT" if role == "user" else "AI"
            truncated = content[:500]
            parts.append(f"\n[{label}]: {truncated}")
    else:
        parts.append("(No chat history available)")

    parts.append("\n=== RUNTIME RESULTS ===")
    if runtime_result.get("runtime_error"):
        parts.append(f"Runtime Error: {runtime_result['runtime_error']}")
    else:
        parts.append("Status: Rendered successfully (no runtime errors)")

    if runtime_result.get("console_errors"):
        parts.append(f"Console Errors: {len(runtime_result['console_errors'])} errors")
        for err in runtime_result["console_errors"][:5]:
            parts.append(f"  - {err[:200]}")
    else:
        parts.append("Console Errors: None")

    if runtime_result.get("rendered"):
        parts.append("Screenshot: Application rendered successfully in browser")
    else:
        parts.append("Screenshot: Failed to render")

    return "\n".join(parts)


async def evaluate_submission(
    problem_name: str,
    problem_description: str,
    requirements: List[Any],
    files: Dict[str, Any],
    chat_history: List[Dict[str, str]],
    runtime_result: Dict[str, Any],
) -> Dict[str, Any]:
    llm = get_llm_router()

    if not llm.is_available():
        logger.warning("LLM not configured, returning default scores")
        return {
            "overallScore": 0,
            "categories": [
                {"name": "Requirement Completion", "score": 0, "maxScore": 10, "feedback": "LLM not configured for evaluation"},
                {"name": "Code Quality", "score": 0, "maxScore": 10, "feedback": "LLM not configured for evaluation"},
                {"name": "Prompt Engineering", "score": 0, "maxScore": 10, "feedback": "LLM not configured for evaluation"},
            ],
            "summary": "Evaluation could not be performed: LLM service not configured.",
            "strengths": [],
            "improvements": [],
            "requirementBreakdown": [],
        }

    context = build_evaluation_context(
        problem_name=problem_name,
        problem_description=problem_description,
        requirements=requirements,
        files=files,
        chat_history=chat_history,
        runtime_result=runtime_result,
    )

    messages = [{"role": "user", "content": context}]

    try:
        response = await llm.chat(
            system_prompt=EVAL_SYSTEM_PROMPT,
            messages=messages,
            temperature=0.3,
            max_tokens=4096,
        )

        if response.get("type") == "error":
            logger.error(f"LLM evaluation error: {response.get('error')}")
            return _fallback_result("LLM evaluation failed: " + response.get("error", ""))

        content = response.get("message", "")

        parsed = _parse_json_response(content)
        if parsed:
            return _validate_result(parsed)
        else:
            logger.warning("Could not parse LLM evaluation response, using fallback")
            return _fallback_result("Could not parse LLM evaluation response")

    except Exception as e:
        logger.error(f"Evaluation error: {e}", exc_info=True)
        return _fallback_result(str(e))


def _parse_json_response(text: str) -> Optional[dict]:
    text = text.strip()

    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return None


def _validate_result(data: dict) -> dict:
    result = {
        "overallScore": min(max(float(data.get("overallScore", 0)), 0), 10),
        "categories": [],
        "summary": data.get("summary", ""),
        "strengths": data.get("strengths", []),
        "improvements": data.get("improvements", []),
        "requirementBreakdown": data.get("requirementBreakdown", []),
    }

    for cat in data.get("categories", []):
        result["categories"].append({
            "name": cat.get("name", ""),
            "score": min(max(float(cat.get("score", 0)), 0), 10),
            "maxScore": float(cat.get("maxScore", 10)),
            "feedback": cat.get("feedback", ""),
        })

    return result


def _fallback_result(error_msg: str) -> dict:
    return {
        "overallScore": 0,
        "categories": [],
        "summary": f"Evaluation error: {error_msg}",
        "strengths": [],
        "improvements": [],
        "requirementBreakdown": [],
    }
