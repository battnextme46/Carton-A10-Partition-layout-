import streamlit as st
import pandas as pd
import itertools

# --- 1. โหลดข้อมูลจากไฟล์ CSV ---
@st.cache_data
def load_data():
    # โหลดไฟล์ข้อมูลที่มีอยู่
    df = pd.read_csv("MasterCarton A10 vs partition 20260708.xlsx - Partition with A10.csv")
    return df

df = load_data()

# --- 2. ฟังก์ชันค้นหาคำตอบจากตาราง (แทนที่การคำนวณสด) ---
def find_packing_from_data(dims, clearance):
    # ปรับจูนสินค้าให้เป็นช่วง (Min, Max) ตามตาราง
    w, l, h = sorted(dims)
    
    # กรองข้อมูลจาก DataFrame
    # โดยเช็คว่าขนาดสินค้าอยู่ในช่วงที่ตารางกำหนด
    matches = df[
        (df['Min.1'] <= w) & (df['MAX.1'] >= w) &
        (df['Min.2'] <= l) & (df['MAX.2'] >= l) &
        (df['Min.3'] <= h) & (df['MAX.3'] >= h)
    ]
    
    if not matches.empty:
        # คืนค่าบรรทัดแรกที่พบ
        return matches.iloc[0]
    return None

# --- 3. ส่วนของ Interface ---
st.title("📦 ระบบคำนวณพาร์ติชัน Carton A10 (Data-Driven)")

st.sidebar.header("กรอกขนาดสินค้า (mm)")
d1 = st.sidebar.number_input("Dimension 1", value=50.0)
d2 = st.sidebar.number_input("Dimension 2", value=100.0)
d3 = st.sidebar.number_input("Dimension 3", value=40.0)

# ค้นหาข้อมูล
result = find_packing_from_data([d1, d2, d3], 0)

if result is not None:
    st.success("พบข้อมูลการจัดวางที่เหมาะสมจากฐานข้อมูล!")
    st.subheader("คำแนะนำการบรรจุ:")
    st.info(result['Box Style\nsuggstion']) # แสดงค่าจากคอลัมน์ Box Style suggstion
    
    with st.expander("ดูรายละเอียดข้อมูลดิบที่พบ"):
        st.write(result)
else:
    st.warning("ไม่พบรูปแบบการบรรจุที่ตรงกับขนาดนี้ในฐานข้อมูล")
    
# แสดงตารางให้เห็นว่าระบบกำลังอ่านไฟล์
with st.expander("ดูตารางข้อมูลทั้งหมด"):
    st.dataframe(df)
