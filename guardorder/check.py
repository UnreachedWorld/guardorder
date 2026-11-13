"""Flags an action that runs before the guard that should come first.

The caller names the guard and the action. A match counts only inside the same
function, and only in code: not in a # comment, a // comment at the start of a
line or after a semicolon, a block comment,
or a quote, even when that quote runs onto the next line. A tab counts as indent.
A nested function is its own scope, and lines after a function are not inside it. A
helper assigned in this function, then called with the same method, counts as that
guard. A longer name, a name after a dot, or a space or tab after that dot, does not.
A select does not hide another call in the same statement. A receiver that was
not assigned here does not. A fixed quoted page, a with-block whose manager
checks before yield at the body indent, a helper whose callers already checked
at that indent, a saved founder name that was not overwritten, and a with-block
that hands the worker to guarded_legacy_call are not fresh misses. An update
or a delete is not a founder admission. An insert before the founder check
still flags, including one through executemany, executescript, or a local
name saved from self.db. SQL with no visible verb gets a card. When
the caller also names a transaction, the guard must sit inside the transaction
that holds the action. If the guard never appears even as text, the pair does
not apply. This module writes nothing, and the game does not import it.
"""

# The two cards. Neither is a rules number.
BEFORE = "the action sits before its guard"
OUTSIDE = "the guard is outside the transaction"


def mask(text):
    """Returns one code line per source line. Comments and quotes, including ones that cross lines, are blank (GuardOrder)."""
    kept = []
    current = []
    quote = ""
    block = False
    line_comment = False
    index = 0
    while index < len(text):
        if text[index] == "\n":
            kept.append("".join(current))
            current = []
            line_comment = False
            index = index + 1
            continue
        if line_comment or block:
            if block and text.startswith("*/", index):
                block = False
                index = index + 2
                continue
            index = index + 1
            continue
        if quote != "":
            if len(quote) == 3 and text.startswith(quote, index):
                quote = ""
                index = index + 3
                continue
            if len(quote) == 1 and text[index] == quote:
                quote = ""
            index = index + 1
            continue
        if text.startswith("'''", index) or text.startswith('"""', index):
            quote = text[index:index + 3]
            index = index + 3
            continue
        if text[index] == "'" or text[index] == '"':
            quote = text[index]
            index = index + 1
            continue
        if text.startswith("/*", index):
            block = True
            index = index + 2
            continue
        if text[index] == "#":
            line_comment = True
            index = index + 1
            continue
        if text.startswith("//", index):
            left = "".join(current).rstrip()
            stripped = left.strip()
            open_at = stripped.find("(")
            name = stripped[:open_at] if open_at > 0 else ""
            bare_call = stripped.endswith(")") and "=" not in stripped and " " not in name and name != ""
            if left == "" or left.endswith(";") or bare_call:
                line_comment = True
                index = index + 2
                continue
        current.append(text[index])
        index = index + 1
    if not text.endswith("\n"):
        kept.append("".join(current))
    return kept


def is_header(line):
    """True when the line starts a function or a class (GuardOrder)."""
    stripped = line.lstrip()
    if stripped.startswith("def ") or stripped.startswith("class ") or stripped.startswith("async def "):
        return True
    if stripped.startswith("function ") or stripped.startswith("async function "):
        return True
    return False


def indent_of(line):
    """Counts the leading indent. A tab is four spaces. A blank line has no indent (GuardOrder)."""
    expanded = line.expandtabs(4)
    if expanded.strip() == "":
        return None
    return len(expanded) - len(expanded.lstrip(" "))


def spans(rows):
    """Each function runs from its header until a line at the same indent or less (GuardOrder)."""
    headers = []
    index = 0
    while index < len(rows):
        if is_header(rows[index]):
            headers.append((index, indent_of(rows[index])))
        index = index + 1
    found = []
    for start, indent in headers:
        end = len(rows)
        later = start + 1
        while later < len(rows):
            later_indent = indent_of(rows[later])
            if later_indent is not None and later_indent <= indent:
                end = later
                break
            later = later + 1
        found.append((start, end, indent))
    return found


