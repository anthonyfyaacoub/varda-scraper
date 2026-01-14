"""
Simple test dashboard to check if Streamlit works
"""
import streamlit as st

st.title("Test Dashboard")
st.write("If you see this, Streamlit is working!")

try:
    from varda_scraper import CATEGORIES
    st.success("✅ Import successful!")
    st.write(f"Categories: {CATEGORIES}")
except Exception as e:
    st.error(f"❌ Import error: {e}")
    import traceback
    st.code(traceback.format_exc())
