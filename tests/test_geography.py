from src.geography import quarter_end_date, quarter_label, quarter_sort_value, standardise_code


def test_quarter_fields_use_ndia_financial_year_convention():
    assert quarter_label("2025Q4") == "2025 Q4"
    assert quarter_end_date("2025Q1") == "2024-09-30"
    assert quarter_end_date("2025Q2") == "2024-12-31"
    assert quarter_end_date("2025Q3") == "2025-03-31"
    assert quarter_end_date("2025Q4") == "2025-06-30"
    assert quarter_sort_value("2025Q4") > quarter_sort_value("2025Q3")


def test_standardise_code_preserves_leading_zeros():
    assert standardise_code("123", width=5) == "00123"
    assert standardise_code("00123", width=5) == "00123"
    assert standardise_code("123.0", width=5) == "00123"
