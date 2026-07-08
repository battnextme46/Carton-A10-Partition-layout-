import streamlit as st
import math

# ตั้งค่าหน้าเว็บให้สวยงามสไตล์ Modern Engineering Portal
st.set_page_config(
    page_title="Carton A10 Partition Optimizer",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📦 Auto-Select Partition Layout Design with Carton A10")
st.write("ระบบวิเคราะห์ คัดเลือกพาร์ติชัน และจำลองการจัดวางชิ้นงานตามพิกัดร่องขัดจริง (True Physical Coordinates)")

# --- CONFIGURATION ENGINE (พิกัดร่องขัดพาร์ติชันมาตรฐานกระดาษ) ---
# ขนาดภายในของกล่อง Carton A10 คือ L: 592 mm, W: 404 mm, H: 255 mm
CARTON_L = 592.0
CARTON_W = 404.0
CARTON_H = 255.0

# พิกัดแนวร่องขัด (Center-to-Center) ของแผ่นพาร์ติชันวัดตามดรออิ้งจริง
GROOVE_X_ALL = [59.5, 177.75, 296.0, 414.25, 532.5]
GROOVE_Y_ALL = [45.5, 84.625, 123.75, 162.875, 202.0, 241.125, 280.25, 319.375, 358.5]

# คำนิยามกริดพาร์ติชันที่เป็นไปได้จริงจากการดึง/เว้นระยะใบมีด (Combinations)
GRID_TEMPLATES = [
    {
        "id": "4x8",
        "name": "Standard Grid (4 x 8)",
        "desc": "ตารางร่องขัดปกติ ใส่แผ่นยาว 5 บล็อค และแผ่นสั้น 9 บล็อค",
        "v_lines": GROOVE_X_ALL,
        "h_lines": GROOVE_Y_ALL,
        "part_short_qty": 5, # แผ่นสั้นต่อชั้น
        "part_long_qty": 9,  # แผ่นยาวต่อชั้น
    },
    {
        "id": "2x8",
        "name": "Double Length Grid (2 x 8)",
        "desc": "ขยายความยาวสล็อต x2 โดยข้ามแนวร่องสั้นเว้นร่อง",
        "v_lines": [59.5, 296.0, 532.5],
        "h_lines": GROOVE_Y_ALL,
        "part_short_qty": 3,
        "part_long_qty": 9,
    },
    {
        "id": "4x4",
        "name": "Double Width Grid (4 x 4)",
        "desc": "ขยายความกว้างสล็อต x2 โดยถอดสลับร่องแผ่นพาร์ติชันตัวยาว",
        "v_lines": GROOVE_X_ALL,
        "h_lines": [45.5, 123.75, 202.0, 280.25, 358.5],
        "part_short_qty": 5,
        "part_long_qty": 5,
    },
    {
        "id": "2x4",
        "name": "Double Both Grid (2 x 4)",
        "desc": "ขยายทั้งกว้างและยาวของช่องสล็อต x2",
        "v_lines": [59.5, 296.0, 532.5],
        "h_lines": [45.5, 123.75, 202.0, 280.25, 358.5],
        "part_short_qty": 3,
        "part_long_qty": 5,
    },
    {
        "id": "4x2",
        "name": "Quad Width Grid (4 x 2)",
        "desc": "รวมช่องแนวกว้างสี่ช่วงสำหรับชิ้นงานขนาดกว้าง",
        "v_lines": GROOVE_X_ALL,
        "h_lines": [45.5, 202.0, 358.5],
        "part_short_qty": 5,
        "part_long_qty": 3,
    },
    {
        "id": "2x2",
        "name": "Quad Both Grid (2 x 2)",
        "desc": "สล็อตขนาดจัมโบ้พิเศษสำหรับแผงวงจรขนาดใหญ่",
        "v_lines": [59.5, 296.0, 532.5],
        "h_lines": [45.5, 202.0, 358.5],
        "part_short_qty": 3,
        "part_long_qty": 3,
    }
]

# --- SIDEBAR INPUTS ---
st.sidebar.header("📐 1. ขนาดผลิตภัณฑ์ (Product Dimension)")
p_w = st.sidebar.number_input("ความกว้างชิ้นงาน (Width - W) (mm)", value=30.0, step=1.0)
p_l = st.sidebar.number_input("ความยาวชิ้นงาน (Length - L) (mm)", value=100.0, step=1.0)
p_h = st.sidebar.number_input("ความหนาชิ้นงาน (Height/Thickness - H) (mm)", value=15.0, step=1.0)

st.sidebar.header("🛡️ 2. ค่าเผื่อสล็อต (Clearance Margin)")
clearance = st.sidebar.slider("ระยะเผื่อช่อง/ความหนาถุง ESD (Clearance) (mm)", 1.0, 15.0, 5.0, step=0.5)

# --- PHYSICAL CALCULATION ENGINE ---
def analyze_feasibility(pw, pl, ph):
    feasible_options = []
    
    # ทดลองหมุนชิ้นงาน 3 มิติ (6-Way Orientations)
    orientations = [
        {"dim": (pw, pl, ph), "label": "W x L x H (ปกติ)"},
        {"dim": (pw, ph, pl), "label": "W x H x L"},
        {"dim": (pl, pw, ph), "label": "L x W x H"},
        {"dim": (pl, ph, pw), "label": "L x H x W"},
        {"dim": (ph, pw, pl), "label": "H x W x L"},
        {"dim": (ph, pl, pw), "label": "H x L x W"}
    ]
    
    for orient in orientations:
        ew, el, eh = orient["dim"]
        
        # 1. เช็คด้านความสูง (Z-Axis) เพื่อระบุความสูงกระดาษและจำนวนชั้น
        # ถ้าความสูงชิ้นงานรวมระยะเผื่อน้อยกว่า 111 mm สามารถซ้อนได้ 2 ชั้น
        if eh + clearance <= 111.0:
            part_height = 111.0
            layers = 2
        elif eh + clearance <= 225.0:
            part_height = 225.0
            layers = 1
        else:
            # ความสูงเกินขีดจำกัดกล่อง Carton A10
            continue
            
        # 2. ตรวจสอบสล๊อตในแนวระนาบ XY
        for temp in GRID_TEMPLATES:
            # คำนวณความกว้างและยาวของช่องกระดาษพิกัดจริง
            v_lines = temp["v_lines"]
            h_lines = temp["h_lines"]
            
            # ขนาดช่องสล็อตมาตรฐานด้านใน (ไม่รวมขอบกันกระแทกนอก)
            slot_len = (v_lines[1] - v_lines[0])
            slot_wid = (h_lines[1] - h_lines[0])
            
            # ตรวจสอบเงื่อนไขว่าลงช่องได้หรือไม่
            # วางแนวตรง: L ชิ้นงานเข้าร่อง L สล็อต และ W ชิ้นงานเข้าร่อง W สล็อต
            fits_straight = (el + clearance <= slot_len) and (ew + clearance <= slot_wid)
            # วางหมุน 90 องศาในระนาบ: L ชิ้นงานเข้าร่อง W สล็อต และ W ชิ้นงานเข้าร่อง L สล็อต
            fits_rotated = (el + clearance <= slot_wid) and (ew + clearance <= slot_len)
            
            if fits_straight or fits_rotated:
                qty_layer = len(v_lines[:-1]) * len(h_lines[:-1]) # จำนวนช่องด้านในทั้งหมด
                qty_box = qty_layer * layers
                
                feasible_options.append({
                    "template": temp,
                    "slot_l": slot_len,
                    "slot_w": slot_wid,
                    "part_height": part_height,
                    "layers": layers,
                    "qty_layer": qty_layer,
                    "qty_box": qty_box,
                    "orient_label": orient["label"],
                    "fit_rotated": fits_rotated and not fits_straight,
                    "used_dims": (ew, el, eh)
                })
                
    # จัดอันดับตัวเลือกที่จุของได้มากที่สุดก่อน (Optimal)
    if feasible_options:
        feasible_options.sort(key=lambda x: x["qty_box"], reverse=True)
        return feasible_options
    return []

options = analyze_feasibility(p_w, p_l, p_h)

# --- SVG REAL BLUEPRINT RENDERER ---
def draw_real_groove_svg(opt):
    temp = opt["template"]
    v_lines = temp["v_lines"]
    h_lines = temp["h_lines"]
    
    # อัตราส่วนสเกลภาพให้พอดีหน้าจอเว็บ (สเกล 1.5 เท่า)
    scale = 1.5
    pad_x = 60
    pad_y = 60
    
    view_w = (CARTON_L * scale) + (pad_x * 2)
    view_h = (CARTON_W * scale) + (pad_y * 2)
    
    svg = f'<svg width="100%" height="auto" viewBox="0 0 {view_w} {view_h}" xmlns="http://www.w3.org/2000/svg" style="background-color: #ffffff; border: 2px solid #334155; border-radius: 12px;">'
    
    # 1. วาดเส้นขอบกล่อง Carton A10 (ID)
    svg += f'<rect x="{pad_x}" y="{pad_y}" width="{CARTON_L * scale}" height="{CARTON_W * scale}" fill="#fffbeb" stroke="#b45309" stroke-width="4" rx="6" />'
    svg += f'<text x="{pad_x + (CARTON_L * scale)/2}" y="{pad_y - 20}" font-family="system-ui, sans-serif" font-size="18" font-weight="bold" fill="#78350f" text-anchor="middle">CARTON A10 (Internal Dimension: {int(CARTON_L)}x{int(CARTON_W)} mm)</text>'
    
    # 2. วาดแผ่นพาร์ติชันแนวตั้ง (Vertical Dividers)
    for vx in v_lines:
        cx = pad_x + (vx * scale)
        svg += f'<line x1="{cx}" y1="{pad_y}" x2="{cx}" y2="{pad_y + CARTON_W * scale}" stroke="#1e293b" stroke-width="4.5" stroke-dasharray="6,4" />'
        
    # 3. วาดแผ่นพาร์ติชันแนวนอน (Horizontal Dividers)
    for vy in h_lines:
        cy = pad_y + (vy * scale)
        svg += f'<line x1="{pad_x}" y1="{cy}" x2="{pad_x + CARTON_L * scale}" y2="{cy}" stroke="#1e293b" stroke-width="4.5" stroke-dasharray="6,4" />'
        
    # 4. วาดโมเดลผลิตภัณฑ์จัดวางจริงลงในแต่ละช่อง
    ew, el, eh = opt["used_dims"]
    
    # พิกัดกริดสล็อตด้านใน
    for i in range(len(v_lines) - 1):
        for j in range(len(h_lines) - 1):
            x_start = v_lines[i]
            x_end = v_lines[i+1]
            y_start = h_lines[j]
            y_end = h_lines[j+1]
            
            slot_w_actual = x_end - x_start
            slot_h_actual = y_end - y_start
            
            # คำนวณจุดกึ่งกลางของสล็อตกระดาษ
            mid_x = pad_x + ((x_start + slot_w_actual/2) * scale)
            mid_y = pad_y + ((y_start + slot_h_actual/2) * scale)
            
            # ขนาดและทิศทางของชิ้นงานที่จะนำมาวาด
            rect_w_mm = el if not opt["fit_rotated"] else ew
            rect_h_mm = ew if not opt["fit_rotated"] else el
            
            # ปรับสเกลภาพวาดผลิตภัณฑ์
            draw_w = rect_w_mm * scale
            draw_h = rect_h_mm * scale
            
            rect_x = mid_x - (draw_w / 2)
            rect_y = mid_y - (draw_h / 2)
            
            # วาดตัวสินค้า (สีส้ม ESD อ่อน)
            svg += f'<rect x="{rect_x}" y="{rect_y}" width="{draw_w}" height="{draw_h}" fill="#fed7aa" stroke="#ea580c" stroke-width="1.5" rx="4" />'
            
            # ใส่ข้อความระบุชื่อชิ้นงานและขนาด
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
        st.success(f"🔥 **ผลวิเคราะห์รูปแบบกริดที่ดีที่สุด:** {best_opt['template']['name']}")
        st.info(f"💡 **ทิศทางการจัดวางชิ้นงาน:** {best_opt['orient_label']}")
        
        # คำนวณจำนวนพาร์ติชันรวมตามระดับชั้น (Layers)
        layers_count = best_opt["layers"]
        p_temp = best_opt["template"]
        
        total_short_parts = p_temp["part_short_qty"] * layers_count
        total_long_parts = p_temp["part_long_qty"] * layers_count
        paper_pads = layers_count + 1 # แผ่นรองล่าง, แผ่นกั้นระหว่างชั้น, แผ่นปิดบนสุด
        
        # สร้างใบ Bill of Materials (BOM) สวยงาม
        bom_items = [
            {"name": "กล่องกระดาษภายนอก (Master Carton A10)", "qty": "1 Pcs", "spec": "OD: 602x414x270 mm | ID: 592x404x255 mm"},
            {"name": f"แผ่นพาร์ติชันตัวสั้น (PARTITION {'111' if best_opt['part_height'] == 111.0 else '225'}x393)", "qty": f"{total_short_parts} Pcs", "spec": "9 ร่องบาก ล็อคความกว้างกล่อง"},
            {"name": f"แผ่นพาร์ติชันตัวยาว (PARTITION {'111' if best_opt['part_height'] == 111.0 else '225'}x584)", "qty": f"{total_long_parts} Pcs", "spec": "5 ร่องบาก ล็อคความยาวกล่อง"},
            {"name": "แผ่นกระดาษลูกฟูกรองขอบแบน (Corrugated Paper Pad)", "qty": f"{paper_pads} Pcs", "spec": "394 x 574 mm"},
            {"name": "ซองพลาสติกกันไฟฟ้าสถิตย์ (ESD Anti-Static Bag)", "qty": f"{best_opt['qty_box']} Pcs", "spec": "ขนาดพอดีตัว PCBA สวมใส่ก่อนแพ็ค"}
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
            
        # การ์ดเมทริกซ์สรุปตัวชี้วัดกำลังผลิต
        m1, m2, m3 = st.columns(3)
        m1.metric("จำนวนสินค้า / ชั้น", f"{best_opt['qty_layer']} Pcs")
        m2.metric("จำนวนชั้น (Layers)", f"{best_opt['layers']} ชั้น")
        m3.metric("ความจุรวม/กล่อง (Qty/Box)", f"{best_opt['qty_box']} Pcs")

    with col2:
        st.subheader("📐 2. แผนผังการแพ็คแบบจำลองเสมือนจริง (Real Grid Layout Blueprint)")
        st.write(draw_real_groove_svg(best_opt), unsafe_allow_html=True)
        st.caption(f"หมายเหตุ: เส้นประสีเทาเข้มระบุตำแหน่งแกนใบมีดร่องจริง {int(best_opt['slot_l'])}x{int(best_opt['slot_w'])} mm (อ้างอิงระยะห่างปลอดภัยและป้องกันความเสียหายบริเวณขอบกล่อง)")

    # แสดงรายการตารางเปรียบเทียบ Grid Layout ทั้งหมดด้านล่าง
    st.write("---")
    st.subheader("📊 ตารางวิเคราะห์รูปแบบกริดและทิศทางการจัดวางที่เป็นไปได้ทั้งหมด (All Feasible Configuration Summary)")
    
    summary_table = []
    for idx, opt in enumerate(options):
        summary_table.append({
            "อันดับความจุ": "🏆 ดีที่สุด (Optimal)" if idx == 0 else f"ทางเลือกที่ {idx+1}",
            "รูปแบบกริดพาร์ติชัน": opt["template"]["name"],
            "ทิศทางการหมุนชิ้นงาน": opt["orient_label"],
            "ขนาดช่องสล็อต (WxLxH)": f"{int(opt['slot_w'])} x {int(opt['slot_l'])} x {int(opt['part_height'])} mm",
            "ความจุต่อชั้น (Layer Qty)": f"{opt['qty_layer']} Pcs",
            "จำนวนชั้นทั้งหมด (Layers)": f"{opt['layers']} ชั้น",
            "ความจุรวมกล่อง (Box Qty)": f"{opt['qty_box']} Pcs/Box"
        })
    st.dataframe(summary_table, use_container_width=True)

else:
    st.error("❌ ไม่พบขนาดพาร์ติชันแบบใดที่สามารถบรรจุผลิตภัณฑ์ขนาดนี้ลงในกล่อง Carton A10 ได้จริง กรุณาปรับระยะ Clearance หรือตรวจสอบขนาดผลิตภัณฑ์อีกครั้ง")
