"""Prompt templates for various agent tasks."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path


@dataclass
class PromptTemplate:
    """A prompt template with variables."""
    name: str
    template: str
    description: str = ""
    variables: List[str] = field(default_factory=list)
    examples: List[Dict[str, str]] = field(default_factory=list)

    def render(self, **kwargs) -> str:
        """Render the template with variables."""
        result = self.template
        for var in self.variables:
            value = kwargs.get(var, f"{{{var}}}")
            # Support both {{var}} and {var} syntax
            result = result.replace(f"{{{{{var}}}}}", str(value))
            result = result.replace(f"{{{var}}}", str(value))
        return result

    def render_with_examples(self, **kwargs) -> str:
        """Render template with few-shot examples."""
        if not self.examples:
            return self.render(**kwargs)
        
        example_str = "\n\nExamples:\n"
        for i, ex in enumerate(self.examples, 1):
            example_str += f"Example {i}:\n"
            for key, value in ex.items():
                example_str += f"  {key}: {value}\n"
            example_str += "\n"
        
        base_prompt = self.render(**kwargs)
        return base_prompt + example_str


# Predefined templates
TEMPLATES: Dict[str, PromptTemplate] = {
    "content_creator": PromptTemplate(
        name="content_creator",
        description="Generate Xiaohongshu content",
        template="""You are an expert Xiaohongshu content creator.

Topic: {{topic}}
Style: {{style}}
Length: {{length}}

Create engaging content that:
1. Has a catchy title (under 20 characters)
2. Uses conversational tone with emojis
3. Includes 3-5 relevant hashtags
4. Has clear structure with spacing

Output format:
```json
{
  "title": "Your title",
  "body": "Your content body",
  "hashtags": ["#tag1", "#tag2"]
}
```""",
        variables=["topic", "style", "length"]
    ),

    "data_analyst": PromptTemplate(
        name="data_analyst",
        description="Analyze performance data",
        template="""Analyze the following performance data:

Account: {{account_id}}
Period: {{period}}
Metrics: {{metrics}}

Provide insights on:
1. Performance score (0-100)
2. Strengths and weaknesses
3. Specific recommendations for improvement

Output format:
```json
{
  "score": 85,
  "strengths": ["strength1", "strength2"],
  "weaknesses": ["weakness1"],
  "recommendations": [{"action": "specific action", "impact": "expected result"}]
}
```""",
        variables=["account_id", "period", "metrics"]
    ),

    "coordinator": PromptTemplate(
        name="coordinator",
        description="Coordinate multi-agent tasks",
        template="""You are a coordinator managing a team of specialized agents.

Available agents:
- content_creator: Create posts
- data_analyst: Analyze data
- scheduler: Optimize schedules

Task: {{task}}

Break down the task and assign to appropriate agents.
Coordinate their work and synthesize results.

Return a plan with:
1. Subtasks
2. Agent assignments
3. Expected outcomes""",
        variables=["task"]
    ),

    "rag_answer": PromptTemplate(
        name="rag_answer",
        description="Answer questions using retrieved context",
        template="""Based on the following context, answer the user's question.

Context:
{{context}}

Question: {{question}}

Instructions:
- Answer based only on the provided context
- If uncertain, say so
- Provide specific references when possible
- Be concise but complete""",
        variables=["context", "question"]
    ),

    "tool_selector": PromptTemplate(
        name="tool_selector",
        description="Select appropriate tools for a task",
        template="""Given the task: {{task}}

Available tools:
{{tools}}

Select the most appropriate tools for this task.
Consider:
1. Which tools directly help with the task
2. The order of tool usage
3. Any dependencies between tools

Return a list of tool names in the order they should be used.""",
        variables=["task", "tools"]
    ),

    "reflection": PromptTemplate(
        name="reflection",
        description="Reflect on actions taken",
        template="""Reflect on the following actions:

Actions taken: {{actions}}
Outcome: {{outcome}}
Goal: {{goal}}

Analyze:
1. What worked well
2. What could be improved
3. Lessons learned
4. Suggested next steps""",
        variables=["actions", "outcome", "goal"]
    )
}


def get_template(name: str) -> Optional[PromptTemplate]:
    """Get a template by name."""
    return TEMPLATES.get(name)


def load_prompt(name: str, **kwargs) -> str:
    """Load and render a prompt template."""
    template = get_template(name)
    if template:
        return template.render(**kwargs)
    return ""


def load_prompt_with_examples(name: str, **kwargs) -> str:
    """Load and render a prompt template with few-shot examples."""
    template = get_template(name)
    if template:
        return template.render_with_examples(**kwargs)
    return ""


def register_template(template: PromptTemplate) -> None:
    """Register a new template."""
    TEMPLATES[template.name] = template


def list_templates() -> List[str]:
    """List all available templates."""
    return list(TEMPLATES.keys())
