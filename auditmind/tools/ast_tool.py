import ast
import os
from pathlib import Path
from dataclasses import dataclass, field
from auditmind.logger import get_logger

logger = get_logger(__name__)

@dataclass
class ASTIssue:
    issue_type: str
    description: str
    file_path: str
    line_number: int
    code_snippet: str = ""


class PerformanceVisitor(ast.NodeVisitor):
    """
    Walks the AST of a Python file and collects performance anti-patterns.
    Each visit_* method targets a specific pattern.
    """

    def __init__(self, file_path: str, source_lines: list[str]):
        self.file_path = file_path
        self.source_lines = source_lines
        self.issues: list[ASTIssue] = []
        self._loop_depth = 0
        self._function_stack: list[str] = []

    def _get_snippet(self, lineno: int) -> str:
        if 0 < lineno <= len(self.source_lines):
            return self.source_lines[lineno - 1].strip()
        return ""

    def _add_issue(self, issue_type: str, description: str, lineno: int):
        self.issues.append(ASTIssue(
            issue_type=issue_type,
            description=description,
            file_path=self.file_path,
            line_number=lineno,
            code_snippet=self._get_snippet(lineno),
        ))

    def visit_For(self, node: ast.For):
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_While(self, node: ast.While):
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._function_stack.append(node.name)
        self.generic_visit(node)
        self._function_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call):
        if self._loop_depth > 0:
            call_str = ast.unparse(node)

            orm_patterns = [
                ".filter(", ".get(", ".all(", ".first()",
                ".query(", ".execute(", ".fetchone(", ".fetchall(",
                "session.query", "db.query", ".objects.",
            ]
            for pattern in orm_patterns:
                if pattern in call_str:
                    self._add_issue(
                        issue_type="n_plus_one_query",
                        description=(
                            f"Possible N+1 query inside a loop: `{call_str[:80]}`. "
                            f"Each iteration may trigger a separate DB call."
                        ),
                        lineno=node.lineno,
                    )
                    break

        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        if self._loop_depth > 0 and isinstance(node.op, ast.Add):
            if isinstance(node.value, (ast.Constant, ast.JoinedStr, ast.Name)):
                self._add_issue(
                    issue_type="string_concat_in_loop",
                    description=(
                        "String concatenation with += inside a loop. "
                        "Use a list and ''.join() instead — O(n²) vs O(n)."
                    ),
                    lineno=node.lineno,
                )
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if node.type is None:
            self._add_issue(
                issue_type="bare_except",
                description=(
                    "Bare `except:` clause swallows all exceptions including "
                    "KeyboardInterrupt and SystemExit. Use `except Exception:` at minimum."
                ),
                lineno=node.lineno,
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._function_stack.append(node.name)
        for default in node.args.defaults + node.args.kw_defaults:
            if default is None:
                continue
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self._add_issue(
                    issue_type="mutable_default_arg",
                    description=(
                        f"Function `{node.name}` uses a mutable default argument "
                        f"(list/dict/set). This is shared across all calls — use None instead."
                    ),
                    lineno=node.lineno,
                )
        self.generic_visit(node)
        self._function_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_For(self, node: ast.For):
        self._loop_depth += 1
        if self._loop_depth >= 2:
            self._add_issue(
                issue_type="nested_loop",
                description=(
                    f"Nested loop detected at depth {self._loop_depth}. "
                    "Verify this is intentional — nested loops are O(n²) or worse."
                ),
                lineno=node.lineno,
            )
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_Global(self, node: ast.Global):
        if self._loop_depth > 0:
            self._add_issue(
                issue_type="global_in_loop",
                description=(
                    f"Global variable access `{', '.join(node.names)}` inside a loop. "
                    "Cache the global in a local variable before the loop."
                ),
                lineno=node.lineno,
            )
        self.generic_visit(node)

def analyse_python_files(py_files: list[str]) -> list[ASTIssue]:
    """
    Runs the PerformanceVisitor over all Python files.
    Returns a flat list of all issues found.
    """
    all_issues: list[ASTIssue] = []

    for file_path in py_files:
        try:
            source = Path(file_path).read_text(encoding="utf-8")
            source_lines = source.splitlines()
            tree = ast.parse(source, filename=file_path)

            visitor = PerformanceVisitor(file_path, source_lines)
            visitor.visit(tree)
            all_issues.extend(visitor.issues)

        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            logger.error(f"AST analysis failed for {file_path}: {e}")

    return all_issues