CAPITALIZED_ASCII_CODE = ord('A')
CAPITALIZED_WINDOW = 26


def col_index_to_label(col_index):
    """
    Given a column index, returns the label corresponding to the column name. For example, index 0 would be
    A ... until 25 which would be Z.
    This function will recurse until a full label is generated using chunks of CAPITALIZED_WINDOW. Meaning,
    an index of 51 should yield a label of ZZ corresponding to the ZZ column.

    :param int col_index: number associated with the index position of the requested column. For example, column index 0
        would correspond to column label A.
    """
    label = ''
    extra_letter_index = (col_index // CAPITALIZED_WINDOW) - 1 # Minor adjustment for the no repeat (0) case.

    # If we do need to prepend a new letter to the column label do so recursively such that we could simulate
    # labels like AA or AAA or AAAA ... etc.
    if extra_letter_index >= 0:
        label += col_index_to_label(extra_letter_index)

    # Otherwise, passthrough and add the letter the input index corresponds to.
    return label + index_to_col_char(col_index)

def index_to_col_char(index):
    return chr(CAPITALIZED_ASCII_CODE + index % CAPITALIZED_WINDOW)
