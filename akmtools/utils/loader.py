"""
Utility functions for File Loading
"""

import polars as pl

def find_header(
    df: pl.DataFrame,
    column_names: list,
    max_search_limit:int = 30
) -> pl.DataFrame:
    for i, row in enumerate(df.iter_rows()):
        if all([(name in row) for name in column_names]):
            # handle unnamed columns and create mapping
            col_mapping = {}
            unnamed_cols = 0
            for old_name, new_name in zip(df.columns, row):
                if new_name is not None:
                    col_mapping[old_name] = new_name
                else:
                    col_mapping[old_name] = f'Unnamed{unnamed_cols}'
                    unnamed_cols += 1
            return df.rename(col_mapping)[i+1:]
        if i > 30:
            break

    return df
