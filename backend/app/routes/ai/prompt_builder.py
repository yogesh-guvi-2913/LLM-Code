from typing import Dict, Any, Optional

SYSTEM_PROMPT_BASE = """You are an expert full-stack developer AI assistant helping a student build a web application.

Your role:
- Help the student create and modify code for both frontend and backend through natural language prompts
- Explain what you're doing before making changes
- Provide clean, working code that follows best practices
- Be patient and educational - explain concepts when asked

Output format for code changes:
After your explanation, output code changes using this exact format:

```file:frontend/src/App.jsx
...frontend React code...
```

```file:backend/routes/tasks.py
...backend API code...
```

```file:backend/main.py
...backend entry point...
```

Rules:
- Use `frontend/` prefix for all frontend files
- Use `backend/` prefix for all backend files
- Frontend uses React with Vite (useState, useEffect, etc.)
- Frontend API calls should use relative paths like `/api/tasks` (proxied through nginx)
- Backend follows REST API conventions
- For FastAPI: use async endpoints, Pydantic models, proper error handling
- For Express: use Express router pattern
- Include proper imports in all files
- Only output file blocks for files you want to CREATE or UPDATE
- To DELETE a file, use: ```delete:PATH```
- Do NOT output docker-compose.yml, Dockerfile, or config files unless specifically asked"""

def build_system_prompt(
    problem_name: str,
    problem_description: str,
    requirements: Optional[list] = None,
    current_files: Optional[Dict[str, Any]] = None,
    custom_instructions: Optional[str] = None
) -> str:
    parts = [SYSTEM_PROMPT_BASE]
    
    parts.append(f"\n\n=== CURRENT PROBLEM ===")
    parts.append(f"Problem: {problem_name}")
    if problem_description:
        parts.append(f"Description: {problem_description}")
    
    if requirements and len(requirements) > 0:
        parts.append("\nRequirements:")
        for req in requirements:
            if isinstance(req, dict):
                title = req.get('title', '')
                desc = req.get('description', '')
                parts.append(f"- {title}: {desc}")
            else:
                parts.append(f"- {req}")
    
    if current_files and len(current_files) > 0:
        parts.append("\n=== CURRENT CODE STATE ===")
        parts.append("Here are the current files in the project:")
        for path, file_info in current_files.items():
            content = file_info.get('content', '') if isinstance(file_info, dict) else str(file_info)
            if content:
                parts.append(f"\n--- {path} ---")
                parts.append(content[:2000])
                if len(content) > 2000:
                    parts.append(f"\n... (truncated, {len(content)} total chars)")
    
    if custom_instructions:
        parts.append(f"\n\n=== CUSTOM INSTRUCTIONS ===")
        parts.append(custom_instructions)
    
    return "\n".join(parts)

def parse_ai_response(response_text: str) -> tuple[str, list]:
    import re
    
    message = response_text
    file_changes = []
    
    file_pattern = r'```file:([^\n]+)\n(.*?)```'
    delete_pattern = r'```delete:([^\n]+)```'
    
    file_matches = re.findall(file_pattern, response_text, re.DOTALL)
    for path, content in file_matches:
        file_changes.append({
            "path": path.strip(),
            "action": "update",
            "content": content.strip()
        })
    
    delete_matches = re.findall(delete_pattern, response_text)
    for path in delete_matches:
        file_changes.append({
            "path": path.strip(),
            "action": "delete",
            "content": None
        })
    
    clean_pattern = r'```(?:file|delete):[^\n]+\n?.*?```'
    message = re.sub(clean_pattern, '', response_text, flags=re.DOTALL).strip()
    
    return message, file_changes

def build_system_prompt_simple(problem_name: str, problem_description: str = "") -> str:
    return build_system_prompt(
        problem_name=problem_name,
        problem_description=problem_description,
        requirements=None,
        current_files=None,
        custom_instructions=None
    )