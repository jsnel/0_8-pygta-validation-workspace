from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from pygta_local_extras.io.params_csv import convert_parameter_table_from_shift_binwidth_bug
from pygta_local_extras.io.params_csv import convert_parameters_from_shift_binwidth_bug
from pygta_local_extras.io.params_csv import copy_estimated_parameters_to_file
from pygta_local_extras.io.params_csv import copy_irf_shape_parameters_to_file
from pygta_local_extras.io.params_csv import copy_shift_conv_parameters_to_file
from pygta_local_extras.io.params_csv import fix_negative_convwidth
from pygta_local_extras.io.params_csv import free_shift_conv_parameters_to_file
from pygta_local_extras.io.params_csv import freeze_all_parameters_with_low_t_value
from pygta_local_extras.io.params_csv import freeze_parameters_with_low_t_value
from pygta_local_extras.io.params_csv import freeze_shift_conv_parameters_to_file
from pygta_local_extras.io.params_csv import parameter_scale_factor_for_shift_binwidth_bug
from pygta_local_extras.io.params_csv import reanchor_conv_multi_multi_gaussian_irf_parameters
from pygta_local_extras.io.params_csv import sort_rate_series_values_descending
from pygta_local_extras.io.params_csv import transform_parameter_for_shift_binwidth_bug


@pytest.fixture
def write_csv(tmp_path: Path):
    def _write(name: str, content: str) -> Path:
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return p

    return _write


def test_negative_convwidth_flipped(write_csv) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary\n"
        "irf.convwidth678,-3.5,None,None,,,False,True\n"
        "irf.convwidth682,2.0,None,None,,0,False,True\n"
        "irf.shift678,-5.0,None,None,,,False,True\n"
    )
    path = write_csv("params.csv", content)
    fix_negative_convwidth(path)
    lines = path.read_text(encoding="utf-8").splitlines()

    # negative convwidth flipped and minimum set to 0
    assert lines[1] == "irf.convwidth678,3.5,None,None,,0,False,True"
    # positive convwidth unchanged
    assert lines[2] == "irf.convwidth682,2.0,None,None,,0,False,True"
    # non-convwidth row unchanged
    assert lines[3] == "irf.shift678,-5.0,None,None,,,False,True"


def test_negative_convwidth_minimum_set_to_zero(write_csv) -> None:
    """When minimum column is empty it must be filled with 0."""
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary\n"
        "irf.convwidth720,-0.009,None,None,,,False,True\n"
    )
    path = write_csv("params2.csv", content)
    fix_negative_convwidth(path)
    cols = path.read_text(encoding="utf-8").splitlines()[1].split(",")
    assert float(cols[1]) == pytest.approx(0.009)
    assert cols[5] == "0"


def test_positive_convwidth_gets_minimum_zero(write_csv) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary\n"
        "irf.convwidth678,5.0,None,None,,,False,True\n"
    )
    path = write_csv("params3.csv", content)
    fix_negative_convwidth(path)
    assert (
        path.read_text(encoding="utf-8").splitlines()[1]
        == "irf.convwidth678,5.0,None,None,,0,False,True"
    )


def test_fix_negative_convwidth_accepts_result_and_path(write_csv, capsys) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary\n"
        "irf.convwidth678,-1.5,None,None,,1,False,True\n"
        "irf.convwidth682,2.0,None,None,,,False,True\n"
    )
    path = write_csv("params4.csv", content)

    changed = fix_negative_convwidth(object(), path)
    lines = path.read_text(encoding="utf-8").splitlines()
    out = capsys.readouterr().out

    assert changed == ["irf.convwidth678", "irf.convwidth682"]
    assert lines[1] == "irf.convwidth678,1.5,None,None,,0,False,True"
    assert lines[2] == "irf.convwidth682,2.0,None,None,,0,False,True"
    assert "Flipped negative convwidth parameters:" in out
    assert "Set minimum=0 for convwidth parameters:" in out


