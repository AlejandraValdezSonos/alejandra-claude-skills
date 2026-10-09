# Pitfalls already hit on this work

Each of these was a real mistake made while building the first brief, caught only because a person read the draft.
They are written with the reason so you can recognise the same shape in a new ticket.

**1. The wrong word for the unit.** A page said the cube reports "Dollarized Demand units". The
measure was `net_sales_units`; Dollarized Demand is a separate model that prices those units.
The phrase was copied from an earlier explainer. *Why it matters:* a stakeholder reads the label
and goes to the wrong model. Confirm each metric's real column name and say it.

**2. A provenance callout that was not true.** "Every number was measured by running the PR's
logic over production" was false: tests ran in a dev build, and some queries ran directly on
production. It also said the queries would run against dev until deploy, but they pointed at
production, where the new columns did not exist yet. *Why it matters:* the callout is the first
thing a skeptical reader tests. State per section where numbers came from, and check the
queries as written can actually run.

**3. A refresh blamed for a closed-quarter change.** A 6-unit difference in a closed quarter
was first explained as "the daily refresh". It was one dealer record created days earlier with
history. *Why it matters:* closed quarters can move when a record arrives late. Find the rows
(compare against an earlier copy) before offering a cause, and do not expect hard-coded totals
to stay put: use bands in tests.

**4. A verification claimed from an earlier day.** A mutation check was tagged "verified today"
but its result came from a prior session's test header. Re-run it, or date it honestly.

**5. A count taken from the last commit, not the PR.** "The PR changes five files" was the last
commit; the PR changed eight. Use the diff against the base branch for anything said about the PR.

**6. Direct evidence labeled second-hand.** A stakeholder's position was tagged "second-hand,
confirm in writing" when it was a first-hand Slack message. Look for the primary source before
down-labeling. The reverse also applies: a stakeholder saying they "would not want" something is
a stated position, not "Finance decided".

**7. A decision baked into persistent text.** A stakeholder's still-open position was about to
be written into column descriptions that persist to the data catalog. Describe the verifiable
fact instead ("not currently in the channel list").

**8. A claim about another system that was only a view on this one.** A view in the legacy
system looked like an independent source for a total but was built on the same table. Check what
an "independent" source is actually built on before calling the check independent.

**9. The sentinel that is a value.** A placeholder like `*N/A` is a value, not an absence:
`coalesce` does not fall through it, and `is not null` keeps every row. Any coverage test over
such a column must exclude the placeholder, and an unresolved case should land on the unknown
dimension row so the key and the names agree.

**10. Items in the ticket that no criterion covers.** The ticket asked to "check for consumers
relying on those NULLs"; no acceptance criterion did. Read the ticket's Impact assessment and
Out of scope sections, not only its criteria, and list what is not done.
