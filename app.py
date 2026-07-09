import streamlit as st
import itertools

# --- ฟังก์ชันคำนวณความจุ (หัวใจหลักที่หายไป) ---
def calculate_capacity(w, l, layers):
    """
    คำนวณจำนวนชิ้นที่สามารถวางได้ใน Slot
    หมายเหตุ: นี่เป็นตรรกะเบื้องต้น หากมีสูตรคำนวณเฉพาะจากไฟล์ Excel สามารถปรับแก้ในนี้ได้เลย
    """
    # ตัวอย่างตรรกะ: สมมติฐานว่ากล่อง A10 มีขนาดพื้นที่วางจำกัด 
    # และพาร์ติชันช่วยแบ่งพื้นที่ออกเป็นช่องๆ
    box_w, box_l = 404, 592 # ID ของ Carton A10
    
    # หารจำนวนช่องที่ใส่ได้ในแต่ละแนว
    cols = box_w // w
    rows = box_l // l
    
    return int(cols * rows * layers)

# --- ส่วนของ Interface และตรรกะหลัก ---
st.title("📦 ระบบคำนวณพาร์ติชัน Carton A10")

st.sidebar.header("กรอกขนาดสินค้า")
d1 = st.sidebar.number_input("Dimension 1 (mm)", value=50.0)
d2 = st.sidebar.number_input("Dimension 2 (mm)", value=100.0)
d3 = st.sidebar.number_input("Dimension 3 (mm)", value=40.0)
clearance = st.sidebar.slider("ระยะเผื่อ (Clearance)", 1.0, 10.0, 5.0)

def get_optimal_layout(dims, clearance):
    possible_orientations = list(itertools.permutations(dims))
    
    best_config = None
    max_qty = -1

    for orient in possible_orientations:
        w, l, h = orient
        
        # เช็คขีดจำกัดความสูงกล่อง Carton A10 (255mm)
        if h + clearance > 255: continue
        
        # เลือกระดับความสูงพาร์ติชัน (111 หรือ 225)
        layer_opts = []
        if h + clearance <= 111: layer_opts.append((111, 2))
        if h + clearance <= 225: layer_opts.append((225, 1))
        
        for part_h, layers in layer_opts:
            target_w = w + clearance
            target_l = l + clearance
            
            # เรียกใช้ฟังก์ชันที่เพิ่มเข้ามา
            qty = calculate_capacity(target_w, target_l, layers)
            
            if qty > max_qty:
                max_qty = qty
                best_config = {"w": w, "l": l, "h": h, "layers": layers, "qty": qty}
    
    return best_config

# ระบบจะมองเป็น Set ของ [d1, d2, d3] ไม่ว่าคุณจะกรอกเลขไหนไว้ช่องใด
result = get_optimal_layout([d1, d2, d3], clearance)

if result:
    st.success(f"พบการจัดวางที่เหมาะสมที่สุด: {result['qty']} ชิ้น/กล่อง")
    st.write(f"แนะนำให้วางสินค้าโดยใช้แนวแกน {result['w']}x{result['l']}x{result['h']} mm")
    st.write(f"จำนวนชั้นที่ใช้: {result['layers']} ชั้น")
else:
    st.error("ไม่สามารถบรรจุชิ้นงานนี้ใน Carton A10 ได้ (ขนาดเกินหรือความสูงไม่พอ)")
