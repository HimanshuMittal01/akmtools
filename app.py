"""
Streamlit entrypoint
"""

import streamlit as st

st.logo(
    'streamlitapp/static/images/akmlogo.jpeg',
    size='large',
)

homepage = st.Page(
    page="streamlitapp/pages/about.py",
    title="AKMTools",
    icon=":material/home:",
    default=True,
)
gstinterestpage = st.Page(
    page="streamlitapp/pages/gst_interest.py",
    title="GST Interest Calculator",
    url_path='gstinterestcalculator',
    icon=":material/function:"
)

pg = st.navigation([homepage, gstinterestpage])
pg.run()
