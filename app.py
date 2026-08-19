import itertools
import math
import streamlit as st

# ============================================================
# PAGE CONFIG
# ============================================================
APP_VERSION = "V0.1.3.1"
APP_NAME = "Carton A10 Partition Layout Optimizer"
MODULE_NAME = "NPI Packaging Engineering Toolkit • Module 03"

st.set_page_config(
    page_title=APP_NAME,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# FIXED CARTON / PARTITION CONFIGURATION
# ============================================================
# Master Carton A10
CARTON_OD_L = 602.0
CARTON_OD_W = 414.0
CARTON_OD_H = 270.0

CARTON_L = 592.0
CARTON_W = 404.0
CARTON_H = 255.0

CARTON_CX = CARTON_L / 2.0
CARTON_CY = CARTON_W / 2.0

# Standard paper pad used by the current A10 packing system
PAD_L = 574.0
PAD_W = 394.0
PAD_T = 3.0

# Drawing-audited A10 partition groove CENTERLINES in CARTON coordinates.
#
# Coordinate convention used by the solver:
#   X = along Carton A10 internal length 592 mm (uses finished PARTITION ...x584)
#   Y = along Carton A10 internal width  404 mm (uses finished PARTITION ...x393)
#
# Finished 584-mm partition is centered in Carton ID 592 -> 4.0 mm sheet offset/side.
# Finished 393-mm partition is centered in Carton ID 404 -> 5.5 mm sheet offset/side.
# Groove width in all audited drawings = 5 mm.
#
# 111x584 drawing: 14 mm edge clearance + 5 mm groove + 40 mm clear gap
# between groove edges -> 140 mm centerline pitch.
GROOVE_X_111 = [16.0, 156.0, 296.0, 436.0, 576.0]

# 111x393 drawing: 14 mm edge clearance, 5 mm groove, 40 mm clear gap
# -> 45 mm centerline pitch.
GROOVE_Y_111 = [22.0, 67.0, 112.0, 157.0, 202.0, 247.0, 292.0, 337.0, 382.0]

# 225x584 drawing: five 5-mm grooves with 120 mm CLEAR gaps.
# Overall 584 mm closes symmetrically at 39.5 mm clear margin/side
# (drawing nominally labels the side margin as 40 mm), therefore
# groove-center pitch = 125 mm and the Carton-coordinate centers are below.
GROOVE_X_225 = [46.0, 171.0, 296.0, 421.0, 546.0]

# 225x393 uses the same 5-mm groove / 40-mm clear-gap geometry as 111x393.
GROOVE_Y_225 = [22.0, 67.0, 112.0, 157.0, 202.0, 247.0, 292.0, 337.0, 382.0]

# Geometry/cache revision guard.
# IMPORTANT: Streamlit cache keys do not automatically include global constants used
# inside a cached function.  Therefore the audited groove geometry is serialized and
# passed into the solver as an explicit argument.  Any future groove-coordinate change
# automatically produces a new cache key and prevents stale layouts from being reused.
def _geometry_signature():
    def pack(values):
        return ",".join(f"{v:.6f}" for v in values)

    return "|".join([
        "A10_DRAWING_AUDIT_R1",
        f"111X:{pack(GROOVE_X_111)}",
        f"111Y:{pack(GROOVE_Y_111)}",
        f"225X:{pack(GROOVE_X_225)}",
        f"225Y:{pack(GROOVE_Y_225)}",
    ])


GEOMETRY_SIGNATURE = _geometry_signature()

# Outer usable envelope for the partition system / pad zone.
PARTITION_SYSTEM = {
    111.0: {
        "groove_x": GROOVE_X_111,
        "groove_y": GROOVE_Y_111,
        "x_pad_start": 4.0,
        "x_pad_end": 588.0,
        "y_pad_start": 5.5,
        "y_pad_end": 398.5,
        "layers": 2,
    },
    225.0: {
        "groove_x": GROOVE_X_225,
        "groove_y": GROOVE_Y_225,
        # Finished partition sheet is 584 x 393 mm, centered in A10 ID 592 x 404 mm.
        "x_pad_start": 4.0,
        "x_pad_end": 588.0,
        "y_pad_start": 5.5,
        "y_pad_end": 398.5,
        "layers": 1,
    },
}

# ============================================================
# SMALL UI HELPERS
# ============================================================
def fmt_num(v):
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.1f}"


def badge(text, tone="neutral"):
    palettes = {
        "neutral": ("#0f172a", "#e2e8f0", "#334155"),
        "good": ("#052e16", "#dcfce7", "#16a34a"),
        "warn": ("#422006", "#fef3c7", "#d97706"),
        "info": ("#082f49", "#e0f2fe", "#0284c7"),
        "bad": ("#450a0a", "#fee2e2", "#dc2626"),
    }
    fg, bg, border = palettes[tone]
    return (
        f'<span style="display:inline-block;padding:3px 9px;margin-right:5px;'
        f'border-radius:999px;border:1px solid {border};background:{bg};'
        f'color:{fg};font-size:11px;font-weight:700;">{text}</span>'
    )


# ============================================================
# SIDEBAR INPUTS
# ============================================================
st.sidebar.header("📐 1. Product Dimension (mm)")
p_w = st.sidebar.number_input(
    "ความกว้างชิ้นงาน (Width - W)",
    min_value=1.0,
    value=135.0,
    step=1.0,
)
p_l = st.sidebar.number_input(
    "ความยาวชิ้นงาน (Length - L)",
    min_value=1.0,
    value=160.0,
    step=1.0,
)
p_h = st.sidebar.number_input(
    "ความหนา / ความสูงชิ้นงาน (Height - H)",
    min_value=1.0,
    value=30.0,
    step=1.0,
)

st.sidebar.header("🧭 2. Allowed Product Orientation")
st.sidebar.checkbox(
    "H-Up — การวางปกติ (Recommended Default)",
    value=True,
    disabled=True,
    help="H-Up ถูกเปิดใช้งานเสมอเป็น Normal Reference",
)
allow_l_up = st.sidebar.checkbox(
    "L-Up — อนุญาตให้หันด้าน L ขึ้น",
    value=False,
    help="เปิดเมื่อ Product / Customer / Label / Handling requirement อนุญาตจริง",
)
allow_w_up = st.sidebar.checkbox(
    "W-Up — อนุญาตให้หันด้าน W ขึ้น",
    value=False,
    help="เปิดเมื่อ Product / Customer / Label / Handling requirement อนุญาตจริง",
)

if allow_l_up or allow_w_up:
    st.sidebar.warning(
        "⚠️ Non-normal orientation ถูกเปิดใช้งาน กรุณายืนยัน Product / Customer / Label / Handling requirement ก่อนนำไปใช้จริง"
    )

