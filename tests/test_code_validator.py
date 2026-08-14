from app.agent.tools.code_validator import collapse_blank_lines_in_code_blocks, validate_python_blocks


def test_valid_python_block_has_no_warnings():
    markdown = "Some text\n```python\nprint('hi')\n```\nmore text"
    assert validate_python_blocks(markdown) == []


def test_invalid_python_block_is_flagged():
    markdown = "```python\ndef f(:\n    pass\n```"
    warnings = validate_python_blocks(markdown)
    assert len(warnings) == 1
    assert "Code block #1" in warnings[0]


def test_non_python_blocks_are_ignored():
    markdown = "```bash\nthis is not : valid python(((\n```"
    assert validate_python_blocks(markdown) == []


def test_multiple_blocks_only_flags_broken_ones():
    markdown = "```python\nprint(1)\n```\n\n```python\nif True\n    pass\n```"
    warnings = validate_python_blocks(markdown)
    assert len(warnings) == 1
    assert "Code block #2" in warnings[0]


def test_collapse_removes_blank_lines_inside_code_block():
    markdown = "```python\nimport copy\nfrom dataclasses import dataclass\n\n@dataclass\nclass Foo:\n    x: int\n```"
    collapsed = collapse_blank_lines_in_code_blocks(markdown)
    assert "\n\n" not in collapsed
    assert "import copy\nfrom dataclasses import dataclass\n@dataclass" in collapsed


def test_collapse_leaves_surrounding_prose_blank_lines_alone():
    markdown = "Para one.\n\n```python\nx = 1\n\ny = 2\n```\n\nPara two."
    collapsed = collapse_blank_lines_in_code_blocks(markdown)
    assert collapsed.startswith("Para one.\n\n```python\nx = 1\ny = 2\n```\n\nPara two.")


def test_collapse_preserves_syntactic_validity():
    markdown = "```python\ndef f():\n\n    return 1\n```"
    collapsed = collapse_blank_lines_in_code_blocks(markdown)
    assert validate_python_blocks(collapsed) == []
