import itertools
import math
import streamlit as st

# ============================================================
# PAGE CONFIG
# ============================================================
APP_VERSION = "V0.1.5.3.1"
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
# 111x584 drawing: 9.5 mm clear edge margin + 5 mm groove + 135 mm clear gap
# between groove edges -> 140 mm centerline pitch.
GROOVE_X_111 = [16.0, 156.0, 296.0, 436.0, 576.0]

# 111x584-01 drawing: 9.5 mm clear edge margin, 5 mm groove,
# 65 mm clear gap -> 70 mm centerline pitch, 9 grooves.
# Sheet coordinates = [12,82,152,222,292,362,432,502,572].
# Finished 584-mm sheet is centered in Carton ID 592 -> +4 mm.
GROOVE_X_111_584_01 = [16.0, 86.0, 156.0, 226.0, 296.0, 366.0, 436.0, 506.0, 576.0]

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
        f"111X_STD:{pack(GROOVE_X_111)}",
        f"111X_584_01:{pack(GROOVE_X_111_584_01)}",
        f"111Y:{pack(GROOVE_Y_111)}",
        f"225X:{pack(GROOVE_X_225)}",
        f"225Y:{pack(GROOVE_Y_225)}",
    ])


GEOMETRY_SIGNATURE = _geometry_signature()

# Solver/cache logic revision guard.
# V0.1.5.3 adds a physical ESD / air-bubble vertical build-up model.
# Folding may reduce projected W/L footprint, but it does not delete bag volume:
# base bag layers remain above/below the product and a folded flap adds local Up-axis build-up.
SOLVER_LOGIC_SIGNATURE = "V01531_AMW_FOLD_DEFAULT_R1"

# Outer usable envelope for the partition system / pad zone.
#
# IMPORTANT V0.1.5:
# Partition height 111 mm has TWO audited long-sheet die-cut variants:
#   - PARTITION 111×584      : 5 grooves, 140-mm pitch
#   - PARTITION 111×584-01   : 9 grooves, 70-mm pitch
# The short sheet PARTITION 111×393 remains the same 9-groove / 45-mm-pitch part.
#
# The solver evaluates both 111-mm variants automatically and only recommends -01
# when its denser groove pattern creates a real capacity / fit benefit.
PARTITION_SYSTEM_VARIANTS = {
    "111_STD": {
        "variant_id": "111_STD",
        "part_height": 111.0,
        "variant_priority": 2,  # prefer standard die-cut on an exact performance tie
        "groove_x": GROOVE_X_111,
        "groove_y": GROOVE_Y_111,
        "x_pad_start": 4.0,
        "x_pad_end": 588.0,
        "y_pad_start": 5.5,
        "y_pad_end": 398.5,
        "layers": 2,
        "short_partition_name": "PARTITION 111×393",
        "long_partition_name": "PARTITION 111×584",
        "variant_label": "111×584 Standard (5 grooves / 140-mm pitch)",
    },
    "111_584_01": {
        "variant_id": "111_584_01",
        "part_height": 111.0,
        "variant_priority": 1,
        "groove_x": GROOVE_X_111_584_01,
        "groove_y": GROOVE_Y_111,
        "x_pad_start": 4.0,
        "x_pad_end": 588.0,
        "y_pad_start": 5.5,
        "y_pad_end": 398.5,
        "layers": 2,
        "short_partition_name": "PARTITION 111×393",
        "long_partition_name": "PARTITION 111×584-01",
        "long_partition_alias": "PARTITION 111×584-1",
        "variant_label": "111×584-01 Fine Pitch (9 grooves / 70-mm pitch)",
    },
    "225_STD": {
        "variant_id": "225_STD",
        "part_height": 225.0,
        "variant_priority": 2,
        "groove_x": GROOVE_X_225,
        "groove_y": GROOVE_Y_225,
        "x_pad_start": 4.0,
        "x_pad_end": 588.0,
        "y_pad_start": 5.5,
        "y_pad_end": 398.5,
        "layers": 1,
        "short_partition_name": "PARTITION 225×393",
        "long_partition_name": "PARTITION 225×584",
        "variant_label": "225×584 Standard (5 grooves / 125-mm pitch)",
    },
}

PARTITION_VARIANTS_BY_HEIGHT = {
    111.0: [
        PARTITION_SYSTEM_VARIANTS["111_STD"],
        PARTITION_SYSTEM_VARIANTS["111_584_01"],
    ],
    225.0: [
        PARTITION_SYSTEM_VARIANTS["225_STD"],
    ],
}


def get_partition_system_for_option(opt):
    """Return the exact audited die-cut system used by an option."""
    variant_id = opt.get("partition_variant_id")
    if variant_id in PARTITION_SYSTEM_VARIANTS:
        return PARTITION_SYSTEM_VARIANTS[variant_id]

    # Defensive backward fallback for old cached/manual option dictionaries.
    if opt.get("part_height") == 111.0:
        return PARTITION_SYSTEM_VARIANTS["111_STD"]
    return PARTITION_SYSTEM_VARIANTS["225_STD"]

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

st.sidebar.header("🛡️ 3. ESD Air-Bubble Bag / Folding Method")

bag_folding_method = st.sidebar.radio(
    "Bag Folding Method",
    options=[
        "Standard Bag — No Fold",
        "Mouth Fold Only",
        "Mouth + Side Fold — AMW Standard",
        "Custom / Verified Packing",
    ],
    index=2,
    help=(
        "เลือกตามวิธีแพ็กจริง. Default = Mouth + Side Fold — AMW Standard ซึ่งเป็น common packing method ของทีม. "
        "ลำดับคือ ใส่ชิ้นงานในถุง → พับปากถุงลงบนชิ้นงาน → พับปีกด้านข้างให้แนบกับชิ้นงาน. "
        "Mouth Fold Only เก็บไว้สำหรับ special case ที่ขนาดถุงใกล้กับ W/L ของ product จนแทบไม่มี side excess."
    ),
)

esd_allowance_per_side = st.sidebar.slider(
    "Company / Nominal Lateral ESD Allowance per Side (mm)",
    min_value=0.0,
    max_value=15.0,
    value=5.0,
    step=0.5,
    help=(
        "ค่า lateral allowance reference ของบริษัท ปัจจุบัน = 5 mm/side. "
        "Standard Bag ใช้ค่านี้เป็น rigid footprint โดยตรง. "
        "Folded preset ใช้ Auto Feasibility และ back-calculate allowable folded footprint."
    ),
)

bubble_build_up_per_layer = st.sidebar.slider(
    "Bubble Packing Build-up per Layer (mm)",
    min_value=0.0,
    max_value=15.0,
    value=5.0,
    step=0.5,
    help=(
        "Engineering packing build-up ของ air-bubble 1 ชั้นในแนว Up-axis. "
        "Default = 5 mm/layer ตาม allowance ที่ใช้อยู่ปัจจุบัน. "
        "ไม่ใช่ film/material thickness; เป็น packing build-up สำหรับ concept screening."
    ),
)

# ------------------------------------------------------------
# Folding preset model
# ------------------------------------------------------------
# Base enclosure always has one bubble layer under + one above the product.
base_bag_vertical_build_up = bubble_build_up_per_layer * 2.0
mouth_fold_vertical_build_up = 0.0
side_fold_local_build_up = 0.0

if bag_folding_method == "Standard Bag — No Fold":
    esd_fit_model = "Standard — Rigid Lateral Allowance"
    solver_esd_allowance_per_side = esd_allowance_per_side

    nominal_bag_vertical_build_up = base_bag_vertical_build_up
    local_bag_vertical_build_up = nominal_bag_vertical_build_up

    st.sidebar.info(
        "Standard Bag: lateral footprint uses the full nominal allowance. "
        "Vertical model = bottom bubble + top bubble."
    )

elif bag_folding_method == "Mouth Fold Only":
    esd_fit_model = "Folded / Compressible — Auto Feasibility (RFQ)"
    solver_esd_allowance_per_side = 0.0

    # Mouth flap is folded back over the product, so it adds one extra bubble layer
    # to the nominal packed height.
    mouth_fold_vertical_build_up = bubble_build_up_per_layer
    nominal_bag_vertical_build_up = (
        base_bag_vertical_build_up + mouth_fold_vertical_build_up
    )
    local_bag_vertical_build_up = nominal_bag_vertical_build_up

    st.sidebar.warning(
        "⚠️ Mouth Fold Auto Feasibility: ไม่ต้องเดา folded lateral allowance. "
        "Solver จะใช้ pure footprint หา candidate แล้ว back-calculate ค่า lateral trial target."
    )

