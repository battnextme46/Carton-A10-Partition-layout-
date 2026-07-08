import streamlit as st
import pandas as pd
import numpy as np
import math
import os
import glob

# ตั้งค่าหน้าเว็บให้สวยงามสไตล์ Modern Engineering Portal
st.set_page_config(
    page_title="Partition Selector & Layout Optimizer",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📦 Auto-Select Partition Layout Design with Carton A10")
st.write("ระบบวิเคราะห์และเลือกรูปแบบพาร์ติชัน (Partition Grid) พร้อมจำลองการวางชิ้นงานจริงในร่องฟันอัตโนมัติ")

# --- DATABASE DEFINITION (ข้อมูลสำรองที่อ้างอิงตรงตามตารางจริงใน Excel) ---
FALLBACK_DATA = [
    {
        "item": 1, "w_min": 1.0, "w_max": 105.0, "l_min": 1.0, "l_max": 115.0, "h_min": 1.0, "h_max": 35.0,
        "layers": 2, "qty_layer": 32, "qty_box": 64,
        "bom_text": "CARTON A-10 = 1 pcs.\nPARTITION 111X393MM = 10 pcs./box\nPARTITION 111x584MM = 18 pcs./box\nPAPER PAD 394X574MM = 3 pcs./box\nESD BAG 7.5\"X10\" = 64 pcs./box",
        "nx": 8, "ny": 4,  # ตารางหลักขนาด 8x4 ช่องใช้งานจริงต่อหนึ่งเลเยอร์
        "type": "standard_grid"
    },
    {
        "item": 2, "w_min": 1.0, "w_max": 105.0, "l_min": 116.0, "l_max": 235.0, "h_min": 1.0, "h_max": 35.0,
        "layers": 2, "qty_layer": 16, "qty_box": 32,
        "bom_text": "CARTON A-10 = 1 pcs.\nPARTITION 111X393MM = 6 pcs./box\nPARTITION 111x584MM = 18 pcs./box\nPAPER PAD 394X574MM = 3 pcs./box\nESD BAG 7.5\"X10\" = 32 pcs./box",
        "nx": 4, "ny": 4,  # รวมช่องสล็อตในแนวยาว
        "type": "merged_length"
    },
    {
        "item": 3, "w_min": 1.0, "w_max": 105.0, "l_min": 236.0, "l_max": 240.0, "h_min": 1.0, "h_max": 35.0,
        "layers": 2, "qty_layer": 16, "qty_box": 32,
        "bom_text": "CARTON A-10 = 1 pcs.\nPARTITION 111X393MM = 6 pcs./box\nPARTITION 111x584MM = 18 pcs./box\nPAPER PAD 394X574MM = 3 pcs./box\nESD BAG 7.5\"X10\" = 32 pcs./box",
        "nx": 4, "ny": 4,
        "type": "merged_length"
    },
    {
        "item": 4, "w_min": 1.0, "w_max": 105.0, "l_min": 116.0, "l_max": 240.0, "h_min": 36.0, "h_max": 80.0,
        "layers": 2, "qty_layer": 8, "qty_box": 16,
        "bom_text": "CARTON A-10 = 1 pcs.\nPARTITION 111X393MM = 6 pcs./box\nPARTITION 111x584MM = 10 pcs./box\nPAPER PAD 394X574MM = 3 pcs./box\nESD BAG 7.5\"X10\" = 16 pcs./box",
        "nx": 4, "ny": 2,  # ตารางแบบ 4x2 ช่องใหญ่
        "type": "merged_both"
    },
    {
        "item": 5, "w_min": 1.0, "w_max": 105.0, "l_min": 116.0, "l_max": 240.0, "h_min": 81.0, "h_max": 170.0,
        "layers": 2, "qty_layer": 4, "qty_box": 8,
        "bom_text": "CARTON A-10 = 1 pcs.\nPARTITION 111X393MM = 6 pcs./box\nPARTITION 111x584MM = 6 pcs./box\nPAPER PAD 394X574MM = 3 pcs./box\nESD BAG 7.5\"X10\" = 8 pcs./box",
        "nx": 2, "ny": 2,  # ตารางแบบ 2x2 ช่องขนาดใหญ่สุด
        "type": "merged_max"
    },
    {
        "item": 6, "w_min": 1.0, "w_max": 115.0, "l_min": 111.0, "l_max": 220.0, "h_min": 1.0, "h_max": 35.0,
        "layers": 1, "qty_layer": 32, "qty_box": 32,
        "bom_text": "CARTON A-10 = 1 pcs.\nPARTITION 225X393MM = 5 pcs./box\nPARTITION 225x584MM = 9 pcs./box\nPAPER PAD 394X574MM = 2 pcs./box\nESD BAG 7.5\"X10\" = 32 pcs./box",
        "nx": 8, "ny": 4,
        "type": "standard_grid"
    }
]

# --- LOAD DATA FROM UPLOADED CSV IF PRESENT ---
def load_database():
    csv_files = glob.glob("*Partition with A10*.csv")
    if csv_files:
        try:
            df = pd.read_csv(csv_files[0], skiprows=3)
            df = df.dropna(subset=['Min', 'MAX', 'Min.1', 'MAX.1', 'Min.2', 'MAX.2'])
            cleaned_rules = []
            for idx, row in df.iterrows():
                try:
                    item_num = int(row.iloc[0])
                    p_type = "standard_grid"
                    if item_num in [2, 3]:
                        p_type = "merged_length"
                    elif item_num == 4:
                        p_type = "merged_both"
                    elif item_num == 5:
                        p_type = "merged_max"

                    cleaned_rules.append({
                        "item": item_num,
                        "w_min": float(row.iloc[13]), "w_max": float(row.iloc[14]),
                        "l_min": float(row.iloc[15]), "l_max": float(row.iloc[16]),
                        "h_min": float(row.iloc[17]), "h_max": float(row.iloc[18]),
                        "layers": int(row.iloc[19]), "qty_layer": int(row.iloc[20]), "qty_box": int(row.iloc[21]),
                        "bom_text": str(row.iloc[22]),
                        "nx": int(row.iloc[20]) // 4 if int(row.iloc[20]) % 4 == 0 else int(row.iloc[20]) // 2,
                        "ny": 4,
                        "type": p_type
                    })
                except Exception:
                    continue
            if len(cleaned_rules) > 0:
                return cleaned_rules
        except Exception:
            pass
    return FALLBACK_DATA

db = load_database()

# --- SIDEBAR INPUTS ---
st.sidebar.header("📐 1. ขนาดผลิตภัณฑ์ (Product Dimension)")
p_w = st.sidebar.number_input("ความกว้างชิ้นงาน (Width - W) (mm)", value=50.0, step=1.0)
p_l = st.sidebar.number_input("ความยาวชิ้นงาน (Length - L) (mm)", value=100.0, step=1.0)
p_h = st.sidebar.number_input("ความหนา/ความสูงชิ้นงาน (Height/Thickness - H) (mm)", value=15.0, step=1.0)

st.sidebar.header("⚙️ 2. ตัวเลือกเสริม (Options)")
auto_rotate = st.sidebar.checkbox("หมุนหรือสลับทิศทางผลิตภัณฑ์อัตโนมัติ (Auto-Orientation Swap)", value=True)

# --- SEARCH LOGIC & ORIENTATION CHECK ---
def find_matching_package(w, l, h):
    orientations = [
        (w, l, h), (w, h, l),
        (l, w, h), (l, h, w),
        (h, w, l), (h, l, w)
    ] if auto_rotate else [(w, l, h)]

    matched_results = []
    for (ew, el, eh) in orientations:
        for rule in db:
            w_match = rule["w_min"] <= ew <= rule["w_max"]
            l_match = rule["l_min"] <= el <= rule["l_max"]
            h_match = rule["h_min"] <= eh <= rule["h_max"]
            
            if w_match and l_match and h_match:
                matched_results.append({
                    "rule": rule,
                    "applied_dimensions": (ew, el, eh)
                })
                
    if matched_results:
        matched_results.sort(key=lambda x: x["rule"]["qty_box"], reverse=True)
        return matched_results[0]
    return None

result = find_matching_package(p_w, p_l, p_h)

# --- SVG REAL BLUEPRINT GENERATION ---
def draw_partition_svg(rule, pw_val, pl_val, ph_val):
    # ขนาดภายในของกล่อง Carton A10 คือ 592 x 404 mm
    carton_l, carton_w = 592, 404
    
    scale = 1.5
    margin_left = 60
    margin_top = 60
    
    svg_w = (carton_l * scale) + (margin_left * 2)
    svg_h = (carton_w * scale) + (margin_top * 2)
    
    svg = f'<svg width="100%" height="auto" viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg" style="background-color: #ffffff; border: 2px solid #1e293b; border-radius: 12px; padding: 10px;">'
    
    # 1. วาดเส้นขอบกล่อง Carton A10 (ภายในกล่อง)
    svg += f'<rect x="{margin_left}" y="{margin_top}" width="{carton_l * scale}" height="{carton_w * scale}" fill="#fef3c7" stroke="#b45309" stroke-width="4" rx="6" />'
    svg += f'<text x="{margin_left + (carton_l * scale)/2}" y="{margin_top - 20}" font-family="system-ui, sans-serif" font-size="18" font-weight="bold" fill="#78350f" text-anchor="middle">CARTON A10 Internal: 592 x 404 mm</text>'
    
    # 2. คำนวณพิกัดร่องฟันจริงจากแบบดรออิ้ง (Engineering Drawing Coordinates)
    # พาร์ติชันตัวยาว (111x584): ร่องฟันที่แกน X
    long_part_len = 584
    long_part_clearance = (carton_l - long_part_len) / 2 # 4 มม.
    # ร่องจริง 5 จุด: 55.5, 173.75, 292.0, 410.25, 528.5 มม.
    slots_x = [55.5, 173.75, 292.0, 410.25, 528.5]
    x_coords = [margin_left + (long_part_clearance + sx) * scale for sx in slots_x]
    
    # พาร์ติชันตัวสั้น (111x393): ร่องฟันที่แกน Y
    short_part_len = 393
    short_part_clearance = (carton_w - short_part_len) / 2 # 5.5 มม.
    # ร่องจริง 9 จุด: 40 + k * 39.125
    slots_y = [40 + (k * 39.125) for k in range(9)]
    y_coords = [margin_top + (short_part_clearance + sy) * scale for sy in slots_y]
    
    # 3. วาดเส้นโครงสร้างแผ่นพาร์ติชันตัวสั้น (Short Partitions - Vertical Lines)
    p_type = rule.get("type", "standard_grid")
    
    active_x_indices = [0, 1, 2, 3, 4]
    if p_type == "merged_length":
        active_x_indices = [0, 2, 4] # ลดการใส่แผ่นสั้นเพื่อขยายความยาวช่อง
    elif p_type == "merged_max":
        active_x_indices = [2] # ใช้แผ่นเดียวแบ่งตรงกลาง

    for idx in active_x_indices:
        cx = x_coords[idx]
        svg += f'<line x1="{cx}" y1="{margin_top}" x2="{cx}" y2="{margin_top + carton_w * scale}" stroke="#334155" stroke-width="4" stroke-dasharray="6,4" />'

    # 4. วาดเส้นโครงสร้างแผ่นพาร์ติชันตัวยาว (Long Partitions - Horizontal Lines)
    active_y_indices = list(range(9))
    if p_type == "merged_both":
        active_y_indices = [1, 3, 5, 7]
    elif p_type == "merged_max":
        active_y_indices = [2, 6]

    for idx in active_y_indices:
        cy = y_coords[idx]
        svg += f'<line x1="{margin_left}" y1="{cy}" x2="{margin_left + carton_l * scale}" y2="{cy}" stroke="#334155" stroke-width="4" stroke-dasharray="6,4" />'

    # 5. วาดผลิตภัณฑ์พร้อมระบุมิติลงในช่องสล็อตพาร์ติชันจริง
    all_x = [margin_left] + x_coords + [margin_left + carton_l * scale]
    all_y = [margin_top] + y_coords + [margin_top + carton_w * scale]
    
    for i in range(1, len(all_x)):
        for j in range(1, len(all_y)):
            cell_w = (all_x[i] - all_x[i-1]) / scale
            cell_h = (all_y[j] - all_y[j-1]) / scale
            
            # ชิ้นงานจัดวางเฉพาะในสล็อตใช้งาน (ไม่รวมช่อง Buffer ขอบกล่อง)
            is_inner_x = i in [2, 3, 4, 5]
            is_inner_y = j in [2, 3, 4, 5, 6, 7, 8, 9]
            
            if p_type == "merged_length":
                is_inner_x = i in [2, 3, 4]
            elif p_type == "merged_max":
                is_inner_x = i == 2
                is_inner_y = j in [2, 3, 4, 5]
                
            if is_inner_x and is_inner_y:
                # วาดกล่องสินค้าสีส้ม (พิกัดและขนาดจะย่อจากขอบสล็อตเล็กน้อยเพื่อให้เห็นพื้นที่ช่องไฟ)
                rect_x = all_x[i-1] + 4 * scale
                rect_y = all_y[j-1] + 4 * scale
                rect_w = (all_x[i] - all_x[i-1]) - 8 * scale
                rect_h = (all_y[j] - all_y[j-1]) - 8 * scale
                
                svg += f'<rect x="{rect_x}" y="{rect_y}" width="{rect_w}" height="{rect_h}" fill="#fed7aa" stroke="#ea580c" stroke-width="1.5" rx="3" />'
                
                text_x = all_x[i-1] + (all_x[i] - all_x[i-1])/2
                text_y = all_y[j-1] + (all_y[j] - all_y[j-1])/2
                
                # แสดงขนาดสินค้าในสล็อตให้เหมาะสมกับสเกลความกว้าง
                if rect_w > 40 * scale:
                    svg += f'<text x="{text_x}" y="{text_y - 2*scale}" font-family="system-ui, sans-serif" font-size="10" font-weight="bold" fill="#9a3412" text-anchor="middle">Product</text>'
                    svg += f'<text x="{text_x}" y="{text_y + 10*scale}" font-family="system-ui, sans-serif" font-size="9" fill="#c2410c" text-anchor="middle">{int(pw_val)}x{int(pl_val)}x{int(ph_val)}</text>'
                else:
                    svg += f'<text x="{text_x}" y="{text_y + 3*scale}" font-family="system-ui, sans-serif" font-size="7" font-weight="bold" fill="#9a3412" text-anchor="middle">{int(pw_val)}x{int(pl_val)}</text>'
                    
    svg += '</svg>'
    return svg

# --- MAIN DISPLAY UI ---
if result:
    rule = result["rule"]
    ew, el, eh = result["applied_dimensions"]
    
    col1, col2 = st.columns([1, 1.2])
    
    with col1:
        st.subheader("📋 1. รายละเอียดวัสดุที่ต้องใช้ (Packing List)")
        st.info(f"💡 **Case ที่จับคู่สำเร็จ:** Case {rule['item']} | **ทิศทางการแพ็ค:** กว้าง={ew} x ยาว={el} x หนา={eh} mm")
        
        # แสดงผล Bill of Materials เป็นรายการการ์ดสวยงาม
        bom_lines = rule["bom_text"].split("\n")
        for line in bom_lines:
            if line.strip():
                parts = line.split("=")
                item_name = parts[0].strip()
                item_qty = parts[1].strip() if len(parts) > 1 else ""
                
                st.markdown(f"""
                <div style="background-color: #f8fafc; border-left: 6px solid #0f172a; padding: 12px; border-radius: 8px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: bold; font-size: 16px; color: #1e293b;">{item_name}</span>
                        <span style="background-color: #334155; color: white; padding: 3px 10px; border-radius: 12px; font-weight: bold; font-size: 14px;">{item_qty}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
        # แสดงเมทริกซ์สรุปปริมาณความจุ
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("จำนวนสินค้า / ชั้น", f"{rule['qty_layer']} Pcs")
        m_col2.metric("จำนวนชั้นทั้งหมด", f"{rule['layers']} ชั้น")
        m_col3.metric("ความจุรวมต่อกล่อง", f"{rule['qty_box']} Pcs/Box")

    with col2:
        st.subheader("📐 2. แผนผังพาร์ติชันจริง (Real Groove Partition Blueprint)")
        st.write(draw_partition_svg(rule, ew, el, eh), unsafe_allow_html=True)
        st.caption("หมายเหตุ: เส้นประสีเทาเข้มแสดงพิกัดร่องฟันจริงจากดรออิ้งพาร์ติชัน 111x584 และ 111x393 สำหรับวางแผนการทำงานร่วมกับผู้ผลิต")

else:
    st.error("❌ ไม่พบขนาดกล่องพาร์ติชันที่เหมาะสมกับขนาดผลิตภัณฑ์ที่ระบุ กรุณาตรวจสอบขนาดและลองอีกครั้ง")
