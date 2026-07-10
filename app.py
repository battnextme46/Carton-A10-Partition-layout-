import streamlit as st
import math
import itertools

# ตั้งค่าหน้าเว็บให้แสดงผลสวยงามเต็มจอ
st.set_page_config(
    page_title="Carton A10 Partition Optimizer",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📦 Auto-Select Partition Layout Design with Carton A10")
st.write("ระบบวิเคราะห์และคัดเลือกพาร์ติชันแบบอสมมาตร ตามพิกัดร่องขัดจริงโดยคำนึงถึงขอบกันชนรอบกล่อง (Fully Enclosed Slots) พร้อมระบบจำลอง Side View")

# --- CONFIGURATION ENGINE (พิกัดร่องขัดพาร์ติชันมาตรฐานกระดาษ) ---
CARTON_L = 592.0
CARTON_W = 404.0
CARTON_H = 255.0

GROOVE_X_ALL = [13.5, 154.75, 296.0, 437.25, 578.5]
GROOVE_Y_ALL = [19.5, 65.125, 110.75, 156.375, 202.0, 247.625, 293.25, 338.875, 384.5]

# --- SIDEBAR INPUTS ---
st.sidebar.header("📐 1. ขนาดผลิตภัณฑ์ (Product Dimension)")
p_w = st.sidebar.number_input("ความกว้างชิ้นงาน (Width - W) (mm)", value=25.0, step=1.0)
p_l = st.sidebar.number_input("ความยาวชิ้นงาน (Length - L) (mm)", value=200.0, step=1.0)
p_h = st.sidebar.number_input("ความหนาชิ้นงาน (Height/Thickness - H) (mm)", value=160.0, step=1.0)

st.sidebar.header("🛡️ 2. ค่าเผื่อสล็อต (Clearance Margin)")
clearance = st.sidebar.slider("ระยะเผื่อช่อง/ความหนาถุง ESD (Clearance) (mm)", 1.0, 15.0, 5.0, step=0.5)

# --- DYNAMIC SOLVER ENGINE ---
def find_asymmetric_optimal_layout(pw, pl, ph):
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

    subsets_x = []
    for r in range(2, len(GROOVE_X_ALL) + 1):
        for comb in itertools.combinations(GROOVE_X_ALL, r):
            subsets_x.append(sorted(list(comb)))

    subsets_y = []
    for r in range(2, len(GROOVE_Y_ALL) + 1):
        for comb in itertools.combinations(GROOVE_Y_ALL, r):
            subsets_y.append(sorted(list(comb)))
            
    unique_subsets_y = []
    y_presets = [
        GROOVE_Y_ALL, 
        [19.5, 110.75, 202.0, 293.25, 384.5], 
        [19.5, 202.0, 384.5], 
    ]
    for s in y_presets + subsets_y:
        s_sorted = sorted(s)
        if s_sorted not in unique_subsets_y and len(s_sorted) >= 2:
            unique_subsets_y.append(s_sorted)

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

        for ax in subsets_x:
            for ay in unique_subsets_y:
                x_bounds = sorted(ax)
                y_bounds = sorted(ay)

                valid_slots = []
                for i in range(len(x_bounds) - 1):
                    for j in range(len(y_bounds) - 1):
                        slot_w = x_bounds[i+1] - x_bounds[i]
                        slot_h = y_bounds[j+1] - y_bounds[j]

                        if slot_w >= target_l and slot_h >= target_w:
                            valid_slots.append({
                                "col_idx": i,
                                "row_idx": j,
                                "x_start": x_bounds[i],
                                "x_end": x_bounds[i+1],
                                "y_start": y_bounds[j],
                                "y_end": y_bounds[j+1]
                            })

                if len(valid_slots) > 0:
                    qty_layer = len(valid_slots)
                    qty_box = qty_layer * layers

                    best_options.append({
                        "qty_box": qty_box,
                        "qty_layer": qty_layer,
                        "layers": layers,
                        "part_height": part_height,
                        "ax": ax,
                        "ay": ay,
                        "x_bounds": [4.0] + ax + [588.0],
                        "y_bounds": [5.5] + ay + [398.5],
                        "valid_slots": valid_slots,
                        "orient_label": orient["label"],
                        "target_w": target_w,
                        "target_l": target_l,
                        "p_w_disp": ew,
                        "p_l_disp": el,
                        "p_h_disp": eh,
                        "total_dividers": len(ax) + len(ay),
                        "is_fixed_h": orient["is_fixed_h"]
                    })

    return best_options

options = find_asymmetric_optimal_layout(p_w, p_l, p_h)

# --- SVG TOP VIEW RENDERER ---
def draw_asymmetric_svg(opt):
    x_bounds = opt["x_bounds"]
    y_bounds = opt["y_bounds"]
    ax = opt["ax"]
    ay = opt["ay"]
    valid_slots = opt["valid_slots"]
    
    scale = 1.4
    pad_x = 60
    pad_y = 60
    
    view_w = (CARTON_L * scale) + (pad_x * 2)
    view_h = (CARTON_W * scale) + (pad_y * 2)
    
    svg = f'<svg width="100%" height="auto" viewBox="0 0 {view_w} {view_h}" xmlns="http://www.w3.org/2000/svg" style="background-color: #ffffff; border: 2px solid #334155; border-radius: 12px;">'
    svg += f'<rect x="{pad_x}" y="{pad_y}" width="{CARTON_L * scale}" height="{CARTON_W * scale}" fill="#f8fafc" stroke="#1e293b" stroke-width="4" rx="6" />'
    svg += f'<text x="{pad_x + (CARTON_L * scale)/2}" y="{pad_y - 20}" font-family="system-ui, sans-serif" font-size="18" font-weight="bold" fill="#0f172a" text-anchor="middle">TOP VIEW: CARTON A10 ({int(CARTON_L)}x{int(CARTON_W)} mm)</text>'
    svg += f'<rect x="{pad_x + 4.0*scale}" y="{pad_y + 5.5*scale}" width="{(584.0)*scale}" height="{(393.0)*scale}" fill="none" stroke="#94a3b8" stroke-dasharray="4,4" stroke-width="1.5" />'

    for sx in GROOVE_X_ALL:
        cx = pad_x + (sx * scale)
        svg += f'<line x1="{cx}" y1="{pad_y + 5.5*scale}" x2="{cx}" y2="{pad_y + 398.5*scale}" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="3,3" />'
    for sy in GROOVE_Y_ALL:
        cy = pad_y + (sy * scale)
        svg += f'<line x1="{(pad_x + 4.0)*scale}" y1="{cy}" x2="{(pad_x + 584.0)*scale}" y2="{cy}" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="3,3" />'

    for vx in ax:
        cx = pad_x + (vx * scale)
        svg += f'<line x1="{cx}" y1="{pad_y + 5.5*scale}" x2="{cx}" y2="{pad_y + 398.5*scale}" stroke="#dc2626" stroke-width="4" stroke-linecap="round" />'
    for vy in ay:
        cy = pad_y + (vy * scale)
        svg += f'<line x1="{pad_x + 4.0*scale}" y1="{cy}" x2="{pad_x + 588.0*scale}" y2="{cy}" stroke="#dc2626" stroke-width="4" stroke-linecap="round" />'
        
    for slot in valid_slots:
        slot_w = slot["x_end"] - slot["x_start"]
        slot_h = slot["y_end"] - slot["y_start"]
        mid_x = pad_x + ((slot["x_start"] + slot_w/2) * scale)
        mid_y = pad_y + ((slot["y_start"] + slot_h/2) * scale)
        
        draw_w = opt["p_l_disp"] * scale
        draw_h = opt["p_w_disp"] * scale
        rect_x = mid_x - (draw_w / 2)
        rect_y = mid_y - (draw_h / 2)
        
        svg += f'<rect x="{rect_x}" y="{rect_y}" width="{draw_w}" height="{draw_h}" fill="#fed7aa" stroke="#ea580c" stroke-width="1.5" rx="4" />'
        svg += f'<text x="{mid_x}" y="{mid_y - 2}" font-family="system-ui, sans-serif" font-size="10" font-weight="bold" fill="#7c2d12" text-anchor="middle">PCBA</text>'
        svg += f'<text x="{mid_x}" y="{mid_y + 11}" font-family="system-ui, sans-serif" font-size="9.5" fill="#ea580c" text-anchor="middle">{int(opt["p_w_disp"])}x{int(opt["p_l_disp"])}</text>'
            
    svg += '</svg>'
    return svg

# --- SVG SIDE VIEW RENDERER (ฟังก์ชันใหม่ตอบโจทย์ MANAGER) ---
def draw_side_view_svg(opt):
    scale_x = 1.4  # อิงตามความยาวกล่อง L
    scale_y = 1.8  # ขยายแกนตั้ง Y ให้เห็นระดับความสูงชัดเจนขึ้น
    pad_x = 60
    pad_y = 60
    
    view_w = (CARTON_L * scale_x) + (pad_x * 2)
    view_h = (CARTON_H * scale_y) + (pad_y * 2)
    
    # ความสูงโครงสร้างวิศวกรรมบรรจุภัณฑ์
    box_h = CARTON_H * scale_y
    part_h = opt["part_height"] * scale_y
    prod_h = opt["p_h_disp"] * scale_y
    pad_thickness = 3.0 * scale_y  # สมมติความหนากระดาษลูกฟูกรองชั้น 3mm
    
    svg = f'<svg width="100%" height="auto" viewBox="0 0 {view_w} {view_h}" xmlns="http://www.w3.org/2000/svg" style="background-color: #ffffff; border: 2px solid #334155; border-radius: 12px;">'
    
    # 1. วาดเส้นขอบนอก/ใน กล่อง Carton A10 (Side Profile)
    svg += f'<rect x="{pad_x}" y="{pad_y}" width="{CARTON_L * scale_x}" height="{box_h}" fill="#f8fafc" stroke="#1e293b" stroke-width="4" rx="4" />'
    svg += f'<text x="{pad_x + (CARTON_L * scale_x)/2}" y="{pad_y - 20}" font-family="system-ui, sans-serif" font-size="18" font-weight="bold" fill="#0f172a" text-anchor="middle">SIDE VIEW: CARTON A10 (Height: {int(CARTON_H)} mm)</text>'
    
    # 2. คำนวณวาดพาร์ติชันและชิ้นงานตามจำนวนชั้น (Layers)
    for layer_idx in range(opt["layers"]):
        # คำนวณระดับพื้นของชั้นนั้นๆ (อิงจากก้นกล่องขึ้นมา)
        # ชั้นล่างสุดเริ่มจากก้นกล่อง (Y สูงสุดในพิกัด SVG คือด้านล่าง)
        level_y_start = pad_y + box_h - (layer_idx * (part_h + pad_thickness)) - pad_thickness
        
        # วาดแผ่นกระดาษลูกฟูกรองชั้น (Paper Pad)
        svg += f'<rect x="{pad_x + 4.0*scale_x}" y="{level_y_start}" width="{(584.0)*scale_x}" height="{pad_thickness}" fill="#cbd5e1" stroke="#94a3b8" />'
        svg += f'<text x="{pad_x + 15}" y="{level_y_start + pad_thickness - 2}" font-family="system-ui, sans-serif" font-size="9" fill="#475569">Pad</text>'
        
        # ระดับหลังคาพาร์ติชันในชั้นนี้
        partition_top_y = level_y_start - part_h
        
        # วาดเส้นแกนพาร์ติชันแนวตั้ง (Active X Dividers ที่ตัดผ่านด้านข้าง)
        for vx in opt["ax"]:
            cx = pad_x + (vx * scale_x)
            svg += f'<line x1="{cx}" y1="{level_y_start}" x2="{cx}" y2="{partition_top_y}" stroke="#dc2626" stroke-width="3" />'
            
    # วาดตัวแทนชิ้นงาน PCBA จัดวางในตู้เพื่อแสดงระยะ Gap ด้านบน (จำลองในช่องกั้นหลัก)
    for layer_idx in range(opt["layers"]):
        level_y_start = pad_y + box_h - (layer_idx * (part_h + pad_thickness)) - pad_thickness
        
        # วาดตัวชิ้นงาน (สีส้ม ESD) วางอยู่บน Pad 
        rect_y = level_y_start - prod_h
        
        # วาดชิ้นงานจำลองตามช่วงช่องสล็อตที่ถูกสร้างขึ้น
        x_bounds = opt["ax"]
        if len(x_bounds) >= 2:
            for b_idx in range(len(x_bounds)-1):
                slot_w = x_bounds[b_idx+1] - x_bounds[b_idx]
                # วาดเฉพาะช่องที่ชิ้นงานลงได้จริง
                if slot_w >= opt["target_l"]:
                    w_draw = opt["p_l_disp"] * scale_x
                    mid_slot_x = pad_x + ((x_bounds[b_idx] + slot_w/2) * scale_x)
                    rect_x = mid_slot_x - (w_draw / 2)
                    
                    # ตัวผลิตภัณฑ์
                    svg += f'<rect x="{rect_x}" y="{rect_y}" width="{w_draw}" height="{prod_h}" fill="#fed7aa" stroke="#ea580c" stroke-width="1.5" rx="3" />'
                    svg += f'<text x="{mid_slot_x}" y="{rect_y + prod_h/2 + 4}" font-family="system-ui, sans-serif" font-size="10" font-weight="bold" fill="#7c2d12" text-anchor="middle">H: {int(opt["p_h_disp"])}</text>'
                    
                    # คำนวณและวาดเส้นมิติตัวชี้วัด Top Gap พื้นที่ว่างด้านบนชิ้นงาน
                    top_gap = opt["part_height"] - opt["p_h_disp"]
                    if top_gap > 0:
                        gap_line_x = mid_slot_x + (w_draw/2) + 8
                        svg += f'<line x1="{gap_line_x}" y1="{rect_y}" x2="{gap_line_x}" y2="{level_y_start - part_h}" stroke="#2563eb" stroke-width="1.5" stroke-dasharray="2,2" />'
                        svg += f'<text x="{gap_line_x + 5}" y="{rect_y - (top_gap*scale_y)/2 + 4}" font-family="system-ui, sans-serif" font-size="10" font-weight="bold" fill="#2563eb">Gap: {int(top_gap)} mm</text>'

    # วาดแผ่นปิดด้านบนสุดปิดกล่อง (Top Pad)
    top_pad_y = pad_y + box_h - (opt["layers"] * (part_h + pad_thickness)) - pad_thickness
    svg += f'<rect x="{pad_x + 4.0*scale_x}" y="{top_pad_y}" width="{(584.0)*scale_x}" height="{pad_thickness}" fill="#cbd5e1" stroke="#94a3b8" />'
    
    # คำนวณ Dead Space รวมที่เหลืออยู่บนสุดของกล่องกระดาษภายนอก
    total_used_h = (opt["part_height"] + 3.0) * opt["layers"] + 3.0
    remaining_box_air_gap = CARTON_H - total_used_h
    if remaining_box_air_gap > 0:
        svg += f'<rect x="{pad_x + 4.0*scale_x}" y="{pad_y}" width="{(584.0)*scale_x}" height="{remaining_box_air_gap * scale_y}" fill="#f1f5f9" opacity="0.6" stroke="#babfc7" stroke-dasharray="4,4"/>'
        svg += f'<text x="{pad_x + (CARTON_L * scale_x)/2}" y="{pad_y + (remaining_box_air_gap * scale_y)/2 + 4}" font-family="system-ui, sans-serif" font-size="11" font-weight="bold" fill="#64748b" text-anchor="middle">📦 โซนว่างบนสุดกล่องภายนอก (Carton Top Air Gap): {int(remaining_box_air_gap)} mm</text>'

    svg += '</svg>'
    return svg

def render_packing_list(opt):
    active_x_qty = len(opt["ax"])
    active_y_qty = len(opt["ay"])
    layers_count = opt["layers"]
    paper_pads = layers_count + 1
    
    bom_items = [
        {"name": "กล่องกระดาษภายนอก (Master Carton A10)", "qty": "1 Pcs", "spec": "OD: 602x414x270 mm | ID: 592x404x255 mm"},
        {"name": f"แผ่นพาร์ติชันตัวสั้น (PARTITION {'111' if opt['part_height'] == 111.0 else '225'}x393)", "qty": f"{active_x_qty * layers_count} Pcs", "spec": f"ใช้จริง {active_x_qty} แผ่นกั้นแนวตั้งต่อชั้น"},
        {"name": f"แผ่นพาร์ติชันตัวยาว (PARTITION {'111' if opt['part_height'] == 111.0 else '225'}x584)", "qty": f"{active_y_qty * layers_count} Pcs", "spec": f"ใช้จริง {active_y_qty} แผ่นกั้นแนวนอนต่อชั้น"},
        {"name": "แผ่นกระดาษลูกฟูกรองขอบแบน (Corrugated Paper Pad)", "qty": f"{paper_pads} Pcs", "spec": "394 x 574 mm"},
        {"name": "ซองพลาสติกกันไฟฟ้าสถิตย์ (ESD Anti-Static Bag)", "qty": f"{opt['qty_box']} Pcs", "spec": "สวมใส่ PCBA ก่อนนำมาบรรจุลงช่องสล็อต"}
    ]
    
    for item in bom_items:
        st.markdown(f"""
        <div style="background-color: #f8fafc; border-left: 6px solid #1e293b; padding: 10px; border-radius: 6px; margin-bottom: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
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
    
    # --- คอลัมน์ซ้าย: FIX H ตามที่กรอก ---
    with col1:
        st.header("1️⃣ Fixed H Layout")
        if best_fixed:
            st.success(f"📌 **ทิศทางการจัดวาง:** {best_fixed['orient_label']}")
            
            m_col1, m_col2, m_col3 = st.columns(3)
            m_col1.metric("จำนวนสินค้า/ชั้น", f"{best_fixed['qty_layer']} Pcs")
            m_col2.metric("จำนวนชั้น (Layers)", f"{best_fixed['layers']} ชั้น")
            m_col3.metric("ความจุรวม/กล่อง", f"{best_fixed['qty_box']} Pcs/Box")
            
            st.subheader("📋 รายการวัสดุบรรจุภัณฑ์ (BOM)")
            render_packing_list(best_fixed)
            
            st.subheader("📐 แผนผังมุมมองจากด้านบน (Top View)")
            st.write(draw_asymmetric_svg(best_fixed), unsafe_allow_html=True)
            
            st.subheader("⏳ แผนผังมุมมองภาคตัดขวางด้านข้าง (Side View Blueprint)")
            st.write(draw_side_view_svg(best_fixed), unsafe_allow_html=True)
        else:
            st.error("❌ ไม่พบรูปแบบพาร์ติชันสำหรับความสูง (H) นี้ได้จริง กรุณาตรวจสอบขนาดและลองอีกครั้ง")

    # --- คอลัมน์ขวา: Alternative Option ---
    with col2:
        st.header("2️⃣ Alternative Option")
        if has_better_alternative:
            st.warning(f"🔥 **แนะนำเปลี่ยนทิศทางการวางเป็น:** {best_overall['orient_label']}")
            
            a_col1, a_col2, a_col3 = st.columns(3)
            a_col1.metric("จำนวนสินค้า/ชั้น", f"{best_overall['qty_layer']} Pcs", f"+{best_overall['qty_layer'] - best_fixed['qty_layer']} Pcs")
            a_col2.metric("จำนวนชั้น (Layers)", f"{best_overall['layers']} ชั้น")
            a_col3.metric("ความจุรวม/กล่อง", f"{best_overall['qty_box']} Pcs/Box", f"+{best_overall['qty_box'] - best_fixed['qty_box']} Pcs")
            
            st.subheader("📋 รายการวัสดุบรรจุภัณฑ์ (BOM)")
            render_packing_list(best_overall)
            
            st.subheader("📐 แผนผังมุมมองจากด้านบน (Top View)")
            st.write(draw_asymmetric_svg(best_overall), unsafe_allow_html=True)
            
            st.subheader("⏳ แผนผังมุมมองภาคตัดขวางด้านข้าง (Side View Blueprint)")
            st.write(draw_side_view_svg(best_overall), unsafe_allow_html=True)
        else:
            st.info("💡 **การประเมินวิศวกรรมเชิงลึก:**")
            st.markdown(f"""
            <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; padding: 20px; border-radius: 12px; margin-top: 10px;">
                <h4 style="color: #16a34a; margin-top: 0px;">✅ ทิศทางความสูงปัจจุบันมีประสิทธิภาพสูงสุดแล้ว</h4>
                <p style="color: #166534; font-size: 15px; line-height: 1.6;">
                    ระบบวิเคราะห์ 3D 6-Way Rotation Engine พบว่าทิศทางที่ป้อนค่าเริ่มต้น ให้กำลังความจุรวมต่อกล่องสูงที่สุดแล้ว
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            if best_fixed:
                st.subheader("📊 รายละเอียดสรุปโครงสร้างปัจจุบัน")
                st.write(f"• **ความสูงพาร์ติชันกระดาษใช้งาน:** {int(best_fixed['part_height'])} mm")
                st.write(f"• **ช่องว่างด้านบนชิ้นงานถึงขอบพาร์ติชัน (Top Gap/Clearance):** {int(best_fixed['part_height'] - best_fixed['p_h_disp'])} mm")
                st.write(f"• **พื้นที่ช่องว่าง Buffer ขอบนอกสุด (Buffer Margin):** ปลอดภัยเป็น Crumple Zone ซับแรงกระแทก")

    # แสดงรายการตารางเปรียบเทียบ Grid Layout ทั้งหมดด้านล่าง
    st.write("---")
    st.subheader("📊 ตารางวิเคราะห์รูปแบบกริดและทิศทางการจัดวางที่เป็นไปได้ทั้งหมด")
    
    summary_table = []
    for idx, opt in enumerate(overall_options[:10]):
        summary_table.append({
            "อันดับความจุ": "🏆 ดีที่สุด (Optimal)" if idx == 0 else f"ทางเลือกที่ {idx+1}",
            "ทิศทางจัดวาง": opt["orient_label"],
            "เป็นแบบ Fixed H?": "✅ ใช่" if opt["is_fixed_h"] else "🔄 หมุน 3D (ทางเลือก)",
            "แผ่นแนวตั้งที่ใช้ (Short)": f"{len(opt['ax'])} / 5 Pcs",
            "แผ่นแนวนอนที่ใช้ (Long)": f"{len(opt['ay'])} / 9 Pcs",
            "ความจุต่อชั้น (Layer Qty)": f"{opt['qty_layer']} Pcs",
            "จำนวนชั้นทั้งหมด (Layers)": f"{opt['layers']} ชั้น",
            "ความจุรวมกล่อง (Box Qty)": f"{opt['qty_box']} Pcs/Box"
        })
    st.dataframe(summary_table, use_container_width=True)

else:
    st.error("❌ ไม่พบรูปแบบแผ่นพาร์ติชันกระดาษลูกฟูกสเกลใดที่สามารถบรรจุผลิตภัณฑ์ขนาดนี้ลงในกล่อง Carton A10 ได้จริง กรุณาปรับระยะ Clearance หรือตรวจสอบขนาดผลิตภัณฑ์อีกครั้ง")