elif bag_folding_method == "Mouth + Side Fold — AMW Standard":
    esd_fit_model = "Folded / Compressible — Auto Feasibility (RFQ)"
    solver_esd_allowance_per_side = 0.0

    # AMW reference process:
    # 1) mouth flap folds onto the product -> contributes to NOMINAL packed height
    # 2) side flap folds onto the product -> creates a LOCAL peak, not a full-area layer
    mouth_fold_vertical_build_up = bubble_build_up_per_layer
    side_fold_local_build_up = bubble_build_up_per_layer

    nominal_bag_vertical_build_up = (
        base_bag_vertical_build_up + mouth_fold_vertical_build_up
    )
    local_bag_vertical_build_up = (
        nominal_bag_vertical_build_up + side_fold_local_build_up
    )

    st.sidebar.warning(
        "⚠️ AMW Mouth + Side Fold: W/L excess is folded back onto the product. "
        "Mouth fold is included in nominal packed height; side fold is treated as a local maximum peak "
        "for compression / load-path screening."
    )

else:
    # Verified mode: use measured packed-envelope data instead of asking the engineer
    # to guess fold-layer counts.
    esd_fit_model = "Folded / Compressible — Verified by Trial"

    verified_default = min(2.0, float(esd_allowance_per_side))
    solver_esd_allowance_per_side = st.sidebar.slider(
        "Verified Effective Lateral Allowance per Side (mm)",
        min_value=0.0,
        max_value=float(esd_allowance_per_side),
        value=verified_default,
        step=0.5,
        help=(
            "ใช้ค่าที่วัดจาก packed sample จริง เช่น Pure width 65 mm → packed width 69 mm "
            "ดังนั้น effective lateral allowance = (69-65)/2 = 2 mm/side"
        ),
    )

    verified_nominal_build_up = st.sidebar.number_input(
        "Verified Nominal Vertical Bag Build-up (mm)",
        min_value=0.0,
        max_value=80.0,
        value=15.0,
        step=0.5,
        help=(
            "ค่าที่วัดจาก packed sample: Nominal packed H - Pure product H. "
            "ควรรวม bottom/top bag และ fold ที่ครอบคลุมพื้นที่หลักแล้ว"
        ),
    )

    verified_local_peak_build_up = st.sidebar.number_input(
        "Verified Local-Max Vertical Bag Build-up (mm)",
        min_value=0.0,
        max_value=100.0,
        value=20.0,
        step=0.5,
        help=(
            "Local maximum build-up ที่บริเวณ fold ซ้อนหนาที่สุด: "
            "Local max packed H - Pure product H"
        ),
    )

    nominal_bag_vertical_build_up = float(verified_nominal_build_up)
    local_bag_vertical_build_up = max(
        float(verified_local_peak_build_up),
        nominal_bag_vertical_build_up,
    )

    # For a verified custom pack, the detailed layer split is not inferred.
    # Keep the whole nominal value in Base/Verified build-up and expose only
    # the additional local peak separately.
    base_bag_vertical_build_up = nominal_bag_vertical_build_up
    mouth_fold_vertical_build_up = 0.0
    side_fold_local_build_up = (
        local_bag_vertical_build_up - nominal_bag_vertical_build_up
    )

    if verified_local_peak_build_up < verified_nominal_build_up:
        st.sidebar.warning(
            "Local-Max build-up ต่ำกว่า Nominal build-up จึงถูกปรับขึ้นให้เท่ากับ Nominal อัตโนมัติ"
        )

    st.sidebar.success(
        "✅ Custom / Verified Packing: solver uses measured lateral + vertical packed-envelope data."
    )

vertical_clearance = st.sidebar.number_input(
    "Vertical / Top Clearance (mm)",
    min_value=0.0,
    max_value=50.0,
    value=0.0,
    step=0.5,
    help=(
        "Engineering clearance แยกจาก bag build-up. "
        "Default = 0 mm; เพิ่มเมื่อ product/customer/handling requirement ต้องการ headroom เพิ่ม"
    ),
)

# ------------------------------------------------------------
# Derived lateral + vertical packed condition
# ------------------------------------------------------------
total_esd_allowance = solver_esd_allowance_per_side * 2.0

# Normal H-Up preview only.
effective_product_w = p_w + total_esd_allowance
effective_product_l = p_l + total_esd_allowance
effective_product_h = (
    p_h + vertical_clearance + nominal_bag_vertical_build_up
)
effective_local_peak_h = (
    p_h + vertical_clearance + local_bag_vertical_build_up
)

if "Auto Feasibility" in esd_fit_model:
    st.sidebar.caption(
        "Product Dimension = PURE product size. Folded preset uses pure product footprint "
        "for lateral candidate generation, then back-calculates the allowable folded-bag trial envelope."
    )
else:
    st.sidebar.caption(
        "Product Dimension = PURE product size. Solver lateral fit allowance = "
        f"{fmt_num(solver_esd_allowance_per_side)} mm/side."
    )

st.sidebar.info(
    f"Normal H-Up • Solver footprint {fmt_num(effective_product_w)} × "
    f"{fmt_num(effective_product_l)} mm • Nominal packed H {fmt_num(effective_product_h)} mm "
    f"• Local max H {fmt_num(effective_local_peak_h)} mm"
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
    slot_limit_basis = "Standard 1 PC/Slot"
    max_pcs_axis = 1
    max_total_pcs_slot = 1
    st.sidebar.caption("Standard mode: 1 product / slot (fixed)")
else:
    slot_limit_basis = st.sidebar.radio(
        "Slot Quantity Limit Basis",
        options=[
            "Max Total Pcs / Slot — Recommended",
            "Max Pcs / Axis — Legacy / Advanced",
        ],
        index=0,
        help=(
            "Recommended = ใช้เมื่อ Packing Spec ระบุชัด เช่น 2 pcs/slot. "
            "Legacy / Advanced = จำกัดจำนวนต่อแกน ทำให้ค่า 2 สามารถเป็น 2×2 = 4 pcs/slot ได้"
        ),
    )

    if slot_limit_basis.startswith("Max Total"):
        max_total_pcs_slot = st.sidebar.slider(
            "Max Total Pcs / Slot",
            min_value=1,
            max_value=8,
            value=2,
            help="จำนวน product สูงสุดรวมบน floor ของ 1 slot สำหรับ Multi-Fit",
        )
        max_pcs_axis = max_total_pcs_slot
    else:
        max_pcs_axis = st.sidebar.slider(
            "Max Pcs / Axis ใน 1 slot",
            min_value=1,
            max_value=4,
            value=2,
            help="Legacy / advanced mode: ค่า 2 อาจอนุญาตสูงสุด 2×2 = 4 pcs/slot",
        )
        max_total_pcs_slot = max_pcs_axis * max_pcs_axis

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
        "Dynamic จะรักษา Baseline เป็นหลัก แล้วตรวจ candidate grid จาก groove จริงทั้งชุด หาก complete grid ที่ทุกช่องใส่สินค้าได้ต้องใช้ span ใหญ่กว่า Baseline "
        "ระบบจะผ่อนเฉพาะเท่าที่ complete feasible grid ต้องใช้. Multi-Fit / Stack-Fit ยังคง scale ตาม Max Pcs / Axis. "
        "Strict = Baseline เป็น hard limit; ถ้า groove ที่จำเป็นเกิน Baseline ระบบจะไม่ยอมรับ layout"
    ),
)

st.sidebar.info(
    "✅ V0.1.5.3.1: AMW Mouth + Side Fold = Recommended Default + Real Folding Method Model"
)