def chunks(text):
    """One list of line pairs per function, plus the lines that are in no function (GuardOrder)."""
    rows = text.splitlines()
    found = spans(rows)
    pieces = []
    covered = []
    for which, (start, end, indent) in enumerate(found):
        nested = []
        for other, (other_start, other_end, other_indent) in enumerate(found):
            if other != which and other_start > start and other_end <= end and other_indent > indent:
                nested.append((other_start, other_end))
        pairs = []
        index = start
        while index < end:
            covered.append(index)
            inside = False
            for nested_start, nested_end in nested:
                if nested_start <= index < nested_end:
                    inside = True
            if not inside:
                pairs.append((index + 1, rows[index]))
            index = index + 1
        pieces.append(pairs)
    module = []
    index = 0
    while index < len(rows):
        if index not in covered:
            module.append((index + 1, rows[index]))
        index = index + 1
    if len(module) > 0:
        pieces.append(module)
    if len(pieces) == 0:
        pieces.append([(number, rows[number - 1]) for number in range(1, len(rows) + 1)])
    return pieces


def find_action(pairs, needle, masked):
    """Returns the first code match that is not a function definition (GuardOrder)."""
    index = 0
    while index < len(pairs):
        line_number, line = pairs[index]
        code = masked[line_number - 1]
        column = code.find(needle)
        prefix = code[:column] if column >= 0 else ""
        header = "def " in prefix or "function " in prefix
        if column >= 0 and not header:
            return line_number, column
        index = index + 1
    return None


def find_in(pairs, needle, masked):
    """Returns the line and column of the first code match in this scope, or nothing (GuardOrder)."""
    index = 0
    while index < len(pairs):
        line_number, line = pairs[index]
        column = masked[line_number - 1].find(needle)
        if column >= 0:
            return line_number, column
        index = index + 1
    return None


def guard_in_code(masked, needle):
    """True when the guard appears in code, not only in a string or a comment (GuardOrder)."""
    for line in masked:
        if needle in line:
            return True
    return False


def check(path, text, rules):
    """Returns one card per scope whose action is not guarded there (GuardOrder)."""
    masked = mask(text)
    cards = []
    for rule in rules:
        real = guard_in_code(masked, rule["guard"])
        if not real and rule["guard"] not in text:
            continue
        for pairs in chunks(text):
            if not real:
                found = choose_action(pairs, rule["action"], masked)
                if found is not None:
                    cards.append(card(path, found[0], BEFORE))
                continue
            cards.extend(cards_for(path, pairs, rule, masked, text))
    return cards


def without_comment(line):
    """Drops a comment but keeps quoted text, so a comment cannot look like SQL (GuardOrder)."""
    kept = []
    quote = ""
    block = False
    index = 0
    while index < len(line):
        if block:
            if line.startswith("*/", index):
                block = False
                index = index + 2
                continue
            index = index + 1
            continue
        if quote != "":
            kept.append(line[index])
            if line[index] == quote:
                quote = ""
            index = index + 1
            continue
        if line[index] == "'" or line[index] == '"':
            quote = line[index]
            kept.append(line[index])
            index = index + 1
            continue
        if line.startswith("/*", index):
            block = True
            index = index + 2
            continue
        if line[index] == "#":
            break
        if line.startswith("//", index):
            break
        kept.append(line[index])
        index = index + 1
    return "".join(kept)


def sql_word(low, word):
    """True when execute quotes that word and the next letter is not part of a longer word (GuardOrder)."""
    for quote in ("'", '"'):
        mark = "execute(" + quote
        start = 0
        while True:
            at = low.find(mark, start)
            if at < 0:
                break
            rest = low[at + len(mark):].lstrip(quote)
            if rest.startswith(word):
                after = rest[len(word):len(word) + 1]
                if after == "" or after in " '\"\n;)*(":
                    return True
            start = at + len(mark)
    return False


def is_setup(code):
    """True when an execute runs a select or a begin. A comment or a longer word is not enough (GuardOrder)."""
    low = without_comment(code).lower()
    if sql_word(low, "select"):
        return True
    if sql_word(low, "begin"):
        return True
    return False