st.sidebar.header("🛡️ 3. ESD Bag / Slot Allowance")
esd_allowance_per_side = st.sidebar.slider(
    "ESD Bag Allowance per Side (mm)",
    min_value=0.0,
    max_value=15.0,
    value=5.0,
    step=0.5,
    help=(
        "กรอกเป็นระยะเผื่อต่อด้านของ ESD bag / packed envelope. "
        "Company standard ปัจจุบัน = 5 mm/side"
    ),
)

# The solver works with TOTAL dimensional allowance.  Example: 5 mm/side
# means +10 mm to W, +10 mm to L and +10 mm to H.
total_esd_allowance = esd_allowance_per_side * 2.0

effective_product_w = p_w + total_esd_allowance
effective_product_l = p_l + total_esd_allowance
effective_product_h = p_h + total_esd_allowance

st.sidebar.caption(
    "Company standard: 5 mm/side → +10 mm per dimension. "
    "กรอก Product Dimension เป็น PURE product size — ห้ามบวก ESD allowance ล่วงหน้า"
)
st.sidebar.info(
    f"Packed envelope = {fmt_num(effective_product_w)} × "
    f"{fmt_num(effective_product_l)} × {fmt_num(effective_product_h)} mm"
)

st.sidebar.header("📦 4. Slot Capacity Mode")
packing_mode = st.sidebar.radio(
    "รูปแบบการจัดชิ้นงานต่อ 1 slot",
    options=[
        "1) Standard 1 PC/Slot",
        "2) Multi-Fit: Side-by-Side",
        "3) Stack-Fit: Side-by-Side & Stacked",
    ],
)

if "Standard 1 PC/Slot" in packing_mode:
    max_pcs_axis = 1
    st.sidebar.caption("Standard mode: Max Pcs / Axis = 1 (fixed)")
else:
    max_pcs_axis = st.sidebar.slider(
        "Max Pcs / Axis ใน 1 slot",
        min_value=1,
        max_value=4,
        value=2,
        help="ใช้กับ Multi-Fit / Stack-Fit เพื่อจำกัดจำนวนชิ้นงานต่อแกนใน 1 slot",
    )

st.sidebar.header("🏗️ 5. Partition Structural Guardrail")
max_slot_span = st.sidebar.number_input(
    "Baseline Unsupported Slot Span (mm)",
    min_value=50.0,
    value=160.0,
    step=10.0,
    help=(
        "Geometry-based engineering screening สำหรับ span ระหว่าง partition ที่ตัดกัน "
        "ไม่ใช่การคำนวณ BCT / ECT strength"
    ),
)

span_mode = st.sidebar.selectbox(
    "Span Guardrail Mode",
    options=[
        "Dynamic — Recommended",
        "Strict",
    ],
    index=0,
    help=(
        "Dynamic จะรักษา Baseline เป็นหลัก และถ้า groove จริงของ A10 บังคับให้ span ขั้นต่ำที่ใส่สินค้าได้ใหญ่กว่า Baseline "
        "ระบบจะผ่อนเฉพาะเท่าที่จำเป็นถึง groove-compatible span นั้น. Multi-Fit / Stack-Fit ยังคง scale ตาม Max Pcs / Axis. "
        "Strict = Baseline เป็น hard limit; ถ้า groove ที่จำเป็นเกิน Baseline ระบบจะไม่ยอมรับ layout"
    ),
)

st.sidebar.info(
    "✅ V0.1.3: Drawing-Corrected Groove Geometry + Groove-Aware Span Guardrail + ESD Packed Envelope + Topology Validation"
)

st.sidebar.caption(
    "Drawing audit: 111×584 pitch 140 mm • 111/225×393 pitch 45 mm • "
    "225×584 pitch 125 mm. Groove coordinates are stored as centerlines in Carton A10 coordinates."
)

# ============================================================
# ORIENTATION ENGINE — deterministic and axis-aware
# ============================================================
def build_orientations(pw, pl, ph, allow_l, allow_w):
    """Return deterministic 6-way orientations while keeping original axis identity."""
    return [
        {
            "orientation_id": "H_WL",
            "up_axis": "H",
            "flat_w": pw,
            "flat_l": pl,
            "vert_h": ph,
            "floor_axis_1": "W",
            "floor_axis_2": "L",
            "allowed": True,
            "normal": True,
            "priority": 3,
        },
        {
            "orientation_id": "H_LW",
            "up_axis": "H",
            "flat_w": pl,
            "flat_l": pw,
            "vert_h": ph,
            "floor_axis_1": "L",
            "floor_axis_2": "W",
            "allowed": True,
            "normal": True,
            "priority": 3,
        },
        {
            "orientation_id": "L_WH",
            "up_axis": "L",
            "flat_w": pw,
            "flat_l": ph,
            "vert_h": pl,
            "floor_axis_1": "W",
            "floor_axis_2": "H",
            "allowed": allow_l,
            "normal": False,
            "priority": 1,
        },
        {
            "orientation_id": "L_HW",
            "up_axis": "L",
            "flat_w": ph,
            "flat_l": pw,
            "vert_h": pl,
            "floor_axis_1": "H",
            "floor_axis_2": "W",
            "allowed": allow_l,
            "normal": False,
            "priority": 1,
        },
        {
            "orientation_id": "W_LH",
            "up_axis": "W",
            "flat_w": pl,
            "flat_l": ph,
            "vert_h": pw,
            "floor_axis_1": "L",
            "floor_axis_2": "H",
            "allowed": allow_w,
            "normal": False,
            "priority": 1,
        },
        {
            "orientation_id": "W_HL",
            "up_axis": "W",
            "flat_w": ph,
            "flat_l": pl,
            "vert_h": pw,
            "floor_axis_1": "H",
            "floor_axis_2": "L",
            "allowed": allow_w,
            "normal": False,
            "priority": 1,
        },
    ]


def orientation_label(orient):
    return (
        f"{fmt_num(orient['flat_w'])} × {fmt_num(orient['flat_l'])} × {fmt_num(orient['vert_h'])} mm"
    )


# ============================================================
# PARTITION / TOPOLOGY HELPERS
# ============================================================
def select_partition_system(vertical_h, clr):
    if vertical_h + clr <= 111.0:
        return 111.0, PARTITION_SYSTEM[111.0]
    if vertical_h + clr <= 225.0:
        return 225.0, PARTITION_SYSTEM[225.0]
    return None, None


def generate_partition_subsets(grooves):
    """
    A valid candidate always retains the first and last partition sheets.
    Inner groove sheets may be selected or omitted.
    """
    first = grooves[0]
    last = grooves[-1]
    inner = grooves[1:-1]
    subsets = []
    for r in range(len(inner) + 1):
        for comb in itertools.combinations(inner, r):
            subsets.append([first] + list(comb) + [last])
    return subsets