def test_reanchor_conv_multi_multi_gaussian_irf_parameters(write_csv) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary\n"
        "irf.test.center1,100,None,None,,0,False,False\n"
        "irf.test.center2,5,None,None,,0,False,True\n"
        "irf.test.center3,20,None,None,,0,False,True\n"
        "irf.test.scale1,1,None,None,,,False,False\n"
        "irf.test.scale2,3,None,None,,,False,True\n"
        "irf.test.scale3,2,None,None,,,False,True\n"
        "irf.test.width1,10,None,None,,,False,False\n"
        "irf.test.width2,20,None,None,,,False,True\n"
        "irf.test.width3,30,None,None,,,False,True\n"
        "irf.test.shift678,7,None,None,,,False,True\n"
        "irf.test.convwidth678,0.5,None,None,,,False,True\n"
    )
    path = write_csv("params_irf_reanchor.csv", content)

    changed = reanchor_conv_multi_multi_gaussian_irf_parameters(path)
    rows = {
        line.split(",")[0]: line.split(",")
        for line in path.read_text(encoding="utf-8").splitlines()[1:]
    }

    assert changed == {"irf.test": 2}
    assert float(rows["irf.test.center1"][1]) == pytest.approx(105.0)
    assert float(rows["irf.test.center2"][1]) == pytest.approx(-5.0)
    assert float(rows["irf.test.center3"][1]) == pytest.approx(15.0)
    assert rows["irf.test.center1"][5] == "0"
    assert rows["irf.test.center2"][5] == ""
    assert rows["irf.test.center3"][5] == "0"
    assert float(rows["irf.test.scale1"][1]) == pytest.approx(1.0)
    assert float(rows["irf.test.scale2"][1]) == pytest.approx(1 / 3)
    assert float(rows["irf.test.scale3"][1]) == pytest.approx(2 / 3)
    assert float(rows["irf.test.width1"][1]) == pytest.approx(20.0)
    assert float(rows["irf.test.width2"][1]) == pytest.approx(10.0)
    assert float(rows["irf.test.width3"][1]) == pytest.approx(30.0)
    assert float(rows["irf.test.shift678"][1]) == pytest.approx(7.0)
    assert float(rows["irf.test.convwidth678"][1]) == pytest.approx(0.5)


class _OptimizedParametersStub:
    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def to_dataframe(self) -> pd.DataFrame:
        return self._df


class _ResultStub:
    def __init__(self, df: pd.DataFrame) -> None:
        self.optimized_parameters = _OptimizedParametersStub(df)


class _TableStub:
    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def to_dataframe(self) -> pd.DataFrame:
        return self._df


def test_freeze_parameters_with_low_t_value(write_csv) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary\n"
        "a,1.0,None,None,,,False,True\n"
        "b,2.0,None,None,,,False,True\n"
        "c,3.0,None,None,,,False,False\n"
    )
    path = write_csv("params_low_t.csv", content)

    result = _ResultStub(
        pd.DataFrame(
            {
                "label": ["a", "b", "c"],
                "t-value": [1.5, -2.1, 0.5],
            }
        )
    )

    changed = freeze_parameters_with_low_t_value(result, path)
    lines = path.read_text(encoding="utf-8").splitlines()

    assert changed == ["a"]
    assert lines[1].endswith(",False")
    assert lines[2].endswith(",True")
    assert lines[3].endswith(",False")


def test_freeze_all_parameters_with_low_t_value(write_csv) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary\n"
        "a,1.0,None,None,,,False,True\n"
        "b,2.0,None,None,,,False,True\n"
        "c,3.0,None,None,,,False,False\n"
    )
    path = write_csv("params_low_t_all.csv", content)

    result = _ResultStub(
        pd.DataFrame(
            {
                "label": ["a", "b", "c"],
                "t-value": [1.5, -2.1, 0.5],
            }
        )
    )

    changed = freeze_all_parameters_with_low_t_value(result, path)
    lines = path.read_text(encoding="utf-8").splitlines()

    assert changed == ["a"]
    assert lines[1].endswith(",False")
    assert lines[2].endswith(",True")
    assert lines[3].endswith(",False")


def test_freeze_parameters_with_low_t_value_uses_index_labels(write_csv) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary\n"
        "x,1.0,None,None,,,False,True\n"
        "y,2.0,None,None,,,False,True\n"
    )
    path = write_csv("params_index_labels.csv", content)

    df = pd.DataFrame({"T_value": [1.1, 3.2]}, index=["x", "y"])
    result = _ResultStub(df)

    changed = freeze_parameters_with_low_t_value(result, path)
    lines = path.read_text(encoding="utf-8").splitlines()

    assert changed == ["x"]
    assert lines[1].endswith(",False")
    assert lines[2].endswith(",True")


