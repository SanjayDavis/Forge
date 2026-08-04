# Replay facts (derived from events.log)

- tasks: 8 · events: 46 · passes: 9 · failures: 1 · retries: 1 · duration: 5 min

- seq 1  task_created           app-factory — planned
- seq 2  task_created           db-schema — planned
- seq 3  task_created           models — planned
- seq 4  task_created           routes — planned
- seq 5  task_created           templates — planned
- seq 6  task_created           static-css — planned
- seq 7  task_created           tests — planned
- seq 8  task_created           readme — planned
- seq 18  verification_passed    app-factory
- seq 21  verification_passed    db-schema
- seq 24  verification_passed    models
- seq 27  verification_failed    routes — POST /done/<id> on an already-done task returns 404; mark_done returns False for both 'not found' and 'already done' — completion must be idempotent
- seq 28  task_reopened          models
- seq 30  verification_passed    models
- seq 31  task_retried           routes
- seq 33  verification_passed    routes
- seq 38  verification_passed    templates
- seq 41  verification_passed    static-css
- seq 43  verification_passed    tests
- seq 46  verification_passed    readme
