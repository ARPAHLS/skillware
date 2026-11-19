import os
import re
from typing import Any, Dict, List, Optional
import warnings
from skillware.core.base_skill import BaseSkill

# Sentinels (private-use unicode, so they never collide with normal text)
# General protected spans use \ue000..\ue001, system-prompt blocks use \ue002..\ue003.
_GEN_OPEN, _GEN_CLOSE = "\ue000", "\ue001"
_SYS_OPEN, _SYS_CLOSE = "\ue002", "\ue003"
_SENT_RE = re.compile(r"([\ue000\ue002])(\d+)[\ue001\ue003]")
_LEADING_SYS_RE = re.compile(r"^(?:\ue002\d+\ue003\s*)+")

# System prompt detection: <system>...</system> or [SYSTEM]...[/SYSTEM]
_SYSTEM_BLOCK_RE = re.compile(
    r"<(?P<tag>system(?:[_-]prompt)?)>.*?</(?P=tag)>"
    r"|\[(?P<btag>system(?:[_-]prompt)?)\].*?\[/(?P=btag)\]",
    re.IGNORECASE | re.DOTALL,
)

# Spans that must never be altered, in any mode
_CODE_PROTECT_PATTERNS = [
    re.compile(r"```.*?```", re.DOTALL),
    re.compile(r"`[^`\n]+`"),
]

_TEMPLATE_PROTECT_PATTERNS = [
    re.compile(r"\{\{.*?\}\}", re.DOTALL),
    re.compile(r"\$\{[^}]*\}"),
    re.compile(r"\{[A-Za-z_][\w.]*\}"),
    re.compile(r"</?[A-Za-z][\w:-]*(?:\s[^<>]*)?>"),
]

