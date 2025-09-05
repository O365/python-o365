import pytest

from O365.utils import col_index_to_label


class TestRange:
    EXPECTED_CHARS = [
        'A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z',
        'AA','AB','AC','AD','AE','AF','AG','AH','AI','AJ','AK','AL','AM','AN','AO','AP','AQ','AR','AS','AT','AU','AV','AW','AX','AY','AZ',
        'BA','BB','BC','BD','BE','BF','BG','BH','BI','BJ','BK','BL','BM','BN','BO','BP','BQ','BR','BS','BT','BU','BV','BW','BX','BY','BZ',
    ]
    def setup_class(self):
        pass

    def teardown_class(self):
        pass

    def test_col_index_to_label(self):
        for i in range(len(self.EXPECTED_CHARS)):
            expected_index = i
            expected_label = self.EXPECTED_CHARS[expected_index]
            label = col_index_to_label(i)
            print(f'Index {i} Letter Index {i} Label {label} Expected {expected_label}')

            assert label == expected_label