def test_freeze_parameters_with_low_t_value_derives_t_from_stderr(write_csv) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary\n"
        "a,1.0,None,None,,,False,True\n"
        "b,2.0,None,None,,,False,True\n"
        "c,3.0,None,None,,,False,True\n"
    )
    path = write_csv("params_t_fallback.csv", content)

    # No explicit T-value column; helper should derive T as value / standard_error.
    result = _ResultStub(
        pd.DataFrame(
            {
                "label": ["a", "b", "c"],
                "value": [1.0, 4.0, 1.0],
                "standard_error": [1.0, 1.0, 0.0],
            }
        )
    )

    changed = freeze_parameters_with_low_t_value(result, path)
    lines = path.read_text(encoding="utf-8").splitlines()

    assert changed == ["a"]
    assert lines[1].endswith(",False")
    assert lines[2].endswith(",True")
    assert lines[3].endswith(",True")


def test_freeze_parameters_with_low_t_value_respects_exclude_prefixes(write_csv, capsys) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary\n"
        "inp.start,1.0,None,None,,,False,True\n"
        "rate.k1,2.0,None,None,,,False,True\n"
        "free.param,3.0,None,None,,,False,True\n"
    )
    path = write_csv("params_exclude.csv", content)

    result = _ResultStub(
        pd.DataFrame(
            {
                "label": ["inp.start", "rate.k1", "free.param"],
                "t-value": [1.5, -1.2, 0.9],
            }
        )
    )

    changed = freeze_parameters_with_low_t_value(result, path, exclude=["inp", "rate"])
    lines = path.read_text(encoding="utf-8").splitlines()
    out = capsys.readouterr().out

    assert changed == ["free.param"]
    assert lines[1].endswith(",True")
    assert lines[2].endswith(",True")
    assert lines[3].endswith(",False")
    assert "inp.start" in out
    assert "rate.k1" in out


def test_copy_estimated_parameters_to_file(write_csv) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary\n"
        "a,1.0,None,None,,,False,True\n"
        "b,2.0,None,None,,,False,True\n"
        "c,3.0,None,None,,,False,False\n"
    )
    path = write_csv("params_copy_values.csv", content)

    result = _ResultStub(
        pd.DataFrame(
            {
                "label": ["a", "b", "c"],
                "value": [1.5, 2.0, 4.2],
            }
        )
    )

    changed = copy_estimated_parameters_to_file(result, path)
    lines = path.read_text(encoding="utf-8").splitlines()

    assert changed == ["a", "c"]
    assert lines[1].split(",")[1] == "1.5"
    assert lines[2].split(",")[1] == "2.0"
    assert lines[3].split(",")[1] == "4.2"


def test_copy_estimated_parameters_to_file_respects_exclude_prefixes(write_csv, capsys) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary\n"
        "inp.start,1.0,None,None,,,False,True\n"
        "rate.k1,2.0,None,None,,,False,True\n"
        "free.param,3.0,None,None,,,False,True\n"
    )
    path = write_csv("params_copy_exclude.csv", content)

    result = _ResultStub(
        pd.DataFrame(
            {
                "label": ["inp.start", "rate.k1", "free.param"],
                "value": [1.5, 2.5, 3.8],
            }
        )
    )

    changed = copy_estimated_parameters_to_file(result, path, exclude=["inp", "rate"])
    lines = path.read_text(encoding="utf-8").splitlines()
    out = capsys.readouterr().out

    assert changed == ["free.param"]
    assert lines[1].split(",")[1] == "1.0"
    assert lines[2].split(",")[1] == "2.0"
    assert lines[3].split(",")[1] == "3.8"
    assert "inp.start" in out
    assert "rate.k1" in out


