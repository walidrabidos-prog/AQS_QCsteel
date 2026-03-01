import streamlit as st
import pandas as pd
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict
import plotly.express as px

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


class DataManager:
    """مدير البيانات باستخدام st.session_state"""
    
    def __init__(self):
        if 'production_data' not in st.session_state:
            st.session_state.production_data = pd.DataFrame(columns=[
                'timestamp', 'date_only', 'time_only', 'shift', 'operator',
                'inspector', 'ccm', 'heat', 'grade', 'strand', 'rh', 'status',
                'd1', 'd2', 'billet_count', 'storage_loc', 'short_billet_length', 'sample_info'
            ])
    
    def get_data(self) -> pd.DataFrame:
        return st.session_state.production_data
    
    def add_records(self, records: List[Dict]):
        new_df = pd.DataFrame(records)
        st.session_state.production_data = pd.concat(
            [st.session_state.production_data, new_df], 
            ignore_index=True
        )
        return True
    
    def export_csv(self):
        return st.session_state.production_data.to_csv(index=False).encode('utf-8-sig')


def generate_label_html(heat_no, grade, ccm, date_str, storage, b_count, s_len, strands_data):
    """توليد ملصق HTML"""
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
    <div id="printable-label" style="width: 350px; border: 3px solid #2a5298; padding: 20px; margin: 20px auto; 
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
                    # كلمة المرور الافتراضية أو من secrets
                    correct_password = st.secrets.get("password", "1100") if hasattr(st, "secrets") else "1100"
                    if password == correct_password:
                        st.session_state.auth = True
                        st.rerun()
                    else:
                        st.error("❌ كلمة المرور غير صحيحة!")
        return
    
    # تهيئة مدير البيانات
    data_manager = DataManager()
    
    # الشريط الجانبي
    with st.sidebar:
        st.markdown("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%); 
                    border-radius: 10px; color: white;'>
            <h3>☁️ نظام QC</h3>
            <p>🟢 متصل</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # تصدير البيانات
        if not data_manager.get_data().empty:
            csv_data = data_manager.export_csv()
            st.download_button(
                label="📥 تصدير جميع البيانات (CSV)",
                data=csv_data,
                file_name=f"steel_qc_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        st.divider()
        
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            st.session_state.auth = False
            st.rerun()
    
    # المحتوى الرئيسي
    st.markdown("""
    <div class="main-header">
        <h2>☁️ Cloud QC Management</h2>
    </div>
    """, unsafe_allow_html=True)
    
    tabs = st.tabs(["📝 إدخال جديد", "📊 لوحة التحكم", "🔍 البحث والتقارير"])
    
    # تبويب الإدخال
    with tabs[0]:
        st.header("إدخال بيانات إنتاج جديدة")
        
        with st.form("production_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                heat = st.text_input("🔥 رقم الصبة (Heat No)", placeholder="مثال: H2024001")
                grade = st.selectbox("⚙️ الرتبة", ["B500", "B500W", "SAE1006", "SAE1008"])
                ccm = st.selectbox("🏭 الماكينة (CCM)", ["CCM01", "CCM02"])
            
            with col2:
                shift = st.selectbox("⏰ الوردية", ["A", "B", "C", "D"])
                operator = st.text_input("👷 عامل الصب", placeholder="اسم العامل")
                area = st.selectbox("📍 المنطقة", ["RM01", "RM02", "RM03", "SMS"])
            
            with col3:
                billet_count = st.number_input("📊 عدد البليتات", min_value=1, max_value=100, value=40)
                max_boxes = 9 if area == "SMS" else 5
                box = st.selectbox("📦 الصندوق", [f"Box {i}" for i in range(1, max_boxes)])
                short_l = st.number_input("📏 Short Billet (m)", min_value=0.0, max_value=12.0, value=0.0, step=0.1)
            
            st.divider()
            st.subheader("📐 قياسات Strands (الحد الأقصى للفرق: 8mm)")
            
            strand_data_list = []
            strand_cols = st.columns(5)
            
            for i in range(1, 6):
                with strand_cols[i-1]:
                    st.markdown(f"**Strand 0{i}**")
                    
                    d1 = st.number_input(f"D1 (mm)", key=f"d1_{i}", min_value=0.0, max_value=200.0, step=0.1, value=0.0)
                    d2 = st.number_input(f"D2 (mm)", key=f"d2_{i}", min_value=0.0, max_value=200.0, step=0.1, value=0.0)
                    
                    sample = st.checkbox(f"🧪 عينة", key=f"s_{i}")
                    s_no = st.text_input("رقم العينة", key=f"sn_{i}", disabled=not sample) if sample else ""
                    
                    strand = StrandData(
                        strand_id=f"S0{i}",
                        d1=d1,
                        d2=d2,
                        sample_taken=sample,
                        sample_no=s_no
                    )
                    strand_data_list.append(strand)
                    
                    # عرض الحالة
                    status_color = "🟢" if strand.status == "PASS" else "🔴"
                    status_bg = "linear-gradient(90deg, #d4edda 0%, #c3e6cb 100%)" if strand.status == "PASS" else "linear-gradient(90deg, #f8d7da 0%, #f5c6cb 100%)"
                    
                    st.markdown(f"""
                    <div style="padding: 8px; border-radius: 5px; background: {status_bg}; text-align: center; margin-top: 5px;">
                        <small>{status_color} <b>RH: {strand.rh}mm</b><br>{strand.status}</small>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.divider()
            
            col_submit, col_clear = st.columns([3, 1])
            with col_submit:
                submitted = st.form_submit_button("💾 حفظ البيانات + عرض الملصق", use_container_width=True, type="primary")
            
            if submitted:
                # التحقق من البيانات
                if not heat:
                    st.error("❌ يجب إدخال رقم الصبة (Heat No)!")
                elif not operator:
                    st.error("❌ يجب إدخال اسم العامل!")
                else:
                    # إنشاء السجلات
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
                        # حفظ البيانات
                        data_manager.add_records(records)
                        st.success(f"✅ تم حفظ {len(records)} سجل بنجاح!")
                        
                        # عرض الملصق
                        label_html = generate_label_html(
                            heat, grade, ccm, now.strftime("%Y-%m-%d"),
                            f"{area} ({box})", billet_count, short_l, strand_data_list
                        )
                        
                        st.markdown("### 🏷️ معاينة الملصق:")
                        st.markdown(label_html, unsafe_allow_html=True)
                        
                        # زر الطباعة
                        st.markdown("""
                        <div style="text-align: center; margin-top: 10px;">
                            <button onclick="window.print()" style="padding: 12px 24px; background: #2a5298; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 16px;">
                                🖨️ طباعة الملصق
                            </button>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # تحميل الملصق كـ HTML
                        full_html = f"""
                        <!DOCTYPE html>
                        <html dir="ltr">
                        <head>
                            <meta charset="UTF-8">
                            <title>Label {heat}</title>
                            <style>
                                @media print {{
                                    body {{ margin: 0; }}
                                    .no-print {{ display: none; }}
                                }}
                            </style>
                        </head>
                        <body>
                            {label_html}
                            <div class="no-print" style="text-align: center; margin-top: 20px;">
                                <button onclick="window.print()" style="padding: 10px 20px;">طباعة</button>
                            </div>
                        </body>
                        </html>
                        """
                        st.download_button(
                            "📄 تحميل الملصق (HTML)",
                            full_html,
                            f"Label_{heat}_{now.strftime('%H%M%S')}.html",
                            "text/html",
                            use_container_width=True
                        )
                    else:
                        st.warning("⚠️ لم يتم إدخال قياسات لأي Strand!")
    
    # تبويب لوحة التحكم
    with tabs[1]:
        st.header("📊 لوحة التحكم والإحصائيات")
        
        df = data_manager.get_data()
        
        if df.empty:
            st.info("📭 لا توجد بيانات مسجلة بعد. ابدأ بإدخال بيانات جديدة من تبويب 'إدخال جديد'.")
            
            # بيانات تجريبية للعرض
            st.divider()
            st.caption("🎯 مثال على شكل لوحة التحكم:")
            
            col_demo = st.columns(4)
            col_demo[0].metric("📊 الإجمالي", "0")
            col_demo[1].metric("✅ المجتاز", "0")
            col_demo[2].metric("❌ المرفوض", "0")
            col_demo[3].metric("📈 النسبة", "0%")
        else:
            # الإحصائيات
            total = len(df)
            pass_count = len(df[df['status'] == 'PASS'])
            reject_count = len(df[df['status'] == 'REJECT'])
            pass_rate = (pass_count / total * 100) if total > 0 else 0
            
            cols = st.columns(4)
            cols[0].metric("📊 إجمالي السجلات", total, help="عدد جميع القياسات المسجلة")
            cols[1].metric("✅ المجتاز", pass_count, f"{pass_rate:.1f}%", delta_color="normal")
            cols[2].metric("❌ المرفوض", reject_count, f"{100-pass_rate:.1f}%", delta_color="inverse")
            cols[3].metric("📈 نسبة النجاح", f"{pass_rate:.1f}%", help="نسبة القياسات ضمن المعيار")
            
            st.divider()
            
            # الرسوم البيانية
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.subheader("📊 توزيع حالة الجودة")
                status_counts = df['status'].value_counts()
                
                colors = {'PASS': '#28a745', 'REJECT': '#dc3545'}
                fig_pie = px.pie(
                    values=status_counts.values,
                    names=status_counts.index,
                    color=status_counts.index,
                    color_discrete_map=colors,
                    hole=0.4,
                    title="نسبة المجتاز vs المرفوض"
                )
                fig_pie.update_traces(textinfo='percent+label', textfont_size=14)
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col_chart2:
                st.subheader("📈 توزيع قيم RH")
                fig_hist = px.histogram(
                    df, 
                    x="rh", 
                    color="status",
                    nbins=20,
                    color_discrete_map=colors,
                    labels={'rh': 'قيمة RH (mm)', 'count': 'التكرار'},
                    title="توزيع قيم الاختلاف"
                )
                fig_hist.add_vline(x=8.0, line_dash="dash", line_color="red", 
                                  annotation_text="الحد الأقصى (8mm)")
                st.plotly_chart(fig_hist, use_container_width=True)
            
            # رسم بياني للاتجاهات
            st.subheader("📉 تطور الجودة عبر الزمن")
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            daily_stats = df.groupby([df['timestamp'].dt.date, 'status']).size().unstack(fill_value=0)
            
            fig_trend = go.Figure()
            if 'PASS' in daily_stats.columns:
                fig_trend.add_trace(go.Scatter(
                    x=daily_stats.index, 
                    y=daily_stats['PASS'],
                    mode='lines+markers',
                    name='✅ PASS',
                    line=dict(color='#28a745', width=3),
                    fill='tozeroy'
                ))
            if 'REJECT' in daily_stats.columns:
                fig_trend.add_trace(go.Scatter(
                    x=daily_stats.index, 
                    y=daily_stats['REJECT'],
                    mode='lines+markers',
                    name='❌ REJECT',
                    line=dict(color='#dc3545', width=3)
                ))
            
            fig_trend.update_layout(
                xaxis_title="التاريخ",
                yaxis_title="عدد القياسات",
                hovermode='x unified',
                legend=dict(orientation="h", yanchor="bottom", y=1.02)
            )
            st.plotly_chart(fig_trend, use_container_width=True)
    
    # تبويب البحث
    with tabs[2]:
        st.header("🔍 البحث والتقارير")
        
        df = data_manager.get_data()
        
        if df.empty:
            st.info("📭 لا توجد بيانات للبحث")
        else:
            # فلاتر البحث
            with st.expander("🔧 خيارات البحث", expanded=True):
                col_search1, col_search2 = st.columns([2, 1])
                
                with col_search1:
                    search_term = st.text_input(
                        "🔍 بحث عام:",
                        placeholder="رقم الصبة، اسم العامل، الموقع..."
                    )
                
                with col_search2:
                    status_filter = st.multiselect(
                        "حالة الجودة:",
                        options=['PASS', 'REJECT'],
                        default=['PASS', 'REJECT']
                    )
            
            # تطبيق الفلاتر
            filtered_df = df.copy()
            
            if search_term:
                mask = (
                    filtered_df['heat'].astype(str).str.contains(search_term, case=False, na=False) |
                    filtered_df['operator'].astype(str).str.contains(search_term, case=False, na=False) |
                    filtered_df['storage_loc'].astype(str).str.contains(search_term, case=False, na=False) |
                    filtered_df['ccm'].astype(str).str.contains(search_term, case=False, na=False)
                )
                filtered_df = filtered_df[mask]
            
            if status_filter:
                filtered_df = filtered_df[filtered_df['status'].isin(status_filter)]
            
            # عرض النتائج
            st.subheader(f"📋 النتائج: {len(filtered_df)} سجل")
            
            if len(filtered_df) > 0:
                # تنسيق الجدول
                display_df = filtered_df.copy()
                if 'rh' in display_df.columns:
                    display_df['rh'] = display_df['rh'].round(2)
                
                st.dataframe(
                    display_df.sort_values('timestamp', ascending=False),
                    use_container_width=True,
                    height=min(600, 100 + (len(display_df) * 35)),
                    column_config={
                        'status': st.column_config.SelectboxColumn(
                            "الحالة",
                            options=['PASS', 'REJECT'],
                            help="حالة الجودة"
                        ),
                        'rh': st.column_config.NumberColumn(
                            "RH (mm)",
                            format="%.2f",
                            help="قيمة الفرق"
                        ),
                        'timestamp': st.column_config.DatetimeColumn(
                            "التاريخ والوقت",
                            format="YYYY-MM-DD HH:mm"
                        )
                    }
                )
                
                # إحصائيات سريعة للنتائج
                if len(filtered_df) > 0:
                    col_stats = st.columns(3)
                    col_stats[0].metric("النتائج المعروضة", len(filtered_df))
                    col_stats[1].metric("المجتاز", len(filtered_df[filtered_df['status'] == 'PASS']))
                    col_stats[2].metric("المرفوض", len(filtered_df[filtered_df['status'] == 'REJECT']))
                
                # تصدير النتائج
                csv_results = filtered_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    "📥 تصدير النتائج (CSV)",
                    csv_results,
                    f"search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    "text/csv",
                    use_container_width=True
                )
            else:
                st.warning("🔍 لا توجد نتائج مطابقة لمعايير البحث")


if __name__ == "__main__":
    main()
