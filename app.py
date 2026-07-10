import streamlit as st
import math
import itertools
import base64

# ตั้งค่าหน้าเว็บ
st.set_page_config(
    page_title="Carton A10 Partition Optimizer",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📦 Auto-Select Partition Layout Design with Carton A10")
st.write("เวอร์ชันเสถียรสูงสุด: ปรับปรุงการเรนเดอร์กราฟิกแบบ Aggregate ป้องกัน Server Crash และรองรับการวางเบียด/แนวตั้ง")

# --- CONFIGURATION ENGINE ---
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

st.sidebar.header("🔄 3. เงื่อนไขการจัดวางในสล็อต (Slot Packing Rule)")
packing_mode = st.sidebar.selectbox(
    "รูปแบบการบรรจุภายในช่องพาร์ติชัน:",
    [
        "มาตรฐาน (1 ช่อง ต่อ 1 ชิ้นงาน เท่านั้น)",
        "วางเบียดกันในแนวราบได้ (Horizontal Side-by-Side)",
        "วางเบียดแนวราบ + วางซ้อนทับกันในแนวตั้งได้ (Side-by-Side & Stacked)"
    ]
)

def safe_svg_render(svg_content):
    b64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{b64}"

# --- OPTIMIZED SOLVER ENGINE (คุม RAM ไม่ให้เกินขีดจำกัด) ---
def find_optimized_layout(pw, pl, ph, mode):
    all_dims = [pw, pl, ph]
    unique_orientations = set(itertools.permutations(all_dims))
    
    orientations_3d = []
    for perm in unique_orientations:
        w_rot, l_rot, h_rot = perm
        orientations_3d.append({
            "flat_w": w_rot,
            "flat_l": l_rot,
            "vert_h": h_rot,
            "label": f"{int(w_rot)} x {int(l_rot)} x {int(h_rot)}",
            "is_fixed_h": (h_rot == ph)
        })

    best_options = []
    
    # เจนเนอเรต Subset แบบจำกัดขนาดเพื่อประหยัด RAM
    subsets_x = []
    for r in range(2, len(GROOVE_X_ALL) + 1):
        for comb in itertools.combinations(GROOVE_X_ALL, r):
            subsets_x.append(list(comb))

    subsets_y = []
    for r in range(2, len(GROOVE_Y_ALL) + 1):
        for comb in itertools.combinations(GROOVE_Y_ALL, r):
            subsets_y.append(list(comb))

    target_w = pw + clearance
    target_l = pl + clearance

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

        t_w = ew + clearance
        t_l = el + clearance

        for ax in subsets_x:
            for ay in subsets_y:
                valid_slots = []
                for i in range(len(ax) - 1):
                    for j in range(len(ay) - 1):
                        slot_w = ax[i+1] - ax[i]
                        slot_h = ay[j+1] - ay[j]

                        # Logic ป้องกันตัวคูณบานปลาย
                        if mode == "มาตรฐาน (1 ช่อง ต่อ 1 ชิ้นงาน เท่านั้น)":
                            items = 1 if (slot_w >= t_l and slot_h >= t_w) else 0
                        elif mode == "วางเบียดกันในแนวราบได้ (Horizontal Side-by-Side)":
                            fits_l = math.floor(slot_w / t_l)
                            fits_w = math.floor(slot_h / t_w)
                            items = fits_l * fits_w if (fits_l >= 1 and fits_w >= 1) else 0
                        else: # วางเบียดแนวราบ + ซ้อนแนวตั้ง
                            fits_l = math.floor(slot_w / t_l)
                            fits_w = math.floor(slot_h / t_w)
                            fits_h = math.floor(part_height / (eh + clearance))
                            items = fits_l * fits_w * fits_h if (fits_l >= 1 and fits_w >= 1 and fits_h >= 1) else 0

                        if items > 0:
                            valid_slots.append({
                                "x_start": ax[i], "x_end": ax[i+1],
                                "y_start": ay[j], "y_end": ay[j+1],
                                "items_count": items
                            })

                if len(valid_slots) > 0:
                    qty_layer = sum(s["items_count"] for s in valid_slots)
                    qty_box = qty_layer * layers

                    best_options.append({
                        "qty_box": qty_box, "qty_layer": qty_layer, "layers": layers,
                        "part_height": part_height, "ax": ax, "ay": ay,
                        "x_bounds": [4.0] + ax + [588.0], "y_bounds": [5.5] + ay + [398.5],
                        "valid_slots": valid_slots, "orient_label": orient["label"],
                        "target_w": t_w, "target_l": t_l, "p_w_disp": ew, "p_l_disp": el, "p_h_disp": eh,
                        "total_dividers": len(ax) + len(ay), "is_fixed_h": orient["is_fixed_h"]
                    })

    return best_options

options = find_optimized_layout(p_w, p_l, p_h, packing_mode)

# --- LIGHTWEIGHT SVG TOP VIEW ---
def draw_top_view_svg(opt):
    scale = 1.4
    pad = 50
    view_w = (CARTON_L * scale) + (pad * 2)
    view_h = (CARTON_W * scale) + (pad * 2)
    
    svg = f'<svg width="100%" height="auto" viewBox="0 0 {view_w} {view_h}" xmlns="http://www.w3.org/2000/svg" style="background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px;">'
    svg += f'<rect x="{pad}" y="{pad}" width="{CARTON_L * scale}" height="{CARTON_W * scale}" fill="#f8fafc" stroke="#334155" stroke-width="3" />'
    
    # วาดเส้นพาร์ติชันหลัก
    for vx in opt["ax"]:
        svg += f'<line x1="{pad + vx*scale}" y1="{pad}" x2="{pad + vx*scale}" y2="{pad + CARTON_W*scale}" stroke="#dc2626" stroke-width="2.5" />'
    for vy in opt["ay"]:
        svg += f'<line x1="{pad}" y1="{pad + vy*scale}" x2="{pad + CARTON_L*scale}" y2="{pad + vy*scale}" stroke="#dc2626" stroke-width="2.5" />'
        
    # จุดเด่น: รวมจำนวนชิ้นงานเพื่อวาดสัญลักษณ์เดียวตรงกลาง ไม่สร้าง Element ซ้ำซ้อนให้ระบบแฮงก์
    for slot in opt["valid_slots"]:
        sw = slot["x_end"] - slot["x_start"]
        sh = slot["y_end"] - slot["y_start"]
        mx = pad + (slot["x_start"] + sw/2) * scale
        my = pad + (slot["y_start"] + sh/2) * scale
        
        svg += f'<rect x="{mx - (sw*scale*0.8)/2}" y="{my - (sh*scale*0.8)/2}" width="{sw*scale*0.8}" height="{sh*scale*0.8}" fill="#ffedd5" stroke="#f97316" stroke-width="1" rx="3" opacity="0.8"/>'
        svg += f'<text x="{mx}" y="{my+4}" font-family="sans-serif" font-size="11" font-weight="bold" fill="#ea580c" text-anchor="middle">PCBA: {slot["items_count"]} ชิ้น/ช่อง</text>'
        
    svg += '</svg>'
    return safe_svg_render(svg)

# --- LIGHTWEIGHT SVG SIDE VIEW ---
def draw_side_view_svg(opt):
    scale_x = 1.4
    scale_y = 1.6
    pad = 50
    view_w = (CARTON_L * scale_x) + (pad * 2)
    view_h = (CARTON_H * scale_y) + (pad * 2)
    
    svg = f'<svg width="100%" height="auto" viewBox="0 0 {view_w} {view_h}" xmlns="http://www.w3.org/2000/svg" style="background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px;">'
    svg += f'<rect x="{pad}" y="{pad}" width="{CARTON_L * scale_x}" height="{CARTON_H * scale_y}" fill="#f8fafc" stroke="#334155" stroke-width="3" />'
    
    # วาดเลเยอร์ชั้น
    for l_idx in range(opt["layers"]):
        ly = pad + (CARTON_H * scale_y) - ((l_idx + 1) * opt["part_height"] * scale_y)
        svg += f'<line x1="{pad}" y1="{ly}" x2="{pad + CARTON_L*scale_x}" y2="{ly}" stroke="#94a3b8" stroke-dasharray="4,4" />'
        svg += f'<text x="{pad + 15}" y="{ly - 10}" font-family="sans-serif" font-size="11" fill="#64748b">--- ชั้นบรรจุที่ {l_idx + 1} (ความสูงแผ่นกั้น: {int(opt["part_height"])} mm) ---</text>'
        
    svg += '</svg>'
    return safe_svg_render(svg)

# --- UI DISPLAY ---
if options:
    fixed_h_options = [o for o in options if o["is_fixed_h"]]
    fixed_h_options.sort(key=lambda x: (x["qty_box"], -x["total_dividers"]), reverse=True)
    overall_options = sorted(options, key=lambda x: (x["qty_box"], -x["total_dividers"]), reverse=True)
    
    best_fixed = fixed_h_options[0] if fixed_h_options else None
    best_overall = overall_options[0] if overall_options else None
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1️⃣ Fixed H Layout")
        if best_fixed:
            st.success(f"📌 ทิศทางการจัดวาง: {best_fixed['orient_label']}")
            st.metric("ความจุรวมทั้งหมด", f"{best_fixed['qty_box']} Pcs/Box", f"{best_fixed['qty_layer']} Pcs ต่อชั้น")
            st.image(draw_top_view_svg(best_fixed), use_container_width=True)
            st.image(draw_side_view_svg(best_fixed), use_container_width=True)
            
    with col2:
        st.subheader("2️⃣ Alternative Option")
        if best_overall and best_fixed and best_overall["qty_box"] > best_fixed["qty_box"]:
            st.warning(f"🔄 แนะนำหมุนด้านชิ้นงาน: {best_overall['orient_label']}")
            st.metric("ความจุรวมทางเลือก", f"{best_overall['qty_box']} Pcs/Box", f"+{best_overall['qty_box'] - best_fixed['qty_box']} Pcs")
            st.image(draw_top_view_svg(best_overall), use_container_width=True)
        else:
            st.info("💡 โครงสร้างความสูงปัจจุบันทำงานได้ดีที่สุดแล้วในโหมดที่เลือก")

else:
    st.error("❌ ไม่พบรูปแบบแผ่นพาร์ติชันที่รองรับขนาดชิ้นงานนี้ได้ กรุณาปรับระยะป้อนข้อมูลอีกครั้ง")
