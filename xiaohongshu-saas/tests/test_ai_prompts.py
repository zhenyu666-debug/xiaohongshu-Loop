"""Tests for prompts module."""
from app.ai.prompts.templates import (
    PromptTemplate,
    get_template,
    load_prompt,
    list_templates,
    register_template,
)


def test_prompt_template_creation():
    tpl = PromptTemplate(name="test", template="Hello {name}", variables=["name"])
    assert tpl.name == "test"
    assert "name" in tpl.variables


def test_prompt_template_render():
    tpl = PromptTemplate(name="test", template="Hello {name}", variables=["name"])
    result = tpl.render(name="Alice")
    assert "Alice" in result


def test_get_template():
    template = get_template("content_creator")
    assert template is not None


def test_load_prompt():
    prompt = load_prompt("content_creator", topic="AI", style="casual", length="short")
    assert prompt != ""
    assert "AI" in prompt


def test_list_templates():
    templates = list_templates()
    assert "content_creator" in templates


def test_register_template():
    tpl = PromptTemplate(name="custom_tpl", template="Custom {x}", variables=["x"])
    register_template(tpl)
    assert "custom_tpl" in list_templates()


def test_load_prompt_unknown():
    prompt = load_prompt("nonexistent_template", x="test")
    assert prompt == ""
