from carbon_mrv.data.metadata import methodology_parameter_consistency


def test_methodology_parameter_consistency_recognizes_case_constants():
    report=methodology_parameter_consistency({
        "CF":"0.47",
        "co2_per_c":"44/12",
        "LK":0,
        "buffer_fraction":"15%",
        "uncertainty_threshold":0.10,
        "other_parameter":"preserve me",
    })
    assert report["mismatch_count"]==0
    assert len(report["recognized_checks"])==5
    assert report["uninterpreted_keys"]==["other_parameter"]


def test_methodology_parameter_consistency_detects_mismatch():
    report=methodology_parameter_consistency({"CF":0.5})
    assert report["mismatch_count"]==1
    assert report["mismatches"][0]["semantic_name"]=="carbon_fraction"
