import ast
import re

_CODE_BLOCK_RE = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)


def collapse_blank_lines_in_code_blocks(markdown: str) -> str:
    """Removes blank lines inside fenced code blocks, leaving the rest of the
    document untouched.

    Works around a Medium paste-import quirk (confirmed live): pasting a
    single correctly-formed fenced code block that contains an internal
    blank line gets split into two separate code blocks by Medium's
    importer, each independently language-auto-detected -- observed
    producing a mislabeled "Go" block for a two-line Python import group.
    Blank lines inside a code block are purely cosmetic (don't affect
    execution), so removing them is a safe, deterministic workaround.
    """

    def _collapse(match: re.Match) -> str:
        lang, code = match.group(1) or "", match.group(2)
        lines = [line for line in code.split("\n") if line.strip() != ""]
        return f"```{lang}\n" + "\n".join(lines) + "\n```"

    return _CODE_BLOCK_RE.sub(_collapse, markdown)


def validate_python_blocks(markdown: str) -> list[str]:
    """Syntax-check every fenced python code block in a markdown article.

    Returns a list of human-readable warnings (empty if everything parses).
    This only guarantees the code is syntactically valid, not that it runs
    -- a cheap, fast guardrail against publishing outright broken examples,
    surfaced to the human reviewer rather than silently blocking anything.
    """
    warnings: list[str] = []
    for i, match in enumerate(_CODE_BLOCK_RE.finditer(markdown), start=1):
        lang, code = match.group(1), match.group(2)
        if (lang or "").lower() not in ("python", "py"):
            continue
        try:
            ast.parse(code)
        except SyntaxError as exc:
            warnings.append(f"Code block #{i}: syntax error - {exc.msg} (line {exc.lineno})")
    return warnings
