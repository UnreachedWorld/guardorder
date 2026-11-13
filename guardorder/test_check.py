"""GuardOrder corpus, before the checker exists.

A named action that sits before its guard is flagged with the file and line.
A guard that sits outside the transaction is flagged even when it is earlier
in the file. A guard in the right place is quiet. The checker writes nothing.
"""
from pathlib import Path

from guardorder.check import BEFORE, OUTSIDE, check


CORPUS = Path(__file__).parent / "corpus"
DRAFT = {"guard": "recover_signed_out", "action": "return draft_only"}
TX = {"guard": "confirm_session", "action": "insert_row", "txn_start": "begin()", "txn_end": "commit()"}
DRAFT_SESSION = {"guard": "confirm_session()", "action": "insert_row()"}
TX_SESSION = {"guard": "confirm_session()", "action": "insert_row()", "txn_start": "begin()", "txn_end": "commit()"}
REACT = {"guard": "recoverSignedOut()", "action": "navigate("}


def text_of(name):
    """Reads one corpus file and returns its text and path."""
    path = CORPUS / name
    return path, path.read_text()


def test_an_action_before_its_guard_is_flagged():
    """The draft return sits above the signed-out recovery, so the card names that line."""
    path, text = text_of("draft_before.py")
    cards = check(str(path), text, [DRAFT])
    assert cards == [{"file": str(path), "line": 2, "reason": BEFORE}]


def test_a_guard_before_its_action_is_quiet():
    """The recovery runs first, so there is no card."""
    path, text = text_of("draft_after.py")
    assert check(str(path), text, [DRAFT]) == []


def test_a_guard_outside_the_transaction_is_flagged():
    """The session check is earlier in the file, but not inside the write, so it still flags."""
    path, text = text_of("outside_tx.py")
    cards = check(str(path), text, [TX])
    assert cards == [{"file": str(path), "line": 4, "reason": OUTSIDE}]


def test_a_guard_inside_the_transaction_is_quiet():
    """The session check sits inside the write, before the insert, so there is no card."""
    path, text = text_of("inside_tx.py")
    assert check(str(path), text, [TX]) == []


def test_a_guard_that_is_not_in_the_text_does_not_apply():
    """A helper with no such guard is not a card. The pair has to be nameable."""
    text = "def add():\n    begin()\n    insert_row()\n    commit()\n"
    rule = {"guard": "confirm()", "action": "insert_row", "txn_start": "begin()", "txn_end": "commit()"}
    assert check("helper.py", text, [rule]) == []


def test_a_guard_in_another_function_does_not_clear_the_action():
    """Atlas's repro: the other function's guard must not make this action quiet."""
    text = "def unrelated():\n    confirm_session()\ndef target():\n    insert_row()\n"
    cards = check("wrong_scope.py", text, [DRAFT_SESSION])
    assert cards == [{"file": "wrong_scope.py", "line": 4, "reason": BEFORE}]


def test_a_second_transaction_is_judged_on_its_own():
    """Atlas's repro: a valid later transaction is not flagged by the earlier one."""
    text = (
        "def earlier():\n    begin()\n    unrelated()\n    commit()\n"
        "def target():\n    begin()\n    confirm_session()\n    insert_row()\n    commit()\n"
    )
    assert check("valid_second.py", text, [TX_SESSION]) == []


def test_a_comment_is_not_the_guard():
    """A comment that names the guard does not count. The real guard is still later."""
    text = "def save():\n    # confirm_session()\n    insert_row()\n    confirm_session()\n"
    cards = check("comment.py", text, [DRAFT_SESSION])
    assert cards == [{"file": "comment.py", "line": 3, "reason": BEFORE}]


def test_the_same_line_still_sees_which_call_comes_first():
    """The action and the guard on one line are ordered by their place on that line."""
    text = "def save():\n    insert_row(); confirm_session()\n"
    cards = check("same_line.py", text, [DRAFT_SESSION])
    assert cards == [{"file": "same_line.py", "line": 2, "reason": BEFORE}]


def test_a_signed_out_recovery_in_another_function_does_not_clear_navigation():
    """Flint's contract: stale navigation is not covered by another function's recovery."""
    text = "async function earlier() {\n    recoverSignedOut();\n}\nasync function go() {\n    navigate(\"/room\");\n}\n"
    cards = check("stale_nav.py", text, [REACT])
    assert cards == [{"file": "stale_nav.py", "line": 5, "reason": BEFORE}]


