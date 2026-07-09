import streamlit as st
import math

# ตั้งค่าหน้าเว็บให้สวยงามสไตล์ Modern Engineering Portal
st.set_page_config(
    page_title="Carton A10 Partition Optimizer",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📦 Auto-Select Partition Layout Design with Carton A10")
st.write("ระบบวิเคราะห์และคัดเลือกพาร์ติชันแบบไดนามิก ตามพิกัดร่องขัดจริง (True Physical Groove Coordinate System)")

# --- CONFIGURATION ENGINE (พิกัดร่องขัดพาร์ติชันมาตรฐานกระดาษ) ---
# ขนาดภายในของกล่อง Carton A10 คือ L: 592 mm, W: 404 mm, H: 255 mm
CARTON_L = 592.0
CARTON_W = 404.0
CARTON_H = 255.0

# พิกัดแนวร่องขัด (Center-to-Center) ของแผ่นพาร์ติชันวัดตามดรออิ้งจริง
# แผ่นยาว 584 มม. (ระยะเผื่อหัวท้ายฝั่งละ 4 มม.) -> มีร่องบาก 5 จุด
GROOVE_X_ALL = [59.5, 177.75, 296.0, 414.25, 532.5]
# แผ่นสั้น 393 มม. (ระยะเผื่อหัวท้ายฝั่งละ 5.5 มม.) -> มีร่องบาก 9 จุด
GROOVE_Y_ALL = [45.5, 84.625, 123.75, 162.875, 202.0, 241.125, 280.25, 319.375, 358.5]

# --- SIDEBAR INPUTS ---
st.sidebar.header("📐 1. ขนาดผลิตภัณฑ์ (Product Dimension)")
p_w = st.sidebar.number_input("ความกว้างชิ้นงาน (Width - W) (mm)", value=30.0, step=1.0)
p_l = st.sidebar.number_input("ความยาวชิ้นงาน (Length - L) (mm)", value=250.0, step=1.0)
p_h = st.sidebar.number_input("ความหนาชิ้นงาน (Height/Thickness - H) (mm)", value=120.0, step=1.0)

st.sidebar.header("🛡️ 2. ค่าเผื่อสล็อต (Clearance Margin)")
clearance = st.sidebar.slider("ระยะเผื่อช่อง/ความหนาถุง ESD (Clearance) (mm)", 1.0, 15.0, 5.0, step=0.5)

# --- DYNAMIC SOLVER ENGINE ---
def find_asymmetric_optimal_layout(pw, pl, ph):
    # 1. เช็คความสูงและคำนวณจำนวนชั้น (Layers)
    if ph + clearance <= 111.0:
        part_height = 111.0
        layers = 2
    elif ph + clearance <= 225.0:
        part_height = 225.0
        layers = 1
    else:
        return []

    # ขนาดที่ต้องการสำหรับหนึ่งช่องสล็อตใช้งานจริง
    req_w = pw + clearance
    req_l = pl + clearance

    # ค้นหาทางเลือกการหมุน 3 มิติ (2 ทิศทางหลักในแนวราบสลับแกน XY)
    orientations = [
        {"ew": pw, "el": pl, "label": "W x L (ปกติ)", "rotated": False},
        {"ew": pl, "el": pw, "label": "L x W (หมุน 90°)", "rotated": True}
    ]

    best_options = []

    # คัดสรรกลุ่ม Subsets แผ่นแนวตั้ง (X) และแนวนอน (Y) ทั้งหมดเพื่อทดสอบความคุ้มค่า
    # เพื่อลดเวลาประมวลผลบนเว็บแอป เราจะสร้าง Combinations แบบสไลด์สมมาตรและไม่สมมาตรที่สมเหตุสมผลเชิงวิศวกรรม
    import itertools
    
    # เจนเนอเรต Subset ที่เป็นไปได้ของแนวแกน X (แผ่นแนวตั้ง 0 ถึง 5 แผ่น)
    subsets_x = []
    for r in range(len(GROOVE_X_ALL) + 1):
        for comb in itertools.combinations(GROOVE_X_ALL, r):
            subsets_x.append(list(comb))

    # เจนเนอเรต Subset ที่เป็นไปได้ของแนวแกน Y (แผ่นแนวนอน 0 ถึง 9 แผ่น)
    # เพื่อป้องกันแอปหน่วง เราจะเลือกเฟ้นแผ่นสลับระยะแบบพารามิเตอร์ระบบบากฟัน
    subsets_y = []
    # ลองรันการขัดร่อง Y แบบเลือกบากทุกร่อง, บากเว้นร่อง, บากเว้นสองร่อง หรือเลือกแบบไม่สมมาตร
    y_presets = [
        [], # ไม่ใส่เลย
        GROOVE_Y_ALL, # ใส่ทั้งหมด
        [45.5, 123.75, 202.0, 280.25, 358.5], # เว้นหนึ่งช่อง
        [45.5, 202.0, 358.5], # เว้นสองช่อง
        [45.5, 280.25], # ไม่สมมาตร 1
        [123.75, 358.5], # ไม่สมมาตร 2
        [162.875], # แบ่งช่องเดี่ยวขยายใหญ่
        [202.0] # แบ่งครึ่งกล่องพอดี
    ]
    # รวมกับบาง Combination อิสระ
    for r in [1, 2, 3, 4, 9]:
        for comb in itertools.combinations(GROOVE_X_ALL if r < 5 else GROOVE_Y_ALL, min(r, len(GROOVE_Y_ALL))):
            subsets_y.append(list(comb))
    
    # ทำความสะอาดข้อมูลซ้ำใน Presets
    unique_subsets_y = []
    for s in y_presets + subsets_y:
        s_sorted = sorted(s)
        if s_sorted not in unique_subsets_y:
            unique_subsets_y.append(s_sorted)

    # วนลูปทดสอบทุกแนวคิด
    for orient in orientations:
        target_w = orient["ew"] + clearance
        target_l = orient["el"] + clearance

        for ax in subsets_x:
            for ay in unique_subsets_y:
                # สร้างแนวขอบเขตช่องจริง (Boundary)
                # แผ่นยาว 584 มม. วางตาม L -> ขอบซ้ายกระดาษอยู่ที่ 4.0 มม. ขอบขวาอยู่ที่ 588.0 มม.
                x_bounds = [4.0] + ax + [588.0]
                # แผ่นสั้น 393 มม. วางตาม W -> ขอบล่างอยู่ที่ 5.5 มม. ขอบบนอยู่ที่ 398.5 มม.
                y_bounds = [5.5] + ay + [398.5]

                # ตรวจสอบสล็อตย่อยที่เกิดขึ้น
                valid_slots = []
                total_slots_created = 0

                for i in range(len(x_bounds) - 1):
                    for j in range(len(y_bounds) - 1):
                        slot_w = x_bounds[i+1] - x_bounds[i]
                        slot_h = y_bounds[j+1] - y_bounds[j]
                        total_slots_created += 1

                        # ชิ้นงานลงล็อกช่องนี้ได้หรือไม่
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
                        "x_bounds": x_bounds,
                        "y_bounds": y_bounds,
                        "valid_slots": valid_slots,
                        "orient_label": orient["label"],
                        "target_w": target_w,
                        "target_l": target_l,
                        "p_w_disp": orient["ew"],
                        "p_l_disp": orient["el"],
                        "total_dividers": len(ax) + len(ay)
                    })

    # จัดอันดับความคุ้มค่า:
    # 1. ได้จำนวนบ๊อกซ์สูงสุด (Quantity)
    # 2. จำนวนแผ่นกั้นรวมน้อยที่สุด (ประหยัดค่าวัสดุและประกอบง่าย)
    if best_options:
        best_options.sort(key=lambda x: (x["qty_box"], -x["total_dividers"]), reverse=True)
        return best_options
    return []