def test_copy_irf_shape_parameters_to_file(write_csv) -> None:
    source_content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary,,,,\n"
        "irf.close.center1,10,None,None,,,False,True,,,,\n"
        "irf.close.scale1,0.5,None,None,,,False,True,,,,\n"
        "irf.open.width1,8,None,None,,,False,True,,,,\n"
        "irf.somei.shift1,-2,None,None,,,False,True,,,,\n"
        "irf.somei.convwidth1,3,None,None,,,False,True,,,,\n"
        "other.center1,99,None,None,,,False,True,,,,\n"
    )
    target_content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary,,,,\n"
        "irf.close.center1,100,None,None,,,False,True,,,,\n"
        "irf.close.scale1,0.5,None,None,,,False,True,,,,\n"
        "irf.open.width1,9,None,None,,,False,False,,,,\n"
        "irf.somei.shift1,0,None,None,,,False,True,,,,\n"
        "irf.somei.convwidth1,99,None,None,,,False,False,,,,\n"
        "irf.close.width9,11,None,None,,,False,True,,,,\n"
        "other.center1,22,None,None,,,False,True,,,,\n"
    )
    source_path = write_csv("params_irf_source.csv", source_content)
    target_path = write_csv("params_irf_target.csv", target_content)

    changed = copy_irf_shape_parameters_to_file(source_path, target_path)
    rows = {
        line.split(",")[0]: line.split(",")
        for line in target_path.read_text(encoding="utf-8").splitlines()[1:]
    }

    assert changed == [
        "irf.close.center1",
        "irf.close.scale1",
        "irf.open.width1",
        "irf.somei.shift1",
        "irf.somei.convwidth1",
    ]
    assert rows["irf.close.center1"][1] == "10"
    assert rows["irf.close.center1"][7] == "False"
    assert rows["irf.close.scale1"][1] == "0.5"
    assert rows["irf.close.scale1"][7] == "False"
    assert rows["irf.open.width1"][1] == "8"
    assert rows["irf.open.width1"][7] == "False"
    assert rows["irf.somei.shift1"][1] == "-2"
    assert rows["irf.somei.shift1"][7] == "False"
    assert rows["irf.somei.convwidth1"][1] == "3"
    assert rows["irf.somei.convwidth1"][7] == "False"
    assert rows["irf.close.width9"][1] == "11"
    assert rows["irf.close.width9"][7] == "True"
    assert rows["other.center1"][1] == "22"
    assert rows["other.center1"][7] == "True"


def test_copy_shift_conv_parameters_to_file(write_csv) -> None:
    source_content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary,,,,\n"
        "irf.open.shift678,-8.0,None,None,,,False,True,,,,\n"
        "irf.open.convwidth678,0.2,None,None,,,False,True,,,,\n"
        "irf.close.shift705,-3.5,None,None,,,False,True,,,,\n"
        "irf.close.convwidth760,1.7,None,None,,,False,True,,,,\n"
        "irf.close.shift677,-9.9,None,None,,,False,True,,,,\n"
        "irf.close.convwidth761,9.9,None,None,,,False,True,,,,\n"
        "irf.somei.shift1,-2,None,None,,,False,True,,,,\n"
        "irf.somei.convwidth1,3,None,None,,,False,True,,,,\n"
    )
    target_content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary,,,,\n"
        "irf.open.shift678,100,None,None,,,False,True,,,,\n"
        "irf.open.convwidth678,200,None,None,,,False,True,,,,\n"
        "irf.close.shift705,300,None,None,,,False,False,,,,\n"
        "irf.close.convwidth760,400,None,None,,,False,True,,,,\n"
        "irf.close.shift677,500,None,None,,,False,True,,,,\n"
        "irf.close.convwidth761,600,None,None,,,False,True,,,,\n"
        "irf.somei.shift1,700,None,None,,,False,True,,,,\n"
        "irf.somei.convwidth1,800,None,None,,,False,True,,,,\n"
    )
    source_path = write_csv("params_shift_conv_source.csv", source_content)
    target_path = write_csv("params_shift_conv_target.csv", target_content)

    changed = copy_shift_conv_parameters_to_file(source_path, target_path)
    rows = {
        line.split(",")[0]: line.split(",")
        for line in target_path.read_text(encoding="utf-8").splitlines()[1:]
    }

    assert changed == [
        "irf.open.shift678",
        "irf.open.convwidth678",
        "irf.close.shift705",
        "irf.close.convwidth760",
    ]
    assert rows["irf.open.shift678"][1] == "-8.0"
    assert rows["irf.open.shift678"][7] == "False"
    assert rows["irf.open.convwidth678"][1] == "0.2"
    assert rows["irf.open.convwidth678"][7] == "False"
    assert rows["irf.close.shift705"][1] == "-3.5"
    assert rows["irf.close.shift705"][7] == "False"
    assert rows["irf.close.convwidth760"][1] == "1.7"
    assert rows["irf.close.convwidth760"][7] == "False"
    assert rows["irf.close.shift677"][1] == "500"
    assert rows["irf.close.shift677"][7] == "True"
    assert rows["irf.close.convwidth761"][1] == "600"
    assert rows["irf.close.convwidth761"][7] == "True"
    assert rows["irf.somei.shift1"][1] == "700"
    assert rows["irf.somei.shift1"][7] == "True"
    assert rows["irf.somei.convwidth1"][1] == "800"
    assert rows["irf.somei.convwidth1"][7] == "True"


