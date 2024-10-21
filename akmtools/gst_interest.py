"""
Calculate the interest on delay GST payment by 180 days
"""

from io import BytesIO
from datetime import date

import xlsxwriter
import polars as pl

from akmtools.utils.loader import find_header


def _find_fy_end_date(date_):
    if date_ <= date(year=date_.year, month=3, day=31):
        return date(year=date_.year, month=3, day=31)
    return date(year=date_.year+1, month=3, day=31)


def _preprocess(
    df: pl.DataFrame,
    date_column_name: str,
    debit_column_name: str,
    credit_column_name: str,
    gst_rate_column_name: str,
) -> pl.DataFrame:
    # Find headers
    df = find_header(df, [date_column_name, debit_column_name, credit_column_name])

    # Check whether GST% column is available
    # Assuming default 18% for every bill
    if gst_rate_column_name not in list(df.columns):
        df = df.with_columns(pl.lit(18).alias(gst_rate_column_name))

    # Rename to standard names
    df = df.rename({
        date_column_name: 'date',
        debit_column_name: 'debit',
        credit_column_name: 'credit',
        gst_rate_column_name: 'gst_rate',
    })

    # Fill 0 where debit and credit is null
    df = df.with_columns(
        pl.col('debit').fill_null(0),
        pl.col('credit').fill_null(0)
    )

    # Filter empty rows
    df = df.drop_nulls(subset=['date', 'debit', 'credit'])

    # Convert date to date format
    if isinstance(df['date'].dtype, pl.String):
        df = df.with_columns(
            pl.col('date').str.strptime(pl.Date, '%Y-%m-%d %H:%M:%S', strict=False)
        )
    
    # Filter end rows which are less than initial date (determined by start date)
    # Assuming date is in sorted order
    df = df.filter(pl.col('date') >= df.row(0, named=True)['date'])

    # Convert debit and credit to float value
    df = df.cast({'debit': pl.Float32, 'credit': pl.Float32})

    # TODO: Validate debit and credit are positive

    return df


def _calculate_gst_180days_interest(df: pl.DataFrame):
    # Store initial column order
    initial_column_order = list(df.columns)

    # Add index
    df = df.with_row_index(name='index')
    debit_list = df.filter(
        pl.col('debit')>0
    ).select(
        pl.col(['date', 'debit'])
    ).rows(named=True)

    last_debit_date = _find_fy_end_date(df.row(df.shape[0]-1, named=True)['date'])
    debit_index, num_debit_rows = 0, len(debit_list)

    # Make output
    current_balance = 0
    output = {
        'index': [],
        'Payment Date': [],
        'Paid Amt (Total)': [],
        'Paid Amt (Bill-wise)': [],
        'Balance Payable': [],
    }
    for (index, credit) in zip(df['index'], df['credit']):
        if credit <= 0:
            output['index'].append(index)
            output['Payment Date'].append(None)
            output['Paid Amt (Total)'].append(None)
            output['Paid Amt (Bill-wise)'].append(None)
            output['Balance Payable'].append(None)
            continue

        if current_balance - credit >= 0:
            # the case will not occur unless one debit row is read
            current_balance -= credit
            output['index'].append(index)
            output['Payment Date'].append(None)
            output['Paid Amt (Total)'].append(None)
            output['Paid Amt (Bill-wise)'].append(credit)
            output['Balance Payable'].append(0)

        else:
            if current_balance > 0:
                output['index'].append(index)
                output['Payment Date'].append(None)
                output['Paid Amt (Total)'].append(None)
                output['Paid Amt (Bill-wise)'].append(current_balance)
                output['Balance Payable'].append(-min(0, current_balance - credit))

            current_balance -= credit
            while current_balance < 0 and debit_index < num_debit_rows:
                debit_amount = debit_list[debit_index]['debit']

                output['index'].append(index)
                output['Payment Date'].append(debit_list[debit_index]['date'])
                output['Paid Amt (Total)'].append(debit_amount)

                if current_balance + debit_amount >= 0:
                    output['Paid Amt (Bill-wise)'].append(-current_balance)
                    output['Balance Payable'].append(0)
                    current_balance += debit_amount

                else:
                    current_balance += debit_amount
                    output['Paid Amt (Bill-wise)'].append(debit_amount)
                    output['Balance Payable'].append(-min(0, current_balance))
                
                debit_index += 1

            if current_balance < 0:
                output['index'].append(index)
                output['Payment Date'].append(last_debit_date)
                output['Paid Amt (Total)'].append(0)
                output['Paid Amt (Bill-wise)'].append(0)
                output['Balance Payable'].append(-min(0, current_balance))
    
    # Create output dataframe
    df_output = pl.DataFrame(output).cast({'index': pl.UInt32}).join(df, on='index').drop('index')

    # Calculate interest
    df_output = df_output.with_columns(
        (pl.col('Payment Date') - pl.col('date')).dt.total_days().alias('Payment Delayed by (Days)'),
        pl.when(
            pl.col('date').dt.month()==12
        ).then(
            pl.date(year=pl.col('date').dt.year()+1, month=1, day=20)
        ).otherwise(
            pl.date(year=pl.col('date').dt.year(), month=pl.col('date').dt.month()+1, day=20)
        ).alias('Date of ITC availed'),
        (pl.col('Paid Amt (Bill-wise)') * pl.col('gst_rate') / (100 + pl.col('gst_rate'))).alias('GST Amt'),
    ).with_columns(
        pl.when(
            pl.col('Payment Delayed by (Days)') > 180
        ).then(
            (pl.col('Payment Date') - pl.col('Date of ITC availed')).dt.total_days()
        ).otherwise(pl.lit(0)).alias('Int.Days (Int. for payment made beyond 180days)')
    ).with_columns(
        (pl.col('GST Amt') * (18 /100) * pl.col('Int.Days (Int. for payment made beyond 180days)') / 365).round(2).alias('Interest Amt @18%')
    )

    # Order column names
    df_output = df_output.select(
        initial_column_order + [
            'Payment Date',
            'Paid Amt (Total)',
            'Paid Amt (Bill-wise)',
            'Balance Payable',
            'Payment Delayed by (Days)',
            'Date of ITC availed',
            'GST Amt',
            'Int.Days (Int. for payment made beyond 180days)',
            'Interest Amt @18%'
        ]
    )

    return df_output


