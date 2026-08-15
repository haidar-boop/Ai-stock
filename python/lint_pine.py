"""
Static checks for the Pine file.

Pine only compiles inside TradingView, so this catches the error classes that
have actually bitten this file, before a paste-and-see round trip:

  1. `ta.*` calls inside an indented (conditional/loop) block. Pine's ta.*
     functions must execute on EVERY bar to maintain internal state; calling
     them conditionally silently yields wrong values.
  1b. Negative `for ... by` steps. Pine requires a positive step and counts down
     automatically when `from` > `to`; `by -1` raises RE10021 at runtime.
  2. Comma-chained `var` declarations and multi-assignment lines, which are not
     valid Pine (`var float a = na, var float b = na`).
  3. Identifiers used before they are declared at global scope.
  4. Unbalanced brackets.

Run:  python lint_pine.py [path]
"""
from __future__ import annotations

import re
import sys

PINE = sys.argv[1] if len(sys.argv) > 1 else "../pine/confluence_signal_engine.pine"
BUILTIN_PREFIX = ("ta.", "math.", "str.", "array.", "color.", "table.", "input.",
                  "request.", "timeframe.", "syminfo.", "plot", "label.", "line.",
                  "box.", "barmerge.", "shape.", "location.", "size.", "position.",
                  "format.", "alert", "indicator", "strategy", "na", "nz", "int",
                  "float", "bool", "string")
KEYWORDS = {"if", "else", "for", "to", "by", "while", "and", "or", "not", "var",
            "varip", "true", "false", "na", "switch", "series", "simple", "const",
            "input", "export", "import", "method", "type", "enum", "break", "continue"}

def strip_code(ln: str) -> str:
    """Remove comments AND string literals — identifiers inside tooltips are text."""
    out, i, quote = [], 0, None
    while i < len(ln):
        ch = ln[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            i += 1
            continue
        if ch == "/" and i + 1 < len(ln) and ln[i + 1] == "/":
            break
        out.append(ch)
        i += 1
    return "".join(out)


lines = open(PINE).read().splitlines()
problems: list[str] = []

# --- 1. ta.* inside an indented block ---------------------------------------
for i, ln in enumerate(lines, 1):
    body = strip_code(ln)
    if not body.strip():
        continue
    indented = len(body) - len(body.lstrip()) > 0
    if indented and re.search(r"\bta\.\w+\s*\(", body):
        problems.append(f"{i}: ta.* called inside an indented block — must run every bar: {body.strip()[:70]}")

# --- 1b. negative loop step (Pine runtime error RE10021) ---------------------
for i, ln in enumerate(lines, 1):
    body = strip_code(ln)
    if re.search(r"\bby\s+-", body):
        problems.append(f"{i}: negative loop step — Pine requires `by` > 0 and counts "
                        f"down automatically when from > to (RE10021)")

# --- 1c. dynamic historical indexing without max_bars_back -------------------
code_all = "\n".join(strip_code(l) for l in lines)
dyn = re.findall(r"\b(?:high|low|close|open|volume)\[([A-Za-z_]\w*)\]", code_all)
if dyn and "max_bars_back" not in code_all:
    problems.append(f"dynamic historical index ({sorted(set(dyn))[:3]}) without "
                    f"max_bars_back in indicator() — Pine may fail to infer the buffer")

# --- 2. invalid multi-declaration / multi-assignment -------------------------
for i, ln in enumerate(lines, 1):
    body = strip_code(ln)
    if re.search(r"\bvar\b.*,\s*var\b", body):
        problems.append(f"{i}: comma-chained `var` declarations are not valid Pine")
    # `a = 1, b = 2` at global scope (ignore function calls and array literals)
    if (not body.startswith((" ", "\t")) and body.count("=") >= 2
            and "," in body and "(" not in body and "?" not in body
            and not body.lstrip().startswith(("//", "[")) and "=>" not in body):
        problems.append(f"{i}: looks like a comma-chained assignment: {body.strip()[:70]}")

# --- 3. use-before-declaration at global scope -------------------------------
declared: dict[str, int] = {}
decl_re = re.compile(r"^(?:var\s+)?(?:float|int|bool|string|color|line|label|table|box)?\s*"
                     r"([A-Za-z_]\w*)\s*(?::?=)(?!=)")
for i, ln in enumerate(lines, 1):
    body = strip_code(ln)
    if body.startswith((" ", "\t")):
        continue
    m = decl_re.match(body.strip())
    if m and m.group(1) not in KEYWORDS:
        declared.setdefault(m.group(1), i)
    fn = re.match(r"^([A-Za-z_]\w*)\s*\(.*\)\s*=>", body.strip())
    if fn:
        declared.setdefault(fn.group(1), i)
    # tuple declarations: [a, b, c] = ...
    tup = re.match(r"^\[([^\]]+)\]\s*=", body.strip())
    if tup:
        for nm in tup.group(1).split(","):
            declared.setdefault(nm.strip(), i)

for i, ln in enumerate(lines, 1):
    body = strip_code(ln)
    for ident in re.findall(r"\b([A-Za-z_]\w*)\b", body):
        if ident in KEYWORDS or ident.startswith(BUILTIN_PREFIX) or ident not in declared:
            continue
        if declared[ident] > i and not re.match(rf"^\s*(?:var\s+\w+\s+)?{ident}\s*:?=", body):
            problems.append(f"{i}: `{ident}` used before its declaration on line {declared[ident]}")

# --- 4. bracket balance ------------------------------------------------------
code = "\n".join(strip_code(l) for l in lines)
for open_c, close_c in [("(", ")"), ("[", "]")]:
    if code.count(open_c) != code.count(close_c):
        problems.append(f"unbalanced {open_c}{close_c}: {code.count(open_c)} vs {code.count(close_c)}")

seen = set()
uniq = [p for p in problems if not (p in seen or seen.add(p))]
print(f"lint: {PINE}")
print(f"  {len(lines)} lines, {len(declared)} global identifiers")
if uniq:
    print(f"  {len(uniq)} PROBLEM(S):")
    for p in uniq[:40]:
        print("   -", p)
else:
    print("  no problems found in the checked classes")
sys.exit(1 if uniq else 0)