def test_recovery_before_navigation_in_the_same_function_is_quiet():
    """The signed-out recovery runs, then the navigation, in one function."""
    text = "async function go() {\n    recoverSignedOut();\n    navigate(\"/room\");\n}\n"
    assert check("recovered.py", text, [REACT]) == []


def test_a_nested_function_does_not_hide_the_outer_action():
    """The guard inside the nested function does not cover the outer insert."""
    text = "def target():\n    def helper():\n        confirm_session()\n    insert_row()\n"
    cards = check("nested.py", text, [DRAFT_SESSION])
    assert cards == [{"file": "nested.py", "line": 4, "reason": BEFORE}]


def test_lines_after_a_function_are_not_inside_it():
    """An action after the function is not covered by that function's guard."""
    text = "def helper():\n    confirm_session()\ninsert_row()\n"
    cards = check("after.py", text, [DRAFT_SESSION])
    assert cards == [{"file": "after.py", "line": 3, "reason": BEFORE}]


def test_a_guard_in_the_outer_function_still_covers_its_own_action():
    """A nested function in between does not split the outer guard from the outer action."""
    text = "def target():\n    confirm_session()\n    def helper():\n        pass\n    insert_row()\n"
    assert check("outer.py", text, [DRAFT_SESSION]) == []


def test_a_string_is_not_the_guard():
    """A quoted name does not run. The insert is still unguarded."""
    text = "def save():\n    note = \"confirm_session()\"\n    insert_row()\n"
    cards = check("string.py", text, [DRAFT_SESSION])
    assert cards == [{"file": "string.py", "line": 3, "reason": BEFORE}]


def test_a_slash_comment_is_not_the_guard():
    """A // comment does not run the recovery. The navigation is still unguarded."""
    text = "async function go() {\n    // recoverSignedOut()\n    navigate(\"/room\");\n}\n"
    cards = check("slash.py", text, [REACT])
    assert cards == [{"file": "slash.py", "line": 3, "reason": BEFORE}]


def test_a_block_comment_is_not_the_guard():
    """A block comment that names the guard does not cover the insert."""
    text = "def save():\n    /*\n    confirm_session()\n    */\n    insert_row()\n"
    cards = check("block.py", text, [DRAFT_SESSION])
    assert cards == [{"file": "block.py", "line": 5, "reason": BEFORE}]


def test_a_quote_past_the_line_is_not_the_guard():
    """A quote that continues on the next line is not a call."""
    text = "def save():\n    note = \"\"\"\n    confirm_session()\n    \"\"\"\n    insert_row()\n"
    cards = check("triple.py", text, [DRAFT_SESSION])
    assert cards == [{"file": "triple.py", "line": 5, "reason": BEFORE}]


def test_a_tab_indent_does_not_merge_two_functions():
    """A nested function indented with tabs is still its own scope."""
    text = "def target():\n\tdef helper():\n\t\tconfirm_session()\n\tinsert_row()\n"
    cards = check("tabs.py", text, [DRAFT_SESSION])
    assert cards == [{"file": "tabs.py", "line": 4, "reason": BEFORE}]


def test_rejecting_a_stale_navigation_before_moving_is_quiet():
    """A stale-navigation check before the move is the fine case."""
    text = "async function go() {\n    if (staleNavigation()) return;\n    navigate(\"/room\");\n}\n"
    rule = {"guard": "staleNavigation()", "action": "navigate("}
    assert check("stale_ok.py", text, [rule]) == []


def test_moving_before_the_stale_check_is_flagged():
    """The move happens before the stale-navigation check."""
    text = "async function go() {\n    navigate(\"/room\");\n    if (staleNavigation()) return;\n}\n"
    rule = {"guard": "staleNavigation()", "action": "navigate("}
    cards = check("stale_bad.py", text, [rule])
    assert cards == [{"file": "stale_bad.py", "line": 2, "reason": BEFORE}]


def test_a_draft_return_before_recovery_is_flagged():
    """A draft-only return before the signed-out recovery is flagged."""
    text = "async function save() {\n    return draftOnly();\n    recoverSignedOut();\n}\n"
    rule = {"guard": "recoverSignedOut()", "action": "return draftOnly()"}
    cards = check("draft_async.py", text, [rule])
    assert cards == [{"file": "draft_async.py", "line": 2, "reason": BEFORE}]


