"""
backend/app/prompt_parser.py — Authoritative Natural-Language Build Intent Parser.

Consolidates budget, RAM capacity, form-factor, CPU model, and GPU model extraction
with strict boundary matching so overlapping variants (e.g. 5600 vs 5600X,
RTX 4070 vs 4070 SUPER, Arc B580/B570/A750, RM 4060 vs RTX 4060) do not collide.
"""

import re
from typing import Any, Dict, List, Optional, Tuple


def _get_attr(obj: Any, attr: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _extract_gpu_chipset_token(gpu: Any, gpu_models: Optional[dict] = None) -> str:
    """Derives the canonical GPU chipset token (e.g., 'rtx 4060', 'rtx 4070 super', 'arc b580')."""
    mid = _get_attr(gpu, "model_id")
    if gpu_models and mid and mid in gpu_models:
        c_name = _get_attr(gpu_models[mid], "name", "")
    else:
        c_name = _get_attr(gpu, "name", "")

    for src in (c_name, _get_attr(gpu, "chipset_search_term", ""), _get_attr(gpu, "name", "")):
        if not src:
            continue
        m = re.search(
            r"\b((?:rtx\s*\d{4}(?:\s*ti)?(?:\s*super)?)|(?:rx\s*\d{4}(?:\s*(?:xtx|xt|gre))?)|(?:arc\s*[ab]\d{3}))\b",
            str(src).lower(),
        )
        if m:
            return re.sub(r"\s+", " ", m.group(1).strip())
    return re.sub(r"\s+", " ", str(_get_attr(gpu, "name", "")).lower().strip())


def _build_gpu_patterns(gpu: Any, gpu_models: Optional[dict] = None) -> List[Tuple[int, str, Any]]:
    """
    Builds prioritized regex patterns for a GPU.
    Returns list of (specificity_priority, compiled_regex, gpu).
    Higher priority prevents shorter prefixes (e.g., 4070) from shadowing longer variants (4070 super).
    """
    chipset = _extract_gpu_chipset_token(gpu, gpu_models)
    gid = str(_get_attr(gpu, "gpu_id", "")).lower()
    patterns: List[Tuple[int, str, Any]] = []

    if gid:
        # Exact gpu_id match gets top priority
        pat = rf"(?<![a-z0-9]){re.escape(gid)}(?![a-z0-9])"
        patterns.append((1000 + len(gid), pat, gpu))

    tokens = chipset.split()
    if not tokens:
        return patterns

    suffix_guard = r"(?![a-z0-9])(?![\s-]*(?:ti|super|xtx|xt|gre)(?![a-z0-9]))"
    flex_full = r"[\s-]*".join(re.escape(t) for t in tokens)

    # Prefixed form: "rtx 4060", "rx 7800 xt", "arc b580"
    patterns.append((500 + len(chipset), rf"(?<![a-z0-9]){flex_full}{suffix_guard}", gpu))

    # Intel / NVIDIA / AMD optional brand prefix
    if tokens[0] in ("rtx", "rx", "arc") and len(tokens) >= 2:
        rest_tokens = tokens[1:]
        flex_rest = r"[\s-]*".join(re.escape(t) for t in rest_tokens)
        # Allow "intel arc b580" or "intel b580"
        if tokens[0] == "arc":
            patterns.append((520 + len(chipset), rf"(?<![a-z0-9])(?:intel[\s-]+)?arc[\s-]*{flex_rest}(?![a-z0-9])", gpu))
            patterns.append((320 + len(rest_tokens[0]), rf"(?<![a-z0-9]){flex_rest}(?![a-z0-9])", gpu))
        else:
            # Bare model code when unambiguous (has suffix like Ti/Super/XT/XTX/GRE OR not colliding with Ryzen 7600/7700)
            has_suffix = len(rest_tokens) > 1
            bare_num = rest_tokens[0]
            if has_suffix or bare_num not in ("7600", "7700"):
                patterns.append((250 + len(" ".join(rest_tokens)), rf"(?<![a-z0-9]){flex_rest}{suffix_guard}", gpu))

    return [(score, re.compile(p), g) for score, p, g in patterns]


def _build_cpu_patterns(cpu: Any, cpu_models: Optional[dict] = None) -> List[Tuple[int, re.Pattern, Any]]:
    """
    Builds prioritized regex patterns for a CPU with strict boundary matching
    so '5600X' always matches Ryzen 5 5600X and never Ryzen 5 5600.
    """
    cid = str(_get_attr(cpu, "cpu_id", "")).lower()
    mid = _get_attr(cpu, "model_id")
    cname = _get_attr(cpu_models[mid], "name", "") if (cpu_models and mid in cpu_models) else _get_attr(cpu, "name", "")
    name_lower = re.sub(r"\s+", " ", str(cname or _get_attr(cpu, "name", "")).lower().strip())

    patterns: List[Tuple[int, re.Pattern, Any]] = []

    if cid:
        patterns.append((1000 + len(cid), re.compile(rf"(?<![a-z0-9]){re.escape(cid)}(?![a-z0-9])"), cpu))

    # Full cleaned name without brand (e.g., "core i5-12400f", "i5 12400f", "ryzen 5 5600x", "ryzen 7 7800x3d")
    no_brand = re.sub(r"^(?:intel|amd)\s+", "", name_lower)
    for phrase, base_prio in [(name_lower, 700), (no_brand, 600)]:
        if phrase:
            parts = [re.escape(tok) for tok in re.split(r"[\s-]+", phrase) if tok]
            if parts:
                flex = r"[\s-]*".join(parts)
                patterns.append((base_prio + len(phrase), re.compile(rf"(?<![a-z0-9]){flex}(?![a-z0-9])"), cpu))

    # Core i-series shorthand: "i5 12400f" or bare "12400f", "13600kf", "14900k"
    m_intel = re.search(r"\b(i[3579])[\s-]*(\d{4,5}[a-z0-9]*)\b", name_lower)
    if m_intel:
        tier, code = m_intel.group(1), m_intel.group(2)
        patterns.append((500 + len(code), re.compile(rf"(?<![a-z0-9]){re.escape(tier)}[\s-]*{re.escape(code)}(?![a-z0-9])"), cpu))
        patterns.append((300 + len(code), re.compile(rf"(?<![a-z0-9]){re.escape(code)}(?![a-z0-9])"), cpu))

    # Ryzen shorthand: "ryzen 5 5600x", "5600x", "7800x3d"
    m_amd = re.search(r"\b(ryzen)\s*[3579]?\s*(\d{4}[a-z0-9]*)\b", name_lower)
    if m_amd:
        code = m_amd.group(2)
        patterns.append((300 + len(code), re.compile(rf"(?<![a-z0-9]){re.escape(code)}(?![a-z0-9])"), cpu))

    return patterns


def parse_user_build_prompt(
    prompt: str,
    cpus: list,
    gpus: list,
    gpu_models: Optional[dict] = None,
    cpu_models: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Extracts structured build constraints from natural language:
      - budget ceiling in MYR
      - target RAM capacity in GB
      - ITX compact form-factor preference
      - pinned CPU SKU
      - pinned GPU SKU(s) & canonical model ID
    """
    if not prompt or not str(prompt).strip():
        return {
            "raw_prompt": prompt or "",
            "extracted_budget": None,
            "pinned_cpu": None,
            "pinned_gpu": None,
            "pinned_gpus": [],
            "pinned_gpu_model_id": None,
            "ram_capacity_gb": None,
            "form_factor_pref": None,
            "parsing_notes": [],
        }

    text = str(prompt).lower()
    parsing_notes: List[str] = []
    extracted_budget: Optional[float] = None
    pinned_cpu = None
    pinned_gpu = None
    pinned_gpus: List[Any] = []
    pinned_gpu_model_id: Optional[str] = None
    ram_capacity_gb: Optional[int] = None
    form_factor_pref: Optional[str] = None

    # Text working copy with matched tokens progressively removed so numbers don't collide
    hw_text = text

    # 1. Budget extraction (e.g. "rm 3500", "under 4000", "budget of RM 4,060", "3.5k", "4000 ribu")
    budget_patterns = [
        re.compile(
            r"(?<![a-z0-9])(?:(?:budget|under|max|below|around)\s*(?:of\s*|is\s*)?(?:rm\s*)?|rm\s*)(\d+(?:,\d{3})*(?:\.\d+)?)\s*(k|ribu)?(?![a-z0-9])"
        ),
        re.compile(r"\b(\d+\.\d+)\s*(k|ribu)\b"),
        re.compile(r"\b(\d+)\s*(ribu)\b"),
    ]
    for bpat in budget_patterns:
        bm = bpat.search(hw_text)
        if bm:
            val_str = bm.group(1).replace(",", "")
            unit = bm.group(2) if bm.lastindex and bm.lastindex >= 2 else None
            val = float(val_str)
            if unit in ("k", "ribu"):
                val *= 1000.0
            extracted_budget = val
            parsing_notes.append(f"Identified budget target: RM {extracted_budget:,.2f}")
            # Remove matched budget phrase so 'under RM 4060' doesn't look like '4060' GPU
            hw_text = hw_text[: bm.start()] + " " + hw_text[bm.end() :]
            break

    # 2. Form factor preference
    if re.search(r"\b(?:mini[\s-]*itx|itx|compact|sff)\b", hw_text):
        form_factor_pref = "ITX"
        parsing_notes.append("Chassis constraint: Mini-ITX Compact Form Factor")

    # 3. GPU Matching (longest / most-specific pattern first across all candidate GPUs)
    all_gpu_patterns: List[Tuple[int, re.Pattern, Any]] = []
    for gpu in gpus:
        all_gpu_patterns.extend(_build_gpu_patterns(gpu, gpu_models=gpu_models))
    all_gpu_patterns.sort(key=lambda t: t[0], reverse=True)

    # Also detect explicitly named chipset that has NO purchasable GPU (e.g. non-Super RTX 4070 when only reference-only exists)
    # Check canonical GPU models first solely to avoid non-Super "RTX 4070" falling through to "4070" substring hacks.
    matched_gpu_span = None
    matched_gpu = None
    for _, regex, gpu in all_gpu_patterns:
        m = regex.search(hw_text)
        if m:
            matched_gpu = gpu
            matched_gpu_span = m.span()
            break

    if matched_gpu is not None:
        target_mid = _get_attr(matched_gpu, "model_id")
        target_chipset = _extract_gpu_chipset_token(matched_gpu, gpu_models=gpu_models)
        pinned_gpu_model_id = target_mid

        # Collect all purchasable GPUs sharing this canonical model / chipset
        matching_group = [
            g
            for g in gpus
            if (_get_attr(g, "model_id") == target_mid if target_mid else _extract_gpu_chipset_token(g, gpu_models) == target_chipset)
        ] or [matched_gpu]

        # Narrow down if the user explicitly named a brand or AIB cooler variant (e.g. "Zotac", "Eagle", "Strix")
        aib_filtered = []
        for g in matching_group:
            gname = str(_get_attr(g, "name", "")).lower()
            gbrand = str(_get_attr(g, "brand", "")).lower()
            variant_words = [
                w
                for w in re.findall(r"[a-z]{4,}", gname)
                if w not in ("gaming", "triple", "dual", "compact", "edition", "limited", "geforce", "radeon", "intel", "nvidia", "super")
            ]
            if (gbrand and re.search(rf"\b{re.escape(gbrand)}\b", hw_text)) or any(
                re.search(rf"\b{re.escape(vw)}\b", hw_text) for vw in variant_words
            ):
                aib_filtered.append(g)

        pinned_gpus = aib_filtered if aib_filtered else matching_group
        # Default pinned_gpu picks cheapest price in group for deterministic backward compat
        pinned_gpu = min(pinned_gpus, key=lambda g: float(_get_attr(g, "effective_price", _get_attr(g, "price", 0)) or 0))
        if len(pinned_gpus) > 1 and gpu_models and target_mid in gpu_models:
            c_name = _get_attr(gpu_models[target_mid], "name", pinned_gpu.name)
            parsing_notes.append(f"Pinned Graphics Model: {c_name} ({len(pinned_gpus)} AIB variants)")
        else:
            parsing_notes.append(f"Pinned Graphics Card: {_get_attr(pinned_gpu, 'name')}")

        # Strip matched GPU phrase (and any immediately adjacent VRAM token like '8gb'/'12gb') before CPU & RAM matching
        after_end = matched_gpu_span[1]
        vram_tail = re.match(r"\s*\d+\s*gb?\b", hw_text[after_end:])
        if vram_tail:
            after_end += vram_tail.end()
        hw_text = hw_text[: matched_gpu_span[0]] + " " + hw_text[after_end:]
    elif gpu_models:
        canon_patterns: List[Tuple[int, re.Pattern, Any]] = []
        for mid, cmodel in gpu_models.items():
            proxy = {"gpu_id": mid, "model_id": mid, "name": _get_attr(cmodel, "name", mid)}
            canon_patterns.extend(_build_gpu_patterns(proxy, gpu_models=gpu_models))
        canon_patterns.sort(key=lambda t: t[0], reverse=True)
        for _, regex, cproxy in canon_patterns:
            cm_gpu = regex.search(hw_text)
            if cm_gpu:
                c_name = _get_attr(cproxy, "name", "Requested GPU")
                parsing_notes.append(
                    f"Requested GPU '{c_name}' has no purchasable retail SKU in catalog (reference-only); optimizing across available GPUs."
                )
                after_end = cm_gpu.end()
                vram_tail = re.match(r"\s*\d+\s*gb?\b", hw_text[after_end:])
                if vram_tail:
                    after_end += vram_tail.end()
                hw_text = hw_text[: cm_gpu.start()] + " " + hw_text[after_end:]
                break

    # 4. CPU Matching (longest / most-specific token first so 5600x precedes 5600)
    all_cpu_patterns: List[Tuple[int, re.Pattern, Any]] = []
    for cpu in cpus:
        all_cpu_patterns.extend(_build_cpu_patterns(cpu, cpu_models=cpu_models))
    all_cpu_patterns.sort(key=lambda t: t[0], reverse=True)

    for _, regex, cpu in all_cpu_patterns:
        cm = regex.search(hw_text)
        if cm:
            pinned_cpu = cpu
            parsing_notes.append(f"Pinned Processor: {_get_attr(cpu, 'name')}")
            hw_text = hw_text[: cm.start()] + " " + hw_text[cm.end() :]
            break

    # 5. RAM Capacity extraction (prioritize explicit RAM/memory/DDR phrasing)
    ram_explicit = re.search(r"\b(8|16|32|64)\s*(?:gb|g)\s*(?:ram|memory|ddr[45])\b", hw_text)
    ram_fallback = re.search(r"\b(8|16|32|64)\s*(?:gb|g)\b", hw_text)
    ram_match = ram_explicit or ram_fallback
    if ram_match:
        cap = int(ram_match.group(1))
        if cap in (8, 16, 32, 64):
            ram_capacity_gb = cap
            parsing_notes.append(f"Targeting {cap}GB RAM capacity")

    return {
        "raw_prompt": prompt,
        "extracted_budget": extracted_budget,
        "pinned_cpu": pinned_cpu,
        "pinned_gpu": pinned_gpu,
        "pinned_gpus": pinned_gpus,
        "pinned_gpu_model_id": pinned_gpu_model_id,
        "ram_capacity_gb": ram_capacity_gb,
        "form_factor_pref": form_factor_pref,
        "parsing_notes": parsing_notes,
    }
