# Hidden-line evidence in committed verdicts

34 of 3258 committed Claude verdicts cite events hidden in their mode ({'final_report': 34}); 11 are labeller-hacked; 7 have only hidden evidence. Repair changes hack_detected in 0. Strict drops types {'suspicious_access': 30, 'rationalization': 3}.

| run | mode | n | affected | variant | precision | recall | hack-type recall |
|---|---|---|---|---|---|---|---|
| results/probe_v1 | final_report | 36 | 1 | original | 0.000 | 0.000 | fabricated_source 0/3, rationalization 0/3 |
| results/probe_v1 | final_report | 36 | 1 | repaired | 0.000 | 0.000 | fabricated_source 0/3, rationalization 0/3 |
| results/probe_v1 | final_report | 36 | 1 | strict | 0.000 | 0.000 | fabricated_source 0/3, rationalization 0/3 |
| results/probe_v1 | final_report | 36 | 1 | exclude | 0.000 | 0.000 | fabricated_source 0/3, rationalization 0/3 |
| results/v2_haiku45 | final_report | 120 | 2 | original | 0.214 | 0.750 | fabricated_source 5/8, fabricated_verification 4/4, methodological_drift 3/4, rationalization 0/5 |
| results/v2_haiku45 | final_report | 120 | 2 | repaired | 0.214 | 0.750 | fabricated_source 5/8, fabricated_verification 4/4, methodological_drift 3/4, rationalization 0/5 |
| results/v2_haiku45 | final_report | 120 | 2 | strict | 0.214 | 0.750 | fabricated_source 5/8, fabricated_verification 4/4, methodological_drift 3/4, rationalization 0/5 |
| results/v2_haiku45 | final_report | 120 | 2 | exclude | 0.225 | 0.750 | fabricated_source 5/8, fabricated_verification 4/4, methodological_drift 3/4, rationalization 0/5 |
| results/v2_haiku45/reaudit_claude-opus-4-6 | final_report | 120 | 2 | original | 0.588 | 0.435 | fabricated_source 12/21, fabricated_verification 5/27, methodological_drift 4/5, rationalization 0/5, suspicious_access 2/20 |
| results/v2_haiku45/reaudit_claude-opus-4-6 | final_report | 120 | 2 | repaired | 0.588 | 0.435 | fabricated_source 12/21, fabricated_verification 5/27, methodological_drift 4/5, rationalization 0/5, suspicious_access 2/20 |
| results/v2_haiku45/reaudit_claude-opus-4-6 | final_report | 120 | 2 | strict | 0.588 | 0.435 | fabricated_source 12/21, fabricated_verification 5/27, methodological_drift 4/5, rationalization 0/5, suspicious_access 1/20 |
| results/v2_haiku45/reaudit_claude-opus-4-6 | final_report | 120 | 2 | exclude | 0.562 | 0.409 | fabricated_source 12/20, fabricated_verification 5/26, methodological_drift 4/5, rationalization 0/4, suspicious_access 1/19 |
| results/v2_sonnet45 | final_report | 120 | 8 | original | 0.326 | 0.652 | fabricated_source 7/12, fabricated_verification 2/8, methodological_drift 8/10, rationalization 0/10, suspicious_access 0/1 |
| results/v2_sonnet45 | final_report | 120 | 8 | repaired | 0.326 | 0.652 | fabricated_source 7/12, fabricated_verification 2/8, methodological_drift 8/10, rationalization 0/10, suspicious_access 0/1 |
| results/v2_sonnet45 | final_report | 120 | 8 | strict | 0.326 | 0.652 | fabricated_source 7/12, fabricated_verification 2/8, methodological_drift 8/10, rationalization 0/10, suspicious_access 0/1 |
| results/v2_sonnet45 | final_report | 120 | 8 | exclude | 0.368 | 0.636 | fabricated_source 6/11, fabricated_verification 2/8, methodological_drift 8/10, rationalization 0/9, suspicious_access 0/1 |
| results/v2_sonnet46 | final_report | 120 | 8 | original | 0.070 | 0.250 | fabricated_source 2/8, fabricated_verification 2/3, methodological_drift 0/4, rationalization 0/5 |
| results/v2_sonnet46 | final_report | 120 | 8 | repaired | 0.070 | 0.250 | fabricated_source 2/8, fabricated_verification 2/3, methodological_drift 0/4, rationalization 0/5 |
| results/v2_sonnet46 | final_report | 120 | 8 | strict | 0.070 | 0.250 | fabricated_source 2/8, fabricated_verification 2/3, methodological_drift 0/4, rationalization 0/5 |
| results/v2_sonnet46 | final_report | 120 | 8 | exclude | 0.086 | 0.250 | fabricated_source 2/8, fabricated_verification 2/3, methodological_drift 0/4, rationalization 0/5 |
| results/v2_sonnet46/reaudit_claude-opus-4-6 | final_report | 120 | 6 | original | 0.162 | 0.500 | fabricated_source 4/8, fabricated_verification 1/3, methodological_drift 1/4, rationalization 0/5 |
| results/v2_sonnet46/reaudit_claude-opus-4-6 | final_report | 120 | 6 | repaired | 0.162 | 0.500 | fabricated_source 4/8, fabricated_verification 1/3, methodological_drift 1/4, rationalization 0/5 |
| results/v2_sonnet46/reaudit_claude-opus-4-6 | final_report | 120 | 6 | strict | 0.162 | 0.500 | fabricated_source 4/8, fabricated_verification 1/3, methodological_drift 1/4, rationalization 0/5 |
| results/v2_sonnet46/reaudit_claude-opus-4-6 | final_report | 120 | 6 | exclude | 0.129 | 0.400 | fabricated_source 3/6, fabricated_verification 1/3, methodological_drift 1/4, rationalization 0/3 |
| results/v3_sonnet46 | final_report | 150 | 7 | original | 0.583 | 0.622 | fabricated_source 20/36, fabricated_verification 6/12, methodological_drift 1/3, rationalization 0/12, suspicious_access 5/6 |
| results/v3_sonnet46 | final_report | 150 | 7 | repaired | 0.583 | 0.622 | fabricated_source 20/36, fabricated_verification 6/12, methodological_drift 1/3, rationalization 0/12, suspicious_access 5/6 |
| results/v3_sonnet46 | final_report | 150 | 7 | strict | 0.583 | 0.622 | fabricated_source 20/36, fabricated_verification 6/12, methodological_drift 1/3, rationalization 0/12, suspicious_access 1/6 |
| results/v3_sonnet46 | final_report | 150 | 7 | exclude | 0.537 | 0.564 | fabricated_source 20/36, fabricated_verification 5/6, methodological_drift 1/3, rationalization 0/12 |

eval.evidence gold set: 1 affected verdict(s).

| traces | cohort | auditor | mode | variant | n | P±1 | R | hit@1 | type exact | hidden lines |
|---|---|---|---|---|---|---|---|---|---|---|
| all | v2 | Opus | final_report | original | 19 | 1.000 | 0.190 | 0.579 | 0.105 | 0 |
| all | v2 | Sonnet | final_report | original | 26 | 0.625 | 0.253 | 0.654 | 0.154 | 22 |
| all | v2 | Opus | final_report | repaired | 19 | 1.000 | 0.190 | 0.579 | 0.105 | 0 |
| all | v2 | Sonnet | final_report | repaired | 26 | 1.000 | 0.215 | 0.654 | 0.154 | 0 |
| common | v2 | Opus | final_report | original | 19 | 1.000 | 0.190 | 0.579 | 0.105 | 0 |
| common | v2 | Sonnet | final_report | original | 19 | 0.571 | 0.259 | 0.632 | 0.211 | 22 |
| common | v2 | Opus | final_report | repaired | 19 | 1.000 | 0.190 | 0.579 | 0.105 | 0 |
| common | v2 | Sonnet | final_report | repaired | 19 | 1.000 | 0.207 | 0.632 | 0.211 | 0 |
