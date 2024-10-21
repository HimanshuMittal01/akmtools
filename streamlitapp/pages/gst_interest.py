"""
GST Interest Calculation Page
"""

import polars as pl
import streamlit as st
import fastexcel

from akmtools.gst_interest import calculate_gst_180days_interest

st.title("Interest on Late Payment of GST")
st.write("According to the GST Penalty regulations, interest will be charged at the rate of 18 percent per annum from the taxpayers who fail to pay their taxes on time. The interest will be levied for the days after the due date.")
st.divider()

uploaded_file = st.file_uploader("Choose a file")

if uploaded_file is not None:
    uploaded_filename = uploaded_file.name

    # Read file
    df = None
    if uploaded_file.type == 'text/csv':
        df = pl.read_csv(uploaded_file)
    else:
        try:
            # Read sheet names
            sheet_names = fastexcel.read_excel(uploaded_file.getvalue()).sheet_names

            # Select sheet
            sheet_name = st.selectbox(
                "Select sheet:",
                sheet_names
            )

            # Read excel
            df = pl.read_excel(uploaded_file, sheet_name=sheet_name)
        except Exception as e:
            st.warning("Only csv/xlsx format are supported.")

    if df is not None:
        output = calculate_gst_180days_interest(df)

        col1, col2, col3 = st.columns(3)
        with col2:
            st.download_button(
                label='Download Interest Sheet',
                data=output,
                file_name=f'{uploaded_filename}-gst_interest_akm.xlsx',
                type='primary'
            )

else:
    st.warning("You need to upload a csv or excel file.")

# Write rules
st.info(
"""
Three columns are expected - 'Date', 'Debit', 'Credit'. Optionally, provide 'GST\%' column otherwise 18\% is used as default for all bills.

Keep the following criteria in mind:
- Values in 'Date' column are assumed to be sorted.
- Columns 'Debit' and 'Credit' should have positive values.
"""
)
