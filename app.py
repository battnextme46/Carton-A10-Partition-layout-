import streamlit as st
import math
import itertools
import base64

# ตั้งค่าหน้าเว็บให้แสดงผลสวยงามเต็มจอ
st.set_page_config(
    page_title="Carton A10 Partition Optimizer",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📦 Auto-Select Partition Layout Design with Carton A10")
st.write("ระบบวิเคราะห์และคัดเลือกพาร์ติชันแบบอสมมาตร ตามพิกัดร่องขัดจริงโดยคำนึงถึงขอบกันชนรอบกล่อง (Fully Enclosed Slots) พร้อมระบบเพิ่มเงื่อนไขการวางเบียด/ซ้อนทับในช่อง")

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

# --- 🚀 NEW SIDEBAR: เงื่อนไขการวางเบียด/ซ้อนในช่องสล็อต ---
st.sidebar.header("🔄 3. เงื่อนไขการจัดวางภายในช่อง (Slot Packing Mode)")
packing_mode = st.sidebar.radio(
    "รูปแบบการบรรจุใน 1 ช่องสล็อต:",
    [
        "1) วาง 1 ชิ้นต่อช่องปกติ (Standard 1 PC/Slot)",
        "2) วางข้างกัน/เบียดกันแนวราบ (Multi-Fit: Side-by-Side Only)",
        "3) วางข้างกัน + ซ้อนทับกันแนวตั้ง (Stack-Fit: Side-by-Side & Stacked)"
    ]
)

# --- ฟังก์ชันพิเศษแปลง SVG เป็นรูปแบบปลอดภัย ไม่ให้ภาพหาย ---
def safe_svg_render(svg_content):
    b64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{b64}"

# --- DYNAMIC SOLVER ENGINE ---
def find_asymmetric_optimal_layout(pw, pl, ph, mode):
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

        # คำนวณความสูงพาร์ติชันและจำนวนชั้นของกล่องตามปกติ
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

                        # ตรวจสอบการจุเบียด/ซ้อนใน 1 ช่องสล็อตตามเงื่อนไขที่เลือก
                        if mode == "1) วาง 1 ชิ้นต่อช่องปกติ (Standard 1 PC/Slot)":
                            if slot_w >= target_l and slot_h >= target_w:
                                items_in_this_slot = 1
                            else:
                                items_in_this_slot = 0
                        
                        elif mode == "2) วางข้างกัน/เบียดกันแนวราบ (Multi-Fit: Side-by-Side Only)":
                            # หารจำนวนชิ้นตามความกว้างหรือยาวที่สามารถเบียดกันได้ในแนวราบ
                            fits_w = math.floor(slot_h / target_w)
                            fits_l = math.floor(slot_w / target_l)
                            if fits_w >= 1 and fits_l >= 1:
                                items_in_this_slot = fits_w * fits_l
                            else:
                                items_in_this_slot = 0
                                
                        elif mode == "3) วางข้างกัน + ซ้อนทับกันแนวตั้ง (Stack-Fit: Side-by-Side & Stacked)":
                            # คำนวณแนวราบก่อน
                            fits_w = math.floor(slot_h / target_w)
                            fits_l = math.floor(slot_w / target_l)
                            # คำนวณดูว่าในความสูงพาร์ติชัน (part_height) จะซ้อนชิ้นงานในแนวตั้งได้กี่ชิ้น
                            fits_h = math.floor(part_height / (eh + clearance))
                            
                            if fits_w >= 1 and fits_l >= 1 and fits_h >= 1:
                                items_in_this_slot = fits_w * fits_l * fits_h
                            else:
                                items_in_this_slot = 0

                        if items_in_this_slot > 0:
                            valid_slots.append({
                                "col_idx": i,
                                "row_idx": j,
                                "x_start": x_bounds[i],
                                "x_end": x_bounds[i+1],
                                "y_start": y_bounds[j],
                                "y_end": y_bounds[j+1],
                                "items_count": items_in_this_slot # บันทึกจำนวนชิ้นงานในช่องนี้ไว้
                            })

                if len(valid_slots) > 0:
                    # รวมจำนวนชิ้นงานทั้งหมดในชั้น (บวกจากทุกช่องสล็อต)
                    qty_layer = sum(s["items_count"] for s in valid_slots)
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

options = find_asymmetric_optimal_layout(p_w, p_l, p_h, packing_mode)

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
        
        # แสดงรูปชิ้นงานหลัก พร้อมตัวเลขระบุจำนวนชิ้นในช่องนั้นๆ เพื่อความชัดเจน
        svg += f'<rect x="{rect_x}" y="{rect_y}" width="{draw_w}" height="{draw_h}" fill="#fed7aa" stroke="#ea580c" stroke-width="1.5" rx="4" />'
        svg += f'<text x="{mid_x}" y="{mid_y - 2}" font-family="system-ui, sans-serif" font-size="11" font-weight="bold" fill="#7c2d12" text-anchor="middle">PCBA (x{slot["items_count"]})</text>'
        svg += f'<text x="{mid_x}" y="{mid_y + 11}" font-family="system-ui, sans-serif" font-size="9.5" fill="#ea580c" text-anchor="middle">{int(opt["p_w_disp"])}x{int(opt["p_l_disp"])}</text>'
            
    svg += '</svg>'
    return safe_svg_render(svg)

# --- SVG SIDE VIEW RENDERER ---
def draw_side_view_svg(opt):
    scale_x = 1.4  
    scale_y = 1.8  
    pad_x = 60
    pad_y = 60
    
    view_w = (CARTON_L * scale_x) + (pad_x * 2)
    view_h = (CARTON_H * scale_y) + (pad_y * 2)
    
    box_h = CARTON_H * scale_y
    part_h = opt["part_height"] * scale_y
    prod_h = opt["p_h_disp"] * scale_y
    pad_thickness = 3.0 * scale_y  
    
    svg = f'<svg width="100%" height="auto" viewBox="0 0 {view_w} {view_h}" xmlns="http://www.w3.org/2000/svg" style="background-color: #ffffff; border: 2px solid #334155; border-radius: 12px;">'
    svg += f'<rect x="{pad_x}" y="{pad_y}" width="{CARTON_L * scale_x}" height="{box_h}" fill="#f8fafc" stroke="#1e293b" stroke-width="4" rx="4" />'
    svg += f'<text x="{pad_x + (CARTON_L * scale_x)/2}" y="{pad_y - 20}" font-family="system-ui, sans-serif" font-size="18" font-weight="bold" fill="#0f172a" text-anchor="middle">SIDE VIEW: CARTON A10 (Height: {int(CARTON_H)} mm)</text>'
    
    for layer_idx in range(opt["layers"]):
        level_y_start = pad_y + box_h - (layer_idx * (part_h + pad_thickness)) - pad_thickness
        svg += f'<rect x="{pad_x + 4.0*scale_x}" y="{level_y_start}" width="{(584.0)*scale_x}" height="{pad_thickness}" fill="#cbd5e1" stroke="#94a3b8" />'
        svg += f'<text x="{pad_x + 15}" y="{level_y_start + pad_thickness - 2}" font-family="system-ui, sans-serif" font-size="9" fill="#475569">Pad</text>'
        
        partition_top_y = level_y_start - part_h
        for vx in opt["ax"]:
            cx = pad_x + (vx * scale_x)
            svg += f'<line x1="{cx}" y1="{level_y_start}" x2="{cx}" y2="{partition_top_y}" stroke="#dc2626" stroke-width="3" />'
            
    for layer_idx in range(opt["layers"]):
        level_y_start = pad_y + box_h - (layer_idx * (part_h + pad_thickness)) - pad_thickness
        rect_y = level_y_start - prod_h
        
        x_bounds = opt["ax"]
        if len(x_bounds) >= 2:
            for b_idx in range(len(x_bounds)-1):
                slot_w = x_bounds[b_idx+1] - x_bounds[b_idx]
                if slot_w >= opt["target_l"]:
                    w_draw = opt["p_l_disp"] * scale_x
                    mid_slot_x = pad_x + ((x_bounds[b_idx] + slot_w/2) * scale_x)
                    rect_x = mid_slot_x - (w_draw / 2)
                    
                    svg += f'<rect x="{rect_x}" y="{rect_y}" width="{w_draw}" height="{prod_h}" fill="#fed7aa" stroke="#ea580c" stroke-width="1.5" rx="3" />'
                    svg += f'<text x="{mid_slot_x}" y="{rect_y + prod_h/2 + 4}" font-family="system-ui, sans-serif" font-size="10" font-weight="bold" fill="#7c2d12" text-anchor="middle">H: {int(opt["p_h_disp"])}</text>'
                    
                    top_gap = opt["part_height"] - opt["p_h_disp"]
                    if top_gap > 0:
                        gap_line_x = mid_slot_x + (w_draw/2) + 8
                        svg += f'<line x1="{gap_line_x}" y1="{rect_y}" x2="{gap_line_x}" y2="{level_y_start - part_h}" stroke="#2563eb" stroke-width="1.5" stroke-dasharray="2,2" />'
                        svg += f'<text x="{gap_line_x + 5}" y="{rect_y - (top_gap*scale_y)/2 + 4}" font-family="system-ui, sans-serif" font-size="10" font-weight="bold" fill="#2563eb">Gap: {int(top_gap)} mm</text>'

    top_pad_y = pad_y + box_h - (opt["layers"] * (part_h + pad_thickness)) - pad_thickness
    svg += f'<rect x="{pad_x + 4.0*scale_x}" y="{top_pad_y}" width="{(584.0)*scale_x}" height="{pad_thickness}" fill="#cbd5e1" stroke="#94a3b8" />'
    
    total_used_h = (opt["part_height"] + 3.0) * opt