def is_fixed_page(code):
    """True when a response argument starts as a quoted page, not a name plus a quote (GuardOrder)."""
    mark = "front_page.response("
    if mark not in code:
        return False
    rest = code.split(mark, 1)[1]
    index = 0
    at_argument = True
    while index < len(rest):
        char = rest[index]
        if char == " " or char == "\t":
            index = index + 1
            continue
        if at_argument and (char == "'" or char == '"'):
            return True
        if char == ",":
            at_argument = True
            index = index + 1
            continue
        at_argument = False
        index = index + 1
    return False


def first_yield(pairs, masked):
    """Returns the line of yield in this scope, or nothing (GuardOrder)."""
    index = 0
    while index < len(pairs):
        line_number, line = pairs[index]
        if "yield" in masked[line_number - 1]:
            return line_number
        index = index + 1
    return None


def raw_statements(code):
    """Splits one line on semicolons that sit outside quotes (GuardOrder)."""
    parts = []
    start = 0
    index = 0
    while index < len(code):
        if code.startswith("'''", index) or code.startswith('"""', index):
            mark = code[index:index + 3]
            end = code.find(mark, index + 3)
            if end < 0:
                break
            index = end + 3
            continue
        if code[index] == "'" or code[index] == '"':
            quote = code[index]
            index = index + 1
            while index < len(code) and code[index] != quote:
                index = index + 1
            index = index + 1
            continue
        if code[index] == ";":
            parts.append(code[start:index])
            start = index + 1
        index = index + 1
    parts.append(code[start:])
    return parts


def statement_index(masked_line, column):
    """Which semicolon-separated piece of the masked line holds this column (GuardOrder)."""
    parts = masked_line.split(";")
    running = 0
    index = 0
    while index < len(parts):
        end = running + len(parts[index])
        if column <= end:
            return index
        running = end + 1
        index = index + 1
    return len(parts) - 1


def statement_piece(raw_line, index):
    """The raw statement at that index, or nothing when the index is past the end (GuardOrder)."""
    parts = raw_statements(raw_line)
    if index < len(parts):
        return parts[index]
    return ""


def outside_quote_columns(code, needle):
    """Columns where needle starts outside quotes (GuardOrder)."""
    found = []
    index = 0
    while index < len(code):
        if code.startswith("'''", index) or code.startswith('"""', index):
            mark = code[index:index + 3]
            end = code.find(mark, index + 3)
            if end < 0:
                break
            index = end + 3
            continue
        if code[index] == "'" or code[index] == '"':
            quote = code[index]
            index = index + 1
            while index < len(code) and code[index] != quote:
                index = index + 1
            index = index + 1
            continue
        if code.startswith(needle, index):
            found.append(index)
            index = index + len(needle)
            continue
        index = index + 1
    return found


def setup_execute_at(code):
    """Column of execute( that quotes select or begin, outside quotes, or nothing (GuardOrder)."""
    index = 0
    while index < len(code):
        if code.startswith("'''", index) or code.startswith('"""', index):
            mark = code[index:index + 3]
            end = code.find(mark, index + 3)
            if end < 0:
                return -1
            index = end + 3
            continue
        if code[index] == "'" or code[index] == '"':
            quote = code[index]
            index = index + 1
            while index < len(code) and code[index] != quote:
                index = index + 1
            index = index + 1
            continue
        if code[index] == "#" or code.startswith("//", index):
            break
        if code.lower().startswith("execute(", index):
            after = code[index + len("execute("):]
            quote_chars = 0
            while quote_chars < len(after) and after[quote_chars] in "'\"":
                quote_chars = quote_chars + 1
            rest = after[quote_chars:].lower()
            for word in ("select", "begin"):
                if rest.startswith(word):
                    endch = rest[len(word):len(word) + 1]
                    if endch == "" or endch in " '\"\n;)*(":
                        return index
        index = index + 1
    return -1


def match_number(masked_line, column, needle):
    """How many times needle has started in this statement, including this column (GuardOrder)."""
    parts = masked_line.split(";")
    which = statement_index(masked_line, column)
    running = 0
    index = 0
    while index < which:
        running = running + len(parts[index]) + 1
        index = index + 1
    local = column - running
    part = parts[which] if which < len(parts) else ""
    count = 0
    start = 0
    while start <= local:
        at = part.find(needle, start)
        if at < 0 or at > local:
            break
        count = count + 1
        start = at + 1
    return count