def test_freeze_shift_conv_parameters_to_file(write_csv) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary,,,,\n"
        "irf.open.shift678,100,None,None,,,False,True,,,,\n"
        "irf.open.convwidth678,200,None,None,,,False,True,,,,\n"
        "irf.close.shift705,300,None,None,,,False,False,,,,\n"
        "irf.close.convwidth760,400,None,None,,,False,True,,,,\n"
        "irf.close.shift677,500,None,None,,,False,True,,,,\n"
        "irf.close.convwidth761,600,None,None,,,False,True,,,,\n"
        "irf.somei.shift1,700,None,None,,,False,True,,,,\n"
        "irf.somei.convwidth1,800,None,None,,,False,True,,,,\n"
    )
    path = write_csv("params_shift_conv_freeze.csv", content)

    changed = freeze_shift_conv_parameters_to_file(path)
    rows = {
        line.split(",")[0]: line.split(",")
        for line in path.read_text(encoding="utf-8").splitlines()[1:]
    }

    assert changed == [
        "irf.open.shift678",
        "irf.open.convwidth678",
        "irf.close.convwidth760",
    ]
    assert rows["irf.open.shift678"][7] == "False"
    assert rows["irf.open.convwidth678"][7] == "False"
    assert rows["irf.close.shift705"][7] == "False"
    assert rows["irf.close.convwidth760"][7] == "False"
    assert rows["irf.close.shift677"][7] == "True"
    assert rows["irf.close.convwidth761"][7] == "True"
    assert rows["irf.somei.shift1"][7] == "True"
    assert rows["irf.somei.convwidth1"][7] == "True"


def test_free_shift_conv_parameters_to_file(write_csv) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary,,,,\n"
        "irf.open.shift678,100,None,None,,,False,False,,,,\n"
        "irf.open.convwidth678,200,None,None,,,False,False,,,,\n"
        "irf.close.shift705,300,None,None,,,False,True,,,,\n"
        "irf.close.convwidth760,400,None,None,,,False,False,,,,\n"
        "irf.close.shift677,500,None,None,,,False,False,,,,\n"
        "irf.close.convwidth761,600,None,None,,,False,False,,,,\n"
        "irf.somei.shift1,700,None,None,,,False,False,,,,\n"
        "irf.somei.convwidth1,800,None,None,,,False,False,,,,\n"
    )
    path = write_csv("params_shift_conv_free.csv", content)

    changed = free_shift_conv_parameters_to_file(path)
    rows = {
        line.split(",")[0]: line.split(",")
        for line in path.read_text(encoding="utf-8").splitlines()[1:]
    }

    assert changed == [
        "irf.open.shift678",
        "irf.open.convwidth678",
        "irf.close.convwidth760",
    ]
    assert rows["irf.open.shift678"][7] == "True"
    assert rows["irf.open.convwidth678"][7] == "True"
    assert rows["irf.close.shift705"][7] == "True"
    assert rows["irf.close.convwidth760"][7] == "True"
    assert rows["irf.close.shift677"][7] == "False"
    assert rows["irf.close.convwidth761"][7] == "False"
    assert rows["irf.somei.shift1"][7] == "False"
    assert rows["irf.somei.convwidth1"][7] == "False"


