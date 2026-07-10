import streamlit as st
import math
import itertools
import base64

# --- 1. SETPAGE CONFIG (ความคลีนแบบดั้งเดิม) ---
st.set_page_config(
    page_title="Carton A10 Partition Optimizer",
    layout="wide"
)

st.title("📦 Carton A10 Partition Optimizer")
st.write("กลับสู่เวอร์ชันเสถียรดั้งเดิมที่ทำงานได้แม่นยำและแสดงผลแผนผังได้ครบถ้วน")

# --- 2. CONFIGURATION MATRIX CORE ---
CARTON_L = 592.0
CARTON_W = 404.0
CARTON_H = 255.0

GROOVE_X_ALL = [13.5, 154.75, 296.0, 437.25, 578.5]
GROOVE_Y_ALL = [19.5, 65.125, 110.75, 156.375, 202.0, 247.625, 293.25, 338.875, 384.5]

# --- 3. SIDEBAR INPUTS ---
st.sidebar.header("📐 1. ขนาดผลิตภัณฑ์ (Product Dimension)")
p_w = st.sidebar.number_input("ความกว้างชิ้นงาน (Width - W) (mm)", value=50.0, step=1.0)
p_l = st.sidebar.number_input("ความยาวชิ้นงาน (Length - L) (mm)", value=160.0, step=1.0)
p_h = st.sidebar.number_input("ความหนาชิ้นงาน (Height/Thickness - H) (mm)", value=150.0, step=1.0)

st.sidebar.header("🛡️ 2. ค่าเผื่อสล็อต (Clearance Margin)")
clearance = st.sidebar.slider("ระยะเผื่อช่อง (Clearance) (mm)", 1.0, 15.0, 5.0, step=0.5)