def this_match_is_setup(piece, needle, nth):
    """True when this match is the select or begin, not a call beside it (GuardOrder)."""
    if nth < 1 or not is_setup(piece):
        return False
    hits = outside_quote_columns(piece, needle)
    if nth > len(hits):
        return False
    raw_at = hits[nth - 1]
    setup_at = setup_execute_at(piece)
    if setup_at < 0:
        return False
    return raw_at <= setup_at < raw_at + len(needle)


def workers_handoff(pairs, action_line, masked):
    """True when this with self._request_workers block hands off to guarded_legacy_call (GuardOrder)."""
    action_indent = None
    action_code = ""
    index = 0
    while index < len(pairs):
        line_number, line = pairs[index]
        if line_number == action_line:
            action_indent = indent_of(line)
            action_code = masked[line_number - 1]
        index = index + 1
    if action_indent is None:
        return False
    if "with " not in action_code or "self._request_workers" not in action_code:
        return False
    index = 0
    while index < len(pairs):
        line_number, line = pairs[index]
        if line_number > action_line:
            indent = indent_of(line)
            if indent is not None and indent <= action_indent:
                break
            if "guarded_legacy_call" in masked[line_number - 1]:
                return True
        index = index + 1
    return False


def choose_action(pairs, needle, masked, after=None):
    """Picks the first action that is not setup, a fixed page, or before yield (GuardOrder)."""
    stop = first_yield(pairs, masked)
    index = 0
    while index < len(pairs):
        line_number, line = pairs[index]
        code = masked[line_number - 1]
        start = 0
        while start <= len(code):
            column = code.find(needle, start)
            if column < 0:
                break
            prefix = code[:column]
            header = "def " in prefix or "function " in prefix
            piece = statement_piece(line, statement_index(code, column))
            setup = this_match_is_setup(piece, needle, match_number(code, column, needle))
            skipped = header or setup or is_fixed_page(piece)
            if stop is not None and line_number < stop and setup:
                skipped = True
            if after is not None and not skipped:
                after_line, after_column = after
                if line_number < after_line or (line_number == after_line and column <= after_column):
                    skipped = True
            if needle == "self._request_workers(" and workers_handoff(pairs, line_number, masked):
                skipped = True
            if not skipped:
                return line_number, column
            start = column + 1
        index = index + 1
    return None


def call_column(code, needle):
    """The column of this call when the receiver is the whole name, not a longer one (GuardOrder)."""
    start = 0
    while start <= len(code):
        column = code.find(needle, start)
        if column < 0:
            return -1
        previous_at = column - 1
        while previous_at >= 0 and code[previous_at] in " \t":
            previous_at = previous_at - 1
        previous = code[previous_at] if previous_at >= 0 else ""
        if previous != "." and not previous.isalnum() and previous != "_":
            return column
        start = column + 1
    return -1


def local_receiver(pairs, guard, masked, action_line, action_column):
    """A helper assigned in this function, then its same method, counts before the action (GuardOrder)."""
    if not guard.startswith("self.") or "(" not in guard:
        return None
    method = guard[len("self."):]
    names = []
    index = 0
    while index < len(pairs):
        line_number, line = pairs[index]
        code = masked[line_number - 1]
        if line_number < action_line and " = " in code:
            left = code.split(" = ", 1)[0].strip()
            name = left.split()[-1] if left != "" else ""
            if name.isidentifier():
                names.append(name)
        for name in list(names):
            needle = name + "." + method
            column = call_column(code, needle)
            before = line_number < action_line or (line_number == action_line and column >= 0 and column < action_column)
            if column >= 0 and before:
                return line_number, column
        index = index + 1
    return None


def alias_before(pairs, rule, masked, action_line, action_column):
    """Returns a guard the rule names in also, when it sits before the action (GuardOrder)."""
    names = rule.get("also") or []
    found = None
    for needle in names:
        index = 0
        while index < len(pairs):
            line_number, line = pairs[index]
            column = masked[line_number - 1].find(needle)
            before = line_number < action_line or (line_number == action_line and column >= 0 and column < action_column)
            if column >= 0 and before:
                found = (line_number, column)
            index = index + 1
    return found


def cleanup_write(line):
    """True when execute quotes update or delete, not a new insert (GuardOrder)."""
    low = without_comment(line).lower()
    if sql_word(low, "update"):
        return True
    if sql_word(low, "delete"):
        return True
    return False


