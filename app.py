import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from dataclasses import dataclass, asdict
from typing import List, Dict
import json

# إعداد الصفحة
st.set_page_config(
    page_title="Steel Quality Cloud",
    layout="wide",
    page_icon="🏭",
    initial_sidebar_state="expanded"
)

# CSS مخصص
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #2a5298;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
</style>
""", unsafe_allow_html=True)


@dataclass
class StrandData:
    strand_id: str
    d1: float
    d2: float
    sample_taken: bool
    sample_no: str = ""
    
    @property
    def rh(self) -> float:
        return round(abs(self.d1 - self.d2), 2)
    
    @property
    def status(self) -> str:
        return "PASS" if self.rh <= 8.0 else "REJECT"


@dataclass
class ProductionRecord:
    timestamp: str
    date_only: str
    time_only: str
    shift: str
    operator: str
    inspector: str
    ccm: str
    heat: str
    grade: str
    strand: str
    rh: float
    status: str
    d1: float
    d2: float
    billet_count: int
    storage_loc: str
    short_billet_length: float
    sample_info: str
    
    def to_dict(self) -> Dict:
        return asdict(self)


class GoogleSheetsManager:
    def __init__(self):
        try:
            self.conn = st.connection("gsheets", type=GSheetsConnection)
            self.worksheet_name = "production_logs"
            self.connected = True
        except Exception as e:
            st.error(f"⚠️ خطأ في الاتصال: {e}")
            self.connected = False
    
    def fetch_data(self) -> pd.DataFrame:
        if not self.connected:
            return pd.DataFrame()
        try:
            df = self.conn.read(worksheet=self.worksheet_name, ttl="0")
            if df.empty:
                return pd.DataFrame(columns=[
                    'timestamp', 'date_only', 'time_only', 'shift', 'operator',
                    'inspector', 'ccm', 'heat', 'grade', 'strand', 'rh', 'status',
                    'd1', 'd2', 'billet_count', 'storage_loc', 'short_billet_length', 'sample_info'
                ])
            return df
        except Exception as e:
            st.error(f"❌ خطأ في جلب البيانات: {e}")
            return pd.DataFrame()
    
    def save_data(self, new_records: List[Dict]) -> bool:
        if not self.connected:
            return False
        try:
            existing_data = self.fetch_data()
            new_df = pd.DataFrame(new_records)
            updated_df = pd.concat([existing_data, new_df], ignore_index=True)
            self.conn.update(worksheet=self.worksheet_name, data=updated_df)
            return True
        except Exception as e:
            st.error(f"❌ خطأ في الحفظ: {e}")
            return False


def generate_label_html(heat_no, grade, ccm, date_str, storage, b_count, s_len, strands_data):
    """توليد ملصق HTML بدلاً من PDF"""
    strands_html = ""
    for strand in strands_data:
        color = "#28a745" if strand.status == "PASS" else "#dc3545"
        status_icon = "✓" if strand.status == "PASS" else "✗"
        strands_html += f"""
        <div style="margin: 5px 0; color: {color}; font-weight: bold;">
            {strand.strand_id}: {status_icon} (RH: {strand.rh}mm)
        </div>
        """
    
    short_billet_html = f"<p><strong>Short Billet:</strong> {s_len} m</p>" if s_len > 0 else ""
    
    html = f"""
    <div style="width: 350px; border: 3px solid #2a5298; padding: 20px; margin: 20px auto; 
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); border-radius: 10px; font-family: Arial;">
        <h2 style="text-align: center; color: #1e3c72; margin-bottom: 20px; border-bottom: 2px solid #2a5298; padding-bottom: 10px;">
            🏭 QC PRODUCTION LABEL
        </h2>
        
        <div style="margin-bottom: 15px;">
            <p style="margin: 8px 0;"><strong>🔥 Heat No:</strong> {heat_no}</p>
            <p style="margin: 8px 0;"><strong>⚙️ Grade:</strong> {grade}</p>
            <p style="margin: 8px 0;"><strong>📍 Storage:</strong> {storage}</p>
            <p style="margin: 8px 0;"><strong>📊 Billet Count:</strong> {b_count}</p>
            <p style="margin: 8px 0;"><strong>🏭 CCM:</strong> {ccm}</p>
            <p style="margin: 8px 0;"><strong>📅 Date:</strong> {date_str}</p>
            {short_billet_html}
        </div>
        
        <div style="background: white; padding: 10px; border-radius: 5px; margin: 15px 0;">
            <strong>Strands Status:</strong>
            {strands_html}
        </div>
        
        <div style="text-align: center; margin-top: 20px; padding: 10px; background: white; border-radius: 5px;">
            <img src="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=HEAT:{heat_no}|LOC:{storage}" 
                 style="width: 150px; height: 150px;" />
            <p style="font-size: 12px; color: #666; margin-top: 5px;">Scan for digital record</p>
        </div>
    </div>
    """
    return html


def main():
    # تهيئة الجلسة
    if "auth" not in st.session_state:
        st.session_state.auth = False
    
    # شاشة تسجيل الدخول
    if not st.session_state.auth:
        st.markdown("""
        <div class="main-header">
            <h1>🏭 نظام إدارة جودة الصلب السحابي</h1>
            <p>Steel Quality Cloud Management System</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.container():
                st.subheader("🔐 تسجيل الدخول")
                password = st.text_input("كلمة المرور:", type="password")
                if st.button("دخول", use_container_width=True, type="primary"):
                    if password == st.secrets.get("auth", {}).get("password", "1100"):
                        st.session_state.auth = True
                        st.rerun()
                    else:
                        st.error("❌ كلمة المرور غير صحيحة!")
        return
    
    # تهيئة مدير Sheets
    sheets_manager = GoogleSheetsManager()
    
    # الشريط الجانبي
    with st.sidebar:
        st.markdown("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%); 
                    border-radius: 10px; color: white;'>
            <h3>☁️ نظام QC</h3>
            <p>متصل</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            st.session_state.auth = False
            st.rerun()
    
    # المحتوى الرئيسي
    st.markdown("""
    <div class="main-header">
        <h2>☁️ Cloud QC Management</h2>
    </div>
    """, unsafe_allow_html=True)
    
    tabs = st.tabs(["📝 إدخال جديد", "📊 لوحة التحكم", "🔍 البحث"])
    
    # تبويب الإدخال
    with tabs[0]:
        st.header("إدخال بيانات إنتاج جديدة")
        
        with st.form("production_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                heat = st.text_input("🔥 رقم الصبة", placeholder="H2024001")
                grade = st.selectbox("⚙️ الرتبة", ["B500", "B500W", "SAE1006", "SAE1008"])
                ccm = st.selectbox("🏭 الماكينة", ["CCM01", "CCM02"])
            
            with col2:
                shift = st.selectbox("⏰ الوردية", ["A", "B", "C", "D"])
                operator = st.text_input("👷 عامل الصب")
                area = st.selectbox("📍 المنطقة", ["RM01", "RM02", "RM03", "SMS"])
            
            with col3:
                billet_count = st.number_input("📊 العدد", min_value=1, value=40)
                max_boxes = 9 if area == "SMS" else 5
                box = st.selectbox("📦 الصندوق", [f"Box {i}" for i in range(1, max_boxes)])
                short_l = st.number_input("📏 Short Billet (m)", min_value=0.0, value=0.0)
            
            st.divider()
            st.subheader("📐 قياسات Strands (الحد الأقصى: 8mm)")
            
            strand_data_list = []
            strand_cols = st.columns(5)
            
            for i in range(1, 6):
                with strand_cols[i-1]:
                    st.write(f"**Strand 0{i}**")
                    d1 = st.number_input(f"D1", key=f"d1_{i}", min_value=0.0, step=0.1)
                    d2 = st.number_input(f"D2", key=f"d2_{i}", min_value=0.0, step=0.1)
                    sample = st.checkbox(f"عينة", key=f"s_{i}")
                    s_no = st.text_input("ترتيب", key=f"sn_{i}") if sample else ""
                    
                    strand = StrandData(
                        strand_id=f"S0{i}",
                        d1=d1,
                        d2=d2,
                        sample_taken=sample,
                        sample_no=s_no
                    )
                    strand_data_list.append(strand)
                    
                    status_color = "🟢" if strand.status == "PASS" else "🔴"
                    st.caption(f"{status_color} RH: {strand.rh}mm")
            
            submitted = st.form_submit_button("💾 حفظ في السحابة", use_container_width=True, type="primary")
            
            if submitted:
                if not heat or not operator:
                    st.error("❌ يجب ملء جميع الحقول الإلزامية!")
                else:
                    now = datetime.now()
                    records = []
                    
                    for strand in strand_data_list:
                        if strand.d1 > 0 or strand.d2 > 0:
                            record = ProductionRecord(
                                timestamp=now.strftime("%Y-%m-%d %H:%M:%S"),
                                date_only=now.strftime("%Y-%m-%d"),
                                time_only=now.strftime("%H:%M:%S"),
                                shift=shift,
                                operator=operator,
                                inspector="Admin",
                                ccm=ccm,
                                heat=heat,
                                grade=grade,
                                strand=strand.strand_id,
                                rh=strand.rh,
                                status=strand.status,
                                d1=strand.d1,
                                d2=strand.d2,
                                billet_count=billet_count,
                                storage_loc=f"{area} ({box})",
                                short_billet_length=short_l,
                                sample_info=f"{strand.strand_id}-#{strand.sample_no}" if strand.sample_taken else "None"
                            )
                            records.append(record.to_dict())
                    
                    if records:
                        with st.spinner("جاري الحفظ..."):
                            if sheets_manager.save_data(records):
                                st.success(f"✅ تم حفظ {len(records)} سجل!")
                                
                                # عرض الملصق
                                label_html = generate_label_html(
                                    heat, grade, ccm, now.strftime("%Y-%m-%d"),
                                    f"{area} ({box})", billet_count, short_l, strand_data_list
                                )
                                st.markdown("### 🏷️ الملصق:")
                                st.markdown(label_html, unsafe_allow_html=True)
                                
                                # زر طباعة
                                st.markdown("""
                                <script>
                                function printLabel() {
                                    window.print();
                                }
                                </script>
                                <button onclick="printLabel()" style="padding: 10px 20px; background: #2a5298; color: white; border: none; border-radius: 5px; cursor: pointer;">
                                    🖨️ طباعة الملصق
                                </button>
                                """, unsafe_allow_html=True)
    
    # تبويب لوحة التحكم
    with tabs[1]:
        st.header("📊 لوحة التحكم")
        df = sheets_manager.fetch_data()
        
        if df.empty:
            st.info("📭 لا توجد بيانات")
        else:
            # الإحصائيات
            total = len(df)
            pass_count = len(df[df['status'] == 'PASS'])
            reject_count = total - pass_count
            pass_rate = (pass_count / total * 100) if total > 0 else 0
            
            cols = st.columns(4)
            cols[0].metric("📊 الإجمالي", total)
            cols[1].metric("✅ المجتاز", pass_count)
            cols[2].metric("❌ المرفوض", reject_count)
            cols[3].metric("📈 النسبة", f"{pass_rate:.1f}%")
            
            # الرسوم البيانية
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                status_counts = df['status'].value_counts()
                fig_pie = px.pie(
                    values=status_counts.values,
                    names=status_counts.index,
                    color=status_counts.index,
                    color_discrete_map={'PASS': '#28a745', 'REJECT': '#dc3545'},
                    hole=0.4,
                    title="حالة الجودة"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col_chart2:
                fig_hist = px.histogram(
                    df, x="rh", color="status",
                    color_discrete_map={'PASS': '#28a745', 'REJECT': '#dc3545'},
                    title="توزيع قيم RH"
                )
                fig_hist.add_vline(x=8.0, line_dash="dash", line_color="red")
                st.plotly_chart(fig_hist, use_container_width=True)
    
    # تبويب البحث
    with tabs[2]:
        st.header("🔍 البحث والأرشيف")
        df = sheets_manager.fetch_data()
        
        if not df.empty:
            search = st.text_input("ابحث برقم الصبة، العامل، أو الموقع:")
            if search:
                results = df[
                    df['heat'].astype(str).str.contains(search, case=False, na=False) |
                    df['operator'].astype(str).str.contains(search, case=False, na=False) |
                    df['storage_loc'].astype(str).str.contains(search, case=False, na=False)
                ]
                st.dataframe(results, use_container_width=True)
                
                csv = results.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 تصدير CSV", csv, "results.csv", "text/csv")


if __name__ == "__main__":
    main()
