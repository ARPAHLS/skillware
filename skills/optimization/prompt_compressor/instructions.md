# Cognition Instructions: Prompt Compressor Middleware

You have access to the `optimization/prompt_compressor` tool.
It saves context window budget and lowers operational costs during extensive loops. It has three actions, selected with the `action` parameter.

## When to use this skill
- The user provides an extremely long prompt, a massive document, or long conversation history that you need to carry forward in your own context.
- You are preparing a long instruction payload for *another* agent or system.
- You need to clean up a list of overlapping or repeated instructions.

Do not compress text the user expects back verbatim, and do not compress short prompts where the savings are negligible.

## Actions

### `compress_prompt` (default)
1. Put the full, unedited text in `text`.
2. Choose a `mode`:
   - `lossless`: Normalizes whitespace and blank lines only. Meaning is unchanged.
   - `balanced`: Also removes conversational filler ("please", "make sure to") and rewrites verbose phrases. Good default for instructions.
   - `aggressive`: Lossy. Also removes decorative punctuation, horizontal rules, intensifiers, articles, and duplicate lines. Best for machine-to-machine context. Re-read the result before relying on it for precise instructions.
   - `cache_optimized`: Like `balanced`, but keeps a leading system prompt (`<system>...</system>` or `[SYSTEM]...[/SYSTEM]`) untouched so it can serve as a stable cache prefix. Put the system block at the very start of the text. Check `agent_hint.warnings`: it tells you if the block is missing, not at the start, or followed by dynamic content before another system block.
3. Optional parameters:
   - `target_tokens`: A token budget. The tool escalates through stronger stages until the target is met or stages run out. Check `agent_hint.target_met` and `agent_hint.stages_applied`.
   - `preserve_prefix_chars`: Number of leading characters to leave untouched (for example, a fixed system prompt of known length). **This takes precedence over `cache_optimized`'s system-block handling.** When it is greater than 0, the tool does not look for `<system>` / `[SYSTEM]` blocks and emits no cache-related warnings. The first N characters are kept byte-for-byte, and only the rest of the text is compressed. Use one or the other:
     - Prefix is wrapped in `<system>` / `[SYSTEM]` tags: use `cache_optimized` and leave `preserve_prefix_chars` unset.
     - Prefix has no tags, or you know its exact length: use `preserve_prefix_chars` with any mode.
   - `protect_code_blocks` / `protect_templates` (default `true`): Keep code and `{placeholders}` verbatim. Leave these on unless you have a reason not to.
4. Use `compressed_text` as your working representation of the text. Check `agent_hint.warnings` and `agent_hint.lossy` before relying on it. Keep the original available if the user may need it.

### `analyze_prompt_density`
Pass `text`. It returns token counts, `information_density`, and estimated savings for each mode in `potential_savings`. Use it to decide whether compression is worth it, or which mode to pick, before compressing.

### `deduplicate_rules`
Pass `rules` as a list of strings (or a newline-delimited string). It strips bullets and filler, removes duplicates, and, with `combine_negatives` (default `true`), groups "Do not..." / "Never..." rules at the end. Use `deduplicated_rules` as the cleaned rule set.

## Playbook: Agent loops

1. When context exceeds your budget, run `analyze_prompt_density` on the older history.
2. Compress old tool outputs with `aggressive` and a `target_tokens` budget.
3. Keep the system prompt and the latest user turn out of compression.
4. Check `agent_hint.target_met`; if false, drop or summarize the oldest turns.

## Playbook: Prompt caching

1. Put the system prompt first, wrapped in `<system>...</system>`.
2. Compress with `cache_optimized` so that prefix stays byte-stable.
3. Check `agent_hint.warnings` for a missing or misplaced system block.
4. Never edit the prefix between calls; any change invalidates the cache.