# --- 4. HELPER FUNCTION TO PREVENT IMAGE LOSS ---
def svg_to_base64_src(svg_str):
    b64 = base64.b64encode(svg_str.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{b64}"

# --- 5. ORIGINAL LAYOUT SOLVER ENGINE ---
def calculate_layouts(pw, pl, ph):
    all_dims = [pw, pl, ph]
    orientations = list(set(itertools.permutations(all_dims)))
    
    valid_options = []
    
    grid_presets = [
        {"ax": GROOVE_X_ALL, "ay": GROOVE_Y_ALL},
        {"ax": GROOVE_X_ALL, "ay": [19.5, 110.75, 202.0, 293.25, 384.5]},
        {"ax": GROOVE_X_ALL, "ay": [19.5, 202.0, 384.5]},
        {"ax": [13.5, 296.0, 578.5], "ay": GROOVE_Y_ALL},
        {"ax": [13.5, 296.0, 578.5], "ay": [19.5, 110.75, 202.0, 293.25, 384.5]},
        {"ax": [13.5, 296.0, 578.5], "ay": [19.5, 202.0, 384.5]}
    ]

    for orient in orientations:
        ew, el, eh = orient
        is_fixed_h = (eh == ph)
        
        # ตัดสินใจเรื่องความสูงเลเยอร์ตามโค้ดดั้งเดิม
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

        for preset in grid_presets:
            x_b = sorted(preset["ax"])
            y_b = sorted(preset["ay"])
            
            valid_slots = []
            is_perfect_grid = True
            
            for i in range(len(x_b) - 1):
                for j in range(len(y_b) - 1):
                    slot_w = x_b[i+1] - x_b[i]
                    slot_h = y_b[j+1] - y_b[j]
                    
                    if slot_w >= target_l and slot_h >= target_w:
                        valid_slots.append({
                            "x_start": x_b[i], "x_end": x_b[i+1],
                            "y_start": y_b[j], "y_end": y_b[j+1]
                        })
                    else:
                        is_perfect_grid = False
                        
            if is_perfect_grid and len(valid_slots) > 0:
                qty_per_layer = len(valid_slots)
                total_qty = qty_per_layer * layers
                
                valid_options.append({
                    "qty_box": total_qty,
                    "qty_layer": qty_per_layer,
                    "layers": layers,
                    "part_height": part_height,
                    "ax": preset["ax"],
                    "ay": preset["ay"],
                    "orient_label": f"{int(ew)} x {int(el)} x {int(eh)}",
                    "valid_slots": valid_slots,
                    "is_fixed_h": is_fixed_h,
                    "total_dividers": len(preset["ax"]) + len(preset["ay"])
                })
                
    return valid_options

options = calculate_layouts(p_w, p_l, p_h)

# --- 6. ORIGINAL DRAWING ENGINES ---
def draw_top_view(opt):
    scale = 1.0
    pad_x, pad_y = 40, 40
    w_svg, h_svg = 680, 480
    
    svg = f'<svg width="{w_svg}" height="{h_svg}" xmlns="http://www.w3.org/2000/svg" style="background-color: #ffffff;">'
    svg += f'<rect x="{pad_x}" y="{pad_y}" width="{CARTON_L*scale}" height="{CARTON_W*scale}" fill="#fafafa" stroke="#000000" stroke-width="2" />'
    
    for slot in opt["valid_slots"]:
        sx = pad_x + slot["x_start"] * scale
        sy = pad_y + slot["y_start"] * scale
        sw = (slot["x_end"] - slot["x_start"]) * scale
        sh = (slot["y_end"] - slot["y_start"]) * scale
        svg += f'<rect x="{sx+4}" y="{sy+4}" width="{sw-8}" height="{sh-8}" fill="#ffe4e6" stroke="#f43f5e" stroke-width="1" rx="2" />'
        svg += f'<text x="{sx + sw/2}" y="{sy + sh/2 + 4}" font-size="11" font-weight="bold" fill="#b91c1c" text-anchor="middle">PCBA</text>'
        
    for vx in opt["ax"]:
        svg += f'<line x1="{pad_x + vx*scale}" y1="{pad_y}" x2="{pad_x + vx*scale}" y2="{pad_y + CARTON_W*scale}" stroke="#000000" stroke-width="1.5" />'
    for vy in opt["ay"]:
        svg += f'<line x1="{pad_x}" y1="{pad_y + vy*scale}" x2="{pad_x + CARTON_L*scale}" y2="{pad_y + vy*scale}" stroke="#000000" stroke-width="1.5" />'
        
    svg += '</svg>'
    return svg_to_base64_src(svg)

def draw_side_view(opt):
    scale_x, scale_y = 1.0, 1.0
    pad_x, pad_y = 40, 40
    w_svg, h_svg = 680, 340
    
    svg = f'<svg width="{w_svg}" height="{h_svg}" xmlns="http://www.w3.org/2000/svg" style="background-color: #ffffff;">'
    svg += f'<rect x="{pad_x}" y="{pad_y}" width="{CARTON_L*scale_x}" height="{CARTON_H*scale_y}" fill="#fafafa" stroke="#000000" stroke-width="2" />'
    
    part_h = opt["part_height"]
    for l in range(opt["layers"]):
        base_y = pad_y + CARTON_H*scale_y - (l * (part_h + 3.0)) - 3.0
        svg += f'<rect x="{pad_x}" y="{base_y}" width="{CARTON_L*scale_x}" height="3" fill="#666666" />'
        
        top_y = base_y - part_h
        for vx in opt["ax"]:
            svg += f'<line x1="{pad_x + vx*scale_x}" y1="{base_y}" x2="{pad_x + vx*scale_x}" y2="{top_y}" stroke="#000000" stroke-width="1.5" />'
            
        svg += f'<text x="{pad_x + 15}" y="{base_y - part_h/2 + 4}" font-size="12" fill="#444444" font-weight="bold">Layer {l+1}</text>'
        
    svg += '</svg>'
    return svg_to_base64_src(svg)

# --- 7. ORIGINAL MAIN DISPLAY CONTROL ---
if options:
    fixed_h_opts = [o for o in options if o["is_fixed_h"]]
    fixed_h_opts.sort(key=lambda x: x["qty_box"], reverse=True)
    
    options.sort(key=lambda x: x["qty_box"], reverse=True)
    best_overall = options[0]
    best_fixed = fixed_h_opts[0] if fixed_h_opts else None

    col1, col2 = st.columns(2)
    
    with col1:
        st.header("1️⃣ แบบแปลนตรงตามแกนจริง (Fixed H Blueprint)")
        if best_fixed:
            st.info(f"📐 มิติจัดวางแนวราบ: {best_fixed['orient_label']} mm")
            st.metric("ความจุรวมทั้งหมด", f"{best_fixed['qty_box']} ชิ้น/กล่อง")
            st.metric("จำนวนชั้นบรรจุ", f"{best_fixed['layers']} ชั้น")
            st.metric("ความสูงแผ่นกั้นใช้งาน", f"{int(best_fixed['part_height'])} mm")
            
            st.subheader("📋 แผนผังมุมมองจากด้านบน (Top View)")
            st.image(draw_top_view(best_fixed), use_container_width=True)
            
            st.subheader("⏳ แผนผังมุมมองภาคตัดขวางด้านข้าง (Side View)")
            st.image(draw_side_view(best_fixed), use_container_width=True)
        else:
            st.warning("⚠️ ขนาดชิ้นงานแนวตั้งสูงเกินขีดจำกัดกล่องในแกนนี้")

    with col2:
        st.header("2️⃣ แบบแปลนที่ได้ความจุสูงสุด (Optimal Blueprint)")
        if best_overall:
            st.success(f"🔄 มิติจัดวางหมุน 3D แนะนำ: {best_overall['orient_label']} mm")
            st.metric("ความจุรวมทั้งหมด", f"{best_overall['qty_box']} ชิ้น/กล่อง")
            st.metric("จำนวนชั้นบรรจุ", f"{best_overall['layers']} ชั้น")
            st.metric("ความสูงแผ่นกั้นใช้งาน", f"{int(best_overall['part_height'])} mm")
            
            st.subheader("📋 แผนผังมุมมองจากด้านบน (Top View)")
            st.image(draw_top_view(best_overall), use_container_width=True)
            
            st.subheader("⏳ แผนผังมุมมองภาคตัดขวางด้านข้าง (Side View)")
            st.image(draw_side_view(best_overall), use_container_width=True)

    # ตารางสรุปแบบคลีนๆ
    st.write("---")
    st.subheader("📊 ตารางวิเคราะห์รูปแบบกริดทั้งหมด")
    summary_data = []
    for idx, opt in enumerate(options[:6]):
        summary_data.append({
            "ทางเลือกที่": idx + 1,
            "การจัดวาง (W x L x H)": opt["orient_label"],
            "แผ่นกั้นแนวตั้ง (Short)": f"{len(opt['ax'])} แผ่น",
            "แผ่นกั้นแนวนอน (Long)": f"{len(opt['ay'])} แผ่น",
            "จำนวนชั้น": f"{opt['layers']} ชั้น",
            "ความจุรวม": f"{opt['qty_box']} ชิ้น/กล่อง"
        })
    st.dataframe(summary_data, width="stretch")

else:
    st.error("❌ ไม่สามารถจัดวางได้เนื่องจากขนาดชิ้นงานบวกระยะเผื่อสล็อตใหญ่เกินมิติภายในของกล่องมาสเตอร์")