def call_word(low, method, word):
    """True when that method quotes the word and the next letter is not part of a longer word (GuardOrder)."""
    for quote in ("'", '"'):
        mark = method + "(" + quote
        start = 0
        while True:
            at = low.find(mark, start)
            if at < 0:
                break
            rest = low[at + len(mark):].lstrip(quote)
            if rest.startswith(word):
                after = rest[len(word):len(word) + 1]
                if after == "" or after in " '\"\n;)*(":
                    return True
            start = at + len(mark)
    return False


def argument_verbs(line, column, method):
    """The statement-opening words inside this call's own string (GuardOrder)."""
    low_line = line.lower()
    at = low_line.find(method + "(", column)
    if at < 0:
        return []
    rest = line[at + len(method) + 1:].lstrip()
    if rest[:1] in ("f", "F"):
        rest = rest[1:].lstrip()
    if rest == "" or (rest[0] != "'" and rest[0] != '"'):
        return []
    quote = rest[0]
    if rest.startswith(quote * 3):
        end = rest.find(quote * 3, 3)
        body = rest[3:] if end < 0 else rest[3:end]
    else:
        end = rest.find(quote, 1)
        body = rest[1:] if end < 0 else rest[1:end]
    verbs = []
    for part in body.split(";"):
        piece = part.strip()
        if piece == "":
            continue
        verbs.append(piece.split()[0].lower())
    return verbs


def admits_at(line, column, method):
    """True when this call's own string is a new insert, has no visible verb, or is an execute that is not only an update or delete (GuardOrder)."""
    verbs = argument_verbs(line, column, method)
    if len(verbs) == 0:
        return True
    if "insert" in verbs:
        return True
    if method != "execute":
        return False
    index = 0
    while index < len(verbs):
        if verbs[index] != "update" and verbs[index] != "delete":
            return True
        index = index + 1
    return False


def holds_cursor(right):
    """True when the right-hand side is self.db.cursor() (GuardOrder)."""
    return right.strip().startswith("self.db.cursor(")


def with_db_name(code):
    """The name in with self.db as name, or nothing (GuardOrder)."""
    low = code.lower()
    mark = "with self.db as "
    at = low.find(mark)
    if at < 0:
        return ""
    rest = code[at + len(mark):].strip()
    name = ""
    index = 0
    while index < len(rest):
        char = rest[index]
        if char.isalnum() or char == "_":
            name = name + char
            index = index + 1
            continue
        break
    if name.isidentifier():
        return name
    return ""


def holds_database(right):
    """True when the right-hand side is self.db itself, not a call on it (GuardOrder)."""
    text = right.strip()
    if not text.startswith("self.db"):
        return False
    after = text[len("self.db"):len("self.db") + 1]
    if after == "" or after in " ,\n":
        return True
    return False


def founder_action(pairs, masked):
    """The earliest founder admission: an insert through execute, executemany, executescript, or a renamed database (GuardOrder)."""
    found = []
    methods = (
        ("execute", "self.db.execute("),
        ("executemany", "self.db.executemany("),
        ("executescript", "self.db.executescript("),
    )
    for method, needle in methods:
        cursor = None
        while True:
            hit = choose_action(pairs, needle, masked, cursor)
            if hit is None:
                break
            line = line_at(pairs, hit[0])
            if admits_at(line, hit[1], method):
                found.append(hit)
                break
            cursor = hit
    names = []
    index = 0
    while index < len(pairs):
        line_number, line = pairs[index]
        code = masked[line_number - 1]
        if " = " in code:
            sides = code.split(" = ", 1)
            left = sides[0].strip()
            name = left.split()[-1] if left != "" else ""
            if name.isidentifier():
                if holds_database(sides[1]) or holds_cursor(sides[1]):
                    if name not in names:
                        names.append(name)
                elif name in names:
                    names.remove(name)
        bound = with_db_name(code)
        if bound != "" and bound not in names:
            names.append(bound)
        for name in list(names):
            for method in ("execute", "executemany", "executescript"):
                column = call_column(code, name + "." + method + "(")
                if column >= 0 and admits_at(line, column, method):
                    found.append((line_number, column))
        index = index + 1
    if len(found) == 0:
        return None
    found.sort()
    return found[0]