def topology_validation(x_dividers, y_dividers):
    """
    Engineering topology rule for A10 partition structure.

    - partition sheets must exist in BOTH directions
    - at least one actual cross-intersection network must exist
    - reject a single giant 1x1 cell
    - allow 1xN or Nx1 grids when N >= 2 because both divider families still interlock
    """
    if len(x_dividers) < 2 or len(y_dividers) < 2:
        return False, "Missing one partition direction"

    cells_x = len(x_dividers) - 1
    cells_y = len(y_dividers) - 1
    total_cells = cells_x * cells_y
    intersections = len(x_dividers) * len(y_dividers)

    if total_cells < 2:
        return False, "Single giant cell is not accepted"

    if intersections < 6:
        return False, "Insufficient interlocked grid intersections"

    return True, "Interlocked grid"


def groove_span_catalog(grooves):
    """Return all unique positive spans that can actually be formed by A10 groove positions."""
    spans = set()
    for i in range(len(grooves)):
        for j in range(i + 1, len(grooves)):
            span = round(grooves[j] - grooves[i], 6)
            if span > 0:
                spans.add(span)
    return sorted(spans)


def minimum_groove_compatible_span(grooves, required_span):
    """Smallest real groove-to-groove span that can physically fit the required packed footprint."""
    for span in groove_span_catalog(grooves):
        if span + 1e-9 >= required_span:
            return span
    return None


def effective_span_limits(
    target_l,
    target_w,
    mode,
    max_pcs_per_axis,
    baseline,
    guardrail_mode,
    groove_x,
    groove_y,
):
    """
    Return effective X/Y maximum span limits plus minimum groove-compatible spans.

    X spans are evaluated against product flat-L and Y spans against flat-W.

    Dynamic mode preserves the previous Multi-Fit scaling behavior, but it will
    never reject a product merely because the A10 groove pitch forces the
    smallest feasible slot to be slightly/largely above the baseline. It relaxes
    only as far as the minimum REAL groove-compatible span required by one
    packed product footprint.

    Strict mode treats the user baseline as a true hard maximum span.
    """
    min_groove_x = minimum_groove_compatible_span(groove_x, target_l)
    min_groove_y = minimum_groove_compatible_span(groove_y, target_w)

    if "Standard 1 PC/Slot" in mode:
        pcs_factor = 1.0
    else:
        pcs_factor = float(max_pcs_per_axis)

    if guardrail_mode.startswith("Dynamic"):
        # Keep V0.1.1 Multi-Fit / Stack-Fit scaling, then add groove awareness.
        eff_x = max(baseline, target_l * pcs_factor)
        eff_y = max(baseline, target_w * pcs_factor)

        # V0.1.2+ fix: discrete A10 groove geometry may make the
        # minimum feasible slot larger than the numerical baseline/footprint.
        if min_groove_x is not None:
            eff_x = max(eff_x, min_groove_x)
        if min_groove_y is not None:
            eff_y = max(eff_y, min_groove_y)
    else:
        # Strict = real hard limit. Product fit and groove geometry are not
        # allowed to silently expand the user's engineering limit.
        eff_x = baseline
        eff_y = baseline

    return eff_x, eff_y, min_groove_x, min_groove_y


def span_stats(bounds):
    spans = [bounds[i + 1] - bounds[i] for i in range(len(bounds) - 1)]
    if not spans:
        return 0.0, 0.0, 0.0
    return min(spans), max(spans), (max(spans) - min(spans))


