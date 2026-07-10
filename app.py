import streamlit as st
import streamlit.components.v1 as components
import math
import itertools

# ตั้งค่าหน้าเว็บให้แสดงผลสวยงามเต็มจอ
st.set_page_config(
    page_title="Carton A10 Partition Optimizer (Heavy-Duty Multi-Pack)",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📦 Carton A10 Partition Optimizer (Heavy-Duty Multi-Pack)")
st.write("ระบบวิเคราะห์พาร์ติชันมาตรฐานและอสมมาตร เวอร์ชัน Sandbox เกรดอุตสาหกรรม ป้องกันการเกิด Segmentation Fault 100%")

# --- CONFIGURATION ENGINE ---
CARTON_L = 592.0
CARTON_W = 404.0
CARTON_H = 255.0

GROOVE_X_ALL = [13.5, 154.75, 296.0, 437.25, 578.5]
GROOVE_Y_ALL = [19.5, 65.125, 110.75, 156.375, 202.0, 247.625, 293.25, 338.875, 384.5]

# --- SIDEBAR INPUTS ---
st.sidebar.header("📐 1. ขนาดผลิตภัณฑ์ (Product Dimension)")
p_w = st.sidebar.number_input("ความกว้างชิ้นงาน (Width - W) (mm)", value=30.0, step=1.0)
p_l = st.sidebar.number_input("ความยาวชิ้นงาน (Length - L) (mm)", value=30.0, step=1.0)
p_h = st.sidebar.number_input("ความหนาชิ้นงาน (Height/Thickness - H) (mm)", value=50.0, step=1.0)

st.sidebar.header("🛡️ 2. ค่าเผื่อสล็อต (Clearance Margin)")
clearance = st.sidebar.slider("ระยะเผื่อช่อง/ความหนาถุง ESD (Clearance) (mm)", 1.0, 15.0, 5.0, step=0.5)

st.sidebar.header("🔄 3. เงื่อนไขการจัดวางในสล็อต (Slot Packing Rule)")
packing_mode = st.sidebar.selectbox(
    "รูปแบบการบรรจุภายในช่องพาร์ติชัน",
    options=[
        "มาตรฐาน (1 ช่อง ต่อ 1 ชิ้นชิ้นงาน เท่านั้น)",
        "วางเบียดกันในแนวราบได้ (Horizontal Multi-pack)",
        "วางเบียดแนวราบ + วางซ้อนทับกันในแกนตั้งได้ (Horizontal + Vertical Stack)"
    ],
    index=0
)

# --- SAFE MATRIX SOLVER ENGINE ---
def find_heavy_duty_layout(pw, pl, ph, mode):
    all_dims = [pw, pl, ph]
    unique_orientations = set(itertools.permutations(all_dims))
    
    orientations_3d = []
    for perm in unique_orientations:
        w_rot, l_rot, h_rot = perm
        is_fixed_h = (h_rot == ph)
        orientations_3d.append({
            "flat_w": w_rot,
            "flat_l": l_rot,
            "vert_h": h_rot,
            "label": f"{int(w_rot)} x {int(l_rot)} x {int(h_rot)}",
            "is_fixed_h": is_fixed_h
        })

    best_options = []
    
    # พรีเซตโครงกริดคงที่ตามร่องขัดจริงของกล่องกระดาษแผ่นนอก
    grid_presets = [
        {"ax": GROOVE_X_ALL, "ay": GROOVE_Y_ALL},
        {"ax": GROOVE_X_ALL, "ay": [19.5, 110.75, 202.0, 293.25, 384.5]},
        {"ax": GROOVE_X_ALL, "ay": [19.5, 202.0, 384.5]},
        {"ax": [13.5, 296.0, 578.5], "ay": GROOVE_Y_ALL},
        {"ax": [13.5, 296.0, 578.5], "ay": [19.5, 110.75, 202.0, 293.25, 384.5]},
        {"ax": [13.5, 296.0, 578.5], "ay": [19.5, 202.0, 384.5]}
    ]

    for orient in orientations_3d:
        ew = orient["flat_w"]
        el = orient["flat_l"]
        eh = orient["vert_h"]

        if eh + clearance <= 111.0:
            part_height = 111.0
            layers = 2
        elif eh + clearance <= 225.0:
            part_height = 225.0
            layers = 1
        else:
            continue

        target_w = ew + clearance
        target_l = el + clearance

        stack_multiplier = 1
        if "Vertical Stack" in mode:
            allowed_stack = math.floor((part_height - clearance) / eh)
            if allowed_stack > 1:
                stack_multiplier = allowed_stack

        for preset in grid_presets:
            x_bounds = sorted(preset["ax"])
            y_bounds = sorted(preset["ay"])

            valid_slots = []
            total_qty_in_layer = 0
            has_invalid_slot_in_grid = False

            for i in range(len(x_bounds) - 1):
                for j in range(len(y_bounds) - 1):
                    slot_w = x_bounds[i+1] - x_bounds[i]
                    slot_h = y_bounds[j+1] - y_bounds[j]

                    horiz_w_count = 0
                    horiz_l_count = 0
                    
                    if "มาตรฐาน" in mode:
                        if slot_w >= target_l and slot_h >= target_w:
                            horiz_w_count = 1
                            horiz_l_count = 1
                    else:
                        horiz_w_count = math.floor(slot_w / target_l)
                        horiz_l_count = math.floor(slot_h / target_w)

                    if horiz_w_count > 0 and horiz_l_count > 0:
                        items_in_this_slot = horiz_w_count * horiz_l_count * stack_multiplier
                        total_qty_in_layer += items_in_this_slot
                        
                        valid_slots.append({
                            "col_idx": i,
                            "row_idx": j,
                            "x_start": x_bounds[i],
                            "x_end": x_bounds[i+1],
                            "y_start": y_bounds[j],
                            "y_end": y_bounds[j+1],
                            "items_per_slot": items_in_this_slot,
                            "w_count": horiz_w_count,
                            "l_count": horiz_l_count,
                            "stack_count": stack_multiplier
                        })
                    else:
                        has_invalid_slot_in_grid = True

            if len(valid_slots) > 0 and not has_invalid_slot_in_grid:
                qty_box = total_qty_in_layer * layers

                best_options.append({
                    "qty_box": qty_box,
                    "qty_layer": total_qty_in_layer,
                    "layers": layers,
                    "part_height": part_height,
                    "ax": preset["ax"],
                    "ay": preset["ay"],
                    "x_bounds": [4.0] + preset["ax"] + [588.0],
                    "y_bounds": [5.5] + preset["ay"] + [398.5],
                    "valid_slots": valid_slots,
                    "orient_label": orient["label"],
                    "target_w": target_w,
                    "target_l": target_l,
                    "p_w_disp": ew,
                    "p_l_disp": el,
                    "p_h_disp": eh,
                    "total_dividers": len(preset["ax"]) + len(preset["ay"]),
                    "is_fixed_h": orient["is_fixed_h"],
                    "stack_multiplier": stack_multiplier
                })

    return best_options

options = find_heavy_duty_layout(p_w, p_l, p_h, packing_mode)

# --- SVG TOP VIEW GENERERATOR (SAFE FOR SANDBOX) ---
def draw_asymmetric_svg_string(opt):
    x_bounds = opt["x_bounds"]
    y_bounds = opt["y_bounds"]
    ax = opt["ax"]
    ay = opt["ay"]
    valid_slots = opt["valid_slots"]
    
    scale = 1.3
    pad_x = 40
    pad_y = 50
    
    view_w = (CARTON_L * scale) + (pad_x * 2)
    view_h = (CARTON_W * scale) + (pad_y * 2)
    
    svg = f'<svg width="{view_w}" height="{view_h}" viewBox="0 0 {view_w} {view_h}" xmlns="http://www.w3.org/2000/svg" style="background-color: #ffffff; font-family: system-ui, -apple-system, sans-serif;">'
    svg += f'<rect x="{pad_x}" y="{pad_y}" width="{CARTON_L * scale}" height="{CARTON_W * scale}" fill="#f8fafc" stroke="#1e293b" stroke-width="4" rx="6" />'
    svg += f'<text x="{pad_x + (CARTON_L * scale)/2}" y="{pad_y - 20}" font-size="18" font-weight="bold" fill="#0f172a" text-anchor="middle">TOP VIEW: CARTON A10 ({int(CARTON_L)}x{int(CARTON_W)} mm)</text>'
    
    svg += f'<rect x="{pad_x + 4.0*scale}" y="{pad_y + 5.5*scale}" width="{(584.0)*scale}" height="{(393.0)*scale}" fill="none" stroke="#94a3b8" stroke-dasharray="4,4" stroke-width="1.5" />'

    # แสดงเส้นไกด์ร่องขัดมาตรฐาน (เส้นประสีเขียว)
    for sx in GROOVE_X_ALL:
        cx = pad_x + (sx * scale)
        svg += f'<line x1="{cx}" y1="{pad_y + 5.5*scale}" x2="{cx}" y2="{pad_y + 398.5*scale}" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="3,3" />'
    for sy in GROOVE_Y_ALL:
        cy = pad_y + (sy * scale)
        svg += f'<line x1="{pad_x + 4.0*scale}" y1="{cy}" x2="{pad_x + 584.0*scale}" y2="{cy}" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="3,3" />'

    # แสดงชิ้นงาน PCBA จัดวาง Center สมมาตรกึ่งกลางสล็อตย่อย
    for slot in valid_slots:
        slot_w = slot["x_end"] - slot["x_start"]
        slot_h = slot["y_end"] - slot["y_start"]
        
        group_w = slot["w_count"] * opt["target_l"]
        group_h = slot["l_count"] * opt["target_w"]
        
        start_offset_x = slot["x_start"] + (slot_w - group_w) / 2
        start_offset_y = slot["y_start"] + (slot_h - group_h) / 2
        
        for wc in range(slot["w_count"]):
            for lc in range(slot["l_count"]):
                item_x = start_offset_x + (wc * opt["target_l"]) + (opt["target_l"] - opt["p_l_disp"])/2
                item_y = start_offset_y + (lc * opt["target_w"]) + (opt["target_w"] - opt["p_w_disp"])/2
                
                rect_x = pad_x + (item_x * scale)
                rect_y = pad_y + (item_y * scale)
                draw_w = opt["p_l_disp"] * scale
                draw_h = opt["p_w_disp"] * scale
                
                svg += f'<rect x="{rect_x}" y="{rect_y}" width="{draw_w}" height="{draw_h}" fill="#fed7aa" stroke="#ea580c" stroke-width="1.2" rx="3" />'
                
                mid_x = rect_x + (draw_w / 2)
                mid_y = rect_y + (draw_h / 2)
                if slot["stack_count"] > 1:
                    svg += f'<text x="{mid_x}" y="{mid_y + 3}" font-size="9" font-weight="bold" fill="#7c2d12" text-anchor="middle">x{slot["stack_count"]} Stack</text>'
                else:
                    svg += f'<text x="{mid_x}" y="{mid_y + 3}" font-size="8" font-weight="bold" fill="#7c2d12" text-anchor="middle">PCBA</text>'

    # แสดงแผ่นกั้นพาร์ติชัน (กริดสีแดงหนาเด่นชัด ไม่หายไม่ยุบโครงสร้าง)
    for vx in ax:
        cx = pad_x + (vx * scale)
        svg += f'<line x1="{cx}" y1="{pad_y + 5.5*scale}" x2="{cx}" y2="{pad_y + 398.5*scale}" stroke="#dc2626" stroke-width="4" stroke-linecap="round" />'
    for vy in ay:
        cy = pad_y + (vy * scale)
        svg += f'<line x1="{pad_x + 4.0*scale}" y1="{cy}" x2="{pad_x + 588.0*scale}" y2="{cy}" stroke="#dc2626" stroke-width="4" stroke-linecap="round" />'
            
    svg += '</svg>'
    return svg, view_w, view_h

# --- SVG SIDE VIEW GENERATOR (SAFE FOR SANDBOX) ---
def draw_side_view_svg_string(opt):
    scale_x = 1.3
    scale_y = 1.6
    pad_x = 40
    pad_y = 50
    
    view_w = (CARTON_L * scale_x) + (pad_x * 2)
    view_h = (CARTON_H * scale_y) + (pad_y * 2)
    
    box_h = CARTON_H * scale_y
    part_h = opt["part_height"] * scale_y
    prod_h = opt["p_h_disp"] * scale_y
    pad_thickness = 3.0 * scale_y
    
    svg = f'<svg width="{view_w}" height="{view_h}" viewBox="0 0 {view_w} {view_h}" xmlns="http://www.w3.org/2000/svg" style="background-color: #ffffff; font-family: system-ui, -apple-system, sans-serif;">'
    svg += f'<rect x="{pad_x}" y="{pad_y}" width="{CARTON_L * scale_x}" height="{box_h}" fill="#f8fafc" stroke="#1e293b" stroke-width="4" rx="4" />'
    svg += f'<text x="{pad_x + (CARTON_L * scale_x)/2}" y="{pad_y - 20}" font-size="18" font-weight="bold" fill="#0f172a" text-anchor="middle">SIDE VIEW: CARTON A10 (Height: {int(CARTON_H)} mm)</text>'
    
    for layer_idx in range(opt["layers"]):
        level_y_start = pad_y + box_h - (layer_idx * (part_h + pad_thickness)) - pad_thickness
        svg += f'<rect x="{pad_x + 4.0*scale_x}" y="{level_y_start}" width="{(584.0)*scale_x}" height="{pad_thickness}" fill="#cbd5e1" stroke="#94a3b8" />'
        
        partition_top_y = level_y_start - part_h
        for vx in opt["ax"]:
            cx = pad_x + (vx * scale_x)
            svg += f'<line x1="{cx}" y1="{level_y_start}" x2="{cx}" y2="{partition_top_y}" stroke="#dc2626" stroke-width="3" />'

    for layer_idx in range(opt["layers"]):
        level_y_start = pad_y + box_h - (layer_idx * (part_h + pad_thickness)) - pad_thickness
        x_bounds = opt["ax"]
        
        if len(x_bounds) >= 2:
            for b_idx in range(len(x_bounds)-1):
                slot_w = x_bounds[b_idx+1] - x_bounds[b_idx]
                
                target_slot = None
                for vs in opt["valid_slots"]:
                    if vs["col_idx"] == b_idx:
                        target_slot = vs
                        break
                
                if target_slot:
                    group_w = target_slot["w_count"] * opt["target_l"]
                    start_offset_x = x_bounds[b_idx] + (slot_w - group_w) / 2
                    
                    for st_idx in range(target_slot["stack_count"]):
                        rect_y = level_y_start - ((st_idx + 1) * prod_h)
                        
                        for wc in range(target_slot["w_count"]):
                            w_draw = opt["p_l_disp"] * scale_x
                            item_x = start_offset_x + (wc * opt["target_l"]) + (opt["target_l"] - opt["p_l_disp"])/2
                            rect_x = pad_x + (item_x * scale_x)
                            
                            svg += f'<rect x="{rect_x}" y="{rect_y}" width="{w_draw}" height="{prod_h}" fill="#fed7aa" stroke="#ea580c" stroke-width="1.5" rx="2" />'
                    
                    total_stacked_h = target_slot["stack_count"] * prod_h
                    top_gap = opt["part_height"] - (target_slot["stack_count"] * opt["p_h_disp"])
                    if top_gap > 0:
                        gap_line_x = pad_x + (x_bounds[b_idx+1] * scale_x) - 10
                        svg += f'<line x1="{gap_line_x}" y1="{level_y_start - total_stacked_h}" x2="{gap_line_x}" y2="{level_y_start - part_h}" stroke="#2563eb" stroke-width="1.2" stroke-dasharray="2,2" />'

    top_pad_y = pad_y + box_h - (opt["layers"] * (part_h + pad_thickness)) - pad_thickness
    svg += f'<rect x="{pad_x + 4.0*scale_x}" y="{top_pad_y}" width="{(584.0)*scale_x}" height="{pad_thickness}" fill="#cbd5e1" stroke="#94a3b8" />'
    
    remaining_box_air_gap = CARTON_H - ((opt["part_height"] + 3.0) * opt["layers"] + 3.0)
    if remaining_box_air_gap > 0:
        svg += f'<rect x="{pad_x + 4.0*scale_x}" y="{pad_y}" width="{(584.0)*scale_x}" height="{remaining_box_air_gap * scale_y}" fill="#f1f5f9" opacity="0.6" stroke="#babfc7" stroke-dasharray="4,4"/>'
    
    svg += '</svg>'
    return svg, view_w, view_h

def render_packing_list(opt):
    active_x_qty = len(opt["ax"])
    active_y_qty = len(opt["ay"])
    layers_count = opt["layers"]
    
    bom_items = [
        {"name": "กล่องกระดาษภายนอก (Master Carton A10)", "qty": "1 Pcs", "spec": "OD: 602x414x270 mm | ID: 592x404x255 mm"},
        {"name": f"แผ่นพาร์ติชันตัวสั้น (PARTITION {'111' if opt['part_height'] == 111.0 else '225'}x393)", "qty": f"{active_x_qty * layers_count} Pcs", "spec": f"ใช้จริง {active_x_qty} แผ่นกั้นแนวตั้งต่อชั้น"},
        {"name": f"แผ่นพาร์ติชันตัวยาว (PARTITION {'111' if opt['part_height'] == 111.0 else '225'}x584)", "qty": f"{active_y_qty * layers_count} Pcs", "spec": f"ใช้จริง {active_y_qty} แผ่นกั้นแนวนอนต่อชั้น"},
        {"name": "แผ่นกระดาษลูกฟูกรองขอบแบน (Corrugated Paper Pad)", "qty": f"{layers_count + 1} Pcs", "spec": "394 x 574 mm"},
        {"name": "ซองพลาสติกกันไฟฟ้าสถิตย์ (ESD Anti-Static Bag)", "qty": f"{opt['qty_box']} Pcs", "spec": f"ความจุรวมโมเดลจัดเรียง {opt['qty_box']} ชิ้นงานต่อกล่องมาสเตอร์"}
    ]
    for item in bom_items:
        st.markdown(f"""
        <div style="background-color: #f8fafc; border-left: 6px solid #1e293b; padding: 10px; border-radius: 6px; margin-bottom: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-weight: bold; font-size: 14px; color: #0f172a;">{item['name']}</div>
                    <div style="font-size: 11px; color: #64748b;">{item['spec']}</div>
                </div>
                <span style="background-color: #1e293b; color: white; padding: 3px 10px; border-radius: 12px; font-weight: bold; font-size: 12px;">{item['qty']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

# --- MAIN RENDER ---
if options:
    fixed_h_options = [o for o in options if o["is_fixed_h"]]
    fixed_h_options.sort(key=lambda x: (x["qty_box"], -x["total_dividers"]), reverse=True)
    overall_options = sorted(options, key=lambda x: (x["qty_box"], -x["total_dividers"]), reverse=True)
    
    best_fixed = fixed_h_options[0] if fixed_h_options else None
    best_overall = overall_options[0] if overall_options else None
    has_better_alternative = best_overall and best_fixed and (best_overall["qty_box"] > best_fixed["qty_box"])

    col1, col2 = st.columns(2)
    
    with col1:
        st.header("1️⃣ Fixed H Layout")
        if best_fixed:
            st.success(f"📌 **ทิศทางการจัดวาง:** {best_fixed['orient_label']}")
            m_col1, m_col2, m_col3 = st.columns(3)
            m_col1.metric("ความจุรวมในชั้น", f"{best_fixed['qty_layer']} Pcs")
            m_col2.metric("จำนวนชั้น (Layers)", f"{best_fixed['layers']} ชั้น")
            m_col3.metric("ความจุรวมทั้งหมด", f"{best_fixed['qty_box']} Pcs/Box")
            
            st.subheader("📋 รายการวัสดุบรรจุภัณฑ์ (BOM)")
            render_packing_list(best_fixed)
            
            st.subheader("📐 แผนผังมุมมองจากด้านบน (Top View)")
            svg_top, w_top, h_top = draw_asymmetric_svg_string(best_fixed)
            components.html(svg_top, width=w_top, height=h_top, scrolling=False)
            
            st.subheader("⏳ แผนผังมุมมองภาคตัดขวางด้านข้าง (Side View)")
            svg_side, w_side, h_side = draw_side_view_svg_string(best_fixed)
            components.html(svg_side, width=w_side, height=h_side, scrolling=False)
        else:
            st.error("❌ ไม่พบรูปแบบสำหรับอินพุตนี้")

    with col2:
        st.header("2️⃣ Alternative Option")
        if has_better_alternative:
            st.warning(f"🔥 **แนะนำเปลี่ยนทิศทางการวางเป็น:** {best_overall['orient_label']}")
            a_col1, a_col2, a_col3 = st.columns(3)
            a_col1.metric("ความจุรวมในชั้น", f"{best_overall['qty_layer']} Pcs", f"+{best_overall['qty_layer'] - best_fixed['qty_layer']} Pcs")
            a_col2.metric("จำนวนชั้น (Layers)", f"{best_overall['layers']} ชั้น")
            a_col3.metric("ความจุรวมทั้งหมด", f"{best_overall['qty_box']} Pcs/Box", f"+{best_overall['qty_box'] - best_fixed['qty_box']} Pcs")
            
            st.subheader("📋 รายการวัสดุบรรจุภัณฑ์ (BOM)")
            render_packing_list(best_overall)
            
            st.subheader("📐 แผนผังมุมมองจากด้านบน (Top View)")
            svg_top_a, w_top_a, h_top_a = draw_asymmetric_svg_string(best_overall)
            components.html(svg_top_a, width=w_top_a, height=h_top_a, scrolling=False)
            
            st.subheader("⏳ แผนผังมุมมองภาคตัดขวางด้านข้าง (Side View)")
            svg_side_a, w_side_a, h_side_a = draw_side_view_svg_string(best_overall)
            components.html(svg_side_a, width=w_side_a, height=h_side_a, scrolling=False)
        else:
            st.info("💡 **การประเมินวิศวกรรมเชิงลึก:** โครงสร้างความสูงอินพุตปัจจุบันทำงานได้ดีที่สุดแล้วในโหมดที่เลือก")

    st.write("---")
    st.subheader("📊 ตารางวิเคราะห์รูปแบบกริดและทิศทางการจัดวางที่เป็นไปได้ทั้งหมด")
    summary_table = []
    for idx, opt in enumerate(overall_options[:10]):
        summary_table.append({
            "อันดับความจุ": "🏆 ดีที่สุด (Optimal)" if idx == 0 else f"ทางเลือกที่ {idx+1}",
            "ทิศทางจัดวาง": opt["orient_label"],
            "เป็นแบบ Fixed H?": "✅ ใช่" if opt["is_fixed_h"] else "🔄 หมุน 3D (ทางเลือก)",
            "แผ่นแนวตั้งที่ใช้ (Short)": f"{len(opt['ax'])} Pcs",
            "แผ่นแนวนอนที่ใช้ (Long)": f"{len(opt['ay'])} Pcs",
            "ความจุรวม/กล่อง (Box Qty)": f"{opt['qty_box']} Pcs/Box"
        })
    # เปลี่ยนพารามิเตอร์ตารางเป็นแบบดั้งเดิมตามข้อกำหนดอัปเดตเวอร์ชันของไลบรารีปัจจุบัน
    st.dataframe(summary_table, width=1500)
else:
    st.error("❌ ไม่พบรูปแบบพาร์ติชันตามขนาดโครงสร้างคงที่ที่ป้อนได้ กรุณาปรับมิติชิ้นงานหรือค่าเผื่อสล็อตให้เหมาะสม")
