---
name: background-task
description: Checklist for adding or changing background work in functions-python - a tasks_executor task, a Cloud Tasks worker, a scheduled job, a batch or fan-out run, or a function that needs worker sizing. Use before writing the code so existing building blocks are reused.
---

# Background task checklist

Read [docs/building-blocks/README.md](../../../docs/building-blocks/README.md) first. Reuse a
block before writing new infrastructure.

1. **Where it runs.** Prefer a handler in `functions-python/tasks_executor` (register it in
   the `tasks` dict with a `description`). A separate function only when it needs its own
   memory, timeout, or dependencies.
2. **Safe by default.** Accept `dry_run` for anything that writes; default it to `true`
   when the task is run by hand.
3. **State.** If the work spans requests or retries, use `TaskExecutionTracker`
   ([detail](../../../docs/building-blocks/task-execution-tracking.md)). Claim with
   `try_acquire` in the worker when it must not run twice; heartbeat long work.
4. **Large runs.** Split with `plan_fanout` and a monitor
   ([detail](../../../docs/building-blocks/fanout.md)). Workers must be idempotent; the
   monitor needs a deadline.
5. **Enqueue.** Use the `create_http_*_task` helpers. Name a task only to deduplicate,
   and never when a quick retry must get through.
6. **Sizing.** If the worst case needs far more memory than the typical job, use
   T-shirt sizing ([detail](../../../docs/building-blocks/tshirt-sizing.md)) and keep the
   tiers in sync with Terraform.
7. **Schedule.** Cloud Scheduler jobs live in `infra/functions-python/main.tf`; set
   `attempt_deadline` above the task's real duration.
8. **Per-feed behaviour.** Use per-feed configuration (register the key with Liquibase,
   validate it in the Operations API), not a new table.
9. **Docs.** Add the task to the function's README with a payload example, add a
   "Patterns used" line to the feature doc, and update the catalogue's "Used by".
