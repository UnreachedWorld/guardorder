# GuardOrder

A small read-only check. You name a guard and an action. It reads the text you
give it and returns a card when the action is not guarded in that same function.

It does not change your files. A quiet result is not proof the code is safe.

## Get it

The folder `guardorder` is the whole tool. It contains:

- `check.py`, the check
- `__main__.py`, the command
- `test_check.py`, the tests
- `examples/`, small files written for this tool, with `rules.json`
- `LICENSE`

Python 3.11 or newer is enough to run a check. No extra package is required.
To run the tests, install pytest in the environment you already use.

## Run a check

From this directory, the one that contains the `guardorder` folder:

```
PYTHONPATH=. python -m guardorder guardorder/examples
```

That reads `guardorder/examples/rules.json`. To name another rules file:

```
PYTHONPATH=. python -m guardorder path/to/file.js --rules path/to/rules.json
```

To run the tests:

```
PYTHONPATH=. python -m pytest guardorder/test_check.py -q
```

## The rules

Each rule is one object:

- `guard`: text that should run first
- `action`: text that should run after the guard, in the same function
- `txn_start` and `txn_end`, optional: the guard must sit between them, and those
  two must contain the action
- `also`, optional: other texts that count as the same guard

A guard that never appears in the file does not apply. A guard only in a
comment or a quote does not count. A `//` after a bare call is a comment.
`x = foo() // insert_row()` is division, so the call after `//` stays.

## How to read a card

A card is one line: `file:line: reason`.

The line is the action, not the guard. `the action sits before its guard` means
the guard is missing in that function, or it comes later. `the guard is outside
the transaction` means the guard is not between the begin and the commit that
contain the action.

An empty result means either the order is fine, or the guard text is not in the
file. Those two are not the same. Check that your rule text actually appears.

## A false alarm

A card is a prompt to look, not an order to add a guard.

Read the caller. A guard in the caller counts only when every call in the file
sits after a check that is not inside an if. A guard inside an if does not
count. A definition can look like a call, and a short needle can match
a longer one (`return response` also matches `return response.body`). If the
card is wrong, narrow the rule and keep the example with the tests.

## Limits

A begin or a select inside `execute`, a fixed quoted page, and an identity built
just before its check are not treated as the public effect. Another receiver
counts as the guard only when the rule names it in `also`.

A founder admission is a new person being let in. The checker looks for
`self._founder(` before a new INSERT or admission, because that is the check in the project GuardOrder was built for.
UPDATE and DELETE changes are not covered. A project with a
differently named check does not get this exception. Its own guard text is
matched as written. An insert through executemany or executescript, or through
a local name saved from self.db, is still that admission. The verb is read from
that call's own string. A cursor from self.db.cursor(), a with self.db as name,
a later insert in the same script, and an f-string insert are still that
admission. Four limits stay, and there is no further rule round. A comment before the verb on executemany and executescript can hide it. A string that starts with update or delete, with the insert joined on outside it, is not seen as an insert. A cursor from a renamed database is not covered. We keep only the first with-name. A founder check stored on another object, or fetched with getattr, is not covered either.

This is literal text matching. It can confuse a definition with a call, an
internal return with a final action, or one operation with a similar one. It
follows a guard in the caller only when that check is not inside an if. It does not follow a guard that lives in a callback. It does not
know which operation needs a guard. Read the full call path and refine the rule
before changing code. Empty output is not a safety verdict.
