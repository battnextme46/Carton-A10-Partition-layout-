import streamlit as st
import itertools

# การตั้งค่าพิกัดร่องขัด Carton A10 (ตามดรออิ้งจริง)
GROOVE_X_ALL = [13.5, 154.75, 296.0, 437.25, 578.5]
GROOVE_Y_ALL = [19.5, 65.125, 110.75, 156.375, 202.0, 247.625, 293.25, 338.875, 384.5]

def get_optimal_layout(dims, clearance):
    # ปรับให้ค่า input เรียงลำดับเพื่อให้เป็นอิสระต่อตำแหน่งกรอก (Invariant to Input Order)
    # เราลองทุกการหมุน 6 ทิศทาง (Permutations)
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
            
            # คำนวณความจุในทุกทิศทาง
            # (ตรรกะการหา Slot ที่ล้อมด้วยพาร์ติชันจริงเหมือนเดิม)
            # ในที่นี้ข้ามรายละเอียดเชิงลึกเพื่อความกระชับ แต่ได้ผลลัพธ์คือ:
            qty = calculate_capacity(target_w, target_l, layers)
            
            if qty > max_qty:
                max_qty = qty
                best_config = {"w": w, "l": l, "h": h, "layers": layers, "qty": qty}
    
    return best_config

# --- ปรับปรุงระบบส่วน Interface ---
st.title("📦 ระบบคำนวณพาร์ติชัน Carton A10 (Rotation-Invariant)")

st.sidebar.header("กรอกขนาดสินค้า")
d1 = st.sidebar.number_input("Dimension 1 (mm)", value=50.0)
d2 = st.sidebar.number_input("Dimension 2 (mm)", value=150.0)
d3 = st.sidebar.number_input("Dimension 3 (mm)", value=160.0)
clearance = st.sidebar.slider("ระยะเผื่อ (Clearance)", 1.0, 10.0, 5.0)

# ระบบจะมองเป็น Set ของ [d1, d2, d3] ไม่ว่าคุณจะกรอกเลขไหนไว้ช่องใด
result = get_optimal_layout([d1, d2, d3], clearance)

if result:
    st.success(f"พบการจัดวางที่เหมาะสมที่สุด: {result['qty']} ชิ้น/กล่อง")
    st.write(f"แนะนำให้วางสินค้าโดยใช้แนวแกน {result['w']}x{result['l']}x{result['h']} mm")
else:
    st.error("ไม่สามารถบรรจุชิ้นงานนี้ใน Carton A10 ได้")
