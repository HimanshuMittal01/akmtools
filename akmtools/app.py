"""
Streamlit entrypoint
"""

import streamlit as st

import polars as pl
import streamlit as st

from akmtools.src.gst_interest import calculate_gst_180days_interest

uploaded_file = st.file_uploader("Choose a file")

if uploaded_file is not None:
    uploaded_filename = uploaded_file.name

    # Read file
    df = None
    if uploaded_file.type == 'text/csv':
        df = pl.read_csv(uploaded_file)
    else:
        try:
            df = pl.read_excel(uploaded_file)
        except Exception as e:
            st.warning("Only csv/xlsx format are supported.")

    if df is not None:
        output = calculate_gst_180days_interest(df)

        st.download_button(
            label='Download Interest Sheet',
            data=output,
            file_name=f'{uploaded_filename}-gst_interest_akm.xlsx'
        )

else:
    st.warning("you need to upload a csv or excel file.")