def test_sort_rate_series_values_descending(write_csv) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary\n"
        "ratecol0.kopen21,0.12,None,None,,0,False,True\n"
        "ratecol0.kopen32,0.40,None,None,,0,False,True\n"
        "ratecol0.kopen43,0.05,None,None,,0,False,True\n"
        "ratecol0.kopen54,0.30,None,None,,0,False,True\n"
        "ratecol0.kopen65,0.20,None,None,,0,False,True\n"
        "ratecol0.kopen76,0.10,None,None,,0,False,True\n"
        "ratecol0.kopen77,0.01,None,None,,0,False,True\n"
        "ratecol0.kclose21,7.94E-05,None,None,,0,False,True\n"
        "ratecol0.kclose32,0.07,None,None,,0,False,True\n"
        "ratecol0.kclose43,0.03,None,None,,0,False,True\n"
        "ratecol0.kclose54,0.01,None,None,,0,False,True\n"
        "ratecol0.kclose65,0.008,None,None,,0,False,True\n"
        "ratecol0.kclose76,0.004,None,None,,0,False,True\n"
        "ratecol0.kclose77,0.002,None,None,,0,False,True\n"
        "ratecol0.kopenx,9.0,None,None,,0,False,True\n"
        "ratenolhcb9.kopen21,0.5,None,None,,0,False,True\n"
        "ratenolhcb9.kopen32,0.4,None,None,,0,False,True\n"
    )
    path = write_csv("params_rate_sort.csv", content)

    changed = sort_rate_series_values_descending(path)
    lines = path.read_text(encoding="utf-8").splitlines()

    assert changed == ["ratecol0.kopen", "ratecol0.kclose"]
    assert lines[1].split(",")[1] == "0.40"
    assert lines[2].split(",")[1] == "0.30"
    assert lines[3].split(",")[1] == "0.20"
    assert lines[4].split(",")[1] == "0.12"
    assert lines[5].split(",")[1] == "0.10"
    assert lines[6].split(",")[1] == "0.05"
    assert lines[7].split(",")[1] == "0.01"
    assert lines[8].split(",")[1] == "0.07"
    assert lines[9].split(",")[1] == "0.03"
    assert lines[10].split(",")[1] == "0.01"
    assert lines[11].split(",")[1] == "0.008"
    assert lines[12].split(",")[1] == "0.004"
    assert lines[13].split(",")[1] == "0.002"
    assert lines[14].split(",")[1] == "7.94E-05"
    assert lines[16].split(",")[1] == "0.5"
    assert lines[17].split(",")[1] == "0.4"


def test_sort_rate_series_values_descending_partial_sequence(write_csv) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary\n"
        "ratenolhcb9.kopen43,0.05,None,None,,0,False,True\n"
        "ratenolhcb9.kopen54,0.30,None,None,,0,False,True\n"
        "ratenolhcb9.kopen65,0.20,None,None,,0,False,True\n"
        "ratenolhcb9.kopen76,0.10,None,None,,0,False,True\n"
        "ratenolhcb9.kopen77,0.01,None,None,,0,False,True\n"
    )
    path = write_csv("params_rate_sort_partial.csv", content)

    changed = sort_rate_series_values_descending(path)
    lines = path.read_text(encoding="utf-8").splitlines()

    assert changed == ["ratenolhcb9.kopen"]
    assert lines[1].split(",")[1] == "0.30"
    assert lines[2].split(",")[1] == "0.20"
    assert lines[3].split(",")[1] == "0.10"
    assert lines[4].split(",")[1] == "0.05"
    assert lines[5].split(",")[1] == "0.01"


def test_transform_parameter_for_shift_binwidth_bug() -> None:
    assert parameter_scale_factor_for_shift_binwidth_bug("irf_common.center") == pytest.approx(0.8)
    assert parameter_scale_factor_for_shift_binwidth_bug("gauss_1.width") == pytest.approx(0.8)
    assert parameter_scale_factor_for_shift_binwidth_bug("kinetic.4") == pytest.approx(1.25)
    assert parameter_scale_factor_for_shift_binwidth_bug("irf_1.dispc") == pytest.approx(1.0)
    assert transform_parameter_for_shift_binwidth_bug("irf_common.center", 125.0) == pytest.approx(
        120.0
    )
    assert transform_parameter_for_shift_binwidth_bug("irf.shift678", 110.0) == pytest.approx(
        108.0
    )
    assert transform_parameter_for_shift_binwidth_bug("gauss_1.width", 50.0) == pytest.approx(40.0)
    assert transform_parameter_for_shift_binwidth_bug("irf.convwidth678", 5.0) == pytest.approx(
        4.0
    )
    assert transform_parameter_for_shift_binwidth_bug("irf_1.disp1", -0.83) == pytest.approx(
        -0.664
    )
    assert transform_parameter_for_shift_binwidth_bug(
        "irf_common.backsweep", 13800.0
    ) == pytest.approx(11040.0)
    assert transform_parameter_for_shift_binwidth_bug("kinetic.4", 0.0031) == pytest.approx(
        0.003875
    )
    assert transform_parameter_for_shift_binwidth_bug("ratecol0.kopen21", 0.12) == pytest.approx(
        0.15
    )
    assert transform_parameter_for_shift_binwidth_bug("irf_1.dispc", 690.0) == pytest.approx(690.0)


