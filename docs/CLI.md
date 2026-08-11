# Forge CLI Reference

`forge` is the human client. It ships with the kernel package and speaks
the official Kernel API directly (it is the kernel's own first-party
interface, not an external SDK client); proposal flows (`plan`,
`propose`) go through the SDK exactly like any other client would.

```
init          create events.log in DIR
create        add a task (--id, --desc, -a acceptance, -f file, --priority)
update        change title/desc/acceptance/files/priority
dep           add/remove a dependency (--remove)
expand        turn a task into a container; children become its work
start         todo -> in_progress
verify-pass   in_progress -> done (requires deps done; --force bypasses)
verify-fail   in_progress -> needs_revision (--reason required)
retry         needs_revision -> in_progress
reopen        done -> in_progress
evidence      attach hard/soft evidence (--kind, --source, --detail)
note          append a note
delete        remove a task (no dependents, no children)
show          context package (--json for machine format)
inspect       full dossier: status, completion, children, evidence, history
query         expression filter / function call (--json)
export        event log as portable JSON (FILE or stdout)
import        merge an exported log; id collisions rejected
graph         render the task tree (optional root TASK)
ready         list tasks ready to work on
next          the single next task
blockers      incomplete deps (--chain for root-cause paths)
progress      done/total + per-status counts
validate      consistency check (cycles, dangling refs)
log           view events (--tail N)
undo [N]      truncate the last N events
replay        reconstruct the graph from the log
demo          seed the Snake Game example (empty project only)
```

## Query language

```
forge query "status == needs_revision"
forge query "priority > medium"                    # low < medium < high
forge query '"snake" in title and not blocked'
forge query "evidence_count >= 2 and status == done"
forge query "id in children(renderer)"
forge query blockers(renderer)
forge query evidence(input)
forge query ready()
```

Safe expression subset: status, priority, evidence_count, files,
depends_on, and/or/not, comparison operators, plus function calls
(`children()`, `blockers()`, `evidence()`, `ready()`).

Unknown field names or enum values are rejected with a clean error --
a typo'd query never silently returns `(no matches)`. A status field
takes `todo`/`in_progress`/`needs_revision`/`done`; a priority field
takes `low`/`medium`/`high`.

## Plugin commands

Additional commands arrive through the `forge.commands` entry-point
group (see forge/plugins.py); a known-but-missing package gets an
install-hint stub instead of a silent no-op.

`forge proof` (provided by the `forge-proof` package) is the reference
evidence pipeline — a stdlib-only, kernel-free tool that derives a
Proof-Standard artifact bundle from a raw `events.log`:

```
forge proof check   <dir>   validate a bundle against the §6 conformance checklist
forge proof derive  <dir>   derive graph.json/metrics.json/replay facts from events.log
forge proof replay  <dir>   render replay.md (Goal/Outcome/Timeline/Turning points)
forge proof bundle  <dir>   emit the full bundle + validate (derived artifacts are
                            verified byte-identical; curated files are never clobbered)
```

`proof` operates on an artifacts directory, not a Forge project: it is
exempt from the `-d` project gate and never constructs a Kernel.