options = find_asymmetric_optimal_layout(p_w, p_l, p_h)

# --- SVG REAL BLUEPRINT RENDERER ---
def draw_asymmetric_svg(opt):
    x_bounds = opt["x_bounds"]
    y_bounds = opt["y_bounds"]
    ax = opt["ax"]
    ay = opt["ay"]
    valid_slots = opt["valid_slots"]
    
    scale = 1.5
    pad_x = 60
    pad_y = 60
    
    view_w = (CARTON_L * scale) + (pad_x * 2)
    view_h = (CARTON_W * scale) + (pad_y * 2)
    
    svg = f'<svg width="100%" height="auto" viewBox="0 0 {view_w} {view_h}" xmlns="http://www.w3.org/2000/svg" style="background-color: #ffffff; border: 2px solid #334155; border-radius: 12px;">'
    
    # 1. วาดเส้นขอบกล่อง Carton A10 (ID)
    svg += f'<rect x="{pad_x}" y="{pad_y}" width="{CARTON_L * scale}" height="{CARTON_W * scale}" fill="#f8fafc" stroke="#1e293b" stroke-width="4" rx="6" />'
    svg += f'<text x="{pad_x + (CARTON_L * scale)/2}" y="{pad_y - 20}" font-family="system-ui, sans-serif" font-size="18" font-weight="bold" fill="#0f172a" text-anchor="middle">CARTON A10 (Internal Dimension: {int(CARTON_L)}x{int(CARTON_W)} mm)</text>'
    
    # 2. วาดขอบเขตเนื้อกระดาษแผ่นพาร์ติชันตัวนอกสุด (Buffer Margins)
    svg += f'<rect x="{pad_x + 4.0*scale}" y="{pad_y + 5.5*scale}" width="{(584.0)*scale}" height="{(393.0)*scale}" fill="none" stroke="#94a3b8" stroke-dasharray="4,4" stroke-width="1.5" />'

    # 3. วาดแผ่นพาร์ติชันแนวตั้งเฉพาะที่เลือกใช้งานจริง (Active X Dividers)
    for vx in ax:
        cx = pad_x + (vx * scale)
        svg += f'<line x1="{cx}" y1="{pad_y + 5.5*scale}" x2="{cx}" y2="{pad_y + 398.5*scale}" stroke="#dc2626" stroke-width="4" stroke-linecap="round" />'
        
    # 4. วาดแผ่นพาร์ติชันแนวนอนเฉพาะที่เลือกใช้งานจริง (Active Y Dividers)
    for vy in ay:
        cy = pad_y + (vy * scale)
        svg += f'<line x1="{pad_x + 4.0*scale}" y1="{cy}" x2="{pad_x + 588.0*scale}" y2="{cy}" stroke="#dc2626" stroke-width="4" stroke-linecap="round" />'
        
    # 5. วาดโมเดลผลิตภัณฑ์จัดวางจริงลงในแต่ละสล็อตที่ผ่านการรับรองขนาด
    for slot in valid_slots:
        slot_w = slot["x_end"] - slot["x_start"]
        slot_h = slot["y_end"] - slot["y_start"]
        
        mid_x = pad_x + ((slot["x_start"] + slot_w/2) * scale)
        mid_y = pad_y + ((slot["y_start"] + slot_h/2) * scale)
        
        # ปรับสเกลกล่องชิ้นงานให้ห่างขอบช่องเล็กน้อย (จำลองการสวมซอง ESD และป้องกันชนขอบช่องกั้น)
        draw_w = opt["p_l_disp"] * scale
        draw_h = opt["p_w_disp"] * scale
        
        rect_x = mid_x - (draw_w / 2)
        rect_y = mid_y - (draw_h / 2)
        
        # วาดบ๊อกซ์ผลิตภัณฑ์ PCBA (สีส้ม ESD พาสเทล)
        svg += f'<rect x="{rect_x}" y="{rect_y}" width="{draw_w}" height="{draw_h}" fill="#fed7aa" stroke="#ea580c" stroke-width="1.5" rx="4" />'
        
        # ป้ายกำกับข้อความในช่อง
        svg += f'<text x="{mid_x}" y="{mid_y - 2}" font-family="system-ui, sans-serif" font-size="10" font-weight="bold" fill="#7c2d12" text-anchor="middle">PCBA</text>'
        svg += f'<text x="{mid_x}" y="{mid_y + 11}" font-family="system-ui, sans-serif" font-size="9.5" fill="#ea580c" text-anchor="middle">{int(p_w)}x{int(p_l)}x{int(p_h)}</text>'
            
    svg += '</svg>'
    return svg