def line_at(pairs, line_number):
    """The source line with this number, or nothing (GuardOrder)."""
    index = 0
    while index < len(pairs):
        number, line = pairs[index]
        if number == line_number:
            return line
        index = index + 1
    return ""


def method_name(code):
    """The name in with self.name(, or nothing (GuardOrder)."""
    mark = "with self."
    at = code.find(mark)
    if at < 0:
        return ""
    rest = code[at + len(mark):]
    name = ""
    index = 0
    while index < len(rest):
        char = rest[index]
        if char.isalnum() or char == "_":
            name = name + char
            index = index + 1
            continue
        break
    return name


def header_name(header):
    """The function name on a def line, or nothing (GuardOrder)."""
    code = header.strip()
    if not code.startswith("def "):
        return ""
    rest = code[len("def "):]
    name = rest.split("(", 1)[0].strip()
    if name.isidentifier():
        return name
    return ""


def inside_if(scope, guard_line, masked):
    """True when an if, elif, or else still open contains this line (GuardOrder)."""
    guard_indent = None
    index = 0
    while index < len(scope):
        line_number, line = scope[index]
        if line_number == guard_line:
            guard_indent = indent_of(line)
        index = index + 1
    if guard_indent is None:
        return True
    index = 0
    while index < len(scope):
        line_number, line = scope[index]
        if line_number >= guard_line:
            break
        indent = indent_of(line)
        code = masked[line_number - 1].strip()
        opened = code.startswith("if ") or code.startswith("elif ") or code.startswith("else:") or code.startswith("else ")
        if indent is not None and indent < guard_indent and opened:
            closed = False
            later = index + 1
            while later < len(scope) and scope[later][0] < guard_line:
                later_indent = indent_of(scope[later][1])
                if later_indent is not None and later_indent <= indent:
                    closed = True
                    break
                later = later + 1
            if not closed:
                return True
        index = index + 1
    return False


def unconditional_guard(scope, guard, masked, before_line):
    """True when a guard before that line is not inside an if (GuardOrder)."""
    index = 0
    while index < len(scope):
        line_number, line = scope[index]
        if line_number >= before_line:
            break
        column = masked[line_number - 1].find(guard)
        if column >= 0 and not inside_if(scope, line_number, masked):
            return True
        index = index + 1
    return False


def context_holds(text, pairs, guard, action_line, masked):
    """A with-block is guarded when its manager runs that guard before yield (GuardOrder)."""
    action_indent = None
    index = 0
    while index < len(pairs):
        line_number, line = pairs[index]
        if line_number == action_line:
            action_indent = indent_of(line)
        index = index + 1
    if action_indent is None:
        return None
    manager = ""
    with_line = 0
    index = len(pairs) - 1
    while index >= 0:
        line_number, line = pairs[index]
        if line_number < action_line:
            indent = indent_of(line)
            code = masked[line_number - 1].strip()
            if indent is not None and indent < action_indent and code.startswith("with "):
                manager = method_name(masked[line_number - 1])
                with_line = line_number
                break
        index = index - 1
    if manager == "":
        return None
    for scope in chunks(text):
        if len(scope) == 0:
            continue
        if header_name(scope[0][1]) != manager:
            continue
        stop = first_yield(scope, masked)
        if stop is not None and unconditional_guard(scope, guard, masked, stop):
            return with_line, 0
    return None


def callers_hold(text, pairs, guard, masked):
    """Every call of this function in the file already ran the guard (GuardOrder)."""
    if len(pairs) == 0:
        return None
    name = header_name(pairs[0][1])
    if name == "":
        return None
    needle = "self." + name + "("
    calls = []
    for scope in chunks(text):
        if len(scope) == 0:
            continue
        if header_name(scope[0][1]) == name:
            continue
        index = 0
        while index < len(scope):
            line_number, line = scope[index]
            column = call_column(masked[line_number - 1], needle)
            if column >= 0:
                if not unconditional_guard(scope, guard, masked, line_number):
                    return None
                calls.append(line_number)
            index = index + 1
    if len(calls) == 0:
        return None
    return 0, 0


