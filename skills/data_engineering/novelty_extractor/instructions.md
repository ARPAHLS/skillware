# Novelty Extractor

You are an agent equipped with the Novelty Extractor skill. This skill filters
large text datasets by semantic similarity, retaining only chunks that carry
genuinely new information.

## When to invoke this skill

Invoke `data_engineering/novelty_extractor` when:

- You need to distill a large corpus into high-signal content before passing
  it to a model or storing it.
- You are processing a dataset in multiple turns and want to avoid redundancy
  across turns by passing prior output as `baseline_chunks`.
- A user asks you to remove repetitive or redundant content from a document
  or dataset.

## Parameters

- `dataset_chunk` (required): The raw text to filter.
- `novelty_threshold` (required): A float between 0.0 and 1.0. Chunks with
  maximum cosine similarity to already-seen content below this value are kept.
  Lower values mean stricter filtering. A value of 0.85 is a sensible default
  for most corpora.
- `baseline_chunks` (optional): Text from a previous call's `distilled_content`.
  Pass this to filter consistently across multiple turns.
- `chunk_strategy` (optional): How to split the input. Use `"paragraph"`
  (default) for documents with clear paragraph breaks, or `"sentence"` for
  denser text.

## Interpreting the output

- `distilled_content`: The filtered text. Pass this to downstream tasks or
  store it as the new baseline for the next turn.
- `compression_ratio`: The percentage of input chunks that were dropped. A
  high ratio (above 80%) may indicate the threshold is too strict or the
  input is highly repetitive.
- `redundant_chunks_dropped`: The raw count of discarded chunks. Use this
  to audit filtering behavior.

## Handling edge cases

- If `distilled_content` is empty and no error is returned, all input chunks
  were too similar to the baseline. Consider lowering `novelty_threshold`.
- If an `error` key is present in the output, the skill encountered an
  unexpected failure. Inspect the value and retry with sanitized input.
- The first call without a baseline always keeps the first chunk regardless
  of threshold, since there is nothing to compare against.

## Multi-turn example

Turn 1: pass the first batch without baseline.
Turn 2: pass the next batch with `baseline_chunks` set to the previous
`distilled_content`.
Repeat until the full corpus is processed.

Note: the skill only filters each batch against the provided baseline. It does
not accumulate results across turns automatically. The caller is responsible
for concatenating `distilled_content` from each turn to build the full
distilled dataset.