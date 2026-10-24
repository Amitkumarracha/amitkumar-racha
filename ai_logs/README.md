# AI conversation evidence

An authentic chronological export has been recovered from the local conversation record, starting with the first assignment prompt. It preserves the original user/assistant messages, tool calls, tool results and user-facing questions, including failed attempts and corrections. It is an export of recorded content, not a rewritten account of the work.

See [INDEX.md](INDEX.md) for delivery status and [manifest.json](manifest.json) for the snapshot boundary, record counts and export SHA-256 hashes. Runtime configuration, internal reasoning and telemetry are not conversation output and are not included.

## Current status: export exists privately; delivery is unfinished

The conversation-content exports are saved locally as:

```text
.private/ai_logs/codex-conversation.jsonl
.private/ai_logs/codex-conversation.html
```

**They contain supplied data in the original tool results. Do not commit or publicly upload these masters.** This is a real conflict between complete-chat evidence and the assignment's prohibition on sharing the pack. Obtain the organizer's permitted confidential-delivery arrangement, then add the approved complete export or assessor-accessible link here. A manifest, index or summary alone does not satisfy the complete-export requirement.

The conversation is still in progress. After the final turn, refresh the local export:

```bash
python .private/export_ai_chat.py
```

The local helper is deliberately private and reads only this assignment's conversation. Its manifest identifies the exact recorded cutoff and any tool call still in flight. Refreshing does not rewrite earlier content.

Before submission:

1. Refresh after all chat work is finished; check the first assignment prompt, latest turn, original code attempts and failed test are present.
2. Open both exports and retain an untouched master. Do not curate, shorten or invent messages.
3. Resolve confidential delivery, add the actual approved file/link to this folder, and record it in `INDEX.md`.
4. Test assessor access. Export any other AI chats used for this assignment as well; this export covers this conversation only.

Do not make the logs look more successful than they were. The original dead ends are evidence the assignment explicitly requests.
