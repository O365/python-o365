
CAPITALIZED_ASCII_CODE = 64
CAPITALIZED_WINDOW = 26

def col_index_to_label(col_index):
    """
    Given a column index, returns the label corresponding to the column name. For example, index 1 would be
    A ... until 26 which would be Z.
    This function will loop until a full label is generated using chunks of 26. Meaning, an index of 52 should
    yield a label of ZZ corresponding to the ZZ column.

    :param int col_index: list of rows to push to this range. If updating a single cell, pass a list
        containing a single row (list) containing a single cell worth of data.
    """
    label = chr(CAPITALIZED_ASCII_CODE + col_index % CAPITALIZED_WINDOW)
    col_index -= CAPITALIZED_WINDOW

    while col_index >= CAPITALIZED_WINDOW:
        label += chr(CAPITALIZED_ASCII_CODE + col_index % CAPITALIZED_WINDOW)
        col_index -= CAPITALIZED_WINDOW
    return label