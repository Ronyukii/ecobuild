# backend/app/prompt_parser.py
import re

def parse_user_build_prompt(prompt: str, cpus: list, gpus: list) -> dict:
    if not prompt:
        return {
            "raw_prompt": "",
            "extracted_budget": None,
            "pinned_cpu": None,
            "pinned_gpu": None,
            "ram_capacity_gb": None,
            "form_factor_pref": None,
            "parsing_notes": []
        }

    text = prompt.lower()
    parsing_notes = []
    extracted_budget = None
    pinned_cpu = None
    pinned_gpu = None
    ram_capacity_gb = None
    form_factor_pref = None

    # 1. Budget extraction: e.g. "rm 3500", "under 4000", "3.5k", "rm3k"
    budget_match = re.search(r'(?:rm\s*|budget\s*|under\s*|max\s*)(\d+(?:\.\d+)?)\s*(k|ribu)?', text)
    if budget_match:
        val = float(budget_match.group(1))
        if budget_match.group(2) in ['k', 'ribu']:
            val *= 1000.0
        extracted_budget = val
        parsing_notes.append(f"Identified budget target: RM {extracted_budget:,.2f}")

    # 2. RAM extraction: e.g. "16gb", "32 gb ram", "64g"
    ram_match = re.search(r'(\d+)\s*(?:gb|g)\s*(?:ram|memory|ddr\d)?', text)
    if ram_match:
        cap = int(ram_match.group(1))
        if cap in [8, 16, 32, 64]:
            ram_capacity_gb = cap
            parsing_notes.append(f"Targeting {cap}GB RAM capacity")

    # 3. Form factor / Chassis preference
    if any(k in text for k in ["itx", "compact", "sff", "mini"]):
        form_factor_pref = "ITX"
        parsing_notes.append("Chassis constraint: Mini-ITX Compact Form Factor")

    # 4. CPU Matching
    for cpu in cpus:
        name_lower = cpu.name.lower()
        id_clean = cpu.cpu_id.lower().replace("_", "")
        # Specific search tokens: "12400f", "5600", "7800x3d", "13700k", "14900k", "12100f"
        model_nums = re.findall(r'\b\d{4,5}[a-z0-9]*\b', name_lower)
        if any(m in text for m in model_nums) or id_clean in text.replace(" ", ""):
            pinned_cpu = cpu
            parsing_notes.append(f"Pinned Processor: {cpu.name}")
            break

    # 5. GPU Matching
    for gpu in gpus:
        name_lower = gpu.name.lower()
        id_clean = gpu.gpu_id.lower().replace("_", "")
        # Match "4060", "4070", "7800 xt", "6600", "5070", "5080", "5090"
        model_nums = re.findall(r'\b(?:rtx|rx|arc)?\s*\d{4}[a-z0-9\s]*\b', name_lower)
        clean_nums = [re.sub(r'[^a-z0-9]', '', m) for m in model_nums if len(m) >= 4]
        if any(cn in text.replace(" ", "") for cn in clean_nums) or id_clean in text.replace(" ", ""):
            pinned_gpu = gpu
            parsing_notes.append(f"Pinned Graphics Card: {gpu.name}")
            break

    return {
        "raw_prompt": prompt,
        "extracted_budget": extracted_budget,
        "pinned_cpu": pinned_cpu,
        "pinned_gpu": pinned_gpu,
        "ram_capacity_gb": ram_capacity_gb,
        "form_factor_pref": form_factor_pref,
        "parsing_notes": parsing_notes
    }