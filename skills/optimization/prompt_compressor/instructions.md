# Cognition Instructions: Prompt Compressor Middleware

You have access to the `optimization/prompt_compressor` tool.
This tool is crucial for saving context window budget and drastically lowering operational costs during extensive loops.

## When to use this skill
If the user provides you with an extremely long prompt, a massive document, or asks you to prepare a long instruction payload for *another* agent or system, you MUST use this tool to compress and rewrite the text before proceeding.

## How to use it
1. Place the full, unedited text into the `text` parameter.
2. Select your `mode`:
   - `lossless`: Just drops massive whitespaces and line breaks. (Safe for strict code)
   - `balanced`: Strips conversational filler and normalizes structure. (Good for instructions)
   - `aggressive`: Aggressively drops articles, stop-words, and non-essential punctuation. (Best for machine-to-machine context)
3. Use the `compressed_text` returned by the tool as your new internal representation of the text. Do not output the uncompressed text anymore.