def bound_alias(pairs, guard, masked, action_line, action_column):
    """A name saved from the guard, then called, counts before the action (GuardOrder)."""
    if not guard.startswith("self.") or not guard.endswith("("):
        return None
    bare = guard[:-1]
    names = []
    index = 0
    while index < len(pairs):
        line_number, line = pairs[index]
        code = masked[line_number - 1]
        if line_number < action_line and " = " in code:
            sides = code.split(" = ", 1)
            left = sides[0].strip()
            right = sides[1]
            name = left.split()[-1] if left != "" else ""
            holds = False
            at = right.find(bare)
            while at >= 0:
                after = right[at + len(bare):at + len(bare) + 1]
                if after != "(":
                    holds = True
                    break
                at = right.find(bare, at + len(bare))
            if name.isidentifier():
                if holds and name not in names:
                    names.append(name)
                if not holds and name in names:
                    names.remove(name)
        for name in list(names):
            column = call_column(code, name + "(")
            before = line_number < action_line or (line_number == action_line and column >= 0 and column < action_column)
            if column >= 0 and before:
                return line_number, column
        index = index + 1
    return None


def cards_for(path, pairs, rule, masked, text):
    """Judges one scope. No action here means nothing to point at (GuardOrder)."""
    if rule["guard"] == "self._founder(":
        found_action = founder_action(pairs, masked)
    else:
        found_action = choose_action(pairs, rule["action"], masked)
    if found_action is None:
        return []
    action_line, action_column = found_action
    found_guard = find_in(pairs, rule["guard"], masked)
    if found_guard is None:
        found_guard = local_receiver(pairs, rule["guard"], masked, action_line, action_column)
    if found_guard is None:
        found_guard = alias_before(pairs, rule, masked, action_line, action_column)
    if found_guard is None:
        found_guard = bound_alias(pairs, rule["guard"], masked, action_line, action_column)
    if found_guard is None:
        found_guard = context_holds(text, pairs, rule["guard"], action_line, masked)
    if found_guard is None:
        found_guard = callers_hold(text, pairs, rule["guard"], masked)
    if found_guard is None:
        return [card(path, action_line, BEFORE)]
    guard_line, guard_column = found_guard
    if "_identity(" in rule["action"] and (guard_line > action_line or (guard_line == action_line and guard_column > action_column)):
        return []
    guard_line, guard_column = found_guard
    if "txn_start" in rule:
        return transaction_card(path, pairs, rule, action_line, action_column, guard_line, guard_column, masked)
    if guard_line > action_line:
        return [card(path, action_line, BEFORE)]
    if guard_line == action_line and guard_column > action_column:
        return [card(path, action_line, BEFORE)]
    return []


def transaction_card(path, pairs, rule, action_line, action_column, guard_line, guard_column, masked):
    """Requires the guard inside the transaction that contains this action (GuardOrder)."""
    start = find_before(pairs, rule["txn_start"], action_line, action_column, masked)
    end = find_after(pairs, rule["txn_end"], action_line, action_column, masked)
    if start is None or end is None:
        return [card(path, action_line, OUTSIDE)]
    inside = guard_line > start[0] or (guard_line == start[0] and guard_column > start[1])
    inside = inside and (guard_line < action_line or (guard_line == action_line and guard_column < action_column))
    if inside:
        return []
    return [card(path, action_line, OUTSIDE)]


def find_before(pairs, needle, action_line, action_column, masked):
    """Returns the last code match that sits before the action (GuardOrder)."""
    found = None
    index = 0
    while index < len(pairs):
        line_number, line = pairs[index]
        column = masked[line_number - 1].find(needle)
        before = line_number < action_line or (line_number == action_line and column >= 0 and column < action_column)
        if column >= 0 and before:
            found = (line_number, column)
        index = index + 1
    return found


def find_after(pairs, needle, action_line, action_column, masked):
    """Returns the first code match that sits after the action (GuardOrder)."""
    index = 0
    while index < len(pairs):
        line_number, line = pairs[index]
        column = masked[line_number - 1].find(needle)
        after = line_number > action_line or (line_number == action_line and column > action_column)
        if column >= 0 and after:
            return (line_number, column)
        index = index + 1
    return None


def card(path, line, reason):
    """Builds one card. The line is the action, not the guard (GuardOrder)."""
    return {"file": path, "line": line, "reason": reason}
