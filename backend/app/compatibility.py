"""
backend/app/compatibility.py — Shared Hardware Compatibility & Physical Clearance Service.

Single source of truth consumed by /simulate, /optimize, and /export/bom.
Every check explicitly classifies its outcome as:
  - INCOMPATIBLE: known specification conflict
  - WARNING: known operational limitation or advisory notice (does not block compatibility)
  - UNVERIFIED: required specification data is missing (never treated as confirmed compatible)
  - COMPATIBLE: available specifications support the configuration
"""

from typing import Any, Dict, List, Optional

from .real_engine import check_physical_clearances

STATUS_COMPATIBLE = "COMPATIBLE"
STATUS_WARNING = "WARNING"
STATUS_UNVERIFIED = "UNVERIFIED"
STATUS_INCOMPATIBLE = "INCOMPATIBLE"

FORM_FACTOR_RANK = {"ATX": 3, "MATX": 2, "ITX": 1}


def _get(obj: Any, attr: str, default: Any = None) -> Any:
    """Reads an attribute from an ORM model instance or dict safely."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _record(
    checks: List[Dict[str, Any]],
    check_id: str,
    category: str,
    status: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "category": category,
            "status": status,
            "message": message,
            "details": details or {},
        }
    )


def evaluate_build_compatibility(
    cpu: Any,
    mobo: Any,
    gpu: Any,
    cooler: Any,
    case: Any,
    ram: Any,
    psu: Any,
    storage: Any,
    canonical_gpu: Any = None,
    canonical_cpu: Any = None,
) -> Dict[str, Any]:
    """
    Runs the complete deterministic 16-check compatibility & physical clearance audit.
    Returns structured status counts, per-check findings, and flat advisory warnings.
    """
    checks: List[Dict[str, Any]] = []

    cpu_name = _get(cpu, "name", _get(cpu, "cpu_id", "CPU"))
    mobo_name = _get(mobo, "name", _get(mobo, "mobo_id", "Motherboard"))
    gpu_id = _get(gpu, "gpu_id", "GPU")
    gpu_name = _get(gpu, "name", gpu_id)
    cooler_id = _get(cooler, "cooler_id", "Cooler")
    cooler_name = _get(cooler, "name", cooler_id)
    case_id = _get(case, "case_id", "Case")
    case_name = _get(case, "name", case_id)
    ram_name = _get(ram, "name", _get(ram, "ram_id", "RAM"))
    psu_name = _get(psu, "name", _get(psu, "psu_id", "PSU"))
    storage_name = _get(storage, "name", _get(storage, "storage_id", "Storage"))

    # ------------------------------------------------------------------
    # 1. CPU Socket <-> Motherboard Socket
    # ------------------------------------------------------------------
    cpu_socket = _get(cpu, "socket")
    mobo_socket = _get(mobo, "socket")
    if not cpu_socket or not mobo_socket:
        _record(
            checks,
            "cpu_mobo_socket",
            "Socket",
            STATUS_UNVERIFIED,
            f"Unverified Socket Compatibility: Socket missing for {cpu_name} or {mobo_name}.",
        )
    elif cpu_socket != mobo_socket:
        _record(
            checks,
            "cpu_mobo_socket",
            "Socket",
            STATUS_INCOMPATIBLE,
            f"Physical Mismatch: Chosen CPU requires an {cpu_socket} socket, but Motherboard is designed for {mobo_socket}.",
            {"cpu_socket": cpu_socket, "mobo_socket": mobo_socket},
        )
    else:
        _record(
            checks,
            "cpu_mobo_socket",
            "Socket",
            STATUS_COMPATIBLE,
            f"CPU and Motherboard share {cpu_socket} socket.",
            {"socket": cpu_socket},
        )

    # ------------------------------------------------------------------
    # 2. Motherboard Form Factor <-> Case Support
    # ------------------------------------------------------------------
    mobo_ff = _get(mobo, "form_factor")
    case_ff = _get(case, "form_factor")
    mobo_rank = FORM_FACTOR_RANK.get(mobo_ff)
    case_rank = FORM_FACTOR_RANK.get(case_ff)
    if mobo_rank is None or case_rank is None:
        _record(
            checks,
            "mobo_case_form_factor",
            "Form Factor",
            STATUS_UNVERIFIED,
            f"Unverified Form Factor: Cannot verify {mobo_name} ({mobo_ff}) fit inside {case_name} ({case_ff}).",
        )
    elif mobo_rank > case_rank:
        _record(
            checks,
            "mobo_case_form_factor",
            "Form Factor",
            STATUS_INCOMPATIBLE,
            f"Sizing Conflict: Motherboard ({mobo_ff}) exceeds Case size limitations ({case_ff}).",
            {"mobo_form_factor": mobo_ff, "case_form_factor": case_ff},
        )
    else:
        _record(
            checks,
            "mobo_case_form_factor",
            "Form Factor",
            STATUS_COMPATIBLE,
            f"{mobo_ff} motherboard fits within {case_ff} chassis.",
            {"mobo_form_factor": mobo_ff, "case_form_factor": case_ff},
        )

    # ------------------------------------------------------------------
    # 3. RAM Generation <-> Motherboard Generation
    # ------------------------------------------------------------------
    ram_type = _get(ram, "ram_type")
    mobo_ram_type = _get(mobo, "ram_type")
    if not ram_type or not mobo_ram_type:
        _record(
            checks,
            "ram_mobo_generation",
            "Memory",
            STATUS_UNVERIFIED,
            f"Unverified Memory Type: Missing DDR generation spec for {ram_name} or {mobo_name}.",
        )
    elif ram_type != mobo_ram_type:
        _record(
            checks,
            "ram_mobo_generation",
            "Memory",
            STATUS_INCOMPATIBLE,
            f"Memory Mismatch: Motherboard supports {mobo_ram_type} RAM, chosen is {ram_type}.",
            {"ram_type": ram_type, "mobo_ram_type": mobo_ram_type},
        )
    else:
        _record(
            checks,
            "ram_mobo_generation",
            "Memory",
            STATUS_COMPATIBLE,
            f"RAM and Motherboard both use {ram_type}.",
            {"ram_type": ram_type},
        )

    # ------------------------------------------------------------------
    # 4. RAM Capacity & Frequency Configuration
    # ------------------------------------------------------------------
    ram_cap = _get(ram, "capacity_gb")
    ram_speed = _get(ram, "speed_mhz")
    if ram_cap is None or ram_speed is None:
        _record(
            checks,
            "ram_capacity_config",
            "Memory",
            STATUS_UNVERIFIED,
            f"Unverified Memory Configuration: Missing capacity or frequency spec for {ram_name}.",
        )
    elif int(ram_cap) < 16:
        _record(
            checks,
            "ram_capacity_config",
            "Memory",
            STATUS_WARNING,
            f"Low Memory Capacity: {ram_name} provides {ram_cap}GB at {ram_speed}MHz; 16GB+ is recommended for modern AAA workloads.",
            {"capacity_gb": int(ram_cap), "speed_mhz": int(ram_speed)},
        )
    else:
        _record(
            checks,
            "ram_capacity_config",
            "Memory",
            STATUS_COMPATIBLE,
            f"{ram_cap}GB {ram_type or ''} memory at {ram_speed}MHz.".strip(),
            {"capacity_gb": int(ram_cap), "speed_mhz": int(ram_speed)},
        )

    # ------------------------------------------------------------------
    # 5. RAM Channel Count
    # ------------------------------------------------------------------
    ram_channels = _get(ram, "channels")
    if ram_channels is None:
        _record(
            checks,
            "ram_channels",
            "Memory",
            STATUS_UNVERIFIED,
            f"Unverified Memory Channels: Channel configuration missing for {ram_name}.",
        )
    elif int(ram_channels) <= 1:
        _record(
            checks,
            "ram_channels",
            "Memory",
            STATUS_WARNING,
            f"Single-Channel Memory Bottleneck: {ram_name} is a single-stick (1x {ram_cap or '?'}GB) configuration. "
            "Halving the memory bus to single-channel reduces 1% low frametimes by up to 20% in CPU-bound games (causing micro-stutters). "
            "We strongly recommend choosing a dual-stick kit (2x8GB or 2x16GB) to activate dual-channel bandwidth.",
            {"channels": int(ram_channels)},
        )
    else:
        _record(
            checks,
            "ram_channels",
            "Memory",
            STATUS_COMPATIBLE,
            f"Dual-channel memory configuration active ({ram_channels} channels).",
            {"channels": int(ram_channels)},
        )

    # ------------------------------------------------------------------
    # 6. RAM Height <-> Cooler Clearance
    # ------------------------------------------------------------------
    ram_height = _get(ram, "height_mm")
    cooler_ram_clearance = _get(cooler, "max_ram_clearance_mm")
    if ram_height is None or cooler_ram_clearance is None:
        _record(
            checks,
            "ram_cooler_clearance",
            "Clearance",
            STATUS_UNVERIFIED,
            f"Unverified RAM Clearance: Height for {ram_name} or clearance limit for {cooler_name} is unavailable.",
        )
    elif ram_height > cooler_ram_clearance:
        overhang_excess = ram_height - cooler_ram_clearance
        _record(
            checks,
            "ram_cooler_clearance",
            "Clearance",
            STATUS_INCOMPATIBLE,
            f"RAM Overhang Conflict: {ram_name} ({ram_height}mm) exceeds {cooler_name} clearance ({cooler_ram_clearance}mm). "
            f"Front fan will be displaced upward by {overhang_excess}mm and may collide with the side panel.",
            {"ram_height_mm": ram_height, "cooler_max_ram_clearance_mm": cooler_ram_clearance},
        )
    else:
        _record(
            checks,
            "ram_cooler_clearance",
            "Clearance",
            STATUS_COMPATIBLE,
            f"RAM module height ({ram_height}mm) clears {cooler_name} ({cooler_ram_clearance}mm limit).",
            {"ram_height_mm": ram_height, "cooler_max_ram_clearance_mm": cooler_ram_clearance},
        )

    # ------------------------------------------------------------------
    # 7. CPU Socket <-> Cooler Supported Sockets
    # ------------------------------------------------------------------
    raw_socket_list = _get(cooler, "socket_list")
    supported_sockets = [s.strip() for s in str(raw_socket_list).split(",") if s.strip()] if raw_socket_list else []
    if not cpu_socket or not supported_sockets:
        _record(
            checks,
            "cpu_cooler_socket",
            "Cooling",
            STATUS_UNVERIFIED,
            f"Unverified Cooler Mounting: Socket support missing for {cpu_name} or {cooler_name}.",
        )
    elif cpu_socket not in supported_sockets:
        _record(
            checks,
            "cpu_cooler_socket",
            "Cooling",
            STATUS_INCOMPATIBLE,
            f"Cooler Socket Mismatch: {cpu_name} uses socket {cpu_socket}, but {cooler_name} only supports [{', '.join(supported_sockets)}].",
            {"cpu_socket": cpu_socket, "cooler_sockets": supported_sockets},
        )
    else:
        _record(
            checks,
            "cpu_cooler_socket",
            "Cooling",
            STATUS_COMPATIBLE,
            f"{cooler_name} includes mounting bracket support for {cpu_socket}.",
            {"cpu_socket": cpu_socket},
        )

    # ------------------------------------------------------------------
    # 8. CPU TDP <-> Cooler Rated Capacity
    # ------------------------------------------------------------------
    cpu_tdp = _get(cpu, "tdp_watts")
    cooler_max_tdp = _get(cooler, "max_tdp")
    if cpu_tdp is None or cooler_max_tdp is None:
        _record(
            checks,
            "cpu_cooler_tdp",
            "Cooling",
            STATUS_UNVERIFIED,
            f"Unverified Cooler Thermal Capacity: TDP rating missing for {cpu_name} or {cooler_name}.",
        )
    elif cpu_tdp > cooler_max_tdp:
        deficit = cpu_tdp - cooler_max_tdp
        _record(
            checks,
            "cpu_cooler_tdp",
            "Cooling",
            STATUS_INCOMPATIBLE,
            f"Cooler Capacity Deficit: {cpu_name} is rated at {cpu_tdp}W TDP, exceeding {cooler_name}'s {cooler_max_tdp}W dissipation rating (+{deficit}W overload).",
            {"cpu_tdp_watts": cpu_tdp, "cooler_max_tdp": cooler_max_tdp},
        )
    else:
        _record(
            checks,
            "cpu_cooler_tdp",
            "Cooling",
            STATUS_COMPATIBLE,
            f"{cooler_name} ({cooler_max_tdp}W rated) handles {cpu_name} ({cpu_tdp}W TDP).",
            {"cpu_tdp_watts": cpu_tdp, "cooler_max_tdp": cooler_max_tdp},
        )

    # ------------------------------------------------------------------
    # 9 & 10. Cooler Height/Radiator & GPU Length <-> Case Clearances
    # ------------------------------------------------------------------
    clearance = check_physical_clearances(
        gpu_id=gpu_id,
        cooler_id=cooler_id,
        case_id=case_id,
        gpu_length_mm=_get(gpu, "length_mm"),
        cooler_type=_get(cooler, "type"),
        cooler_height_mm=_get(cooler, "height_mm"),
        cooler_rad_size_mm=_get(cooler, "rad_size_mm"),
        case_name=case_name,
        case_max_gpu_len_mm=_get(case, "max_gpu_len_mm"),
        case_max_cooler_height_mm=_get(case, "max_cooler_height_mm"),
        case_max_radiator_mm=_get(case, "max_radiator_mm"),
    )

    gpu_conflict_msgs = [m for m in clearance["conflicts"] if m.startswith("GPU Collision")]
    gpu_unverified_msgs = [m for m in clearance["unverified"] if "GPU Clearance" in m]
    cooler_conflict_msgs = [m for m in clearance["conflicts"] if not m.startswith("GPU Collision")]
    cooler_unverified_msgs = [m for m in clearance["unverified"] if "GPU Clearance" not in m]

    if cooler_conflict_msgs:
        for msg in cooler_conflict_msgs:
            _record(checks, "cooler_case_clearance", "Clearance", STATUS_INCOMPATIBLE, msg, clearance["metrics"])
    elif cooler_unverified_msgs:
        for msg in cooler_unverified_msgs:
            _record(checks, "cooler_case_clearance", "Clearance", STATUS_UNVERIFIED, msg, clearance["metrics"])
    else:
        _record(
            checks,
            "cooler_case_clearance",
            "Clearance",
            STATUS_COMPATIBLE,
            f"{cooler_name} fits inside {case_name}.",
            clearance["metrics"],
        )

    if gpu_conflict_msgs:
        for msg in gpu_conflict_msgs:
            _record(checks, "gpu_case_length", "Clearance", STATUS_INCOMPATIBLE, msg, clearance["metrics"])
    elif gpu_unverified_msgs:
        for msg in gpu_unverified_msgs:
            _record(checks, "gpu_case_length", "Clearance", STATUS_UNVERIFIED, msg, clearance["metrics"])
    else:
        _record(
            checks,
            "gpu_case_length",
            "Clearance",
            STATUS_COMPATIBLE,
            f"GPU length ({clearance['metrics']['gpu_length_mm']}mm) clears {case_name} ({clearance['metrics']['max_gpu_allowed_mm']}mm limit).",
            clearance["metrics"],
        )

    # ------------------------------------------------------------------
    # 11. GPU Slot Thickness <-> Case Slot Capacity
    # ------------------------------------------------------------------
    gpu_thickness_raw = _get(gpu, "slot_thickness")
    case_max_slots_raw = _get(case, "max_gpu_slots")
    if gpu_thickness_raw is None or case_max_slots_raw is None:
        _record(
            checks,
            "gpu_case_slot_thickness",
            "Clearance",
            STATUS_UNVERIFIED,
            f"Unverified Expansion Slot Clearance: Slot thickness for {gpu_name} or slot capacity for {case_name} is unavailable.",
        )
    else:
        gpu_thickness = float(gpu_thickness_raw)
        case_max_slots = float(case_max_slots_raw)
        if gpu_thickness > case_max_slots:
            _record(
                checks,
                "gpu_case_slot_thickness",
                "Clearance",
                STATUS_INCOMPATIBLE,
                f"Expansion Slot Conflict: {gpu_name} has a {gpu_thickness}-slot thick cooler, but {case_name} only provides {case_max_slots} PCIe expansion slots. "
                "The card will collide with the side frame or bottom PSU shroud.",
                {"gpu_slot_thickness": gpu_thickness, "case_max_gpu_slots": case_max_slots},
            )
        else:
            _record(
                checks,
                "gpu_case_slot_thickness",
                "Clearance",
                STATUS_COMPATIBLE,
                f"GPU {gpu_thickness}-slot width fits within {case_max_slots}-slot chassis allowance.",
                {"gpu_slot_thickness": gpu_thickness, "case_max_gpu_slots": case_max_slots},
            )

    # ------------------------------------------------------------------
    # 12. GPU Power Connector & Cable Requirements <-> PSU Capability
    # ------------------------------------------------------------------
    gpu_power_type = _get(gpu, "power_connector")
    gpu_cables_req = _get(gpu, "min_pcie_cables")
    psu_has_12vhpwr = _get(psu, "has_12vhpwr")
    psu_8pin_count = _get(psu, "pcie_8pin_count")
    if not gpu_power_type or gpu_cables_req is None or psu_has_12vhpwr is None or psu_8pin_count is None:
        _record(
            checks,
            "gpu_psu_power_connectors",
            "Power",
            STATUS_UNVERIFIED,
            f"Unverified GPU Power Cabling: Missing connector or cable specifications between {gpu_name} and {psu_name}.",
        )
    else:
        is_16pin_power = any(tok in str(gpu_power_type).lower() for tok in ("12v-2x6", "12vhpwr", "16-pin"))
        psu_atx_ver = _get(psu, "atx_version") or "ATX 2.0"
        if is_16pin_power:
            if bool(psu_has_12vhpwr):
                _record(
                    checks,
                    "gpu_psu_power_connectors",
                    "Power",
                    STATUS_COMPATIBLE,
                    f"{psu_name} provides native 12VHPWR/12V-2x6 cable for {gpu_name}.",
                    {"gpu_power_connector": gpu_power_type, "psu_has_12vhpwr": True},
                )
            elif int(psu_8pin_count) < int(gpu_cables_req):
                _record(
                    checks,
                    "gpu_psu_power_connectors",
                    "Power",
                    STATUS_INCOMPATIBLE,
                    f"Critical Power Shortage: {gpu_name} requires either a native 16-pin 12V-2x6 cable or {gpu_cables_req}x separate 8-pin PCIe cables. "
                    f"{psu_name} only provides {psu_8pin_count}x 8-pin cables and cannot power this card.",
                    {"gpu_cables_req": int(gpu_cables_req), "psu_8pin_count": int(psu_8pin_count), "psu_has_12vhpwr": False},
                )
            else:
                _record(
                    checks,
                    "gpu_psu_power_connectors",
                    "Power",
                    STATUS_WARNING,
                    f"Cable Adapter Notice: {gpu_name} relies on a 16-pin 12V-2x6 connection. "
                    f"{psu_name} is an older {psu_atx_ver} unit and will require using a bulky {gpu_cables_req}x 8-pin adapter octopus.",
                    {"gpu_cables_req": int(gpu_cables_req), "psu_8pin_count": int(psu_8pin_count), "psu_has_12vhpwr": False},
                )
        else:
            if int(psu_8pin_count) < int(gpu_cables_req):
                _record(
                    checks,
                    "gpu_psu_power_connectors",
                    "Power",
                    STATUS_INCOMPATIBLE,
                    f"Power Cable Shortage: {gpu_name} requires {gpu_cables_req}x 8-pin PCIe power cables, but {psu_name} only provides {psu_8pin_count}.",
                    {"gpu_cables_req": int(gpu_cables_req), "psu_8pin_count": int(psu_8pin_count)},
                )
            else:
                _record(
                    checks,
                    "gpu_psu_power_connectors",
                    "Power",
                    STATUS_COMPATIBLE,
                    f"{psu_name} provides {psu_8pin_count}x 8-pin PCIe connectors ({gpu_cables_req} required).",
                    {"gpu_cables_req": int(gpu_cables_req), "psu_8pin_count": int(psu_8pin_count)},
                )

    # ------------------------------------------------------------------
    # 13. CPU + GPU Power Demand <-> PSU Wattage Headroom
    # ------------------------------------------------------------------
    gpu_tdp = _get(gpu, "tdp_watts")
    psu_wattage = _get(psu, "wattage")
    if cpu_tdp is None or gpu_tdp is None or psu_wattage is None:
        _record(
            checks,
            "psu_wattage_headroom",
            "Power",
            STATUS_UNVERIFIED,
            f"Unverified PSU Wattage Headroom: Missing TDP or PSU wattage spec for {cpu_name}, {gpu_name}, or {psu_name}.",
        )
    else:
        total_system_tdp = cpu_tdp + gpu_tdp + 50
        minimum_required_psu = total_system_tdp / 0.80
        if psu_wattage < minimum_required_psu:
            _record(
                checks,
                "psu_wattage_headroom",
                "Power",
                STATUS_INCOMPATIBLE,
                f"Power Supply Risk: Minimum recommended PSU is {round(minimum_required_psu)}W, chosen is {psu_wattage}W.",
                {"minimum_required_psu_w": round(minimum_required_psu), "psu_wattage": psu_wattage, "total_system_tdp_w": total_system_tdp},
            )
        else:
            _record(
                checks,
                "psu_wattage_headroom",
                "Power",
                STATUS_COMPATIBLE,
                f"{psu_wattage}W PSU meets {round(minimum_required_psu)}W recommended headroom.",
                {"minimum_required_psu_w": round(minimum_required_psu), "psu_wattage": psu_wattage},
            )

    # ------------------------------------------------------------------
    # 14. PSU Form Factor & Depth Length <-> Case Support
    # ------------------------------------------------------------------
    psu_ff = _get(psu, "form_factor")
    raw_supported_psu_ff = _get(case, "supported_psu_form_factors")
    case_supported_ff = [s.strip() for s in str(raw_supported_psu_ff).split(",") if s.strip()] if raw_supported_psu_ff else []
    if not psu_ff or not case_supported_ff:
        _record(
            checks,
            "psu_case_form_factor",
            "Clearance",
            STATUS_UNVERIFIED,
            f"Unverified PSU Form Factor: Missing PSU form-factor spec between {psu_name} and {case_name}.",
        )
    elif psu_ff not in case_supported_ff:
        _record(
            checks,
            "psu_case_form_factor",
            "Clearance",
            STATUS_INCOMPATIBLE,
            f"PSU Fitment Conflict: {case_name} strictly requires a [{','.join(case_supported_ff)}] power supply, but {psu_name} is an [{psu_ff}] unit.",
            {"psu_form_factor": psu_ff, "case_supported_psu_ff": case_supported_ff},
        )
    else:
        _record(
            checks,
            "psu_case_form_factor",
            "Clearance",
            STATUS_COMPATIBLE,
            f"{psu_ff} PSU supported by {case_name}.",
        )

    psu_len = _get(psu, "length_mm")
    case_max_psu_len = _get(case, "max_psu_len_mm")
    if psu_len is None or case_max_psu_len is None:
        _record(
            checks,
            "psu_case_length",
            "Clearance",
            STATUS_UNVERIFIED,
            f"Unverified PSU Depth Clearance: Length missing for {psu_name} or {case_name}.",
        )
    elif psu_len > case_max_psu_len:
        _record(
            checks,
            "psu_case_length",
            "Clearance",
            STATUS_INCOMPATIBLE,
            f"PSU Depth Conflict: {psu_name} depth ({psu_len}mm) exceeds {case_name} clearance ({case_max_psu_len}mm). Cabling will collide with internal cages.",
            {"psu_length_mm": psu_len, "case_max_psu_len_mm": case_max_psu_len},
        )
    else:
        _record(
            checks,
            "psu_case_length",
            "Clearance",
            STATUS_COMPATIBLE,
            f"PSU depth ({psu_len}mm) fits within {case_max_psu_len}mm allowance.",
        )

    # ------------------------------------------------------------------
    # 15. Storage Interface <-> Motherboard Support
    # ------------------------------------------------------------------
    storage_type = _get(storage, "type")
    mobo_m2_slots = _get(mobo, "m2_slots_count")
    if not storage_type:
        _record(
            checks,
            "storage_mobo_interface",
            "Storage",
            STATUS_UNVERIFIED,
            f"Unverified Storage Interface: Storage type missing for {storage_name}.",
        )
    elif storage_type == "NVMe_M2":
        if mobo_m2_slots is None:
            _record(
                checks,
                "storage_mobo_interface",
                "Storage",
                STATUS_UNVERIFIED,
                f"Unverified M.2 Support: M.2 slot count missing on {mobo_name} for {storage_name}.",
            )
        elif int(mobo_m2_slots) <= 0:
            _record(
                checks,
                "storage_mobo_interface",
                "Storage",
                STATUS_INCOMPATIBLE,
                f"Storage Interface Conflict: {mobo_name} has 0 M.2 NVMe slots and cannot mount {storage_name}.",
                {"mobo_m2_slots": int(mobo_m2_slots)},
            )
        elif int(mobo_m2_slots) == 1:
            _record(
                checks,
                "storage_mobo_interface",
                "Storage",
                STATUS_WARNING,
                f"Storage Expansion Notice: {mobo_name} features only 1x physical M.2 NVMe slot. "
                f"Installing {storage_name} will fully occupy all high-speed M.2 slots. "
                "Future secondary drive upgrades must use slower 2.5\" SATA SSDs or a PCIe riser card.",
                {"mobo_m2_slots": 1},
            )
        else:
            _record(
                checks,
                "storage_mobo_interface",
                "Storage",
                STATUS_COMPATIBLE,
                f"{mobo_name} provides {mobo_m2_slots}x M.2 NVMe slots.",
                {"mobo_m2_slots": int(mobo_m2_slots)},
            )
    else:
        _record(
            checks,
            "storage_mobo_interface",
            "Storage",
            STATUS_COMPATIBLE,
            f"Standard {storage_type} interface supported.",
        )

    # ------------------------------------------------------------------
    # 16. Platform Advisories: Motherboard VRM TDP, PCIe Gen/Lanes, USB-C Header
    # ------------------------------------------------------------------
    mobo_vrm_limit = _get(mobo, "max_recommended_cpu_tdp")
    has_vrm_heatsink = bool(_get(mobo, "vrm_heatsink", True))
    if cpu_tdp is None or mobo_vrm_limit is None:
        _record(
            checks,
            "mobo_vrm_tdp",
            "Platform",
            STATUS_UNVERIFIED,
            f"Unverified VRM Power Delivery: CPU TDP or VRM thermal rating unavailable for {cpu_name} / {mobo_name}.",
        )
    elif cpu_tdp > mobo_vrm_limit:
        excess_tdp = cpu_tdp - mobo_vrm_limit
        heatsink_note = "lacks VRM heatsinks" if not has_vrm_heatsink else "has inadequate power phases"
        _record(
            checks,
            "mobo_vrm_tdp",
            "Platform",
            STATUS_INCOMPATIBLE,
            f"VRM Overheat & Power Throttling Risk: {mobo_name} {heatsink_note} and is rated for <= {mobo_vrm_limit}W CPUs. "
            f"{cpu_name} demands {cpu_tdp}W under load (+{excess_tdp}W overload). The motherboard VRMs will reach 105°C+ and throttle the CPU clocks down heavily.",
            {"cpu_tdp_watts": cpu_tdp, "mobo_vrm_limit_w": mobo_vrm_limit},
        )
    else:
        _record(
            checks,
            "mobo_vrm_tdp",
            "Platform",
            STATUS_COMPATIBLE,
            f"{mobo_name} VRM ({mobo_vrm_limit}W max) supports {cpu_name} ({cpu_tdp}W TDP).",
        )

    # PCIe 3.0 x8 Bandwidth Advisory (with safe handling of canonical vs product spec drift)
    cpu_pcie = _get(cpu, "pcie_gen")
    mobo_pcie = _get(mobo, "pcie_gen")
    gpu_lanes = _get(gpu, "pcie_lanes")
    canon_gpu_lanes = _get(canonical_gpu, "pcie_lanes") if canonical_gpu is not None else None
    if cpu_pcie is None or mobo_pcie is None or (gpu_lanes is None and canon_gpu_lanes is None):
        _record(
            checks,
            "pcie_bandwidth_x8",
            "Platform",
            STATUS_UNVERIFIED,
            f"Unverified PCIe Link Negotiation: PCIe generation or lane width missing for {cpu_name}, {mobo_name}, or {gpu_name}.",
        )
    else:
        effective_system_pcie = min(int(cpu_pcie), int(mobo_pcie))
        if gpu_lanes is not None and int(gpu_lanes) <= 8 and effective_system_pcie <= 3:
            _record(
                checks,
                "pcie_bandwidth_x8",
                "Platform",
                STATUS_WARNING,
                f"PCIe 3.0 x8 Bandwidth Throttling: {gpu_name} is physically wired with only x8 lanes. "
                f"Running on a PCIe {effective_system_pcie}.0 platform ({cpu_name} / {mobo_name}) restricts bus throughput to ~7.8 GB/s. "
                "Expect a 6% to 12% framerate degradation and micro-stutters when texture memory is saturated.",
                {"effective_system_pcie": effective_system_pcie, "gpu_lanes": int(gpu_lanes)},
            )
        elif (
            gpu_lanes is not None
            and canon_gpu_lanes is not None
            and int(gpu_lanes) != int(canon_gpu_lanes)
            and min(int(gpu_lanes), int(canon_gpu_lanes)) <= 8
            and effective_system_pcie <= 3
        ):
            # Safely handle conflicting product vs canonical pcie_lanes spec without rewriting fixtures
            _record(
                checks,
                "pcie_bandwidth_x8",
                "Platform",
                STATUS_WARNING,
                f"PCIe Bandwidth Spec Notice: {gpu_name} lists x{gpu_lanes} lanes while canonical model lists x{canon_gpu_lanes} lanes; "
                f"on PCIe {effective_system_pcie}.0 ({cpu_name} / {mobo_name}), an x8-wired card may experience bandwidth throttling.",
                {"effective_system_pcie": effective_system_pcie, "product_lanes": int(gpu_lanes), "canonical_lanes": int(canon_gpu_lanes)},
            )
        else:
            _record(
                checks,
                "pcie_bandwidth_x8",
                "Platform",
                STATUS_COMPATIBLE,
                f"PCIe {effective_system_pcie}.0 x{gpu_lanes or canon_gpu_lanes} interface link.",
                {"effective_system_pcie": effective_system_pcie, "gpu_lanes": gpu_lanes or canon_gpu_lanes},
            )

    # Front-Panel USB-C Header Advisory
    case_usb_c = _get(case, "has_front_usb_c")
    mobo_usb_c = _get(mobo, "has_usb_c_header")
    if case_usb_c is None or mobo_usb_c is None:
        _record(
            checks,
            "case_mobo_usbc_header",
            "Platform",
            STATUS_UNVERIFIED,
            f"Unverified Front USB-C Header: Missing USB-C header capability for {case_name} or {mobo_name}.",
        )
    elif bool(case_usb_c) and not bool(mobo_usb_c):
        _record(
            checks,
            "case_mobo_usbc_header",
            "Platform",
            STATUS_WARNING,
            f"Front Panel Header Alert: {case_name} features a front-panel USB Type-C port, but {mobo_name} lacks an internal USB 3.2 Type-E header. "
            "The front USB-C port will be non-functional without a separate PCIe/19-pin adapter.",
        )
    else:
        _record(
            checks,
            "case_mobo_usbc_header",
            "Platform",
            STATUS_COMPATIBLE,
            "Front-panel USB-C / header compatibility satisfied.",
        )

    # Aggregate results
    incompatible_findings = [c for c in checks if c["status"] == STATUS_INCOMPATIBLE]
    unverified_findings = [c for c in checks if c["status"] == STATUS_UNVERIFIED]
    warning_findings = [c for c in checks if c["status"] == STATUS_WARNING]

    if incompatible_findings:
        overall_status = STATUS_INCOMPATIBLE
    elif unverified_findings:
        overall_status = STATUS_UNVERIFIED
    elif warning_findings:
        overall_status = STATUS_WARNING
    else:
        overall_status = STATUS_COMPATIBLE

    warnings = [
        c["message"]
        for c in checks
        if c["status"] in (STATUS_INCOMPATIBLE, STATUS_WARNING, STATUS_UNVERIFIED)
    ]

    return {
        "overall_status": overall_status,
        "is_compatible": len(incompatible_findings) == 0 and len(unverified_findings) == 0,
        "has_known_incompatibility": len(incompatible_findings) > 0,
        "has_unverified": len(unverified_findings) > 0,
        "has_warnings": len(warning_findings) > 0,
        "counts": {
            "total": len(checks),
            "compatible": sum(1 for c in checks if c["status"] == STATUS_COMPATIBLE),
            "warning": len(warning_findings),
            "unverified": len(unverified_findings),
            "incompatible": len(incompatible_findings),
        },
        "checks": checks,
        "incompatible_findings": incompatible_findings,
        "warning_findings": warning_findings,
        "unverified_findings": unverified_findings,
        "warnings": warnings,
        "clearance_metrics": clearance["metrics"],
    }