def test_a_trailing_slash_comment_is_not_the_guard():
    """A // after a semicolon is a comment. It does not cover the later move."""
    text = "async function go() {\n    doWork(); // recoverSignedOut()\n    navigate(\"/room\");\n}\n"
    cards = check("trail.py", text, [REACT])
    assert cards == [{"file": "trail.py", "line": 3, "reason": BEFORE}]


def test_the_limits_do_not_deny_a_caller_check():
    """The limits agree that a caller check counts when it is not inside an if."""
    root = Path(__file__).resolve().parents[1]
    for name in ("README.md", "guardorder/README.md"):
        limits = (root / name).read_text().split("## Limits", 1)[1]
        assert "does not follow a guard that lives in the caller" not in limits
        assert "not inside an if" in limits


def test_an_executemany_insert_is_a_founder_admission():
    """An insert through executemany still needs the founder check."""
    text = (
        "def kept(self):\n"
        "    self._founder()\n"
        "def admit(self):\n"
        "    self.db.executemany('insert into t values(?)', rows)\n"
    )
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    cards = check("many.py", text, [rule])
    assert cards == [{"file": "many.py", "line": 4, "reason": BEFORE}]


def test_an_executescript_insert_is_a_founder_admission():
    """An insert through executescript still needs the founder check."""
    text = (
        "def kept(self):\n"
        "    self._founder()\n"
        "def admit(self):\n"
        "    self.db.executescript('insert into t values(1)')\n"
    )
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    cards = check("script.py", text, [rule])
    assert cards == [{"file": "script.py", "line": 4, "reason": BEFORE}]


def test_an_executemany_update_is_not_covered():
    """An update through executemany stays outside the founder admission."""
    text = (
        "def kept(self):\n"
        "    self._founder()\n"
        "def change(self):\n"
        "    self.db.executemany('update t set done=1', rows)\n"
    )
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    assert check("manyupdate.py", text, [rule]) == []


def test_a_renamed_database_insert_is_a_founder_admission():
    """db = self.db and then db.execute of an insert still needs the founder check."""
    text = (
        "def kept(self):\n"
        "    self._founder()\n"
        "def admit(self):\n"
        "    db = self.db\n"
        "    db.execute('insert into t values(1)')\n"
    )
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    cards = check("renamed.py", text, [rule])
    assert cards == [{"file": "renamed.py", "line": 5, "reason": BEFORE}]


def test_sql_with_no_visible_verb_still_flags():
    """A variable or a joined string has no visible verb, so the call still flags."""
    text = (
        "def kept(self):\n"
        "    self._founder()\n"
        "def admit(self, sql):\n"
        "    self.db.execute(sql)\n"
        "def joined(self, a):\n"
        "    self.db.execute(a + 'insert into t values(1)')\n"
        "def batch(self, sql):\n"
        "    self.db.executemany(sql, rows)\n"
        "def script(self, sql):\n"
        "    self.db.executescript(sql)\n"
    )
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    cards = check("hidden.py", text, [rule])
    assert cards == [
        {"file": "hidden.py", "line": 4, "reason": BEFORE},
        {"file": "hidden.py", "line": 6, "reason": BEFORE},
        {"file": "hidden.py", "line": 8, "reason": BEFORE},
        {"file": "hidden.py", "line": 10, "reason": BEFORE},
    ]


def test_a_neighbour_update_does_not_hide_the_insert():
    """The verb is read from each call, so an update beside an insert does not hide it."""
    text = (
        "def kept(self):\n"
        "    self._founder()\n"
        "def admit(self):\n"
        "    self.db.execute('update t set a=1'); self.db.execute('insert into t values(1)')\n"
    )
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    cards = check("neighbour.py", text, [rule])
    assert cards == [{"file": "neighbour.py", "line": 4, "reason": BEFORE}]


def test_the_word_insert_inside_an_update_is_not_an_admission():
    """An update string that mentions insert is still an update."""
    text = (
        "def kept(self):\n"
        "    self._founder()\n"
        "def change(self):\n"
        "    self.db.execute('update t set note=\"insert row\"')\n"
    )
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    assert check("word.py", text, [rule]) == []


def test_a_cursor_insert_is_a_founder_admission():
    """A cursor taken from self.db still needs the founder check."""
    text = (
        "def kept(self):\n"
        "    self._founder()\n"
        "def admit(self):\n"
        "    cur = self.db.cursor()\n"
        "    cur.execute('insert into t values(1)')\n"
    )
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    cards = check("cursor.py", text, [rule])
    assert cards == [{"file": "cursor.py", "line": 5, "reason": BEFORE}]


