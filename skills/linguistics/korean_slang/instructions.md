# Instructions: Korean Slang (`linguistics/korean_slang`)

You have access to the `linguistics/korean_slang` tool.

This skill is a **deterministic, offline slang lexicon** for modern Korean
internet language (Gen-Z / MZ 줄임말, Konglish blends, jamo abbreviations).
`execute()` never calls a model and never uses the network. If a phrase is not
in the bundled pack, the tool reports `unmatched` instead of inventing a gloss.

The pack is a September 2026 snapshot. Slang moves weekly; treat misses as
honest gaps, not as permission to improvise fake 줄임말.

## When to invoke

- The end user wrote Korean (or heavily mixed 한영) that looks abbreviated,
  jokey, or "too internet" for a textbook model.
- You need to **speak like a Korean peer** in a group chat, comment, or DM
  without sounding like a textbook or a news anchor.
- You need a formality check before sending Korean to elders, managers, or
  mixed-age rooms.

Do not invoke it for literary translation, legal Korean, or standard polite
prose that contains no slang. Do not invoke it to generate insults.

## Actions

- `interpret` (default) — gloss `text`. Returns the issue contract fields
  `translation`, `slang_breakdown`, `nuance`, `formality`, plus `hits`.
- `suggest` — produce peer-register Korean lines from templates. Pass
  `intent` (praise, food, work, tired, annoyed, agree, greeting, bye,
  thanks, workout, weekend, dating, fandom, competence) and/or English/Korean
  `text` to classify. Set `audience` to `peers`, `mixed`, `work`, or `elders`.
- `lookup` — exact surface, alias, or romanization lookup.

## How to interpret the output

- Copy `translation` and `nuance` into your reply. Do not recast unmatched
  slang as if you understood it.
- If `warnings` mention caution or blocked terms, explain the incoming text
  without repeating slurs or appearance-policing jokes.
- If `audience=elders`, send the polite `suggestions` and do not add ㅋㅋ,
  ㄹㅇ, or 반말 on top.
- `formality` of `Informal / Vulgar` means you should not paste the Korean
  into a workplace or elder-facing message unless the operator explicitly
  asked for that register (`vulgar_ok`).
- On `status=error`, tell the operator the `error.detail` and do not guess.

## Examples

- User: "What does 요즘 완전 폼 미쳤다 mean on a YouTube comment?"
  -> Call `linguistics/korean_slang` with
  `text="요즘 완전 폼 미쳤다"`, `context="YouTube comment about a singer"`,
  `action="interpret"`.
- User: "Reply like a Korean twenty-something: that performance was insane."
  -> Call suggest with `intent="praise"`, `audience="peers"`.
- User: "Say thanks to my friend's grandmother in Korean."
  -> Call suggest with `intent="thanks"`, `audience="elders"` (no slang).
