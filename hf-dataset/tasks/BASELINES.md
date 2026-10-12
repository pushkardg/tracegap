Baselines on the `test` split (2832 examples).

| Baseline | Task | Metrics |
|---|---|---|
| majority | T1_completeness | accuracy 0.626, defect_f1 0.000, balanced_accuracy 0.500 |
| majority | T2_fidelity | accuracy 0.875, defect_f1 0.000, balanced_accuracy 0.500 |
| majority | T3_defects | micro_f1 0.000, macro_f1 0.000, exact_match 0.589 |
| majority | T4_reconstruction | call_accuracy 0.764, macro_f1 0.173, case_exact_match 0.383 |
| heuristic | T1_completeness | accuracy 0.817, defect_f1 0.795, balanced_accuracy 0.843 |
| heuristic | T2_fidelity | accuracy 0.819, defect_f1 0.085, balanced_accuracy 0.497 |
| heuristic | T3_defects | micro_f1 0.373, macro_f1 0.258, exact_match 0.466 |
| heuristic | T4_reconstruction | call_accuracy 0.741, macro_f1 0.404, case_exact_match 0.601 |
