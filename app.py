import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
import logging
from functools import lru_cache

# مكتبات الملصقات
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import mm
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing, renderPDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- إعدادات الصفحة ---
st.set_page_config(
    page_title="نظام إدارة جودة الصلب السحابي",
    layout="wide",
    page_icon="🏭",
    initial_sidebar_state="expanded"
)

# --- CSS مخصص ---
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
    .stTabs [data-baseweb="tab"] {
        background-color: #f0f2f6;
        border-radius: 5px 5px 0 0;
    }
</style>
""", unsafe_allow_html=True)


@dataclass
class StrandData:
    """كلاس بيانات الـ Strand"""
    strand_id: str
    d1: float
    d2: float
    sample_taken: bool
    sample_no: str = ""
    
    @property
    def rh(self) -> float:
        """حساب الفرق"""
        return round(abs(self.d1 - self.d2), 2)
    
    @property
    def status(self) -> str:
        """تحديد الحالة"""
        return "PASS" if self.rh <= 8.0 else "REJECT"


@dataclass
class ProductionRecord:
    """كلاس سجل الإنتاج"""
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
    """مدير Google Sheets"""
    
    def __init__(self):
        self.conn = st.connection("gsheets", type=GSheetsConnection)
        self.worksheet_name = "production_logs"
    
    @st.cache_data(ttl=60)
    def fetch_data(_self) -> pd.DataFrame:
        """جلب البيانات مع تخزين مؤقت"""
        try:
            df = _self.conn.read(worksheet=_self.worksheet_name, ttl="0")
            if df.empty:
                return pd.DataFrame(columns=[
                    'timestamp', 'date_only', 'time_only', 'shift', 'operator',
                    'inspector', 'ccm', 'heat', 'grade', 'strand', 'rh', 'status',
                    'd1', 'd2', 'billet_count', 'storage_loc', 'short_billet_length', 'sample_info'
                ])
            # تحويل الأعمدة الرقمية
            numeric_cols = ['rh', 'd1', 'd2', 'short_billet_length']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        except Exception as e:
            logger.error(f"خطأ في جلب البيانات: {e}")
            st.error(f"❌ خطأ في الاتصال بـ Google Sheets: {str(e)}")
            return pd.DataFrame()
    
    def save_data(self, new_records: List[Dict]) -> bool:
        """حفظ البيانات الجديدة"""
        try:
            existing_data = self.fetch_data()
            new_df = pd.DataFrame(new_records)
            updated_df = pd.concat([existing_data, new_df], ignore_index=True)
            self.conn.update(worksheet=self.worksheet_name, data=updated_df)
            st.cache_data.clear()
            logger.info(f"تم حفظ {len(new_records)} سجل بنجاح")
            return True
        except Exception as e:
            logger.error(f"خطأ في حفظ البيانات: {e}")
            st.error(f"❌ فشل الحفظ: {str(e)}")
            return False
    
    def get_statistics(self) -> Dict:
        """إحصائيات سريعة"""
        df = self.fetch_data()
        if df.empty:
            return {}
        
        return {
            'total_records': len(df),
            'pass_count': len(df[df['status'] == 'PASS']),
            'reject_count': len(df[df['status'] == 'REJECT']),
            'pass_rate': (len(df[df['status'] == 'PASS']) / len(df) * 100) if len(df) > 0 else 0,
            'unique_heats': df['heat'].nunique() if 'heat' in df.columns else 0,
            'last_update': df['timestamp'].max() if 'timestamp' in df.columns else None
        }


class LabelGenerator:
    """مولد الملصقات"""
    
    def __init__(self):
        self.page_size = (100*mm, 100*mm)
    
    def generate(self, heat_no: str, grade: str, ccm: str, date_str: str, 
                 storage: str, b_count: int, s_len: float, strands_data: List[StrandData]) -> BytesIO:
        """توليد ملصق PDF"""
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=self.page_size)
        
        # خلفية ملونة
        c.setFillColor(HexColor('#f8f9fa'))
        c.rect(0, 0, 100*mm, 100*mm, fill=True, stroke=False)
        
        # الإطار الخارجي
        c.setStrokeColor(HexColor('#2a5298'))
        c.setLineWidth(2)
        c.rect(3*mm, 3*mm, 94*mm, 94*mm)
        
        # العنوان
        c.setFillColor(HexColor('#1e3c72'))
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(50*mm, 88*mm, "QC PRODUCTION LABEL")
        
        # خط فاصل
        c.setStrokeColor(HexColor('#2a5298'))
        c.line(10*mm, 83*mm, 90*mm, 83*mm)
        
        # البيانات الرئيسية
        c.setFont("Helvetica-Bold", 11)
        y_position = 75*mm
        
        data_lines = [
            ("Heat No:", heat_no),
            ("Grade:", grade),
            ("Storage:", storage),
            ("Billet Count:", str(b_count)),
            ("CCM:", ccm),
            ("Date:", date_str),
        ]
        
        if s_len > 0:
            data_lines.append(("Short Billet:", f"{s_len} m"))
        
        for label, value in data_lines:
            c.setFillColor(HexColor('#333333'))
            c.setFont("Helvetica-Bold", 10)
            c.drawString(10*mm, y_position, label)
            c.setFont("Helvetica", 10)
            c.drawString(40*mm, y_position, value)
            y_position -= 8*mm
        
        # إحصائيات Strands
        c.setFont("Helvetica-Bold", 9)
        c.drawString(10*mm, y_position, "Strands Status:")
        y_position -= 6*mm
        
        for strand in strands_data:
            color = HexColor('#28a745') if strand.status == "PASS" else HexColor('#dc3545')
            c.setFillColor(color)
            status_text = "✓" if strand.status == "PASS" else "✗"
            c.drawString(15*mm, y_position, f"{strand.strand_id}: {status_text} (RH: {strand.rh}mm)")
            y_position -= 5*mm
        
        # QR Code
        qr_data = f"HEAT:{heat_no}|GRADE:{grade}|LOC:{storage}|DATE:{date_str}"
        qr_code = qr.QrCodeWidget(qr_data)
        bounds = qr_code.getBounds()
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        
        d = Drawing(25*mm, 25*mm, transform=[25*mm/width, 0, 0, 25*mm/height, 0, 0])
        d.add(qr_code)
        renderPDF.draw(d, c, 37.5*mm, 8*mm)
        
        # تذييل
        c.setFillColor(HexColor('#666666'))
        c.setFont("Helvetica", 8)
        c.drawCentredString(50*mm, 3*mm, "Scan for digital record")
        
        c.save()
        buffer.seek(0)
        return buffer


class AuthManager:
    """مدير المصادقة"""
    
    def __init__(self):
        if "auth" not in st.session_state:
            st.session_state.auth = False
        if "user_role" not in st.session_state:
            st.session_state.user_role = None
    
    def login(self):
        """شاشة تسجيل الدخول"""
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
                
                username = st.text_input("اسم المستخدم:", placeholder="أدخل اسم المستخدم")
                password = st.text_input("كلمة المرور:", type="password", placeholder="أدخل كلمة المرور")
                
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.button("دخول", use_container_width=True, type="primary"):
                        self._validate_credentials(username, password)
                
                with col_btn2:
                    if st.button("زائر", use_container_width=True):
                        st.session_state.auth = True
                        st.session_state.user_role = "guest"
                        st.rerun()
    
    def _validate_credentials(self, username: str, password: str):
        """التحقق من بيانات الاعتماد"""
        # في الإنتاج، استخدم قاعدة بيانات أو secrets
        users = st.secrets.get("USERS", {
            "admin": {"password": "1100", "role": "admin"},
            "operator": {"password": "2200", "role": "operator"},
            "inspector": {"password": "3300", "role": "inspector"}
        })
        
        if username in users and users[username]["password"] == password:
            st.session_state.auth = True
            st.session_state.user_role = users[username]["role"]
            st.success(f"✅ مرحباً {username}!")
            st.rerun()
        else:
            st.error("❌ بيانات الدخول غير صحيحة!")
    
    def logout(self):
        """تسجيل الخروج"""
        st.session_state.auth = False
        st.session_state.user_role = None
        st.rerun()
    
    def check_permission(self, required_role: str) -> bool:
        """التحقق من الصلاحيات"""
        role_hierarchy = {"guest": 0, "operator": 1, "inspector": 2, "admin": 3}
        user_level = role_hierarchy.get(st.session_state.user_role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        return user_level >= required_level


def render_input_tab(sheets_manager: GoogleSheetsManager, auth_manager: AuthManager):
    """تبويب إدخال البيانات"""
    st.header("📝 إدخال بيانات إنتاج جديدة")
    
    with st.form("production_form", clear_on_submit=True):
        # الصف الأول: المعلومات الأساسية
        st.subheader("📋 المعلومات الأساسية")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            heat = st.text_input("🔥 رقم الصبة (Heat No)", placeholder="مثال: H2024001")
            grade = st.selectbox("⚙️ الرتبة", ["B500", "B500W", "SAE1006", "SAE1008", "B400"])
            ccm = st.selectbox("🏭 الماكينة", ["CCM01", "CCM02", "CCM03"])
        
        with col2:
            shift = st.selectbox("⏰ الوردية", ["A", "B", "C", "D"])
            operator = st.text_input("👷 عامل الصب", placeholder="اسم العامل")
            area = st.selectbox("📍 المنطقة", ["RM01", "RM02", "RM03", "SMS", "YARD"])
        
        with col3:
            billet_count = st.number_input("📊 عدد البليتات", min_value=1, max_value=100, value=40)
            max_boxes = 9 if area == "SMS" else 5
            box = st.selectbox("📦 الصندوق", [f"Box {i}" for i in range(1, max_boxes)])
            short_l = st.number_input("📏 Short Billet (m)", min_value=0.0, max_value=12.0, value=0.0, step=0.1)
        
        st.divider()
        
        # الصف الثاني: بيانات Strands
        st.subheader("📐 قياسات Strands (الحد الأقصى للفرق: 8mm)")
        
        strand_data_list = []
        strand_cols = st.columns(5)
        
        for i in range(1, 6):
            with strand_cols[i-1]:
                st.markdown(f"**Strand 0{i}**")
                
                d1 = st.number_input(
                    f"القطر 1 (mm)", 
                    key=f"d1_{i}", 
                    min_value=0.0, 
                    max_value=200.0,
                    step=0.1,
                    help="أدخل القطر الأول بالمليمتر"
                )
                
                d2 = st.number_input(
                    f"القطر 2 (mm)", 
                    key=f"d2_{i}", 
                    min_value=0.0, 
                    max_value=200.0,
                    step=0.1,
                    help="أدخل القطر الثاني بالمليمتر"
                )
                
                sample = st.checkbox(f"🧪 عينة", key=f"s_{i}")
                s_no = ""
                if sample:
                    s_no = st.text_input(f"رقم العينة", key=f"sn_{i}", placeholder="مثال: 001")
                
                strand_obj = StrandData(
                    strand_id=f"S0{i}",
                    d1=d1,
                    d2=d2,
                    sample_taken=sample,
                    sample_no=s_no
                )
                strand_data_list.append(strand_obj)
                
                # عرض الحالة مباشرة
                status_color = "🟢" if strand_obj.status == "PASS" else "🔴"
                st.caption(f"{status_color} RH: {strand_obj.rh}mm | {strand_obj.status}")
        
        st.divider()
        
        # أزرار التحكم
        col_submit, col_clear = st.columns([3, 1])
        
        with col_submit:
            submitted = st.form_submit_button(
                "💾 حفظ في السحابة + طباعة الملصق", 
                use_container_width=True,
                type="primary"
            )
        
        with col_clear:
            st.form_submit_button("🔄 مسح النموذج", use_container_width=True)
        
        if submitted:
            if not heat:
                st.error("❌ يجب إدخال رقم الصبة!")
                return
            
            if not operator:
                st.error("❌ يجب إدخال اسم العامل!")
                return
            
            # إنشاء السجلات
            now = datetime.now()
            records = []
            
            for strand in strand_data_list:
                if strand.d1 > 0 or strand.d2 > 0:  # قبول إذا كان أحد القياسات موجوداً
                    record = ProductionRecord(
                        timestamp=now.strftime("%Y-%m-%d %H:%M:%S"),
                        date_only=now.strftime("%Y-%m-%d"),
                        time_only=now.strftime("%H:%M:%S"),
                        shift=shift,
                        operator=operator,
                        inspector=st.session_state.get("user_role", "unknown"),
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
                with st.spinner("جاري الحفظ في Google Sheets..."):
                    if sheets_manager.save_data(records):
                        st.success(f"✅ تم حفظ {len(records)} سجل بنجاح!")
                        
                        # توليد الملصق
                        label_gen = LabelGenerator()
                        label_pdf = label_gen.generate(
                            heat, grade, ccm, now.strftime("%Y-%m-%d"),
                            f"{area} ({box})", billet_count, short_l, strand_data_list
                        )
                        
                        col_download, col_preview = st.columns(2)
                        
                        with col_download:
                            st.download_button(
                                label="🖨️ تحميل ملصق PDF",
                                data=label_pdf,
                                file_name=f"Label_{heat}_{now.strftime('%H%M%S')}.pdf",
                                mime="application/pdf",
                                use_container_width=True
                            )
                        
                        with col_preview:
                            with st.expander("👁️ معاينة البيانات المحفوظة"):
                                st.json(records[0])
            else:
                st.warning("⚠️ لا توجد بيانات صالحة للحفظ!")


def render_dashboard_tab(sheets_manager: GoogleSheetsManager):
    """تبويب لوحة التحكم"""
    st.header("📊 لوحة التحكم والإحصائيات")
    
    df = sheets_manager.fetch_data()
    
    if df.empty:
        st.info("📭 لا توجد بيانات لعرضها")
        return
    
    # الإحصائيات العلوية
    stats = sheets_manager.get_statistics()
    
    cols = st.columns(4)
    with cols[0]:
        with st.container():
            st.metric("📊 إجمالي السجلات", stats.get('total_records', 0))
    with cols[1]:
        with st.container():
            st.metric("✅ المجتاز", stats.get('pass_count', 0))
    with cols[2]:
        with st.container():
            st.metric("❌ المرفوض", stats.get('reject_count', 0))
    with cols[3]:
        with st.container():
            pass_rate = stats.get('pass_rate', 0)
            st.metric("📈 نسبة النجاح", f"{pass_rate:.1f}%")
    
    st.divider()
    
    # الرسوم البيانية
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("📊 حالة الجودة الإجمالية")
        status_counts = df['status'].value_counts()
        fig_pie = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            color=status_counts.index,
            color_discrete_map={'PASS': '#28a745', 'REJECT': '#dc3545'},
            hole=0.4
        )
        fig_pie.update_traces(textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col_chart2:
        st.subheader("📈 توزيع قيم RH")
        fig_hist = px.histogram(
            df, 
            x="rh", 
            color="status",
            nbins=20,
            color_discrete_map={'PASS': '#28a745', 'REJECT': '#dc3545'},
            labels={'rh': 'قيمة RH (mm)', 'count': 'التكرار'}
        )
        fig_hist.add_vline(x=8.0, line_dash="dash", line_color="red", 
                          annotation_text="الحد الأقصى (8mm)")
        st.plotly_chart(fig_hist, use_container_width=True)
    
    # رسم بياني للاتجاهات الزمنية
    st.subheader("📉 تطور الجودة عبر الزمن")
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    daily_stats = df.groupby([df['timestamp'].dt.date, 'status']).size().unstack(fill_value=0)
    
    fig_trend = go.Figure()
    if 'PASS' in daily_stats.columns:
        fig_trend.add_trace(go.Scatter(
            x=daily_stats.index, 
            y=daily_stats['PASS'],
            mode='lines+markers',
            name='PASS',
            line=dict(color='#28a745', width=2)
        ))
    if 'REJECT' in daily_stats.columns:
        fig_trend.add_trace(go.Scatter(
            x=daily_stats.index, 
            y=daily_stats['REJECT'],
            mode='lines+markers',
            name='REJECT',
            line=dict(color='#dc3545', width=2)
        ))
    
    fig_trend.update_layout(
        xaxis_title="التاريخ",
        yaxis_title="عدد البليتات",
        hovermode='x unified'
    )
    st.plotly_chart(fig_trend, use_container_width=True)
    
    # أفضل وأسوأ الأداء
    st.subheader("🏆 تحليل الأداء")
    col_perf1, col_perf2 = st.columns(2)
    
    with col_perf1:
        operator_stats = df.groupby('operator')['status'].apply(
            lambda x: (x == 'PASS').sum() / len(x) * 100
        ).sort_values(ascending=False).head(5)
        
        st.write("**👷 أفضل العاملين (نسبة النجاح)**")
        for op, rate in operator_stats.items():
            st.progress(rate/100, text=f"{op}: {rate:.1f}%")
    
    with col_perf2:
        ccm_stats = df.groupby('ccm')['status'].apply(
            lambda x: (x == 'PASS').sum() / len(x) * 100
        )
        
        st.write("**🏭 أداء الماكينات**")
        for ccm, rate in ccm_stats.items():
            st.progress(rate/100, text=f"{ccm}: {rate:.1f}%")


def render_search_tab(sheets_manager: GoogleSheetsManager):
    """تبويب البحث والأرشيف"""
    st.header("🔍 البحث والأرشيف")
    
    df = sheets_manager.fetch_data()
    
    if df.empty:
        st.info("📭 لا توجد بيانات للبحث")
        return
    
    # فلاتر البحث
    with st.expander("🔧 خيارات البحث المتقدمة", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_term = st.text_input(
                "🔍 بحث عام:",
                placeholder="رقم الصبة، الموقع، العامل..."
            )
        
        with col2:
            date_from = st.date_input("من تاريخ:", value=None)
            date_to = st.date_input("إلى تاريخ:", value=None)
        
        with col3:
            status_filter = st.multiselect(
                "حالة الجودة:",
                options=['PASS', 'REJECT'],
                default=['PASS', 'REJECT']
            )
            grade_filter = st.multiselect(
                "الرتبة:",
                options=df['grade'].unique() if 'grade' in df.columns else []
            )
    
    # تطبيق الفلاتر
    filtered_df = df.copy()
    
    if search_term:
        mask = (
            filtered_df['heat'].astype(str).str.contains(search_term, case=False, na=False) |
            filtered_df['storage_loc'].astype(str).str.contains(search_term, case=False, na=False) |
            filtered_df['operator'].astype(str).str.contains(search_term, case=False, na=False)
        )
        filtered_df = filtered_df[mask]
    
    if date_from:
        filtered_df = filtered_df[pd.to_datetime(filtered_df['date_only']) >= pd.Timestamp(date_from)]
    if date_to:
        filtered_df = filtered_df[pd.to_datetime(filtered_df['date_only']) <= pd.Timestamp(date_to)]
    
    if status_filter:
        filtered_df = filtered_df[filtered_df['status'].isin(status_filter)]
    
    if grade_filter:
        filtered_df = filtered_df[filtered_df['grade'].isin(grade_filter)]
    
    # عرض النتائج
    st.subheader(f"📋 النتائج ({len(filtered_df)} سجل)")
    
    if len(filtered_df) > 0:
        # خيارات العرض
        col_view1, col_view2 = st.columns([3, 1])
        
        with col_view1:
            view_mode = st.radio("طريقة العرض:", ["جدول", "بطاقات"], horizontal=True)
        
        with col_view2:
            page_size = st.selectbox("السجلات/الصفحة:", [10, 25, 50, 100])
        
        if view_mode == "جدول":
            # تنسيق الجدول
            display_df = filtered_df.copy()
            if 'rh' in display_df.columns:
                display_df['rh'] = display_df['rh'].round(2)
            
            st.dataframe(
                display_df,
                use_container_width=True,
                height=min(600, 100 + (len(display_df) * 35)),
                column_config={
                    'status': st.column_config.SelectboxColumn(
                        "الحالة",
                        help="حالة الجودة",
                        options=['PASS', 'REJECT']
                    ),
                    'rh': st.column_config.NumberColumn(
                        "RH",
                        help="قيمة الفرق",
                        format="%.2f mm"
                    )
                }
            )
        else:
            # عرض البطاقات
            for idx, row in filtered_df.head(page_size).iterrows():
                with st.container():
                    col_card1, col_card2, col_card3 = st.columns([2, 2, 1])
                    
                    with col_card1:
                        st.write(f"**🔥 Heat:** {row.get('heat', 'N/A')}")
                        st.write(f"**⚙️ Grade:** {row.get('grade', 'N/A')}")
                        st.write(f"**📍 Location:** {row.get('storage_loc', 'N/A')}")
                    
                    with col_card2:
                        st.write(f"**👷 Operator:** {row.get('operator', 'N/A')}")
                        st.write(f"**📅 Date:** {row.get('date_only', 'N/A')}")
                        st.write(f"**📐 RH:** {row.get('rh', 'N/A')} mm")
                    
                    with col_card3:
                        status_color = "🟢" if row.get('status') == 'PASS' else "🔴"
                        st.markdown(f"### {status_color}")
                        st.caption(row.get('status', 'N/A'))
                    
                    st.divider()
        
        # أدوات التصدير
        st.divider()
        col_exp1, col_exp2, col_exp3 = st.columns(3)
        
        with col_exp1:
            csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 تصدير CSV",
                csv,
                f"steel_qc_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv",
                use_container_width=True
            )
        
        with col_exp2:
            # تصدير Excel
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='Data')
            excel_data = excel_buffer.getvalue()
            
            st.download_button(
                "📊 تصدير Excel",
                excel_data,
                f"steel_qc_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        with col_exp3:
            if st.button("🗑️ حذف السجلات المحددة", use_container_width=True, type="secondary"):
                st.warning("⚠️ هذه الميزة تتطلب صلاحيات المسؤول")
    else:
        st.warning("🔍 لا توجد نتائج مطابقة لمعايير البحث")


def main():
    """الدالة الرئيسية"""
    # تهيئة المدراء
    auth_manager = AuthManager()
    sheets_manager = GoogleSheetsManager()
    
    # التحقق من المصادقة
    if not st.session_state.auth:
        auth_manager.login()
        return
    
    # الشريط الجانبي
    with st.sidebar:
        st.markdown(f"""
        <div style='text-align: center; padding: 20px; background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%); border-radius: 10px; color: white;'>
            <h3>🏭 نظام QC</h3>
            <p>المستخدم: <b>{st.session_state.user_role.upper()}</b></p>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # الإحصائيات السريعة
        stats = sheets_manager.get_statistics()
        if stats:
            st.caption("📊 إحصائيات سريعة")
            st.write(f"• إجمالي السجلات: **{stats.get('total_records', 0)}**")
            st.write(f"• نسبة النجاح: **{stats.get('pass_rate', 0):.1f}%**")
            st.write(f"• آخر تحديث: **{stats.get('last_update', 'N/A')}**")
        
        st.divider()
        
        if st.button("🚪 تسجيل الخروج", use_container_width=True, type="secondary"):
            auth_manager.logout()
    
    # المحتوى الرئيسي
    st.markdown("""
    <div class="main-header">
        <h2>☁️ Cloud QC Management System</h2>
        <p>نظام إدارة الجودة السحابي المتكامل</p>
    </div>
    """, unsafe_allow_html=True)
    
    # التبويبات
    tabs = st.tabs(["📝 إدخال جديد", "📊 لوحة التحكم", "🔍 البحث والأرشيف"])
    
    with tabs[0]:
        render_input_tab(sheets_manager, auth_manager)
    
    with tabs[1]:
        render_dashboard_tab(sheets_manager)
    
    with tabs[2]:
        render_search_tab(sheets_manager)


if __name__ == "__main__":
    main()