def test_a_with_database_insert_is_a_founder_admission():
    """with self.db as db still needs the founder check before an insert."""
    text = (
        "def kept(self):\n"
        "    self._founder()\n"
        "def admit(self):\n"
        "    with self.db as db:\n"
        "        db.execute('insert into t values(1)')\n"
    )
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    cards = check("withdb.py", text, [rule])
    assert cards == [{"file": "withdb.py", "line": 5, "reason": BEFORE}]


def test_a_later_insert_inside_executescript_is_a_founder_admission():
    """An insert after an update in the same script still needs the founder check."""
    text = (
        "def kept(self):\n"
        "    self._founder()\n"
        "def admit(self):\n"
        "    self.db.executescript('update t set a=1; insert into t values(1)')\n"
    )
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    cards = check("later.py", text, [rule])
    assert cards == [{"file": "later.py", "line": 4, "reason": BEFORE}]


def test_an_f_string_insert_is_a_founder_admission():
    """An f-string insert through executemany still needs the founder check."""
    text = (
        "def kept(self):\n"
        "    self._founder()\n"
        "def admit(self, n):\n"
        "    self.db.executemany(f'insert into t values({n})', rows)\n"
    )
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    cards = check("fstring.py", text, [rule])
    assert cards == [{"file": "fstring.py", "line": 4, "reason": BEFORE}]


def test_the_limits_name_the_four_leftovers():
    """The notes name the four leftovers, and no further rule round."""
    root = Path(__file__).resolve().parents[1]
    for name in ("README.md", "guardorder/README.md"):
        limits = (root / name).read_text().split("## Limits", 1)[1]
        assert "comment before the verb on executemany and executescript" in limits
        assert "joined on outside it" in limits
        assert "cursor from a renamed database" in limits
        assert "only the first with-name" in limits


def test_the_limits_name_the_project_the_check_was_built_for():
    """Outside readers are told which check this package was built for."""
    root = Path(__file__).resolve().parents[1]
    for name in ("README.md", "guardorder/README.md"):
        limits = (root / name).read_text().split("## Limits", 1)[1]
        assert "the check in the project GuardOrder was built for" in limits
        assert "this trial used" not in limits
        assert "executemany" in limits


def test_the_limits_explain_a_founder_admission():
    """The notes say the check is a new INSERT, and that UPDATE and DELETE are not covered."""
    root = Path(__file__).resolve().parents[1]
    for name in ("README.md", "guardorder/README.md"):
        limits = (root / name).read_text().split("## Limits", 1)[1]
        assert "new INSERT or admission" in limits
        assert "UPDATE and DELETE" in limits
        assert "not covered" in limits
        assert "self._founder(" in limits
        assert "differently named" in limits
    assert "0.1.0" in (root / "CHANGELOG.md").read_text()


def test_the_readme_starts_from_the_repository_root():
    """The run line is from the directory that contains the guardorder folder."""
    readme = (Path(__file__).parent / "README.md").read_text()
    assert "contains the guardorder folder" in readme
    assert "tools/guardorder" not in readme
    assert "PYTHONPATH=tools" not in readme
    assert "contains this folder" not in readme


def test_a_comment_after_a_call_without_a_semicolon_is_not_the_guard():
    """A // after a call is still a comment when the semicolon was left off."""
    text = "async function go() {\n    doWork() // recoverSignedOut()\n    navigate(\"/room\");\n}\n"
    cards = check("nosemi.py", text, [REACT])
    assert cards == [{"file": "nosemi.py", "line": 3, "reason": BEFORE}]


def test_a_function_definition_is_not_the_action():
    """The definition of a function is not a call. The real call comes after the guard."""
    text = (
        "def save():\n"
        "    def validate(snapshot):\n"
        "        pass\n"
        "    copy_tree(descriptor, snapshot)\n"
        "    validate(snapshot)\n"
    )
    rule = {"guard": "copy_tree(descriptor, snapshot)", "action": "validate(snapshot)"}
    assert check("define.py", text, [rule]) == []


def test_a_shorter_needle_can_flag_a_different_call():
    """A short action text also matches a longer call. That card is a known limit."""
    text = "def send():\n    os.open(root)\n    if not allowed(child):\n        return\n    os.open(child)\n"
    rule = {"guard": "if not allowed(", "action": "os.open("}
    cards = check("similar.py", text, [rule])
    assert cards == [{"file": "similar.py", "line": 2, "reason": BEFORE}]