def _make_excel(
    df: pl.DataFrame,
    excel_save_path: str | BytesIO,
    date_column_name: str,
) -> None:
    with xlsxwriter.Workbook(excel_save_path) as workbook:
        worksheet = workbook.add_worksheet('Sheet1')
        df.write_excel(
            workbook=workbook,
            worksheet='Sheet1',
            column_totals=['Interest Amt @18%'],
            table_style='first_column',
            freeze_panes="A2",
            float_precision=2,
        )

        header_format = workbook.add_format({'bold': True})
        date_format = workbook.add_format({'num_format':'dd-mmm-yy'})
        red_format = workbook.add_format({'font_color':'#9C0006', 'bg_color': '#FFC7CE'})
        yellow_format = workbook.add_format({'bg_color': 'yellow'})

        output_column_names = list(df.columns)
        for col_num, column_name in enumerate(output_column_names):
            worksheet.write(0, col_num, column_name, header_format)
        
        # Add date formats
        for date_column in [date_column_name, 'Payment Date', 'Date of ITC availed']:
            col_index = output_column_names.index(date_column)
            for row_num, value in enumerate(df[date_column]):
                worksheet.write(row_num+1, col_index, value, date_format)
        
        worksheet.conditional_format(
            first_row=1,
            first_col=output_column_names.index('Payment Delayed by (Days)'),
            last_row=1 + len(df),
            last_col=output_column_names.index('Payment Delayed by (Days)'),
            options={
                'type': 'cell',
                'criteria': 'greater than',
                'value': 180,
                'format': yellow_format
            }
        )


def calculate_gst_180days_interest(
    df: pl.DataFrame,
    date_column_name: str = 'Date',
    debit_column_name: str = 'Debit',
    credit_column_name: str = 'Credit',
    gst_rate_column_name: str = 'GST%',
) -> bytes:
    df = _preprocess(
        df,
        date_column_name=date_column_name,
        debit_column_name=debit_column_name,
        credit_column_name=credit_column_name,
        gst_rate_column_name=gst_rate_column_name,
    )
    if df.shape[0] == 0:
        return df
    
    # Calculate interest
    df_output = _calculate_gst_180days_interest(df)
    df_output = df_output.rename({
        'date': date_column_name,
        'debit': debit_column_name,
        'credit': credit_column_name,
        'gst_rate': gst_rate_column_name,
    })

    # Create excel
    output = BytesIO()
    _make_excel(
        df=df_output,
        excel_save_path=output,
        date_column_name=date_column_name,
    )

    # Return bytes
    output = output.getvalue()
    return output