# ============================================================
# SOLVER
# ============================================================
@st.cache_data(show_spinner=False)
def solve_a10_partition_layouts(
    pw,
    pl,
    ph,
    clr,
    mode,
    max_pcs_per_axis,
    max_span_limit,
    guardrail_mode,
    allow_l,
    allow_w,
    geometry_signature,
):
    # geometry_signature is intentionally consumed only as a cache-key dependency.
    # The solver still reads the canonical audited geometry from PARTITION_SYSTEM.
    _ = geometry_signature
    orientations = build_orientations(pw, pl, ph, allow_l, allow_w)
    options = []
    rejected_topology = 0
    rejected_span = 0
    rejected_fit = 0
    span_requirements = []

    for orient in orientations:
        ew = orient["flat_w"]
        el = orient["flat_l"]
        eh = orient["vert_h"]

        part_height, system = select_partition_system(eh, clr)
        if system is None:
            continue

        layers = system["layers"]
        groove_x = system["groove_x"]
        groove_y = system["groove_y"]

        # clr is TOTAL packed-envelope allowance (2 × per-side ESD allowance).
        target_w = ew + clr
        target_l = el + clr
        target_h = eh + clr

        eff_span_x, eff_span_y, min_groove_span_x, min_groove_span_y = effective_span_limits(
            target_l,
            target_w,
            mode,
            max_pcs_per_axis,
            max_span_limit,
            guardrail_mode,
            groove_x,
            groove_y,
        )

        span_requirements.append(
            {
                "orientation_id": orient["orientation_id"],
                "up_axis": orient["up_axis"],
                "allowed": orient["allowed"],
                "part_height": part_height,
                "target_l": target_l,
                "target_w": target_w,
                "min_groove_span_x": min_groove_span_x,
                "min_groove_span_y": min_groove_span_y,
                "eff_span_x": eff_span_x,
                "eff_span_y": eff_span_y,
            }
        )

        subsets_x = generate_partition_subsets(groove_x)
        subsets_y = generate_partition_subsets(groove_y)

        for x_dividers in subsets_x:
            for y_dividers in subsets_y:
                topo_ok, topo_note = topology_validation(x_dividers, y_dividers)
                if not topo_ok:
                    rejected_topology += 1
                    continue

                x_spans = [x_dividers[i + 1] - x_dividers[i] for i in range(len(x_dividers) - 1)]
                y_spans = [y_dividers[i + 1] - y_dividers[i] for i in range(len(y_dividers) - 1)]

                # Every cell must physically fit at least one product footprint.
                if any(span < target_l for span in x_spans) or any(span < target_w for span in y_spans):
                    rejected_fit += 1
                    continue

                # V0.1: span guardrail is now evaluated for every packing mode.
                if any(span > eff_span_x for span in x_spans) or any(span > eff_span_y for span in y_spans):
                    rejected_span += 1
                    continue

                valid_slots = []

                for i in range(len(x_dividers) - 1):
                    for j in range(len(y_dividers) - 1):
                        slot_x = x_dividers[i + 1] - x_dividers[i]
                        slot_y = y_dividers[j + 1] - y_dividers[j]

                        if "Standard 1 PC/Slot" in mode:
                            qty_x = 1
                            qty_y = 1
                            qty_z = 1
                        else:
                            qty_x = min(max_pcs_per_axis, max(1, int(slot_x // target_l)))
                            qty_y = min(max_pcs_per_axis, max(1, int(slot_y // target_w)))

                            if "Stack-Fit" in mode:
                                # Each stacked product has its own ESD packed envelope.
                                qty_z = max(1, int(part_height // target_h))
                            else:
                                qty_z = 1

                        pcs_slot = qty_x * qty_y * qty_z
                        valid_slots.append(
                            {
                                "col_idx": i,
                                "row_idx": j,
                                "x_start": x_dividers[i],
                                "x_end": x_dividers[i + 1],
                                "y_start": y_dividers[j],
                                "y_end": y_dividers[j + 1],
                                "qty_x": qty_x,
                                "qty_y": qty_y,
                                "qty_z": qty_z,
                                "pcs_per_slot": pcs_slot,
                            }
                        )

                if not valid_slots:
                    continue

                qty_layer = sum(s["qty_x"] * s["qty_y"] for s in valid_slots)
                qty_per_partition_layer = sum(s["pcs_per_slot"] for s in valid_slots)
                qty_box = qty_per_partition_layer * layers
                base_slots_layer = len(valid_slots)

                min_x_span, max_x_span, var_x = span_stats(x_dividers)
                min_y_span, max_y_span, var_y = span_stats(y_dividers)
                span_ratio = max(
                    max_x_span / eff_span_x if eff_span_x > 0 else 999,
                    max_y_span / eff_span_y if eff_span_y > 0 else 999,
                )
                slot_variation = var_x + var_y

                grid_cx = (x_dividers[0] + x_dividers[-1]) / 2.0
                grid_cy = (y_dividers[0] + y_dividers[-1]) / 2.0
                center_offset = abs(grid_cx - CARTON_CX) + abs(grid_cy - CARTON_CY)

                envelope_area = max(
                    1.0,
                    (x_dividers[-1] - x_dividers[0]) * (y_dividers[-1] - y_dividers[0]),
                )
                product_area_layer = qty_layer * ew * el
                area_occupancy = min(100.0, (product_area_layer / envelope_area) * 100.0)

                # Gap is measured from the OUTSIDE of the packed ESD envelope,
                # not from the pure product body.
                top_gap = part_height - (target_h * valid_slots[0]["qty_z"])
                total_used_h = (part_height + PAD_T) * layers + PAD_T
                carton_top_air_gap = CARTON_H - total_used_h

                option = {
                    "orientation_id": orient["orientation_id"],
                    "up_axis": orient["up_axis"],
                    "floor_axis_1": orient["floor_axis_1"],
                    "floor_axis_2": orient["floor_axis_2"],
                    "allowed": orient["allowed"],
                    "normal": orient["normal"],
                    "orientation_priority": orient["priority"],
                    "orient_label": orientation_label(orient),
                    "flat_w": ew,
                    "flat_l": el,
                    "vert_h": eh,
                    "p_w_disp": ew,
                    "p_l_disp": el,
                    "p_h_disp": eh,
                    "target_w": target_w,
                    "target_l": target_l,
                    "target_h": target_h,
                    "esd_total_allowance": clr,
                    "part_height": part_height,
                    "layers": layers,
                    "x_dividers": list(x_dividers),
                    "y_dividers": list(y_dividers),
                    # Backward-friendly aliases for renderer / BOM semantics.
                    "ax": list(x_dividers),
                    "ay": list(y_dividers),
                    "x_bounds": [system["x_pad_start"]] + list(x_dividers) + [system["x_pad_end"]],
                    "y_bounds": [system["y_pad_start"]] + list(y_dividers) + [system["y_pad_end"]],
                    "valid_slots": valid_slots,
                    "base_slots_layer": base_slots_layer,
                    "base_qty_box": base_slots_layer * layers,
                    "qty_layer": qty_layer,
                    "qty_partition_layer": qty_per_partition_layer,
                    "qty_box": qty_box,
                    "total_dividers_per_layer": len(x_dividers) + len(y_dividers),
                    "short_dividers_per_layer": len(x_dividers),
                    "long_dividers_per_layer": len(y_dividers),
                    "topology_note": topo_note,
                    "eff_span_x": eff_span_x,
                    "eff_span_y": eff_span_y,
                    "min_groove_span_x": min_groove_span_x,
                    "min_groove_span_y": min_groove_span_y,
                    "max_span_x": max_x_span,
                    "max_span_y": max_y_span,
                    "span_ratio": span_ratio,
                    "slot_variation": slot_variation,
                    "center_offset": center_offset,
                    "area_occupancy": area_occupancy,
                    "top_gap": top_gap,
                    "carton_top_air_gap": carton_top_air_gap,
                }
                options.append(option)

    debug = {
        "rejected_topology": rejected_topology,
        "rejected_span": rejected_span,
        "rejected_fit": rejected_fit,
        "evaluated_valid": len(options),
        "span_requirements": span_requirements,
    }
    return options, debug


# ============================================================
# OPTION RANKING / DEDUPLICATION
# ============================================================
def option_rank(opt):
    """
    Capacity first, then prefer normal orientation on a tie, then structure,
    then lower BOM complexity.
    """
    return (
        opt["qty_box"],
        opt["orientation_priority"],
        -opt["vert_h"],
        opt["qty_layer"],
        -opt["span_ratio"],
        -opt["slot_variation"],
        -opt["total_dividers_per_layer"],
        opt["area_occupancy"],
        -opt["center_offset"],
    )


def dedupe_options(options):
    """Keep meaningful engineering scenarios and remove near-duplicate grids."""
    best_by_key = {}
    for opt in options:
        key = (
            opt["orientation_id"],
            opt["part_height"],
            opt["qty_box"],
            opt["qty_layer"],
            opt["layers"],
            opt["base_slots_layer"],
            opt["short_dividers_per_layer"],
            opt["long_dividers_per_layer"],
        )
        if key not in best_by_key or option_rank(opt) > option_rank(best_by_key[key]):
            best_by_key[key] = opt
    return sorted(best_by_key.values(), key=option_rank, reverse=True)


# ============================================================
# GEOMETRY SYNCHRONIZATION VALIDATION
# ============================================================
def validate_active_dividers_against_grooves(opt, tolerance=0.01):
    """Confirm every active divider lies on an audited available groove centerline."""
    system = PARTITION_SYSTEM[opt["part_height"]]
    problems = []

    def check_axis(axis_name, active_values, available_values):
        for value in active_values:
            nearest = min(available_values, key=lambda g: abs(g - value))
            delta = abs(nearest - value)
            if delta > tolerance:
                problems.append(
                    f"{axis_name} active divider {fmt_num(value)} mm is not on an audited groove "
                    f"(nearest {fmt_num(nearest)} mm, Δ={delta:.3f} mm)."
                )

    check_axis("X", opt["x_dividers"], system["groove_x"])
    check_axis("Y", opt["y_dividers"], system["groove_y"])
    return problems


def option_geometry_is_synchronized(opt, tolerance=0.01):
    return len(validate_active_dividers_against_grooves(opt, tolerance)) == 0


# ============================================================
# SVG TOP VIEW
# ============================================================
def draw_top_view_svg(opt):
    sync_problems = validate_active_dividers_against_grooves(opt)
    if sync_problems:
        raise ValueError("Active partition / groove geometry mismatch: " + " | ".join(sync_problems))

    x_dividers = opt["x_dividers"]
    y_dividers = opt["y_dividers"]
    valid_slots = opt["valid_slots"]

    scale = 1.36
    pad_x = 64
    pad_y = 66

    view_w = CARTON_L * scale + pad_x * 2
    view_h = CARTON_W * scale + pad_y * 2

    system = PARTITION_SYSTEM[opt["part_height"]]
    x_start_pad = system["x_pad_start"]
    x_end_pad = system["x_pad_end"]
    y_start_pad = system["y_pad_start"]
    y_end_pad = system["y_pad_end"]

    svg = (
        f'<svg width="100%" height="auto" viewBox="0 0 {view_w} {view_h}" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#fff;border:2px solid #334155;border-radius:12px;">'
    )

    svg += (
        f'<text x="{view_w/2}" y="28" font-family="system-ui,sans-serif" '
        f'font-size="18" font-weight="700" fill="#0f172a" text-anchor="middle">'
        f'SMART TOP PATTERN — CARTON A10 ({int(CARTON_L)} × {int(CARTON_W)} mm)</text>'
    )

    svg += (
        f'<rect x="{pad_x}" y="{pad_y}" width="{CARTON_L*scale}" height="{CARTON_W*scale}" '
        f'fill="#f8fafc" stroke="#1e293b" stroke-width="4" rx="6" />'
    )

    svg += (
        f'<rect x="{pad_x + x_start_pad*scale}" y="{pad_y + y_start_pad*scale}" '
        f'width="{(x_end_pad-x_start_pad)*scale}" height="{(y_end_pad-y_start_pad)*scale}" '
        f'fill="none" stroke="#94a3b8" stroke-width="1.4" stroke-dasharray="4,4" />'
    )

    groove_x = system["groove_x"]
    groove_y = system["groove_y"]

    # Available groove reference — light green dotted lines.
    for x in groove_x:
        px = pad_x + x * scale
        svg += (
            f'<line x1="{px}" y1="{pad_y+y_start_pad*scale}" x2="{px}" y2="{pad_y+y_end_pad*scale}" '
            f'stroke="#22c55e" stroke-width="1" stroke-dasharray="3,3" opacity="0.65" />'
        )
    for y in groove_y:
        py = pad_y + y * scale
        svg += (
            f'<line x1="{pad_x+x_start_pad*scale}" y1="{py}" x2="{pad_x+x_end_pad*scale}" y2="{py}" '
            f'stroke="#22c55e" stroke-width="1" stroke-dasharray="3,3" opacity="0.65" />'
        )

    # Active partition sheets — red.
    for x in x_dividers:
        px = pad_x + x * scale
        svg += (
            f'<line x1="{px}" y1="{pad_y+y_start_pad*scale}" x2="{px}" y2="{pad_y+y_end_pad*scale}" '
            f'stroke="#dc2626" stroke-width="4" stroke-linecap="round" />'
        )
    for y in y_dividers:
        py = pad_y + y * scale
        svg += (
            f'<line x1="{pad_x+x_start_pad*scale}" y1="{py}" x2="{pad_x+x_end_pad*scale}" y2="{py}" '
            f'stroke="#dc2626" stroke-width="4" stroke-linecap="round" />'
        )

    draw_w = opt["p_l_disp"] * scale
    draw_h = opt["p_w_disp"] * scale
    env_w = opt["target_l"] * scale
    env_h = opt["target_w"] * scale

    # Product placement in every valid slot.
    for slot in valid_slots:
        slot_w = slot["x_end"] - slot["x_start"]
        slot_h = slot["y_end"] - slot["y_start"]
        step_x = slot_w * scale / slot["qty_x"]
        step_y = slot_h * scale / slot["qty_y"]

        for kx in range(slot["qty_x"]):
            for ky in range(slot["qty_y"]):
                cx = pad_x + slot["x_start"] * scale + kx * step_x + step_x / 2
                cy = pad_y + slot["y_start"] * scale + ky * step_y + step_y / 2
                # ESD packed envelope (blue dashed) surrounds the pure product.
                erx = cx - env_w / 2
                ery = cy - env_h / 2
                svg += (
                    f'<rect x="{erx+1}" y="{ery+1}" width="{max(2,env_w-2)}" height="{max(2,env_h-2)}" '
                    f'fill="#dbeafe" fill-opacity="0.28" stroke="#2563eb" stroke-width="1" stroke-dasharray="4,3" rx="4" />'
                )

                rx = cx - draw_w / 2
                ry = cy - draw_h / 2
                svg += (
                    f'<rect x="{rx+1}" y="{ry+1}" width="{max(2,draw_w-2)}" height="{max(2,draw_h-2)}" '
                    f'fill="#fed7aa" stroke="#ea580c" stroke-width="1.25" rx="3" />'
                )
                if slot["qty_x"] * slot["qty_y"] <= 4 or (kx == 0 and ky == 0):
                    txt = "Product" if slot["qty_z"] == 1 else f"Product ×{slot['qty_z']}"
                    svg += (
                        f'<text x="{cx}" y="{cy+3}" font-family="system-ui,sans-serif" font-size="9" '
                        f'font-weight="700" fill="#7c2d12" text-anchor="middle">{txt}</text>'
                    )

    svg += (
        f'<text x="{view_w/2}" y="{view_h-14}" font-family="system-ui,sans-serif" font-size="11" '
        f'fill="#475569" text-anchor="middle">Red = Active Partition • Green dotted = Available A10 Groove • Blue dashed = ESD Packed Envelope</text>'
    )
    svg += '</svg>'
    return svg


# ============================================================
# SVG SIDE SECTION
# ============================================================
def draw_side_view_svg(opt):
    scale_x = 1.34
    scale_y = 1.75
    pad_x = 64
    pad_y = 65

    view_w = CARTON_L * scale_x + pad_x * 2
    view_h = CARTON_H * scale_y + pad_y * 2

    box_h = CARTON_H * scale_y
    part_h_px = opt["part_height"] * scale_y
    prod_h_px = opt["p_h_disp"] * scale_y
    env_h_px = opt["target_h"] * scale_y
    pad_t_px = PAD_T * scale_y

    system = PARTITION_SYSTEM[opt["part_height"]]
    x_start_pad = system["x_pad_start"]
    x_end_pad = system["x_pad_end"]
    envelope_w = x_end_pad - x_start_pad

    svg = (
        f'<svg width="100%" height="auto" viewBox="0 0 {view_w} {view_h}" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#fff;border:2px solid #334155;border-radius:12px;">'
    )

    svg += (
        f'<text x="{view_w/2}" y="28" font-family="system-ui,sans-serif" font-size="18" '
        f'font-weight="700" fill="#0f172a" text-anchor="middle">SIDE SECTION — CARTON A10 HEIGHT {int(CARTON_H)} mm</text>'
    )

    svg += (
        f'<rect x="{pad_x}" y="{pad_y}" width="{CARTON_L*scale_x}" height="{box_h}" '
        f'fill="#f8fafc" stroke="#1e293b" stroke-width="4" rx="4" />'
    )

    # Draw partition levels, pads and representative product projection.
    for layer_idx in range(opt["layers"]):
        level_bottom = pad_y + box_h - layer_idx * (part_h_px + pad_t_px) - pad_t_px

        svg += (
            f'<rect x="{pad_x+x_start_pad*scale_x}" y="{level_bottom}" '
            f'width="{envelope_w*scale_x}" height="{pad_t_px}" fill="#cbd5e1" stroke="#94a3b8" />'
        )

        partition_top = level_bottom - part_h_px
        for x in opt["x_dividers"]:
            px = pad_x + x * scale_x
            svg += (
                f'<line x1="{px}" y1="{level_bottom}" x2="{px}" y2="{partition_top}" '
                f'stroke="#dc2626" stroke-width="3" />'
            )

        # Use the first row as a representative projection for each column.
        for col_idx in range(len(opt["x_dividers"]) - 1):
            matching_slot = next(
                (s for s in opt["valid_slots"] if s["col_idx"] == col_idx and s["row_idx"] == 0),
                None,
            )
            if matching_slot is None:
                continue

            slot_left = opt["x_dividers"][col_idx]
            slot_right = opt["x_dividers"][col_idx + 1]
            slot_span = slot_right - slot_left
            qty_x = matching_slot["qty_x"]
            qty_z = matching_slot["qty_z"]
            product_w_px = opt["p_l_disp"] * scale_x
            env_w_px = opt["target_l"] * scale_x
            step_x = slot_span * scale_x / qty_x
            slot_start_px = pad_x + slot_left * scale_x

            for kx in range(qty_x):
                cx = slot_start_px + kx * step_x + step_x / 2
                rx = cx - product_w_px / 2
                erx = cx - env_w_px / 2

                for kz in range(qty_z):
                    # Packed envelopes stack against each other; pure product is centered inside each envelope.
                    env_top = level_bottom - env_h_px * (kz + 1)
                    svg += (
                        f'<rect x="{erx+1}" y="{env_top+1}" width="{max(2,env_w_px-2)}" '
                        f'height="{max(2,env_h_px-2)}" fill="#dbeafe" fill-opacity="0.28" '
                        f'stroke="#2563eb" stroke-width="1" stroke-dasharray="4,3" rx="3" />'
                    )

                    ry = env_top + (env_h_px - prod_h_px) / 2.0
                    svg += (
                        f'<rect x="{rx+1}" y="{ry+1}" width="{max(2,product_w_px-2)}" '
                        f'height="{max(2,prod_h_px-2)}" fill="#fed7aa" stroke="#ea580c" stroke-width="1.2" rx="3" />'
                    )

        # Show product-to-partition gap on the last visible column.
        if opt["top_gap"] > 0:
            gx = pad_x + (x_end_pad - 25) * scale_x
            product_top = level_bottom - opt["target_h"] * opt["valid_slots"][0]["qty_z"] * scale_y
            svg += (
                f'<line x1="{gx}" y1="{product_top}" x2="{gx}" y2="{partition_top}" '
                f'stroke="#2563eb" stroke-width="1.4" stroke-dasharray="3,3" />'
            )
            svg += (
                f'<text x="{gx+5}" y="{(product_top+partition_top)/2}" font-family="system-ui,sans-serif" '
                f'font-size="10" font-weight="700" fill="#2563eb">Slot Top Gap: {fmt_num(opt["top_gap"])} mm</text>'
            )

    # Top pad
    top_pad_y = pad_y + box_h - opt["layers"] * (part_h_px + pad_t_px) - pad_t_px
    svg += (
        f'<rect x="{pad_x+x_start_pad*scale_x}" y="{top_pad_y}" width="{envelope_w*scale_x}" '
        f'height="{pad_t_px}" fill="#cbd5e1" stroke="#94a3b8" />'
    )

    if opt["carton_top_air_gap"] > 0:
        gap_px = opt["carton_top_air_gap"] * scale_y
        svg += (
            f'<rect x="{pad_x+x_start_pad*scale_x}" y="{pad_y}" width="{envelope_w*scale_x}" height="{gap_px}" '
            f'fill="#f1f5f9" opacity="0.7" stroke="#94a3b8" stroke-dasharray="4,4" />'
        )
        svg += (
            f'<text x="{view_w/2}" y="{pad_y+gap_px/2+4}" font-family="system-ui,sans-serif" font-size="11" '
            f'font-weight="700" fill="#64748b" text-anchor="middle">Carton Top Air Gap: {fmt_num(opt["carton_top_air_gap"])} mm</text>'
        )

    svg += '</svg>'
    return svg


# ============================================================
# BOM
# ============================================================
def build_bom(opt):
    layers = opt["layers"]
    paper_pads = layers + 1
    htxt = "111" if opt["part_height"] == 111.0 else "225"

    return [
        {
            "name": "Master Carton A10",
            "qty": "1 Pc",
            "spec": f"OD {fmt_num(CARTON_OD_L)}×{fmt_num(CARTON_OD_W)}×{fmt_num(CARTON_OD_H)} mm | ID {fmt_num(CARTON_L)}×{fmt_num(CARTON_W)}×{fmt_num(CARTON_H)} mm",
        },
        {
            "name": f"Short Partition — PARTITION {htxt}×393",
            "qty": f"{opt['short_dividers_per_layer'] * layers} Pcs",
            "spec": f"{opt['short_dividers_per_layer']} sheet(s) / partition layer × {layers} layer(s)",
        },
        {
            "name": f"Long Partition — PARTITION {htxt}×584",
            "qty": f"{opt['long_dividers_per_layer'] * layers} Pcs",
            "spec": f"{opt['long_dividers_per_layer']} sheet(s) / partition layer × {layers} layer(s)",
        },
        {
            "name": "Corrugated Paper Pad",
            "qty": f"{paper_pads} Pcs",
            "spec": f"{fmt_num(PAD_W)} × {fmt_num(PAD_L)} mm",
        },
        {
            "name": "ESD Anti-Static Bag",
            "qty": f"{opt['qty_box']} Pcs",
            "spec": "1 bag / product unless product packaging specification defines otherwise",
        },
    ]


def render_bom(opt):
    for item in build_bom(opt):
        st.markdown(
            f"""
            <div style="background:#f8fafc;border-left:5px solid #334155;padding:10px 12px;
                        border-radius:7px;margin:0 0 8px 0;box-shadow:0 1px 2px rgba(0,0,0,.05);">
              <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;">
                <div>
                  <div style="font-weight:800;font-size:14px;color:#0f172a;">{item['name']}</div>
                  <div style="font-size:11px;color:#64748b;">{item['spec']}</div>
                </div>
                <div style="white-space:nowrap;background:#1e293b;color:white;padding:4px 10px;
                            border-radius:999px;font-weight:800;font-size:12px;">{item['qty']}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# RESULT RENDERER
# ============================================================
def render_result(opt, title, status_tone="good", comparison_text=None):
    icon = "✅" if status_tone == "good" else "⚠️"
    st.subheader(f"{icon} {title}")

    up_tone = "good" if opt["up_axis"] == "H" else "warn"
    status_badges = (
        badge(f"{opt['up_axis']}-Up", up_tone)
        + badge(f"Partition {int(opt['part_height'])} mm", "info")
        + badge(opt["topology_note"], "good")
    )
    if opt["up_axis"] != "H":
        status_badges += badge("Non-normal orientation", "warn")
    st.markdown(status_badges, unsafe_allow_html=True)

    if opt["up_axis"] == "H":
        st.success(f"Normal orientation: **{opt['orient_label']}**")
    else:
        st.warning(f"Non-normal orientation: **{opt['orient_label']}**")

    if comparison_text:
        st.caption(comparison_text)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Products / Layer", f"{opt['qty_layer']} pcs")
    c2.metric("Packing Layers", f"{opt['layers']}")
    c3.metric("Total Capacity", f"{opt['qty_box']} pcs/A10")
    c4.metric("Base Slots / Layer", f"{opt['base_slots_layer']}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Partition Height", f"{int(opt['part_height'])} mm")
    c6.metric("Slot Top Gap", f"{fmt_num(opt['top_gap'])} mm")
    c7.metric("Product Area Occupancy", f"{opt['area_occupancy']:.1f}%")
    c8.metric("Partition Sheets / Layer", f"{opt['total_dividers_per_layer']}")

    st.caption(
        f"Packed orientation envelope: {fmt_num(opt['target_w'])} × {fmt_num(opt['target_l'])} × {fmt_num(opt['target_h'])} mm • "
        f"Grid: {len(opt['x_dividers'])-1} × {len(opt['y_dividers'])-1} cells • "
        f"Max span X/Y: {fmt_num(opt['max_span_x'])} / {fmt_num(opt['max_span_y'])} mm • "
        f"Effective guardrail X/Y: {fmt_num(opt['eff_span_x'])} / {fmt_num(opt['eff_span_y'])} mm • "
        f"Min groove-compatible X/Y: {fmt_num(opt['min_groove_span_x']) if opt['min_groove_span_x'] is not None else 'N/A'} / "
        f"{fmt_num(opt['min_groove_span_y']) if opt['min_groove_span_y'] is not None else 'N/A'} mm"
    )

    top_tab, side_tab, bom_tab = st.tabs(
        ["📐 Smart Top Pattern", "⏳ Side Section", "📋 Packaging BOM"]
    )

    with top_tab:
        sync_problems = validate_active_dividers_against_grooves(opt)
        if sync_problems:
            st.error(
                "Active Partition / Available Groove synchronization failed. "
                "The drawing is intentionally blocked so a misleading layout cannot be shown."
            )
            for problem in sync_problems:
                st.caption(f"• {problem}")
        else:
            st.write(draw_top_view_svg(opt), unsafe_allow_html=True)

    with side_tab:
        st.write(draw_side_view_svg(opt), unsafe_allow_html=True)

    with bom_tab:
        render_bom(opt)


# ============================================================
# RUN SOLVER
# ============================================================
with st.spinner("Evaluating Carton A10 groove-based partition layouts..."):
    options, debug = solve_a10_partition_layouts(
        p_w,
        p_l,
        p_h,
        total_esd_allowance,
        packing_mode,
        max_pcs_axis,
        max_slot_span,
        span_mode,
        allow_l_up,
        allow_w_up,
        GEOMETRY_SIGNATURE,
    )

# Defensive synchronization gate: even if a stale/malformed result somehow reaches
# this point, never rank or render it as a valid engineering option.
geometry_sync_rejected = [o for o in options if not option_geometry_is_synchronized(o)]
options = [o for o in options if option_geometry_is_synchronized(o)]
debug["geometry_sync_rejected"] = len(geometry_sync_rejected)
debug["geometry_signature"] = GEOMETRY_SIGNATURE

options = dedupe_options(options)
allowed_options = [o for o in options if o["allowed"]]
locked_options = [o for o in options if not o["allowed"]]
h_options = [o for o in options if o["up_axis"] == "H"]

best_h = max(h_options, key=option_rank) if h_options else None
best_allowed = max(allowed_options, key=option_rank) if allowed_options else None
best_locked = max(locked_options, key=option_rank) if locked_options else None

# ============================================================
# HEADER / WORKING CONDITION
# ============================================================
st.title("📦 Auto-Select Partition Layout Design with Carton A10")
st.caption(
    f"{APP_VERSION} • {MODULE_NAME} — Solver Cache / Groove Sync Fix + Drawing-Corrected Geometry + Groove-Aware Span Guardrail + ESD Packed-Envelope + Topology Validation"
)
st.caption(
    "Geometry Sync Guard: active red partition lines are validated against the current audited green groove centerlines before ranking/rendering."
)

st.subheader("📦 Carton A10 Working Condition")
wc1, wc2, wc3, wc4 = st.columns(4)
wc1.metric("Carton A10 ID", f"{int(CARTON_L)} × {int(CARTON_W)} × {int(CARTON_H)} mm")
wc2.metric("Pure Product", f"{fmt_num(p_w)} × {fmt_num(p_l)} × {fmt_num(p_h)} mm")
wc3.metric("ESD Allowance", f"{fmt_num(esd_allowance_per_side)} mm / side")
wc4.metric("Valid Layouts", f"{len(options)}")

st.info(
    f"**Effective Packed Envelope:** {fmt_num(effective_product_w)} × "
    f"{fmt_num(effective_product_l)} × {fmt_num(effective_product_h)} mm  "
    f"(Total dimensional allowance = +{fmt_num(total_esd_allowance)} mm)"
)

allowed_txt = ["H-Up"]
if allow_l_up:
    allowed_txt.append("L-Up")
if allow_w_up:
    allowed_txt.append("W-Up")
st.info("Allowed Product Orientation: **" + ", ".join(allowed_txt) + "**")

st.caption(
    "V0.1.3 uses drawing-audited groove centerlines, PURE Product Dimension, and automatically builds the ESD packed envelope before solving. "
    "The legacy Excel standard-configuration library itself is not yet imported as a database in this version."
)

st.divider()

# ============================================================
# ADAPTIVE RECOMMENDATION UI
# ============================================================
if not options:
    st.error(
        "❌ ไม่พบ layout ที่ผ่าน Product Fit + Partition Topology + Structural Span Guardrail กรุณาตรวจสอบ Product Dimension, ESD Allowance หรือ Span Guardrail"
    )
    if span_mode == "Strict":
        allowed_reqs = [r for r in debug.get("span_requirements", []) if r.get("allowed")]
        if allowed_reqs:
            # Prefer H-Up diagnostic because it is the normal engineering reference.
            diag = next((r for r in allowed_reqs if r.get("up_axis") == "H"), allowed_reqs[0])
            req_x = diag.get("min_groove_span_x")
            req_y = diag.get("min_groove_span_y")
            if req_x is not None and req_y is not None:
                st.info(
                    f"Strict diagnostic — minimum groove-compatible span for {diag['up_axis']}-Up is "
                    f"X/Y = {fmt_num(req_x)} / {fmt_num(req_y)} mm, while Strict baseline = {fmt_num(max_slot_span)} mm."
                )
else:
    if best_allowed is None:
        st.error("❌ ไม่พบ layout ใน orientation ที่อนุญาต")
        if best_locked:
            st.warning(
                f"มี Potential {best_locked['up_axis']}-Up layout ที่ {best_locked['qty_box']} pcs/A10 แต่ orientation นี้ยัง Locked อยู่"
            )
    else:
        # CASE A: allowed non-normal orientation gives a real capacity benefit vs H-Up.
        allowed_alt = None
        if best_h:
            non_h_allowed = [o for o in allowed_options if o["up_axis"] != "H"]
            if non_h_allowed:
                candidate = max(non_h_allowed, key=option_rank)
                if candidate["qty_box"] > best_h["qty_box"]:
                    allowed_alt = candidate

        # CASE B: non-normal is locked but has higher potential capacity.
        locked_benefit = None
        if best_h and best_locked and best_locked["qty_box"] > best_h["qty_box"]:
            locked_benefit = best_locked

        if allowed_alt and best_h:
            delta = allowed_alt["qty_box"] - best_h["qty_box"]
            pct = (delta / best_h["qty_box"] * 100.0) if best_h["qty_box"] else 0.0
            st.warning(
                f"⚠️ Higher Capacity Alternative: **{allowed_alt['up_axis']}-Up = {allowed_alt['qty_box']} pcs/A10** "
                f"vs Normal H-Up {best_h['qty_box']} pcs/A10 (**+{delta} pcs / +{pct:.1f}%**) — engineering confirmation required"
            )
            left, right = st.columns(2)
            with left:
                render_result(best_h, "Normal H-Up Reference", "good")
            with right:
                render_result(
                    allowed_alt,
                    "Higher Capacity Alternative",
                    "warn",
                    comparison_text=f"Capacity benefit vs H-Up: +{delta} pcs/A10 (+{pct:.1f}%)",
                )
        else:
            # One primary result only — avoids duplicated UI when capacity is the same.
            if best_allowed["up_axis"] == "H":
                st.success(
                    f"✅ Recommended: **H-Up / {best_allowed['qty_box']} pcs per A10 / Partition {int(best_allowed['part_height'])} mm / {best_allowed['layers']} packing layer(s)**"
                )
                render_result(best_allowed, "Best & Recommended Layout — Normal H-Up", "good")
            else:
                st.warning(
                    f"⚠️ No valid H-Up layout found under current guardrails. Recommended allowed orientation is {best_allowed['up_axis']}-Up at {best_allowed['qty_box']} pcs/A10."
                )
                render_result(best_allowed, "Best Allowed Layout", "warn")

            if locked_benefit:
                delta = locked_benefit["qty_box"] - best_h["qty_box"]
                pct = (delta / best_h["qty_box"] * 100.0) if best_h and best_h["qty_box"] else 0.0
                st.warning(
                    f"🔒 Potential higher-capacity **{locked_benefit['up_axis']}-Up** geometry = "
                    f"**{locked_benefit['qty_box']} pcs/A10 (+{delta}, +{pct:.1f}%)**, but this orientation is currently not permitted. "
                    f"Enable {locked_benefit['up_axis']}-Up only after Product / Customer / Label / Handling confirmation."
                )

# ============================================================
# SCENARIO EXPLORER
# ============================================================
st.divider()
with st.expander("📊 Layout Scenario Explorer", expanded=False):
    if options:
        rows = []
        for idx, opt in enumerate(options[:15], start=1):
            rows.append(
                {
                    "Rank": idx,
                    "Orientation": f"{opt['up_axis']}-Up",
                    "Status": "Allowed" if opt["allowed"] else "Locked",
                    "Floor × Height": opt["orient_label"],
                    "Partition": f"{int(opt['part_height'])} mm",
                    "Grid": f"{len(opt['x_dividers'])-1}×{len(opt['y_dividers'])-1}",
                    "Base Slots/Layer": opt["base_slots_layer"],
                    "Pcs/Layer": opt["qty_layer"],
                    "Layers": opt["layers"],
                    "Total Pcs/A10": opt["qty_box"],
                    "Short Part./Layer": opt["short_dividers_per_layer"],
                    "Long Part./Layer": opt["long_dividers_per_layer"],
                    "Max Span X": round(opt["max_span_x"], 1),
                    "Max Span Y": round(opt["max_span_y"], 1),
                    "Area Occupancy %": round(opt["area_occupancy"], 1),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No valid scenario")

with st.expander("🧠 Solver / Engineering Note", expanded=False):
    st.markdown(
        f"""
- **Orientation-aware:** H-Up is the default normal reference. L-Up / W-Up are not used in recommendation unless the user explicitly enables them.
- **Axis identity is tracked explicitly:** the solver no longer decides Fixed-H by comparing equal dimension values.
- **Partition Topology Validation:** layouts must use both partition directions and form an interlocked grid. A single giant 1×1 cell is rejected.
- **ESD Packed Envelope:** Product inputs are PURE dimensions. Current allowance = **{fmt_num(esd_allowance_per_side)} mm/side** → total **+{fmt_num(total_esd_allowance)} mm per dimension**.
- **Stack-Fit vertical logic:** every stacked product uses its own packed-envelope height; the ESD allowance is no longer subtracted only once for the whole stack.
- **Span Guardrail:** checked in every packing mode. **Dynamic** keeps the baseline but auto-relaxes only when the actual A10 groove pitch requires a larger minimum span to fit one packed product. **Strict** uses the baseline as a hard maximum. Current mode = **{span_mode}**; baseline = **{fmt_num(max_slot_span)} mm**.
- **Strength limitation:** the span check is a geometry-based engineering screening only; it is **not** BCT / ECT / compression-strength validation.
- **Groove constrained:** candidate partition sheets are selected only from the defined Carton A10 groove coordinates.
- **BOM:** partition quantities follow the number of active short/long partition sheets per layer × packing layers.
- **Standard Excel library:** V0.1.3 has not yet converted the historical Excel standard packing table into a master database. That can be added as a later Standard Match layer after the V0.1 solver is validated against real cases.
        """
    )
    st.caption(
        f"Solver diagnostics: valid {debug['evaluated_valid']} • topology rejects {debug['rejected_topology']} • "
        f"fit rejects {debug['rejected_fit']} • span rejects {debug['rejected_span']}"
    )