def test_convert_parameters_from_shift_binwidth_bug(write_csv) -> None:
    content = (
        "label,value,standard_error,expression,maximum,minimum,non_negative,vary\n"
        "irf_common.center,125,None,None,,,False,True\n"
        "irf.shift678,110,None,None,,,False,True\n"
        "gauss_1.width,50,None,None,,,False,True\n"
        "irf_1.disp1,-0.83,None,None,,,False,True\n"
        "irf_1.dispc,690,None,None,,,False,True\n"
        "irf_common.backsweep,13800,None,None,,,False,True\n"
        "kinetic.4,0.0031,None,None,,,False,True\n"
        "ratecol0.kopen21,0.12,None,None,,,False,True\n"
        "amplitude.scale,0.3,None,None,,,False,True\n"
    )
    path = write_csv("params_shift_fix.csv", content)

    changed = convert_parameters_from_shift_binwidth_bug(path)
    lines = path.read_text(encoding="utf-8").splitlines()

    assert changed["irf_common.center"] == pytest.approx((125.0, 120.0))
    assert changed["kinetic.4"] == pytest.approx((0.0031, 0.003875))
    assert lines[1].split(",")[1] == "120.0"
    assert lines[2].split(",")[1] == "108.0"
    assert lines[3].split(",")[1] == "40.0"
    assert lines[4].split(",")[1] == str(-0.83 * 0.8)
    assert lines[5].split(",")[1] == "690"
    assert lines[6].split(",")[1] == "11040.0"
    assert lines[7].split(",")[1] == "0.003875"
    assert lines[8].split(",")[1] == "0.15"
    assert lines[9].split(",")[1] == "0.3"


def test_convert_parameter_table_from_shift_binwidth_bug_dataframe() -> None:
    table = pd.DataFrame(
        {
            "label": ["irf_common.center", "kinetic.4", "amplitude.scale"],
            "value": [125.0, 0.0031, 0.3],
            "standard_error": [5.0, 0.0002, 0.02],
            "t-value": [25.0, 15.5, 15.0],
        }
    )

    converted = convert_parameter_table_from_shift_binwidth_bug(table)

    assert converted is not table
    assert converted.loc[0, "value"] == pytest.approx(120.0)
    assert converted.loc[0, "standard_error"] == pytest.approx(4.0)
    assert converted.loc[0, "t-value"] == pytest.approx(30.0)
    assert converted.loc[1, "value"] == pytest.approx(0.003875)
    assert converted.loc[1, "standard_error"] == pytest.approx(0.00025)
    assert converted.loc[1, "t-value"] == pytest.approx(15.5)
    assert converted.loc[2, "value"] == pytest.approx(0.3)
    assert converted.loc[2, "standard_error"] == pytest.approx(0.02)
    assert converted.loc[2, "t-value"] == pytest.approx(15.0)
    assert table.loc[0, "value"] == pytest.approx(125.0)


def test_convert_parameter_table_from_shift_binwidth_bug_object_with_index_labels() -> None:
    table = pd.DataFrame(
        {
            "value": [110.0, 50.0, 690.0],
            "stderr": [2.0, 10.0, 3.0],
            "T_value": [55.0, 5.0, 230.0],
        },
        index=["irf.shift678", "gauss_1.width", "irf_1.dispc"],
    )

    converted = convert_parameter_table_from_shift_binwidth_bug(_TableStub(table))

    assert converted.loc["irf.shift678", "value"] == pytest.approx(108.0)
    assert converted.loc["irf.shift678", "stderr"] == pytest.approx(1.6)
    assert converted.loc["irf.shift678", "T_value"] == pytest.approx(67.5)
    assert converted.loc["gauss_1.width", "value"] == pytest.approx(40.0)
    assert converted.loc["gauss_1.width", "stderr"] == pytest.approx(8.0)
    assert converted.loc["gauss_1.width", "T_value"] == pytest.approx(5.0)
    assert converted.loc["irf_1.dispc", "value"] == pytest.approx(690.0)
    assert converted.loc["irf_1.dispc", "stderr"] == pytest.approx(3.0)