def test_floor_division_of_a_call_is_not_hidden():
    """foo() // insert_row() is division. The call after // still counts."""
    text = "def save():\n    x = foo() // insert_row()\n    confirm_session()\n"
    cards = check("callfloor.py", text, [DRAFT_SESSION])
    assert cards == [{"file": "callfloor.py", "line": 2, "reason": BEFORE}]


def test_a_missing_path_is_an_error(capsys):
    """A path that is not there is an error, not a quiet pass."""
    from guardorder.__main__ import main
    rules = Path(__file__).parent / "examples" / "rules.json"
    code = main(["/tmp/does-not-exist-guardorder", "--rules", str(rules)])
    assert code == 2
    assert "No such path" in capsys.readouterr().err


def test_rules_without_a_file_is_an_error(capsys):
    """--rules with no file is an error, not a crash."""
    from guardorder.__main__ import main
    example = Path(__file__).parent / "examples" / "draft_return.js"
    code = main([str(example), "--rules"])
    captured = capsys.readouterr()
    assert code == 2
    assert "rules" in captured.err


def test_a_begin_before_yield_is_not_the_public_action():
    """The context manager starts the write, then yields. The guard is in the caller."""
    text = (
        "def owner():\n"
        "    def _write(self):\n"
        "        self.db.execute('begin immediate')\n"
        "        yield\n"
        "    def remove(self):\n"
        "        self._founder()\n"
        "        self.db.execute('delete from members')\n"
    )
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    assert check("yield.py", text, [rule]) == []


def test_a_select_in_the_guard_helper_is_not_the_public_action():
    """The helper's own select is part of the guard, not the effect."""
    text = (
        "def api():\n"
        "    def _founder(self):\n"
        "        self.db.execute('select founder from projects')\n"
        "    def remove(self):\n"
        "        self._founder()\n"
        "        self.db.execute('delete from members')\n"
    )
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    assert check("select.py", text, [rule]) == []


def test_a_fixed_refusal_page_is_not_the_guarded_action():
    """A fixed page does not wait for the name lookup. The real page does."""
    text = (
        "def http():\n"
        "    def _refusal(self):\n"
        "        return front_page.response('<p>Not allowed.</p>')\n"
        "    def page(self):\n"
        "        self.names.get()\n"
        "        return front_page.response(body)\n"
    )
    rule = {"guard": "self.names.get(", "action": "front_page.response("}
    assert check("refusal.py", text, [rule]) == []


def test_building_an_identity_before_authorize_is_quiet():
    """The identity is built, then checked, then returned."""
    text = "def authenticate(self):\n    self.base._identity(key)\n    self._authorize(identity)\n    return identity\n"
    rule = {"guard": "self._authorize(", "action": "self.base._identity("}
    assert check("identity.py", text, [rule]) == []


def test_an_equivalent_receiver_counts_as_the_guard():
    """An alias counts only when the rule names it."""
    text = (
        "def other(self):\n"
        "    self._headers()\n"
        "def oauth(self):\n"
        "    framing._headers()\n"
        "    self._request_workers()\n"
    )
    plain = {"guard": "self._headers(", "action": "self._request_workers("}
    named = {"guard": "self._headers(", "action": "self._request_workers(", "also": ["framing._headers("]}
    assert check("alias.py", text, [plain]) == [{"file": "alias.py", "line": 5, "reason": BEFORE}]
    assert check("alias.py", text, [named]) == []


def test_a_quoted_select_does_not_hide_the_action():
    """The word select inside a quote is not a database read."""
    text = "def show(self):\n    publish(\"select a colour\")\ndef other(self):\n    authorize()\n"
    rule = {"guard": "authorize()", "action": "publish("}
    cards = check("prose.py", text, [rule])
    assert cards == [{"file": "prose.py", "line": 2, "reason": BEFORE}]


def test_an_action_before_yield_is_still_visible():
    """Only a begin before yield is quiet. A publish before yield still flags."""
    text = "def worker(self):\n    publish()\n    yield\ndef caller(self):\n    authorize()\n"
    rule = {"guard": "authorize()", "action": "publish("}
    cards = check("early.py", text, [rule])
    assert cards == [{"file": "early.py", "line": 2, "reason": BEFORE}]


