import streamlit as st
import math
import itertools

# ตั้งค่าหน้าเว็บ
st.set_page_config(page_title="Carton A10 Partition Optimizer", layout="wide", initial_sidebar_state="expanded")

st.title("📦 Auto-Select Partition Layout Design with Carton A10")

# --- CONFIGURATION ENGINE ---
CARTON_L, CARTON_W, CARTON_H = 592.0, 404.0, 255.0
GROOVE_X_ALL = [13.5, 154.75, 296.0, 437.25, 578.5]
GROOVE_Y_ALL = [19.5, 65.125, 110.75, 156.375, 202.0, 247.625, 293.25, 338.875, 384.5]

# --- SIDEBAR INPUTS ---
p_w = st.sidebar.number_input("ความกว้างชิ้นงาน (W) (mm)", value=25.0, step=1.0)
p_l = st.sidebar.number_input("ความยาวชิ้นงาน (L) (mm)", value=200.0, step=1.0)
p_h = st.sidebar.number_input("ความหนาชิ้นงาน (H) (mm)", value=160.0, step=1.0)
clearance = st.sidebar.slider("Clearance (mm)", 1.0, 15.0, 5.0, step=0.5)

# --- เพิ่มตัวเลือกโหมดการวาง ---
packing_mode = st.sidebar.radio("รูปแบบการวาง:", ["1) 1 ชิ้น/ช่อง", "2) วางเบียดแนวราบ", "3) เบียดราบ + ซ้อนแนวตั้ง"])

# --- CORE LOGIC (ปรับปรุงให้รองรับโหมดใหม่) ---
def get_capacity_per_slot(slot_w, slot_h, part_h, p_w, p_l, p_h, clearance, mode):
    target_w, target_l = p_w + clearance, p_l + clearance
    if mode == "1) 1 ชิ้น/ช่อง":
        return 1 if (slot_w >= target_l and slot_h >= target_w) else 0
    elif mode == "2) วางเบียดแนวราบ":
        return math.floor(slot_w / target_l) * math.floor(slot_h / target_w)
    elif mode == "3) เบียดราบ + ซ้อนแนวตั้ง":
        fits_flat = math.floor(slot_w / target_l) * math.floor(slot_h / target_w)
        fits_stack = math.floor(part_h / (p_h + clearance))
        return fits_flat * fits_stack
    return 0

def find_asymmetric_optimal_layout(pw, pl, ph, mode):
    # ... (ส่วนการวน Loop หา Layout เหมือนเดิมทุกประการ) ...
    all_dims = [pw, pl, ph]
    unique_orientations = set(itertools.permutations(all_dims))
    orientations = [{"flat_w": w, "flat_l": l, "vert_h": h, "label": f"{int(w)}x{int(l)}x{int(h)}", "is_fixed_h": (h == ph)} for w, l, h in unique_orientations]
    
    best_options = []
    subsets_x = [sorted(list(comb)) for r in range(2, len(GROOVE_X_ALL) + 1) for comb in itertools.combinations(GROOVE_X_ALL, r)]
    subsets_y = [sorted(list(comb)) for r in range(2, len(GROOVE_Y_ALL) + 1) for comb in itertools.combinations(GROOVE_Y_ALL, r)]

    for orient in orientations:
        eh = orient["vert_h"]
        part_height = 111.0 if eh + clearance <= 111.0 else (225.0 if eh + clearance <= 225.0 else None)
        if not part_height: continue
        layers = 2 if part_height == 111.0 else 1

        for ax in subsets_x:
            for ay in subsets_y:
                x_bounds, y_bounds = sorted(ax), sorted(ay)
                valid_slots = []
                total_qty = 0
                for i in range(len(x_bounds)-1):
                    for j in range(len(y_bounds)-1):
                        q = get_capacity_per_slot(x_bounds[i+1]-x_bounds[i], y_bounds[j+1]-y_bounds[j], part_height, orient["flat_w"], orient["flat_l"], orient["vert_h"], clearance, mode)
                        if q > 0:
                            valid_slots.append({"x_start": x_bounds[i], "x_end": x_bounds[i+1], "y_start": y_bounds[j], "y_end": y_bounds[j+1]})
                            total_qty += q
                
                if total_qty > 0:
                    best_options.append({
                        "qty_box": total_qty * layers, "qty_layer": total_qty, "layers": layers,
                        "part_height": part_height, "ax": ax, "ay": ay, "x_bounds": [4.0]+ax+[588.0], "y_bounds": [5.5]+ay+[398.5],
                        "valid_slots": valid_slots, "orient_label": orient["label"], "p_w_disp": orient["flat_w"], 
                        "p_l_disp": orient["flat_l"], "p_h_disp": orient["vert_h"], "is_fixed_h": orient["is_fixed_h"], 
                        "total_dividers": len(ax) + len(ay), "target_w": orient["flat_w"]+clearance, "target_l": orient["flat_l"]+clearance
                    })
    return best_options

# --- เรียกใช้ Logic ---
options = find_asymmetric_optimal_layout(p_w, p_l, p_h, packing_mode)

# --- [ส่วนของฟังก์ชัน render เดิมของคุณ (draw_asymmetric_svg, draw_side_view_svg, render_packing_list)] ---
# นำฟังก์ชันแสดงผล SVG ทั้งหมดของคุณใส่ตรงนี้ได้เลย (ผมเว้นไว้เพื่อไม่ให้ข้อความยาวเกินไป)
# จากนั้นเรียกใช้ในส่วนของ MAIN RENDER ด้านล่าง

# --- MAIN RENDER (คง UI เดิมที่ Manager ชอบไว้) ---
if options:
    # ... (ส่วนการคัดกรอง best_fixed, best_overall เหมือนเดิม) ...
    overall_options = sorted(options, key=lambda x: (x["qty_box"], -x["total_dividers"]), reverse=True)
    best_overall = overall_options[0]
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 รายการวัสดุและผังการวาง")
        # ตรงนี้เรียกใช้ฟังก์ชัน render_packing_list และ draw_asymmetric_svg ของคุณ
        st.write(f"ความจุรวม: {best_overall['qty_box']} ชิ้น")
        
    with col2:
        st.subheader("⏳ Side View")
        # ตรงนี้เรียกใช้ draw_side_view_svg ของคุณ
else:
    st.error("ไม่พบรูปแบบที่ใส่ชิ้นงานได้ตามโหมดที่เลือก")