_OTHER_PROTECT_PATTERNS = [
    re.compile(r"https?://[^\s)>\]]+"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
]

# Level 2: phrases deleted outright (longest first, word-bounded)
_DELETE_PHRASES = sorted(
    [
        "please", "kindly", "could you", "would you", "can you", "will you",
        "I want you to", "I need you to", "I would like you to", "I'd like you to",
        "I was wondering if you could", "make sure to",
        "be sure to", "feel free to", "it is important to",
        "note that", "keep in mind that",
    ],
    key=len,
    reverse=True,
)
_DELETE_RE = re.compile(
    r"(?<![\w'])(?:" + "|".join(re.escape(p) for p in _DELETE_PHRASES) + r")(?![\w'])"
                                                                         r"[,]?[ \t]*(?P<nxt>[a-z])?",
    re.IGNORECASE,
)

# Level 2: verbose phrase -> short equivalent
_REWRITES = {
    "in order to": "to",
    "so as to": "to",
    "due to the fact that": "because",
    "for the reason that": "because",
    "for the purpose of": "for",
    "at this point in time": "now",
    "at the present time": "now",
    "in the event that": "if",
    "in the case that": "if",
    "with regard to": "about",
    "with respect to": "about",
    "prior to": "before",
    "a number of": "several",
    "a large number of": "many",
    "a lot of": "many",
    "the majority of": "most",
    "as well as": "and",
    "is able to": "can",
    "are able to": "can",
    "has the ability to": "can",
    "utilize": "use",
    "in addition to": "besides",
    "it is necessary to": "must",
    "make sure that": "ensure",
    "ensure that": "ensure",
}
_REWRITE_RE = re.compile(
    r"(?<![\w'])(?:"
    + "|".join(re.escape(p) for p in sorted(_REWRITES, key=len, reverse=True))
    + r")(?![\w'])",
    re.IGNORECASE,
)

# Level 3 (aggressive, lossy by design)
_INTENSIFIERS_RE = re.compile(
    r"(?<![\w'-])(?:just|really|very|basically|actually|simply|quite|in fact)(?![\w'-])[ \t]*",
    re.IGNORECASE,
)
# Lowercase articles only: spares sentence-initial "The" and things like "Vitamin A".
_ARTICLES_RE = re.compile(r"(?<![\w'-])(?:a|an|the)(?![\w'-])[ \t]+")
_DECOR_PUNCT_RE = re.compile(r"(?<=\S)\*+|\*+(?=\S)|[!~]+")
_HRULE_RE = re.compile(r"^[ \t]*([-=_*])\1{2,}[ \t]*$", re.MULTILINE)


class PromptCompressor(BaseSkill):

    VALID_ACTIONS = {"compress_prompt", "analyze_prompt_density"}

    VALID_MODES = {
        "lossless": "lossless",
        "balanced": "balanced",
        "cache_optimized": "cache_optimized",
        "aggressive": "aggressive",
        # deprecated
        "low": "lossless",
        "medium": "balanced",
        "high": "aggressive",
    }

    DEPRECATED_MODES = ['low', 'medium', 'high']

    @property
    def manifest(self) -> Dict[str, Any]:
        return self.load_manifest_from_dir(os.path.dirname(__file__))

    # tokens
    def _estimate_tokens(self, text: str) -> int:
        """Uses tiktoken if installed, else a char/word blend heuristic."""
        if not text:
            return 0
        try:
            import tiktoken

            return len(tiktoken.get_encoding("cl100k_base").encode(text))
        except Exception:
            return max(1, round((len(text) / 4 + len(text.split()) * 1.3) / 2))

    @staticmethod
    def _get_compression_stages(mode):
        stages = {
            "lossless": ["lossless", "balanced", "aggressive"],
            "balanced": ["balanced", "aggressive"],
            "aggressive": ["aggressive"],
            "cache_optimized": ["balanced", "aggressive"],
        }
        return stages[mode]

    # protection
    @staticmethod
    def _protect(text: str, pattern: re.Pattern, store: List[str], o: str, c: str) -> str:
        def repl(m: re.Match) -> str:
            store.append(m.group(0))
            return f"{o}{len(store) - 1}{c}"

        return pattern.sub(repl, text)

    @staticmethod
    def _restore(text, store):
        while _SENT_RE.search(text):
            text = _SENT_RE.sub(lambda m: store[int(m.group(2))], text)
        return text

    # compression
    @staticmethod
    def _normalize_ws(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t\f\v]+", " ", text)
        text = re.sub(r" ?\n ?", "\n", text)  # trim around newlines
        text = re.sub(r"\n{3,}", "\n\n", text)  # keep paragraph breaks
        return text.strip()

    @staticmethod
    def _delete_sub(m: re.Match) -> str:
        nxt = m.group("nxt") or ""
        before = m.string[: m.start()].rstrip(" \t")
        at_sentence_start = (not before) or before[-1] in ".!?\n"
        return nxt.upper() if (nxt and at_sentence_start) else nxt

    @staticmethod
    def _rewrite_sub(m: re.Match) -> str:
        rep = _REWRITES[m.group(0).lower()]
        return rep.capitalize() if m.group(0)[0].isupper() else rep

    @staticmethod
    def _dedupe_lines(text: str) -> str:
        seen, out = set(), []
        for line in text.split("\n"):
            key = line.strip().casefold()
            if len(key) >= 20 and not _SENT_RE.search(line):
                if key in seen:
                    continue
                seen.add(key)
            out.append(line)
        return "\n".join(out)

    def _compress_body(self, text: str, mode: str) -> str:
        # Level 1: lossless whitespace normalization (keeps lists/paragraphs intact)
        text = self._lossless(self, text)

        # Level 2: filler removal + verbose phrase rewriting
        if mode in ("balanced", "aggressive", "cache_optimized"):
            text = self._balanced(self, text)

        # Level 3: lossy trimming
        if mode == "aggressive":
            text = self._aggressive(self, text)

        # Cleanup artifacts left by removals and return
        return self._cleanup(self, text)

    @staticmethod
    def _lossless(self, text: str) -> str:
        return self._normalize_ws(text)

    @staticmethod
    def _balanced(self, text: str) -> str:
        # The delete regex consumes the first letter of the following word,
        # which can hide an adjacent filler ("Please make sure to ...").
        # Re-run until nothing changes.
        for _ in range(4):
            new_text = _DELETE_RE.sub(self._delete_sub, text)
            if new_text == text:
                break
            text = new_text
        text = _REWRITE_RE.sub(self._rewrite_sub, text)
        return text

    @staticmethod
    def _aggressive(self, text: str) -> str:
        text = _HRULE_RE.sub("", text)
        text = _DECOR_PUNCT_RE.sub("", text)
        text = _INTENSIFIERS_RE.sub("", text)
        text = _ARTICLES_RE.sub("", text)
        text = re.sub(r"\.{2,}", ".", text)
        text = self._dedupe_lines(text)
        return text

    @staticmethod
    def _cleanup(self, text: str) -> str:
        text = re.sub(r"[ \t]+([,.;:?])", r"\1", text)
        text = re.sub(r"([,;:])\1+", r"\1", text)
        return self._lossless(self, text)

    def execute(self, params: Dict[str, Any]) -> Any:
        action = params.get("action", "compress_prompt")
        if action == "analyze_prompt_density":
            return self._analyze_density(params)
        if action == "compress_prompt":
            return self._compress(params)
        return {"status": "error",
                "error": f"action must be one of {sorted(self.VALID_ACTIONS)}, got '{action}'."}

    # compress
    def _compress(self, params: Dict[str, Any]) -> Any:
        text = params.get("text", params.get("raw_text", ""))
        mode = params.get("mode", params.get("compression_aggression", "balanced")).lower()

        if not isinstance(text, str) or not text.strip():
            return {"status": "error", "error": "text cannot be empty."}

        if mode in self.DEPRECATED_MODES:
            warnings.warn(
                f"'{mode}' is deprecated; use '{self.VALID_MODES[mode]}'.",
                DeprecationWarning,
                stacklevel=2
            )

        if mode not in self.VALID_MODES:
            return {
                "status": "error",
                "error": f"mode must be one of {self.VALID_MODES.keys()}, got '{mode}'."}

        mode = self.VALID_MODES[mode].lower()

        preserve_prefix_chars = params.get("preserve_prefix_chars", 0)

        if (not isinstance(preserve_prefix_chars, int)
                or isinstance(preserve_prefix_chars, bool)
                or preserve_prefix_chars < 0
        ):
            return {
                "status": "error",
                "error": "preserve_prefix_chars must be a non-negative integer."
            }

        cache_optimized = self.VALID_MODES['cache_optimized'] == mode and preserve_prefix_chars == 0
        prefix_preservation = preserve_prefix_chars > 0

        original_tokens = self._estimate_tokens(text)

        # Separate the explicitly preserved prefix before any text modification.
        preserved_prefix = ""
        if prefix_preservation:
            preserved_prefix = text[:preserve_prefix_chars]
            text = text[preserve_prefix_chars:]

        # Remove existing sentinel characters only from the compressible portion.
        text = re.sub(r"[\ue000-\ue003]", "", text)

        warns: List[str] = []
        store: List[str] = []
        sys_blocks = 0

        # 1. Protect inline system blocks
        if cache_optimized:
            def _protect_sys(m: re.Match) -> str:
                nonlocal sys_blocks
                sys_blocks += 1
                store.append(m.group(0))
                return f"{_SYS_OPEN}{len(store) - 1}{_SYS_CLOSE}"

            text = _SYSTEM_BLOCK_RE.sub(_protect_sys, text)

        # 2. Protect other important content
        protect_code_blocks = params.get("protect_code_blocks", True)
        protect_templates = params.get("protect_templates", True)

        patterns = list(_OTHER_PROTECT_PATTERNS)

        if protect_code_blocks:
            patterns.extend(_CODE_PROTECT_PATTERNS)

        if protect_templates:
            patterns.extend(_TEMPLATE_PROTECT_PATTERNS)

        for pattern in patterns:
            text = self._protect(text, pattern, store, _GEN_OPEN, _GEN_CLOSE)

        # 3. Identify the cacheable prefix before compression
        leading_prefix = ""
        text_to_compress = text

        if cache_optimized:
            # Automatically identify leading system instructions
            lead = _LEADING_SYS_RE.match(text)

            if lead:
                leading_prefix = lead.group(0)

                # Remove the system prefix from the text being compressed
                text_to_compress = text[lead.end():]

                if (lead.end() < len(text)
                        and sys_blocks > len(_SENT_RE.findall(lead.group(0)))
                ):
                    warns.append(
                        "Some system blocks appear after dynamic content; only the leading "
                        "block(s) form a stable cache prefix."
                    )

            elif sys_blocks:
                warns.append(
                    "System block is not at the start of the prompt. It was preserved, but "
                    "text before it breaks prefix caching. Move it to the top."
                )

            else:
                warns.append(
                    "cache_optimized=True but no system prompt found. Pass `system_prompt` "
                    "or wrap it in <system>...</system> or [SYSTEM]...[/SYSTEM]."
                )

        # 4. Compress only the remaining text
        # if target tokens are provided
        target_tokens = params.get("target_tokens")

        if target_tokens is not None:
            if (not isinstance(target_tokens, int)
                    or isinstance(target_tokens, bool)
                    or target_tokens <= 0
            ):
                return {
                    "status": "error",
                    "error": "target_tokens must be a positive integer."
                }

        best_compressed = ""
        best_token_count = float("inf")
        compressed = None
        target_met = None
        stages_applied = None

        if target_tokens and 0 < target_tokens < original_tokens:
            target_met = False
            compression_stages = self._get_compression_stages(mode)
            body = text_to_compress
            for compression_mode in compression_stages:
                body = self._compress_body(
                    text=body,
                    mode=compression_mode
                )
                if not stages_applied:
                    stages_applied = []
                stages_applied.append(compression_mode)
                # 5. Restore protected content
                compressed_body = self._restore(body, store)

                # 6. Assemble the final prompt
                if prefix_preservation:
                    compressed = preserved_prefix + compressed_body
                elif cache_optimized and leading_prefix:
                    original_prefix = self._restore(leading_prefix, store)
                    compressed = original_prefix + compressed_body
                else:
                    compressed = compressed_body

                # 7. Calculate token statistics
                current_token_count = self._estimate_tokens(compressed)
                if current_token_count <= best_token_count:
                    best_compressed = compressed
                    best_token_count = current_token_count
                else:
                    compressed = best_compressed
                if best_token_count <= target_tokens:
                    target_met = True
                    break

        else:
            body = self._compress_body(
                text=text_to_compress,
                mode=mode
            )

            # 5. Restore protected content
            compressed_body = self._restore(body, store)

            # 6. Assemble the final prompt
            if prefix_preservation:
                compressed = preserved_prefix + compressed_body

            elif leading_prefix:
                original_prefix = self._restore(leading_prefix, store)
                compressed = original_prefix + compressed_body

            else:
                compressed = compressed_body

        # 7. Calculate token statistics
        new_tokens = self._estimate_tokens(compressed)

        result: Dict[str, Any] = {
            "status": "ready",
            "compressed_text": compressed,
            "original_tokens": original_tokens,
            "compressed_tokens": new_tokens,
            "tokens_saved": original_tokens - new_tokens,
            "reduction_percentage": round(
                100 * (original_tokens - new_tokens) / max(1, original_tokens), 1
            ),
            "protected_blocks_count": len(store),
            "agent_hint": {
                "mode_used": mode,
                "target_tokens": target_tokens if target_tokens else None,
                "stages_applied": stages_applied if stages_applied and target_tokens else [],
                "target_met": target_met if target_tokens else None,
                "warnings": warns,
                "lossy": mode == self.VALID_MODES['aggressive'],
                "deprecated_mode": mode if mode in self.DEPRECATED_MODES else None
            }
        }

        return result

    def _analyze_density(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text = params.get("text", "")
        if not isinstance(text, str) or not text.strip():
            return {"status": "error", "error": "text cannot be empty."}

        text = re.sub(r"[\ue000-\ue003]", "", text)
        total = self._estimate_tokens(text)

        # Structural = whitespace, rules, decorative punctuation, filler phrases.
        # Protected spans (code, templates, URLs) are never counted as structural.
        store: List[str] = []
        work = text
        for p in (_OTHER_PROTECT_PATTERNS + _CODE_PROTECT_PATTERNS + _TEMPLATE_PROTECT_PATTERNS):
            work = self._protect(work, p, store, _GEN_OPEN, _GEN_CLOSE)
        work = _HRULE_RE.sub("", work)
        work = _DECOR_PUNCT_RE.sub("", work)
        for _ in range(4):
            new = _DELETE_RE.sub(self._delete_sub, work)
            if new == work:
                break
            work = new
        work = self._normalize_ws(work)
        semantic = min(total, self._estimate_tokens(self._restore(work, store)))
        structural = total - semantic

        savings = {}
        for m in ("lossless", "balanced", "aggressive"):
            r = self._compress({"text": text, "mode": m})
            savings[m] = {
                "tokens_saved": r["tokens_saved"],
                "reduction_percentage": r["reduction_percentage"],
            }

        return {
            "status": "ready",
            "total_tokens": total,
            "structural_tokens": structural,
            "semantic_tokens": semantic,
            "information_density": round(semantic / max(1, total), 3),
            "potential_savings": savings,
        }