def test_an_unrelated_receiver_is_not_the_guard():
    """other.authorize is not self.authorize."""
    text = "def other(self):\n    self.authorize()\ndef page(self):\n    other.authorize()\n    publish()\n"
    rule = {"guard": "self.authorize(", "action": "publish("}
    cards = check("other.py", text, [rule])
    assert cards == [{"file": "other.py", "line": 5, "reason": BEFORE}]


def test_rules_that_are_not_a_file_is_an_error(capsys):
    """A rules path that is a folder is an error, not a crash."""
    from guardorder.__main__ import main
    example = Path(__file__).parent / "examples" / "draft_return.js"
    code = main([str(example), "--rules", str(example.parent)])
    assert code == 2
    assert "rules" in capsys.readouterr().err


def test_a_commented_select_does_not_hide_the_action():
    """A comment that mentions execute select is not a database read."""
    text = "def show(self):\n    publish()  # execute('select')\ndef other(self):\n    authorize()\n"
    rule = {"guard": "authorize()", "action": "publish("}
    cards = check("commented.py", text, [rule])
    assert cards == [{"file": "commented.py", "line": 2, "reason": BEFORE}]


def test_beginner_is_not_a_begin():
    """execute of beginner_table is a real action, not a begin."""
    text = "def save(self):\n    self.db.execute('beginner_table')\ndef other(self):\n    self._founder()\n"
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    cards = check("beginner.py", text, [rule])
    assert cards == [{"file": "beginner.py", "line": 2, "reason": BEFORE}]


def test_a_block_comment_does_not_hide_the_action():
    """A block comment that mentions execute select is not a database read."""
    text = "def show(self):\n    publish() /* execute('select') */\ndef other(self):\n    authorize()\n"
    rule = {"guard": "authorize()", "action": "publish("}
    cards = check("blocksql.py", text, [rule])
    assert cards == [{"file": "blocksql.py", "line": 2, "reason": BEFORE}]


def test_select_ended_by_a_semicolon_is_still_a_select():
    """execute('select;') is a select. It is not the public action."""
    text = "def save(self):\n    self.db.execute('select;')\ndef other(self):\n    self._founder()\n"
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    assert check("selectsemi.py", text, [rule]) == []


def test_select_star_is_still_a_select():
    """execute('select*from t') is a select. The star does not make it an action."""
    text = "def save(self):\n    self.db.execute('select*from t')\ndef other(self):\n    self._founder()\n"
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    assert check("star.py", text, [rule]) == []


def test_select_call_is_still_a_select():
    """execute('select(1)') is a select. The parenthesis ends the word."""
    text = "def save(self):\n    self.db.execute('select(1)')\ndef other(self):\n    self._founder()\n"
    rule = {"guard": "self._founder(", "action": "self.db.execute("}
    assert check("callsql.py", text, [rule]) == []


def test_the_command_prints_a_card_for_an_example(capsys):
    """A user can point the tool at a file and read one card."""
    from guardorder.__main__ import main
    example = Path(__file__).parent / "examples" / "draft_return.js"
    rules = Path(__file__).parent / "examples" / "rules.json"
    code = main([str(example), "--rules", str(rules)])
    assert code == 0
    assert "draft_return.js:2: the action sits before its guard" in capsys.readouterr().out


def test_the_public_examples_match_their_cards():
    """The examples shipped with the tool are the same cases as the contract."""
    folder = Path(__file__).parent / "examples"
    stale = (folder / "stale_ok.js").read_text()
    draft = (folder / "draft_return.js").read_text()
    floor = (folder / "floor.py").read_text()
    assert check("stale_ok.js", stale, [{"guard": "staleNavigation()", "action": "navigate("}]) == []
    draft_cards = check("draft_return.js", draft, [{"guard": "recoverSignedOut()", "action": "return draftOnly()"}])
    assert draft_cards == [{"file": "draft_return.js", "line": 2, "reason": BEFORE}]
    floor_cards = check("floor.py", floor, [DRAFT_SESSION])
    assert floor_cards == [{"file": "floor.py", "line": 2, "reason": BEFORE}]


def test_floor_division_does_not_hide_the_action():
    """In Python, // is division. The call after it still counts."""
    text = "def save():\n    x = 1 // insert_row()\n    confirm_session()\n"
    cards = check("floor.py", text, [DRAFT_SESSION])
    assert cards == [{"file": "floor.py", "line": 2, "reason": BEFORE}]


def test_the_checker_does_not_change_the_file():
    """Reading the corpus leaves every byte as it was."""
    path, before = text_of("draft_before.py")
    check(str(path), before, [DRAFT])
    assert path.read_text() == before