# --- MAIN RENDER ---
if options:
    best_opt = options[0]
    
    col1, col2 = st.columns([1, 1.3])
    
    with col1:
        st.subheader("📋 1. รายละเอียดวัสดุบรรจุภัณฑ์ (Packing List)")
        st.success(f"🔥 **วิเคราะห์รูปแบบกริดที่ดีที่สุดแบบไม่สมมาตร:** {best_opt['qty_layer']} ช่อง/ชั้น")
        st.info(f"💡 **ทิศทางการจัดวางชิ้นงาน:** {best_opt['orient_label']}")
        
        # สรุปปริมาณแผ่นกั้นใช้งานจริง
        active_x_qty = len(best_opt["ax"])
        active_y_qty = len(best_opt["ay"])
        layers_count = best_opt["layers"]
        paper_pads = layers_count + 1
        
        # ใบรายการชิ้นส่วนวัสดุแพ็คเกจจิ้ง (BOM)
        bom_items = [
            {"name": "กล่องกระดาษภายนอก (Master Carton A10)", "qty": "1 Pcs", "spec": "OD: 602x414x270 mm | ID: 592x404x255 mm"},
            {"name": f"แผ่นพาร์ติชันตัวสั้น (PARTITION {'111' if best_opt['part_height'] == 111.0 else '225'}x393)", "qty": f"{active_x_qty * layers_count} Pcs", "spec": f"ใช้จริง {active_x_qty} แผ่นกั้นแนวตั้งต่อชั้น (ดึงออก {5 - active_x_qty} แผ่น)"},
            {"name": f"แผ่นพาร์ติชันตัวยาว (PARTITION {'111' if best_opt['part_height'] == 111.0 else '225'}x584)", "qty": f"{active_y_qty * layers_count} Pcs", "spec": f"ใช้จริง {active_y_qty} แผ่นกั้นแนวนอนต่อชั้น (ดึงออก {9 - active_y_qty} แผ่น)"},
            {"name": "แผ่นกระดาษลูกฟูกรองขอบแบน (Corrugated Paper Pad)", "qty": f"{paper_pads} Pcs", "spec": "394 x 574 mm"},
            {"name": "ซองพลาสติกกันไฟฟ้าสถิตย์ (ESD Anti-Static Bag)", "qty": f"{best_opt['qty_box']} Pcs", "spec": "สวมใส่ PCBA ก่อนนำมาบรรจุลงช่องสล็อต"}
        ]
        
        for item in bom_items:
            st.markdown(f"""
            <div style="background-color: #f8fafc; border-left: 6px solid #1e293b; padding: 12px; border-radius: 8px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-weight: bold; font-size: 16px; color: #0f172a;">{item['name']}</div>
                        <div style="font-size: 13px; color: #64748b;">{item['spec']}</div>
                    </div>
                    <span style="background-color: #1e293b; color: white; padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 14px;">{item['qty']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        m1, m2, m3 = st.columns(3)
        m1.metric("จำนวนสินค้า / ชั้น", f"{best_opt['qty_layer']} Pcs")
        m2.metric("จำนวนชั้น (Layers)", f"{best_opt['layers']} ชั้น")
        m3.metric("ความจุรวม/กล่อง (Qty/Box)", f"{best_opt['qty_box']} Pcs")

    with col2:
        st.subheader("📐 2. แผนผังการแพ็คแบบจำลองจริง (Asymmetric Partition Blueprint)")
        st.write(draw_asymmetric_svg(best_opt), unsafe_allow_html=True)
        st.caption("หมายเหตุ: เส้นสีแดงทึบระบุตำแหน่งแผ่นกั้นกระดาษพาร์ติชันที่ต้องใส่เข้างานจริง และเว้นส่วนที่เหลือออกเพื่อขยายขนาดสล็อตแบบอสมมาตร")

    # แสดงรายการทางเลือกทั้งหมดด้านล่าง
    st.write("---")
    st.subheader("📊 ตารางวิเคราะห์รูปแบบกริดที่เป็นไปได้ทั้งหมด (All Feasible Configuration Summary)")
    
    summary_table = []
    for idx, opt in enumerate(options[:8]): # แสดง Top 8 ทางเลือกเพื่อความสะอาดของตาราง
        summary_table.append({
            "อันดับความจุ": "🏆 ดีที่สุด (Optimal)" if idx == 0 else f"ทางเลือกที่ {idx+1}",
            "ทิศทางจัดวาง": opt["orient_label"],
            "แผ่นแนวตั้งที่ใช้ (Short)": f"{len(opt['ax'])} / 5 Pcs",
            "แผ่นแนวนอนที่ใช้ (Long)": f"{len(opt['ay'])} / 9 Pcs",
            "ความจุต่อชั้น (Layer Qty)": f"{opt['qty_layer']} Pcs",
            "จำนวนชั้นทั้งหมด (Layers)": f"{opt['layers']} ชั้น",
            "ความจุรวมกล่อง (Box Qty)": f"{opt['qty_box']} Pcs/Box"
        })
    st.dataframe(summary_table, use_container_width=True)

else:
    st.error("❌ ไม่พบรูปแบบแผ่นพาร์ติชันกระดาษลูกฟูกสเกลใดที่สามารถบรรจุผลิตภัณฑ์ขนาดนี้ลงในกล่อง Carton A10 ได้จริง กรุณาปรับระยะ Clearance หรือตรวจสอบขนาดผลิตภัณฑ์อีกครั้ง")