st.sidebar.caption(
    "Drawing audit: 111×584 pitch 140 mm • 111×584-01 pitch 70 mm • "
    "111/225×393 pitch 45 mm • 225×584 pitch 125 mm. Groove coordinates are stored as centerlines in Carton A10 coordinates."
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
def select_partition_systems(vertical_h, vertical_clr):
    """
    Return every audited die-cut system whose PARTITION height can protect the
    pure product Up-axis + explicit engineering clearance.

    V0.1.5.3 also evaluates the 225-mm / one-layer system as a fallback when a
    product is short enough for 111 mm but the REAL packed package height
    (bag + fold build-up) makes the 2-layer 111-mm carton stack too tall.
    """
    required_vertical_h = vertical_h + vertical_clr

    if required_vertical_h <= 111.0:
        systems = (
            PARTITION_VARIANTS_BY_HEIGHT[111.0]
            + PARTITION_VARIANTS_BY_HEIGHT[225.0]
        )
        return 111.0, systems

    if required_vertical_h <= 225.0:
        return 225.0, PARTITION_VARIANTS_BY_HEIGHT[225.0]

    return None, []


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
    """Pairwise groove diagnostic only; not sufficient by itself to prove a complete grid."""
    for span in groove_span_catalog(grooves):
        if span + 1e-9 >= required_span:
            return span
    return None


def _candidate_axis_spans(dividers):
    return [dividers[i + 1] - dividers[i] for i in range(len(dividers) - 1)]


def best_floor_fit_with_total_limit(max_fit_x, max_fit_y, max_total):
    """
    Choose qx × qy that maximizes floor pcs in one slot without exceeding max_total.

    This makes an RFQ statement such as "2 pcs/slot" mean TWO total,
    rather than the legacy Max-Pcs/Axis interpretation where 2 may become 2×2 = 4.
    """
    best = (1, 1)
    best_score = (-1, -999, -999, -999)

    for qx in range(1, max(1, max_fit_x) + 1):
        for qy in range(1, max(1, max_fit_y) + 1):
            total = qx * qy
            if total > max_total:
                continue
            score = (total, -abs(qx - qy), -qx, -qy)
            if score > best_score:
                best_score = score
                best = (qx, qy)

    return best


def find_complete_grid_span_requirement(
    subsets_x,
    subsets_y,
    target_l,
    target_w,
    base_eff_x,
    base_eff_y,
):
    """
    Find the smallest PRACTICALLY FEASIBLE complete A10 grid relaxation.

    Why this exists:
    A pairwise groove span may fit one product but still leave a residual cell
    that is too small.  Example: a 380-mm product may have a 420-mm groove pair,
    but retaining the mandatory first/last sheets can create 420 + 140 mm cells;
    the 140-mm residual cell invalidates the complete grid.  The real feasible
    structure may therefore require one 560-mm cell.

    Candidate requirements:
      1) topology must be a valid interlocked grid,
      2) EVERY X interval must fit target_l,
      3) EVERY Y interval must fit target_w.

    Ranking minimizes the amount of relaxation from the current base guardrail,
    then prefers the smaller absolute maximum spans, then the simpler grid.
    """
    best = None

    for x_dividers in subsets_x:
        x_spans = _candidate_axis_spans(x_dividers)
        if not x_spans or any(span + 1e-9 < target_l for span in x_spans):
            continue
        max_x = max(x_spans)

        for y_dividers in subsets_y:
            topo_ok, _ = topology_validation(x_dividers, y_dividers)
            if not topo_ok:
                continue

            y_spans = _candidate_axis_spans(y_dividers)
            if not y_spans or any(span + 1e-9 < target_w for span in y_spans):
                continue
            max_y = max(y_spans)

            req_x = max(base_eff_x, max_x)
            req_y = max(base_eff_y, max_y)

            # Relative relaxation is the primary criterion so one axis cannot
            # become excessively loose merely to improve the other axis.
            relax_x = req_x / base_eff_x if base_eff_x > 0 else float("inf")
            relax_y = req_y / base_eff_y if base_eff_y > 0 else float("inf")
            worst_relax = max(relax_x, relax_y)
            total_extra = max(0.0, req_x - base_eff_x) + max(0.0, req_y - base_eff_y)

            score = (
                worst_relax,
                total_extra,
                max_x + max_y,
                len(x_dividers) + len(y_dividers),
            )

            candidate = {
                "required_eff_x": req_x,
                "required_eff_y": req_y,
                "complete_max_span_x": max_x,
                "complete_max_span_y": max_y,
                "x_dividers": list(x_dividers),
                "y_dividers": list(y_dividers),
                "score": score,
            }

            if best is None or score < best["score"]:
                best = candidate

    return best


def effective_span_limits(
    target_l,
    target_w,
    mode,
    max_pcs_per_axis,
    baseline,
    guardrail_mode,
    groove_x,
    groove_y,
    subsets_x,
    subsets_y,
):
    """
    Return effective X/Y maximum span limits plus diagnostics.

    V0.1.5 Dynamic mode remains COMPLETE-GRID aware:
      - start from the normal engineering baseline / Multi-Fit scaling,
      - enumerate real groove-subset grids,
      - require every cell to fit at least one packed product footprint,
      - require the whole X/Y topology to be a valid interlocked grid,
      - relax only as far as the best complete feasible grid needs.

    Strict mode remains a true hard maximum and never auto-relaxes.
    """
    pairwise_min_x = minimum_groove_compatible_span(groove_x, target_l)
    pairwise_min_y = minimum_groove_compatible_span(groove_y, target_w)

    if "Standard 1 PC/Slot" in mode:
        pcs_factor = 1.0
    else:
        pcs_factor = float(max_pcs_per_axis)

    if guardrail_mode.startswith("Dynamic"):
        base_eff_x = max(baseline, target_l * pcs_factor)
        base_eff_y = max(baseline, target_w * pcs_factor)
    else:
        base_eff_x = baseline
        base_eff_y = baseline

    complete_req = find_complete_grid_span_requirement(
        subsets_x,
        subsets_y,
        target_l,
        target_w,
        base_eff_x,
        base_eff_y,
    )

    if guardrail_mode.startswith("Dynamic") and complete_req is not None:
        eff_x = complete_req["required_eff_x"]
        eff_y = complete_req["required_eff_y"]
    else:
        # Strict stays hard. If no complete feasible grid exists, keep the
        # baseline so the normal solver naturally returns no valid layout.
        eff_x = base_eff_x
        eff_y = base_eff_y

    return (
        eff_x,
        eff_y,
        pairwise_min_x,
        pairwise_min_y,
        complete_req,
        base_eff_x,
        base_eff_y,
    )

def span_stats(bounds):
    spans = [bounds[i + 1] - bounds[i] for i in range(len(bounds) - 1)]
    if not spans:
        return 0.0, 0.0, 0.0
    return min(spans), max(spans), (max(spans) - min(spans))


# ============================================================
# SOLVER
# ============================================================
# FIT MARGIN / CRITICAL BOUNDARY ANALYSIS
# ============================================================
def calculate_fit_margin(
    valid_slots,
    target_l,
    target_w,
    esd_total_allowance,
):
    """
    Nominal geometry margin for the CURRENT selected layout/capacity.

    Solver coordinate convention:
      - slot X is checked against target_l
      - slot Y is checked against target_w

    For a slot carrying qty_x × qty_y products:
      reserve_x = slot_x - qty_x * target_l
      reserve_y = slot_y - qty_y * target_w

    Because ESD allowance is entered PER SIDE, increasing the input by delta mm/side
    increases each packed floor dimension by 2*delta. Therefore the maximum additional
    per-side allowance that preserves the CURRENT qty_x / qty_y in the CURRENT grid is:
      reserve_x / (2 * qty_x)
      reserve_y / (2 * qty_y)

    This is a nominal geometry screening only. Product tolerance, ESD bag forming
    variation, partition die-cut tolerance and assembly deformation are NOT included.
    """
    if not valid_slots:
        return {
            "min_slot_reserve_x": 0.0,
            "min_slot_reserve_y": 0.0,
            "esd_headroom_x_per_side": 0.0,
            "esd_headroom_y_per_side": 0.0,
            "esd_headroom_per_side": 0.0,
            "max_esd_per_side_current_layout": esd_total_allowance / 2.0,
            "fit_margin_status": "CRITICAL",
            "fit_margin_note": "No valid slot data",
            "limiting_floor_direction": "X/Y",
        }

    reserve_x_values = []
    reserve_y_values = []
    headroom_x_values = []
    headroom_y_values = []

    for slot in valid_slots:
        slot_x = slot["x_end"] - slot["x_start"]
        slot_y = slot["y_end"] - slot["y_start"]

        qty_x = max(1, int(slot["qty_x"]))
        qty_y = max(1, int(slot["qty_y"]))

        reserve_x = slot_x - (qty_x * target_l)
        reserve_y = slot_y - (qty_y * target_w)

        if abs(reserve_x) < 1e-9:
            reserve_x = 0.0
        if abs(reserve_y) < 1e-9:
            reserve_y = 0.0

        reserve_x_values.append(reserve_x)
        reserve_y_values.append(reserve_y)
        headroom_x_values.append(reserve_x / (2.0 * qty_x))
        headroom_y_values.append(reserve_y / (2.0 * qty_y))

    min_reserve_x = min(reserve_x_values)
    min_reserve_y = min(reserve_y_values)
    headroom_x = min(headroom_x_values)
    headroom_y = min(headroom_y_values)
    headroom = min(headroom_x, headroom_y)

    current_esd_per_side = esd_total_allowance / 2.0
    max_esd_per_side = current_esd_per_side + headroom

    if headroom_x < headroom_y - 1e-9:
        limiting_direction = "X"
    elif headroom_y < headroom_x - 1e-9:
        limiting_direction = "Y"
    else:
        limiting_direction = "X/Y"

    if headroom <= 0.01:
        status = "CRITICAL"
        note = "Zero / near-zero lateral reserve at the selected capacity."
    elif headroom <= 0.50:
        status = "TIGHT"
        note = "Very small reserve; the next 0.5 mm/side allowance step may change capacity/grid."
    else:
        status = "OK"
        note = "Nominal lateral reserve remains before the selected layout loses current capacity."

    return {
        "min_slot_reserve_x": min_reserve_x,
        "min_slot_reserve_y": min_reserve_y,
        "esd_headroom_x_per_side": headroom_x,
        "esd_headroom_y_per_side": headroom_y,
        "esd_headroom_per_side": headroom,
        "max_esd_per_side_current_layout": max_esd_per_side,
        "fit_margin_status": status,
        "fit_margin_note": note,
        "limiting_floor_direction": limiting_direction,
    }


# ============================================================
@st.cache_data(show_spinner=False)
def solve_a10_partition_layouts(
    pw,
    pl,
    ph,
    esd_total_allowance,
    nominal_esd_per_side,
    effective_esd_per_side,
    esd_model,
    folding_method,
    base_bag_vertical_buildup,
    mouth_fold_vertical_buildup,
    side_fold_local_buildup,
    nominal_bag_vertical_buildup,
    local_bag_vertical_buildup,
    vertical_clr,
    mode,
    slot_limit_basis,
    max_pcs_per_axis,
    max_total_pcs_per_slot,
    max_span_limit,
    guardrail_mode,
    allow_l,
    allow_w,
    geometry_signature,
    solver_logic_signature,
):
    # Explicit cache-key dependencies. Geometry and solver-logic changes must not
    # reuse stale layouts from an older Streamlit cache.
    _ = (geometry_signature, solver_logic_signature)
    orientations = build_orientations(pw, pl, ph, allow_l, allow_w)
    options = []
    rejected_topology = 0
    rejected_span = 0
    rejected_fit = 0
    rejected_height = 0
    span_requirements = []

    for orient in orientations:
        ew = orient["flat_w"]
        el = orient["flat_l"]
        eh = orient["vert_h"]

        part_height, feasible_systems = select_partition_systems(eh, vertical_clr)
        if not feasible_systems:
            continue

        # Lateral geometry and vertical packed height are deliberately separated.
        # Folding can reduce W/L projected footprint, but the air-bubble / ESD bag
        # still contributes physical build-up in the Up-axis.
        target_w = ew + esd_total_allowance
        target_l = el + esd_total_allowance

        # Partition selection still references pure product height + explicit clearance.
        partition_required_h = eh + vertical_clr

        # V0.1.5.3 physical folding method:
        # nominal packed height = product + base enclosure + mouth fold + clearance
        # local maximum adds side-fold overlap only at the fold region.
        base_vertical_build_up = base_bag_vertical_buildup
        mouth_vertical_build_up = mouth_fold_vertical_buildup
        side_local_vertical_build_up = side_fold_local_buildup
        bag_vertical_build_up = nominal_bag_vertical_buildup

        packed_unit_height = (
            eh + vertical_clr + nominal_bag_vertical_buildup
        )
        local_peak_unit_height = (
            eh + vertical_clr + local_bag_vertical_buildup
        )

        for system in feasible_systems:
            # If the pure product itself is taller than this partition, do not use it.
            if partition_required_h > system["part_height"] + 1e-9:
                continue
            part_height = system["part_height"]
            layers = system["layers"]
            groove_x = system["groove_x"]
            groove_y = system["groove_y"]

            subsets_x = generate_partition_subsets(groove_x)
            subsets_y = generate_partition_subsets(groove_y)

            (
                eff_span_x,
                eff_span_y,
                min_groove_span_x,
                min_groove_span_y,
                complete_grid_req,
                base_eff_span_x,
                base_eff_span_y,
            ) = effective_span_limits(
                target_l,
                target_w,
                mode,
                max_pcs_per_axis,
                max_span_limit,
                guardrail_mode,
                groove_x,
                groove_y,
                subsets_x,
                subsets_y,
            )

            min_complete_grid_span_x = (
                complete_grid_req["complete_max_span_x"] if complete_grid_req is not None else None
            )
            min_complete_grid_span_y = (
                complete_grid_req["complete_max_span_y"] if complete_grid_req is not None else None
            )

            span_requirements.append(
                {
                    "orientation_id": orient["orientation_id"],
                    "up_axis": orient["up_axis"],
                    "allowed": orient["allowed"],
                    "part_height": part_height,
                    "partition_variant_id": system["variant_id"],
                    "partition_variant_label": system["variant_label"],
                    "target_l": target_l,
                    "target_w": target_w,
                    "min_groove_span_x": min_groove_span_x,
                    "min_groove_span_y": min_groove_span_y,
                    "min_complete_grid_span_x": min_complete_grid_span_x,
                    "min_complete_grid_span_y": min_complete_grid_span_y,
                    "base_eff_span_x": base_eff_span_x,
                    "base_eff_span_y": base_eff_span_y,
                    "eff_span_x": eff_span_x,
                    "eff_span_y": eff_span_y,
                }
            )

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
                                max_fit_x = max(1, int(slot_x // target_l))
                                max_fit_y = max(1, int(slot_y // target_w))

                                if slot_limit_basis.startswith("Max Total"):
                                    qty_x, qty_y = best_floor_fit_with_total_limit(
                                        max_fit_x,
                                        max_fit_y,
                                        max_total_pcs_per_slot,
                                    )
                                else:
                                    qty_x = min(max_pcs_per_axis, max_fit_x)
                                    qty_y = min(max_pcs_per_axis, max_fit_y)

                                if "Stack-Fit" in mode:
                                    # Stack quantity uses NOMINAL packed unit height.
                                    # Local side-fold peaks are screened separately because
                                    # they do not cover the full product area.
                                    qty_z = max(1, int(part_height // packed_unit_height))
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

                    # ------------------------------------------------------------
                    # V0.1.5.3 — PHYSICAL VERTICAL STACK / CARTON HEIGHT MODEL
                    # ------------------------------------------------------------
                    # Every product keeps its base bag build-up. Folded bag material is
                    # transferred into local Up-axis build-up instead of disappearing.
                    qty_z_reference = max(s["qty_z"] for s in valid_slots)

                    # Nominal full-area packed stack height.
                    packed_stack_height = packed_unit_height * qty_z_reference

                    # Local peak includes side-fold overlap at the thickest region.
                    local_peak_stack_height = local_peak_unit_height * qty_z_reference

                    # The NORMAL layer pitch is governed by partition or nominal packed stack.
                    # Local side-fold peak is not automatically promoted to full-area layer pitch,
                    # because it exists only at the fold zone and is compressible/localized.
                    layer_pitch = max(part_height, packed_stack_height)
                    local_peak_layer_pitch = max(part_height, local_peak_stack_height)

                    # A10 uses bottom + interlayer + top pads => layers + 1 pads.
                    total_used_h = (layer_pitch * layers) + (PAD_T * (layers + 1))
                    local_peak_total_used_h = (
                        local_peak_layer_pitch * layers
                    ) + (PAD_T * (layers + 1))

                    carton_top_air_gap = CARTON_H - total_used_h
                    local_peak_carton_gap = CARTON_H - local_peak_total_used_h

                    # Reject only when the NOMINAL full-area stack exceeds carton ID.
                    # Local peak over-height becomes a trial/compression warning because
                    # side folds are localized and may compress or stagger spatially.
                    if carton_top_air_gap < -1e-9:
                        rejected_height += 1
                        continue

                    partition_height_delta = part_height - packed_stack_height
                    partition_headroom = max(0.0, partition_height_delta)
                    package_protrusion = max(0.0, -partition_height_delta)

                    local_peak_partition_delta = (
                        part_height - local_peak_stack_height
                    )
                    local_peak_partition_headroom = max(
                        0.0, local_peak_partition_delta
                    )
                    local_peak_package_protrusion = max(
                        0.0, -local_peak_partition_delta
                    )

                    local_peak_compression_required = max(
                        0.0, -local_peak_carton_gap
                    )

                    # Backward-friendly positive top-gap field.
                    top_gap = partition_headroom

                    # V0.1.5.3 — quantify how close the CURRENT selected grid/capacity is
                    # to its next lateral ESD / slot-fit breakpoint.
                    fit_margin = calculate_fit_margin(
                        valid_slots,
                        target_l,
                        target_w,
                        esd_total_allowance,
                    )

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
                        "target_h": partition_required_h,
                        "packed_unit_height": packed_unit_height,
                        "local_peak_unit_height": local_peak_unit_height,
                        "packed_stack_height": packed_stack_height,
                        "local_peak_stack_height": local_peak_stack_height,
                        "layer_pitch": layer_pitch,
                        "local_peak_layer_pitch": local_peak_layer_pitch,
                        "base_bag_vertical_build_up": base_vertical_build_up,
                        "mouth_fold_vertical_build_up": mouth_vertical_build_up,
                        "side_fold_local_build_up": side_local_vertical_build_up,
                        "nominal_bag_vertical_build_up": nominal_bag_vertical_buildup,
                        "local_bag_vertical_build_up": local_bag_vertical_buildup,
                        "bag_folding_method": folding_method,
                        "partition_height_delta": partition_height_delta,
                        "partition_headroom": partition_headroom,
                        "package_protrusion": package_protrusion,
                        "local_peak_partition_headroom": local_peak_partition_headroom,
                        "local_peak_package_protrusion": local_peak_package_protrusion,
                        "total_used_height": total_used_h,
                        "local_peak_total_used_height": local_peak_total_used_h,
                        "local_peak_carton_gap": local_peak_carton_gap,
                        "local_peak_compression_required": local_peak_compression_required,
                        "carton_height_utilization": (total_used_h / CARTON_H) * 100.0,
                        "local_peak_height_utilization": (local_peak_total_used_h / CARTON_H) * 100.0,
                        "esd_total_allowance": esd_total_allowance,
                        "vertical_clearance": vertical_clr,
                        "esd_fit_model": esd_model,
                        "nominal_esd_per_side": nominal_esd_per_side,
                        "effective_esd_per_side": effective_esd_per_side,
                        "slot_limit_basis": slot_limit_basis,
                        "max_total_pcs_per_slot": max_total_pcs_per_slot,
                        "max_pcs_per_axis": max_pcs_per_axis,
                        "part_height": part_height,
                        "partition_variant_id": system["variant_id"],
                        "partition_variant_label": system["variant_label"],
                        "variant_priority": system["variant_priority"],
                        "short_partition_name": system["short_partition_name"],
                        "long_partition_name": system["long_partition_name"],
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
                        "min_complete_grid_span_x": min_complete_grid_span_x,
                        "min_complete_grid_span_y": min_complete_grid_span_y,
                        "base_eff_span_x": base_eff_span_x,
                        "base_eff_span_y": base_eff_span_y,
                        "max_span_x": max_x_span,
                        "max_span_y": max_y_span,
                        "span_ratio": span_ratio,
                        "slot_variation": slot_variation,
                        "center_offset": center_offset,
                        "area_occupancy": area_occupancy,
                        "top_gap": top_gap,
                        "carton_top_air_gap": carton_top_air_gap,
                        "min_slot_reserve_x": fit_margin["min_slot_reserve_x"],
                        "min_slot_reserve_y": fit_margin["min_slot_reserve_y"],
                        "esd_headroom_x_per_side": fit_margin["esd_headroom_x_per_side"],
                        "esd_headroom_y_per_side": fit_margin["esd_headroom_y_per_side"],
                        "esd_headroom_per_side": fit_margin["esd_headroom_per_side"],
                        "max_esd_per_side_current_layout": fit_margin["max_esd_per_side_current_layout"],
                        "fit_margin_status": fit_margin["fit_margin_status"],
                        "fit_margin_note": fit_margin["fit_margin_note"],
                        "limiting_floor_direction": fit_margin["limiting_floor_direction"],
                    }
                    options.append(option)

    debug = {
        "rejected_topology": rejected_topology,
        "rejected_span": rejected_span,
        "rejected_fit": rejected_fit,
        "rejected_height": rejected_height,
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
        opt.get("variant_priority", 0),
        -opt["vert_h"],
        opt["qty_layer"],
        -opt.get("local_peak_compression_required", 0.0),
        -opt.get("package_protrusion", 0.0),
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
            opt.get("partition_variant_id", "legacy"),
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
    system = get_partition_system_for_option(opt)
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

    system = get_partition_system_for_option(opt)
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

    # Groove edge ticks remain visible even when a red active partition line
    # completely covers the green dotted groove reference.
    tick = 7
    for x in groove_x:
        px = pad_x + x * scale
        y0 = pad_y + y_start_pad * scale
        svg += (
            f'<line x1="{px}" y1="{y0-tick}" x2="{px}" y2="{y0-1}" '
            f'stroke="#16a34a" stroke-width="2.2" />'
        )
    for y in groove_y:
        py = pad_y + y * scale
        x0 = pad_x + x_start_pad * scale
        svg += (
            f'<line x1="{x0-tick}" y1="{py}" x2="{x0-1}" y2="{py}" '
            f'stroke="#16a34a" stroke-width="2.2" />'
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

    is_auto_folded = "Auto Feasibility" in opt.get("esd_fit_model", "")
    if is_auto_folded:
        # Show the engineering TRIAL envelope, not the 0-mm candidate-generation
        # envelope. Cap at company nominal when the grid allows more than nominal.
        visual_allowance = min(
            opt["nominal_esd_per_side"],
            max(0.0, opt["max_esd_per_side_current_layout"]),
        )
        visual_envelope_label = "Auto Folded-Bag Trial Envelope"
    else:
        visual_allowance = opt["effective_esd_per_side"]
        visual_envelope_label = "Packed Fit Envelope"

    env_w = (opt["p_l_disp"] + 2.0 * visual_allowance) * scale
    env_h = (opt["p_w_disp"] + 2.0 * visual_allowance) * scale

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
        f'fill="#475569" text-anchor="middle">Red = Active Partition • Green dotted = Available Groove • Green edge ticks = All Groove Positions • Blue dashed = {visual_envelope_label}</text>'
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
    pure_prod_h_px = opt["p_h_disp"] * scale_y
    nominal_unit_h_px = opt["packed_unit_height"] * scale_y
    local_unit_h_px = opt["local_peak_unit_height"] * scale_y
    layer_pitch_px = opt["layer_pitch"] * scale_y
    pad_t_px = PAD_T * scale_y

    base_total = opt["base_bag_vertical_build_up"]
    base_each = base_total / 2.0
    base_each_px = base_each * scale_y
    mouth_px = opt["mouth_fold_vertical_build_up"] * scale_y
    side_local_px = opt["side_fold_local_build_up"] * scale_y
    clearance_px = opt["vertical_clearance"] * scale_y

    system = get_partition_system_for_option(opt)
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
        f'font-weight="700" fill="#0f172a" text-anchor="middle">'
        f'SIDE SECTION — {opt.get("bag_folding_method","Bag Packing")}</text>'
    )

    svg += (
        f'<rect x="{pad_x}" y="{pad_y}" width="{CARTON_L*scale_x}" height="{box_h}" '
        f'fill="#f8fafc" stroke="#1e293b" stroke-width="4" rx="4" />'
    )

    for layer_idx in range(opt["layers"]):
        level_bottom = (
            pad_y
            + box_h
            - layer_idx * (layer_pitch_px + pad_t_px)
            - pad_t_px
        )

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
            step_x = slot_span * scale_x / qty_x
            slot_start_px = pad_x + slot_left * scale_x

            for kx in range(qty_x):
                cx = slot_start_px + kx * step_x + step_x / 2
                rx = cx - product_w_px / 2

                for kz in range(qty_z):
                    unit_bottom = level_bottom - nominal_unit_h_px * kz
                    nominal_top = unit_bottom - nominal_unit_h_px
                    local_top = unit_bottom - local_unit_h_px

                    # Nominal packed envelope.
                    svg += (
                        f'<rect x="{rx}" y="{nominal_top}" width="{product_w_px}" '
                        f'height="{nominal_unit_h_px}" fill="#dbeafe" fill-opacity="0.18" '
                        f'stroke="#2563eb" stroke-width="1.1" stroke-dasharray="4,3" rx="3" />'
                    )

                    # Local side-fold peak envelope.
                    if side_local_px > 0:
                        local_band_w = max(12.0, product_w_px * 0.42)
                        local_x = cx - local_band_w / 2
                        svg += (
                            f'<rect x="{local_x}" y="{local_top}" width="{local_band_w}" '
                            f'height="{local_unit_h_px}" fill="none" '
                            f'stroke="#7c3aed" stroke-width="1.2" stroke-dasharray="3,3" rx="3" />'
                        )

                    # Bottom base bag layer.
                    if base_each_px > 0:
                        svg += (
                            f'<rect x="{rx+1}" y="{unit_bottom-base_each_px}" width="{max(2,product_w_px-2)}" '
                            f'height="{base_each_px}" fill="#bfdbfe" fill-opacity="0.75" stroke="#60a5fa" stroke-width="0.5" />'
                        )

                    # Pure product.
                    product_bottom = unit_bottom - base_each_px
                    product_top = product_bottom - pure_prod_h_px
                    svg += (
                        f'<rect x="{rx+1}" y="{product_top}" width="{max(2,product_w_px-2)}" '
                        f'height="{pure_prod_h_px}" fill="#fed7aa" stroke="#ea580c" stroke-width="1.1" rx="3" />'
                    )

                    # Top base bag layer.
                    top_base_y = product_top - base_each_px
                    if base_each_px > 0:
                        svg += (
                            f'<rect x="{rx+1}" y="{top_base_y}" width="{max(2,product_w_px-2)}" '
                            f'height="{base_each_px}" fill="#bfdbfe" fill-opacity="0.75" stroke="#60a5fa" stroke-width="0.5" />'
                        )

                    # Mouth fold = full-width extra layer over the product.
                    mouth_y = top_base_y - mouth_px
                    if mouth_px > 0:
                        svg += (
                            f'<rect x="{rx+2}" y="{mouth_y}" width="{max(2,product_w_px-4)}" '
                            f'height="{mouth_px}" fill="#93c5fd" fill-opacity="0.8" '
                            f'stroke="#2563eb" stroke-width="0.6" />'
                        )

                    # Side fold = LOCAL peak only, narrower than full product width.
                    if side_local_px > 0:
                        side_w = max(12.0, product_w_px * 0.42)
                        side_x = cx - side_w / 2
                        side_y = mouth_y - side_local_px
                        svg += (
                            f'<rect x="{side_x}" y="{side_y}" width="{side_w}" '
                            f'height="{side_local_px}" fill="#c4b5fd" fill-opacity="0.85" '
                            f'stroke="#7c3aed" stroke-width="0.7" rx="2" />'
                        )

                    # Optional engineering clearance shown above nominal package.
                    if clearance_px > 0:
                        svg += (
                            f'<line x1="{rx}" y1="{nominal_top}" x2="{rx+product_w_px}" y2="{nominal_top}" '
                            f'stroke="#0f766e" stroke-width="0.8" stroke-dasharray="2,2" />'
                        )

        # Right-side partition/local peak annotation.
        gx = pad_x + (x_end_pad - 18) * scale_x
        nominal_stack_top = level_bottom - opt["packed_stack_height"] * scale_y
        local_stack_top = level_bottom - opt["local_peak_stack_height"] * scale_y

        if opt["package_protrusion"] > 0:
            svg += (
                f'<text x="{gx+5}" y="{partition_top+12}" '
                f'font-family="system-ui,sans-serif" font-size="9.5" font-weight="700" fill="#b45309">'
                f'Nominal above partition: {fmt_num(opt["package_protrusion"])} mm</text>'
            )

        if opt["local_peak_package_protrusion"] > 0:
            svg += (
                f'<line x1="{gx}" y1="{partition_top}" x2="{gx}" y2="{local_stack_top}" '
                f'stroke="#7c3aed" stroke-width="1.2" stroke-dasharray="3,3" />'
            )
            svg += (
                f'<text x="{gx+5}" y="{max(pad_y+12, local_stack_top+10)}" '
                f'font-family="system-ui,sans-serif" font-size="9.5" font-weight="700" fill="#6d28d9">'
                f'Local peak above partition: {fmt_num(opt["local_peak_package_protrusion"])} mm</text>'
            )

    top_pad_y = (
        pad_y
        + box_h
        - opt["layers"] * (layer_pitch_px + pad_t_px)
        - pad_t_px
    )
    svg += (
        f'<rect x="{pad_x+x_start_pad*scale_x}" y="{top_pad_y}" width="{envelope_w*scale_x}" '
        f'height="{pad_t_px}" fill="#cbd5e1" stroke="#94a3b8" />'
    )

    gap_px = max(0.0, opt["carton_top_air_gap"]) * scale_y
    if gap_px > 0:
        svg += (
            f'<rect x="{pad_x+x_start_pad*scale_x}" y="{pad_y}" '
            f'width="{envelope_w*scale_x}" height="{gap_px}" '
            f'fill="#f1f5f9" opacity="0.7" stroke="#94a3b8" stroke-dasharray="4,4" />'
        )

    svg += (
        f'<text x="{view_w/2}" y="{pad_y+max(16,gap_px/2+4)}" '
        f'font-family="system-ui,sans-serif" font-size="11" font-weight="700" '
        f'fill="#64748b" text-anchor="middle">Nominal Carton Top Air Gap: '
        f'{fmt_num(opt["carton_top_air_gap"])} mm</text>'
    )

    summary_y = view_h - 18
    svg += (
        f'<text x="{view_w/2}" y="{summary_y}" font-family="system-ui,sans-serif" '
        f'font-size="10.2" fill="#475569" text-anchor="middle">'
        f'Nominal packed H = {fmt_num(opt["packed_unit_height"])} mm • '
        f'Local max H = {fmt_num(opt["local_peak_unit_height"])} mm • '
        f'Base {fmt_num(opt["base_bag_vertical_build_up"])} + '
        f'Mouth {fmt_num(opt["mouth_fold_vertical_build_up"])} + '
        f'Side-local {fmt_num(opt["side_fold_local_build_up"])} mm</text>'
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
    short_name = opt.get("short_partition_name", f"PARTITION {htxt}×393")
    long_name = opt.get("long_partition_name", f"PARTITION {htxt}×584")

    return [
        {
            "name": "Master Carton A10",
            "qty": "1 Pc",
            "spec": f"OD {fmt_num(CARTON_OD_L)}×{fmt_num(CARTON_OD_W)}×{fmt_num(CARTON_OD_H)} mm | ID {fmt_num(CARTON_L)}×{fmt_num(CARTON_W)}×{fmt_num(CARTON_H)} mm",
        },
        {
            "name": f"Short Partition — {short_name}",
            "qty": f"{opt['short_dividers_per_layer'] * layers} Pcs",
            "spec": f"{opt['short_dividers_per_layer']} sheet(s) / partition layer × {layers} layer(s)",
        },
        {
            "name": f"Long Partition — {long_name}",
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
        + badge(opt.get("long_partition_name", "Long partition"), "info")
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
    c6.metric("Nominal Packed H", f"{fmt_num(opt['packed_unit_height'])} mm")
    c7.metric("Local Max Fold H", f"{fmt_num(opt['local_peak_unit_height'])} mm")
    c8.metric("Nominal Carton Top Gap", f"{fmt_num(opt['carton_top_air_gap'])} mm")

    vh1, vh2, vh3, vh4 = st.columns(4)
    vh1.metric("Base Bag Build-up", f"{fmt_num(opt['base_bag_vertical_build_up'])} mm")
    vh2.metric("Mouth Fold Build-up", f"{fmt_num(opt['mouth_fold_vertical_build_up'])} mm")
    vh3.metric("Side Fold Local Peak", f"{fmt_num(opt['side_fold_local_build_up'])} mm")
    vh4.metric("Layer Pitch", f"{fmt_num(opt['layer_pitch'])} mm")

    st.caption(f"Folding method: **{opt.get('bag_folding_method','-')}**")

    if opt["package_protrusion"] > 0:
        st.warning(
            "⚠️ **Nominal packed package is taller than the partition** — "
            f"nominal stack exceeds the {fmt_num(opt['part_height'])} mm partition by "
            f"**{fmt_num(opt['package_protrusion'])} mm**. "
            "Upper paper pad may bear on bag/product; confirm compression / load path."
        )

    if opt["local_peak_package_protrusion"] > opt["package_protrusion"] + 0.01:
        st.warning(
            "⚠️ **Local fold peak is higher than nominal package height** — "
            f"local peak exceeds the partition by **{fmt_num(opt['local_peak_package_protrusion'])} mm**. "
            "This is a localized side-fold condition, not a full-area layer height."
        )

    if opt["local_peak_compression_required"] > 0:
        st.warning(
            "⚠️ **Local Peak Compression / Staggering Required** — "
            f"if the local side-fold peaks align vertically through every layer, the theoretical local stack "
            f"would exceed Carton A10 ID height by **{fmt_num(opt['local_peak_compression_required'])} mm**. "
            "Because the peak is localized/compressible, the layout is not auto-rejected, but a physical packing trial is mandatory."
        )
    else:
        st.info(
            "✅ Local fold peak remains within the nominal Carton A10 height envelope "
            f"(local-peak top gap ≈ {fmt_num(opt['local_peak_carton_gap'])} mm)."
        )

    st.caption(
        f"Up-axis model: Product {fmt_num(opt['p_h_disp'])} + "
        f"Base enclosure {fmt_num(opt['base_bag_vertical_build_up'])} + "
        f"Mouth fold {fmt_num(opt['mouth_fold_vertical_build_up'])} = "
        f"Nominal packed H {fmt_num(opt['packed_unit_height'])} mm; "
        f"+ Side-fold local peak {fmt_num(opt['side_fold_local_build_up'])} = "
        f"Local max H {fmt_num(opt['local_peak_unit_height'])} mm."
    )

    # --------------------------------------------------------
    # V0.1.5.3.1 — MODEL-AWARE FIT MARGIN / FOLDED-BAG FEASIBILITY
    # --------------------------------------------------------
    is_auto_folded = "Auto Feasibility" in opt.get("esd_fit_model", "")
    is_verified_folded = "Verified by Trial" in opt.get("esd_fit_model", "")

    if is_auto_folded:
        folded_limit = max(0.0, opt["max_esd_per_side_current_layout"])
        nominal = opt["nominal_esd_per_side"]
        reduction_required = max(0.0, nominal - folded_limit)

        fm1, fm2, fm3, fm4 = st.columns(4)
        fm1.metric("Min Slot Reserve X", f"{fmt_num(opt['min_slot_reserve_x'])} mm")
        fm2.metric("Min Slot Reserve Y", f"{fmt_num(opt['min_slot_reserve_y'])} mm")
        fm3.metric("Required Folded Bag ≤", f"{fmt_num(folded_limit)} mm/side")
        fm4.metric("Reduction vs Nominal", f"{fmt_num(reduction_required)} mm/side")

        if folded_limit + 1e-9 >= nominal:
            st.success(
                "✅ **Folded-Bag Feasibility PASS against nominal reference** — "
                f"the selected layout/capacity geometrically allows an effective folded-bag allowance up to "
                f"**{fmt_num(folded_limit)} mm/side**, which is not tighter than the company nominal "
                f"**{fmt_num(nominal)} mm/side**."
            )
        elif folded_limit > 0.01:
            st.warning(
                "⚠️ **RFQ Trial Target — Folded / Compressible Bag** — "
                f"to keep **{opt['qty_box']} pcs/A10** with this partition grid, the actual bag after folding/compression "
                f"must fit within **≤ {fmt_num(folded_limit)} mm/side effective lateral allowance** "
                f"(nominal company reference = {fmt_num(nominal)} mm/side). "
                f"Required reduction from the nominal rigid-envelope assumption = at least "
                f"**{fmt_num(reduction_required)} mm/side**. "
                "Confirm with sample / packing trial before release."
            )
        else:
            st.error(
                "❌ **Auto Feasibility is at zero nominal reserve** — "
                "this selected capacity requires the folded package to be essentially at the pure-product footprint "
                "in the limiting direction. Treat as high-risk until a physical packing trial proves it."
            )

        st.caption(
            "Auto Feasibility does NOT claim that the ESD bag material is this thin. "
            "It back-calculates the maximum effective lateral footprint growth that the selected grid can tolerate."
        )

    else:
        fm1, fm2, fm3, fm4 = st.columns(4)
        fm1.metric("Min Slot Reserve X", f"{fmt_num(opt['min_slot_reserve_x'])} mm")
        fm2.metric("Min Slot Reserve Y", f"{fmt_num(opt['min_slot_reserve_y'])} mm")
        fm3.metric("ESD Headroom / Side", f"{fmt_num(opt['esd_headroom_per_side'])} mm")
        fm4.metric(
            "Selected-Layout ESD Limit",
            f"{fmt_num(opt['max_esd_per_side_current_layout'])} mm/side",
        )

        if is_verified_folded:
            verified_margin = (
                opt["max_esd_per_side_current_layout"] - opt["effective_esd_per_side"]
            )
            if verified_margin < -0.01:
                st.error(
                    "❌ Verified folded-bag allowance exceeds the selected-layout nominal limit."
                )
            elif verified_margin <= 0.50:
                st.warning(
                    "⚠️ **Verified Folded-Bag Fit is tight** — "
                    f"verified effective allowance = **{fmt_num(opt['effective_esd_per_side'])} mm/side**; "
                    f"selected-layout nominal limit = **{fmt_num(opt['max_esd_per_side_current_layout'])} mm/side**."
                )
            else:
                st.success(
                    "✅ **Verified Folded-Bag Fit PASS** — "
                    f"verified effective allowance = **{fmt_num(opt['effective_esd_per_side'])} mm/side**; "
                    f"remaining nominal headroom = **{fmt_num(verified_margin)} mm/side**."
                )
        else:
            if opt["fit_margin_status"] == "CRITICAL":
                st.warning(
                    "⚠️ **Critical Fit / Zero Lateral Reserve** — "
                    f"current packed footprint uses the selected slot capacity at its nominal limit "
                    f"(limiting direction: {opt['limiting_floor_direction']}). "
                    f"Current solver fit allowance = **{fmt_num(opt['effective_esd_per_side'])} mm/side**; "
                    f"the current selected grid/capacity limit is approximately "
                    f"**{fmt_num(opt['max_esd_per_side_current_layout'])} mm/side**. "
                    "Increasing beyond this point may reduce capacity or force a different partition grid."
                )
            elif opt["fit_margin_status"] == "TIGHT":
                st.warning(
                    "⚠️ **Tight Fit Margin** — "
                    f"only **{fmt_num(opt['esd_headroom_per_side'])} mm/side** nominal ESD headroom remains "
                    f"before the current selected grid/capacity reaches its next fit breakpoint "
                    f"(limiting direction: {opt['limiting_floor_direction']})."
                )
            else:
                st.info(
                    "✅ **Fit Margin Available** — "
                    f"minimum nominal ESD headroom = **{fmt_num(opt['esd_headroom_per_side'])} mm/side**; "
                    f"current selected grid/capacity remains geometrically valid up to approximately "
                    f"**{fmt_num(opt['max_esd_per_side_current_layout'])} mm/side**."
                )

        st.caption(
            "Fit Margin is nominal geometry screening only; product tolerance, ESD bag forming variation, "
            "partition die-cut tolerance and assembly deformation are not included."
        )

    st.caption(
        f"Solver lateral footprint: {fmt_num(opt['target_w'])} × {fmt_num(opt['target_l'])} mm • "
        f"Pure partition-required H: {fmt_num(opt['target_h'])} mm • "
        f"Nominal packed H: {fmt_num(opt['packed_unit_height'])} mm • "
        f"Local max H: {fmt_num(opt['local_peak_unit_height'])} mm • "
        f"Grid: {len(opt['x_dividers'])-1} × {len(opt['y_dividers'])-1} cells • "
        f"Max span X/Y: {fmt_num(opt['max_span_x'])} / {fmt_num(opt['max_span_y'])} mm • "
        f"Base guardrail X/Y: {fmt_num(opt['base_eff_span_x'])} / {fmt_num(opt['base_eff_span_y'])} mm • "
        f"Effective guardrail X/Y: {fmt_num(opt['eff_span_x'])} / {fmt_num(opt['eff_span_y'])} mm • "
        f"Min complete-grid requirement X/Y: "
        f"{fmt_num(opt['min_complete_grid_span_x']) if opt['min_complete_grid_span_x'] is not None else 'N/A'} / "
        f"{fmt_num(opt['min_complete_grid_span_y']) if opt['min_complete_grid_span_y'] is not None else 'N/A'} mm"
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
        esd_allowance_per_side,
        solver_esd_allowance_per_side,
        esd_fit_model,
        bag_folding_method,
        base_bag_vertical_build_up,
        mouth_fold_vertical_build_up,
        side_fold_local_build_up,
        nominal_bag_vertical_build_up,
        local_bag_vertical_build_up,
        vertical_clearance,
        packing_mode,
        slot_limit_basis,
        max_pcs_axis,
        max_total_pcs_slot,
        max_slot_span,
        span_mode,
        allow_l_up,
        allow_w_up,
        GEOMETRY_SIGNATURE,
        SOLVER_LOGIC_SIGNATURE,
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
    f"{APP_VERSION} • {MODULE_NAME} — AMW Mouth + Side Fold Default + Real Folding Method Model + Local Peak Screening"
)
st.caption(
    "Geometry Sync Guard: active red partition lines are validated against the current audited green groove centerlines before ranking/rendering."
)

st.subheader("📦 Carton A10 Working Condition")
wc1, wc2, wc3, wc4, wc5, wc6 = st.columns(6)
wc1.metric("Carton A10 ID", f"{int(CARTON_L)} × {int(CARTON_W)} × {int(CARTON_H)} mm")
wc2.metric("Pure Product", f"{fmt_num(p_w)} × {fmt_num(p_l)} × {fmt_num(p_h)} mm")
wc3.metric("Nominal ESD", f"{fmt_num(esd_allowance_per_side)} mm / side")
wc4.metric(
    "Solver Lateral Fit",
    "AUTO" if "Auto Feasibility" in esd_fit_model else f"{fmt_num(solver_esd_allowance_per_side)} mm / side",
)
wc5.metric("H-Up Nominal H", f"{fmt_num(effective_product_h)} mm")
wc6.metric("H-Up Local Max H", f"{fmt_num(effective_local_peak_h)} mm")

st.info(
    f"**Normal H-Up Effective Condition:** Solver footprint {fmt_num(effective_product_w)} × "
    f"{fmt_num(effective_product_l)} mm • Nominal packed H {fmt_num(effective_product_h)} mm • "
    f"Local max fold H {fmt_num(effective_local_peak_h)} mm. "
    f"Folding method = **{bag_folding_method}**. "
    + (
        "Auto RFQ uses pure footprint for lateral candidate generation, then back-calculates the folded lateral trial target."
        if "Auto Feasibility" in esd_fit_model
        else f"Lateral solver adds +{fmt_num(total_esd_allowance)} mm per floor dimension."
    )
)

allowed_txt = ["H-Up"]
if allow_l_up:
    allowed_txt.append("L-Up")
if allow_w_up:
    allowed_txt.append("W-Up")
st.info("Allowed Product Orientation: **" + ", ".join(allowed_txt) + "**")

st.caption(
    "V0.1.5.3.1 keeps the real folding workflow and makes Mouth + Side Fold — AMW Standard the recommended default. "
    "Mouth Fold Only remains available as a special-case option when the bag size is already close to the product footprint."
)

st.divider()

# ============================================================
# ADAPTIVE RECOMMENDATION UI
# ============================================================
if not options:
    st.error(
        "❌ ไม่พบ layout ที่ผ่าน Product Fit + Partition Topology + Structural Span + Carton Height กรุณาตรวจสอบ Product Dimension, ESD/Bag Build-up, Vertical Clearance หรือ Span Guardrail"
    )

    allowed_reqs = [r for r in debug.get("span_requirements", []) if r.get("allowed")]
    diag = next((r for r in allowed_reqs if r.get("up_axis") == "H"), allowed_reqs[0] if allowed_reqs else None)
    if diag is not None:
        req_x = diag.get("min_complete_grid_span_x")
        req_y = diag.get("min_complete_grid_span_y")
        if req_x is None or req_y is None:
            st.warning(
                f"Complete-grid diagnostic — {diag['up_axis']}-Up / {diag.get('partition_variant_label','partition variant')} has no groove-subset grid where every cell fits the packed footprint and the topology remains valid."
            )
        elif span_mode.startswith("Dynamic"):
            st.info(
                f"Dynamic diagnostic — minimum complete-grid max span for {diag['up_axis']}-Up is "
                f"X/Y = {fmt_num(req_x)} / {fmt_num(req_y)} mm; effective Dynamic guardrail = "
                f"{fmt_num(diag['eff_span_x'])} / {fmt_num(diag['eff_span_y'])} mm."
            )

    if span_mode == "Strict":
        allowed_reqs = [r for r in debug.get("span_requirements", []) if r.get("allowed")]
        if allowed_reqs:
            # Prefer H-Up diagnostic because it is the normal engineering reference.
            diag = next((r for r in allowed_reqs if r.get("up_axis") == "H"), allowed_reqs[0])
            req_x = diag.get("min_complete_grid_span_x")
            req_y = diag.get("min_complete_grid_span_y")
            if req_x is not None and req_y is not None:
                st.info(
                    f"Strict diagnostic — minimum complete-grid max span for {diag['up_axis']}-Up is "
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
                    "Long Partition Variant": opt.get("long_partition_name", ""),
                    "Folding Method": opt.get("bag_folding_method", ""),
                    "ESD Fit Model": "Folded" if opt.get("esd_fit_model", "").startswith("Folded") else "Standard",
                    "Slot Limit": (
                        f"Total {opt.get('max_total_pcs_per_slot', 1)} pcs/slot"
                        if opt.get("slot_limit_basis", "").startswith("Max Total")
                        else opt.get("slot_limit_basis", "")
                    ),
                    "Grid": f"{len(opt['x_dividers'])-1}×{len(opt['y_dividers'])-1}",
                    "Base Slots/Layer": opt["base_slots_layer"],
                    "Pcs/Layer": opt["qty_layer"],
                    "Layers": opt["layers"],
                    "Total Pcs/A10": opt["qty_box"],
                    "Short Part./Layer": opt["short_dividers_per_layer"],
                    "Long Part./Layer": opt["long_dividers_per_layer"],
                    "Max Span X": round(opt["max_span_x"], 1),
                    "Max Span Y": round(opt["max_span_y"], 1),
                    "Min Reserve X": round(opt["min_slot_reserve_x"], 2),
                    "Min Reserve Y": round(opt["min_slot_reserve_y"], 2),
                    "ESD Headroom/Side": round(opt["esd_headroom_per_side"], 2),
                    "ESD Limit/Side": round(opt["max_esd_per_side_current_layout"], 2),
                    "Folded Trial Target ≤": (
                        round(opt["max_esd_per_side_current_layout"], 2)
                        if "Auto Feasibility" in opt.get("esd_fit_model", "")
                        else None
                    ),
                    "Reduction vs Nominal": (
                        round(max(0.0, opt["nominal_esd_per_side"] - opt["max_esd_per_side_current_layout"]), 2)
                        if "Auto Feasibility" in opt.get("esd_fit_model", "")
                        else None
                    ),
                    "Fit Status": opt["fit_margin_status"],
                    "Nominal Packed H": round(opt["packed_unit_height"], 1),
                    "Local Max H": round(opt["local_peak_unit_height"], 1),
                    "Partition Protrusion": round(opt["package_protrusion"], 1),
                    "Local Peak Protrusion": round(opt["local_peak_package_protrusion"], 1),
                    "Layer Pitch": round(opt["layer_pitch"], 1),
                    "Carton Top Gap": round(opt["carton_top_air_gap"], 1),
                    "Local Peak Top Gap": round(opt["local_peak_carton_gap"], 1),
                    "Local Compression Req.": round(opt["local_peak_compression_required"], 1),
                    "Height Util. %": round(opt["carton_height_utilization"], 1),
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
- **Bag Folding Method:** current method = **{bag_folding_method}**.
- **Standard Bag — No Fold:** lateral fit uses the full company nominal allowance; Up-axis includes one bubble layer below + one above the product.
- **Mouth Fold Only:** lateral layout uses Auto Feasibility; the mouth flap adds one extra bubble layer to the **nominal** packed height.
- **Mouth + Side Fold — AMW Standard:** follows the actual reference process `Insert → Mouth Fold → Side Fold`. The mouth fold is included in nominal packed height; the side fold is modeled as a **localized maximum peak**, not a full-area layer.
- **Auto Folded-Bag Feasibility (RFQ):** lateral candidate grids start from pure product footprint and the tool back-calculates the maximum effective folded lateral growth per side that preserves the selected grid/capacity.
- **Physical volume transfer:** folding reduces projected W/L excess but does not remove bag volume. Current base enclosure = **{fmt_num(base_bag_vertical_build_up)} mm**, mouth-fold build-up = **{fmt_num(mouth_fold_vertical_build_up)} mm**, side-fold local peak = **{fmt_num(side_fold_local_build_up)} mm**.
- **Nominal vs local height:** nominal full-area height is used for layer pitch / automatic carton-height pass-fail. Local side-fold peak is screened separately. If local peaks would exceed carton height when perfectly aligned, the tool reports required compression/staggering but does not auto-reject because the peak is localized and compressible.
- **Custom / Verified Packing:** use measured lateral allowance, nominal packed-height build-up and local maximum build-up from a physical packing trial.
- **Fit Margin / Critical Boundary:** each valid slot is checked for remaining X/Y reserve at the CURRENT selected capacity. The tool converts that reserve into additional allowable ESD mm/side and reports the approximate ESD limit before the current grid/capacity loses nominal fit.
- **Fit Margin limitation:** this is nominal geometry only; Product tolerance, ESD bag forming variation, partition die-cut tolerance and assembly deformation are not included.
- **Vertical / Top Clearance:** current value = **{fmt_num(vertical_clearance)} mm**. Partition protection height is referenced to **Pure Up-axis + Vertical Clearance**; physical carton-height screening separately adds base bag + fold build-up.
- **Slot Quantity Limit:** current basis = **{slot_limit_basis}**. In `Max Total Pcs / Slot` mode, an RFQ requirement such as **2 pcs/slot** is enforced as the maximum TOTAL floor quantity, avoiding the legacy 2×2=4 interpretation.
- **Stack-Fit vertical logic:** every stacked product uses its own vertical requirement (`pure Up-axis + vertical clearance`). In total-slot mode, the total floor limit is applied before the vertical stack factor.
- **Span Guardrail:** checked in every packing mode. **Dynamic** keeps the baseline but auto-relaxes only when the actual A10 groove pitch requires a larger minimum span to fit one packed product. **Strict** uses the baseline as a hard maximum. Current mode = **{span_mode}**; baseline = **{fmt_num(max_slot_span)} mm**.
- **Strength limitation:** the span check is a geometry-based engineering screening only; it is **not** BCT / ECT / compression-strength validation.
- **Partition Variant Auto-Select:** for 111-mm systems the solver evaluates both **111×584 Standard (5 grooves / 140-mm pitch)** and **111×584-01 (9 grooves / 70-mm pitch)** against the common 111×393 short partition.
- **Groove constrained:** candidate partition sheets are selected only from the audited Carton A10 groove coordinates of the selected die-cut variant.
- **BOM:** partition quantities follow the number of active short/long partition sheets per layer × packing layers.
- **Legacy Excel reference:** historical A10 configurations are being audited as validation references only; they are not treated as master logic or automatically imported into the solver.
        """
    )
    st.caption(
        f"Solver diagnostics: valid {debug['evaluated_valid']} • topology rejects {debug['rejected_topology']} • "
        f"fit rejects {debug['rejected_fit']} • span rejects {debug['rejected_span']} • "
        f"carton-height rejects {debug.get('rejected_height', 0)}"
    )
