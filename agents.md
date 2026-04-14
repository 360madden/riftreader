{
  "bundle_id": "codex_camera_yaw_anchor_hunt_v1",
  "version": "2026-04-14",
  "scope": {
    "authorized_local_analysis_only": true,
    "deliverable": "Find one live memory anchor that changes with camera yaw while player position and actor orientation remain interpretable.",
    "stop_on_first_success": true,
    "forbidden": [
      "anti_cheat_bypass",
      "multiplayer_targeting",
      "stealth_or_evasion",
      "network_tampering",
      "credential_access",
      "persistence",
      "automation_or_cheat_feature_buildout_beyond_single_anchor_validation"
    ]
  },
  "recommended_boot_sequence": [
    {
      "action": "mkdir",
      "path": ".agent/results"
    },
    {
      "action": "write_file",
      "path": "AGENTS.md"
    },
    {
      "action": "write_file",
      "path": ".agent/TASK.json"
    },
    {
      "action": "write_file",
      "path": ".agent/RESULT.schema.json"
    },
    {
      "action": "optional_command",
      "value": "/plan"
    },
    {
      "action": "send_prompt",
      "path": "LAUNCH_PROMPT.txt"
    }
  ],
  "files": {
    "AGENTS.md": [
      "# Mission",
      "- Deliver exactly one validated yaw-sensitive memory anchor.",
      "- Success target: one live anchor that changes with camera yaw while player position and actor orientation remain interpretable.",
      "",
      "# Scope freeze",
      "- In scope: discovery, ranking, validation, and the minimal neighborhood interpretation needed to prove one anchor.",
      "- Out of scope: full memory maps, cheat features, automation, aim logic, pointer trees beyond what is needed to reacquire the single anchor, and unrelated engine reverse engineering.",
      "- Stop immediately after the first passing anchor.",
      "",
      "# Authorization boundary",
      "- Operate only on targets you are authorized to inspect.",
      "- Do not attempt anti-cheat bypass, multiplayer targeting, stealth, persistence, network tampering, credential access, or detection evasion.",
      "",
      "# Work model",
      "- Keep one main thread for this deliverable.",
      "- Use explicit subagents only for bounded, disjoint work.",
      "- Main thread owns scope control, state, ranking, pruning, fallback decisions, and final result emission.",
      "- All intermediate outputs must be machine-readable JSON written to .agent/STATE.json or .agent/results/*.json.",
      "- Never paste raw logs or dumps into the main thread.",
      "",
      "# Efficiency rules",
      "- Highest-yield search order: reuse known anchors if available, controlled differential scans, structural scans, targeted access tracing, minimal neighborhood mapping.",
      "- Do not run broad pointer scans before a candidate is proven live.",
      "- Do not spawn more than 2 scout subagents in parallel.",
      "- Do not validate more than 3 promoted candidates total.",
      "- Kill low-signal branches early.",
      "",
      "# Context discipline",
      "- Update state only at stage boundaries or material branch changes.",
      "- Keep summaries terse and numeric where possible.",
      "- If context grows, compact only after state has been written.",
      "",
      "# Output contract",
      "- Final response must equal the JSON object in .agent/RESULT.json.",
      "- If blocked or exhausted, return a JSON result with precise blocker data and best remaining candidates."
    ],
    ".agent/TASK.json": {
      "mission_id": "find_one_live_memory_anchor_camera_yaw",
      "objective": "Find one live memory anchor that changes with camera yaw while player position and actor orientation remain interpretable.",
      "stop_on_first_success": true,
      "environment_discovery": {
        "discover_at_runtime": [
          "target_process",
          "platform_and_architecture",
          "available_memory_tools",
          "debugger_or_watchpoint_availability",
          "existing_known_player_position_anchor",
          "existing_known_actor_orientation_anchor",
          "whether_camera_pitch_can_be_held_stable"
        ]
      },
      "scope_freeze": {
        "deliverable_count": 1,
        "accept_only_minimal_validation_surface": true,
        "out_of_scope": [
          "full_camera_system_mapping",
          "global_pointer_tree_hunting_before_liveness",
          "secondary_anchor_collection",
          "automation_features",
          "unrelated_engine_RE"
        ]
      },
      "semantic_requirement": {
        "preferred": "Anchor resides in or near a structure where player position and actor orientation remain interpretable from nearby fields.",
        "acceptable_fallback": "Anchor can be deterministically paired with already-known position and actor-orientation anchors without ambiguity."
      },
      "control_protocol": {
        "principle": "one_variable_at_a_time",
        "requirements": [
          "hold_player_position_fixed",
          "hold_camera_pitch_as_constant_as_practical",
          "avoid_translation_and_state_transitions_during_yaw_sweeps",
          "collect_no_yaw_hold_windows_before_and_after_each_sweep",
          "repeat_same_pattern_at_least_twice"
        ],
        "yaw_sweep_template_degrees": {
          "stops": [
            -180,
            -120,
            -60,
            0,
            60,
            120,
            180
          ],
          "passes": [
            "cw",
            "ccw"
          ],
          "repeats": 2
        }
      },
      "conditional_priority_shift": [
        {
          "if": "existing_known_player_position_anchor OR existing_known_actor_orientation_anchor",
          "then": [
            "seed_structural_search_around_known_anchor_neighborhoods",
            "attempt_neighborhood_first_before_broader_scans"
          ]
        }
      ],
      "candidate_models": [
        {
          "id": "scalar_angle",
          "priority": 1,
          "representations": [
            "float32_deg",
            "float32_rad",
            "signed_norm",
            "unsigned_norm",
            "float64_deg",
            "float64_rad"
          ]
        },
        {
          "id": "paired_scalar",
          "priority": 1,
          "representations": [
            "sin_cos_pair",
            "cos_sin_pair"
          ]
        },
        {
          "id": "direction_vector",
          "priority": 1,
          "representations": [
            "forward_xz",
            "right_xz",
            "forward_xyz"
          ]
        },
        {
          "id": "quaternion_fragment",
          "priority": 2,
          "representations": [
            "quat_y",
            "quat_w",
            "paired_quat_components"
          ]
        },
        {
          "id": "matrix_element",
          "priority": 2,
          "representations": [
            "view_matrix_row_or_col",
            "camera_transform_element"
          ]
        }
      ],
      "reject_patterns": [
        "changes_more_during_no_yaw_hold_than_during_yaw_steps",
        "tracks_pitch_or_roll_more_strongly_than_yaw",
        "ui_only_heading_without_stable_reacquisition_recipe",
        "transient_scratch_value_without_reacquisition_or_writer_trace",
        "candidate_requires_scope_expansion_beyond_single_anchor_validation"
      ],
      "scoring": {
        "weights": {
          "yaw_fit": 0.35,
          "repeatability": 0.2,
          "stability_in_hold_windows": 0.15,
          "semantic_neighborhood": 0.15,
          "writer_or_reacquisition_clarity": 0.15
        },
        "promote_threshold": 0.72,
        "medium_confidence_threshold": 0.55,
        "pass_threshold": 0.82
      },
      "cost_controls": {
        "max_parallel_scout_subagents": 2,
        "max_validation_subagents": 1,
        "max_promoted_candidates": 3,
        "max_fallback_cycles": 1,
        "max_candidates_per_scout": 5,
        "max_agent_output_bytes": 2500,
        "raw_log_paste_to_main_thread": false,
        "broad_pointer_scan_before_liveness": false
      },
      "state_contract": {
        "state_file": ".agent/STATE.json",
        "results_dir": ".agent/results",
        "state_fields": [
          "mission_id",
          "stage",
          "environment",
          "capture_protocol",
          "known_anchors",
          "top_candidates",
          "rejected_hypotheses",
          "next_action",
          "fallbacks_used"
        ],
        "update_rule": "write_state_at_stage_boundary_or_material_branch_change_only"
      },
      "agents": {
        "main_orchestrator": {
          "responsibilities": [
            "environment_discovery",
            "state_management",
            "candidate_fusion",
            "global_ranking",
            "pruning",
            "fallback_control",
            "final_result_emit"
          ],
          "must_not_idle": true,
          "work_during_parallel_scouts": [
            "prepare_value_canonicalization_rules",
            "prepare_dedupe_rules_by_region_writer_or_structure",
            "prepare_validation_checklist",
            "inspect_known_anchor_neighborhoods_if_any",
            "prebuild_RESULT_json_shell"
          ]
        },
        "scout_scalar": {
          "spawn_stage": "parallel_scout",
          "goal": "Find scalar_or_simple_paired candidates that track yaw under the control protocol.",
          "search_space": [
            "float32_deg",
            "float32_rad",
            "signed_norm",
            "unsigned_norm",
            "float64_only_if_float32_is_inconclusive",
            "simple_2_value_pairs"
          ],
          "rules": [
            "prioritize_float32",
            "test_wrap_and_normalization_transforms",
            "reject_hold_window_instability",
            "output_top_ranked_candidates_only"
          ],
          "output_file": ".agent/results/scout_scalar.json"
        },
        "scout_struct": {
          "spawn_stage": "parallel_scout",
          "goal": "Find vector_quaternion_matrix_or_structure candidates linked to yaw and preserve neighboring semantics.",
          "search_space": [
            "sin_cos_pair",
            "camera_forward_vector",
            "camera_right_vector",
            "quat_fragments",
            "view_or_camera_matrix_elements",
            "neighborhood_of_known_position_or_orientation_if_available"
          ],
          "rules": [
            "prioritize_known_anchor_neighborhoods_if_present",
            "score_geometric_consistency",
            "prefer_candidates_with_interpretable_neighbor_fields",
            "output_top_ranked_candidates_only"
          ],
          "output_file": ".agent/results/scout_struct.json"
        },
        "validator": {
          "spawn_stage": "validate",
          "goal": "Prove one promoted candidate is a usable live anchor.",
          "methods": [
            "resweep_revalidation",
            "hold_window_stability_check",
            "minimal_neighborhood_mapping",
            "writer_or_access_trace_if_available_and_authorized",
            "reacquisition_recipe_if_address_is_ephemeral"
          ],
          "output_file_template": ".agent/results/validator_<n>.json"
        }
      },
      "stages": [
        {
          "id": "setup_discovery",
          "actions": [
            "discover_runtime_environment",
            "detect_existing_known_position_or_orientation_anchors",
            "create_state_and_results_files",
            "write_control_protocol_to_state",
            "record_candidate_models_and_thresholds_in_state"
          ],
          "outputs": [
            ".agent/STATE.json"
          ]
        },
        {
          "id": "parallel_scout",
          "spawn": [
            "scout_scalar",
            "scout_struct"
          ],
          "main_thread_work": [
            "prepare_canonicalization_and_dedupe_rules",
            "inspect_known_anchor_neighborhoods_if_available",
            "prepare_validator_inputs_and_pass_fail_checks"
          ],
          "completion_rule": "wait_for_both_scout_outputs_or_early_promote_if_any_candidate_score_exceeds_pass_threshold"
        },
        {
          "id": "fuse_and_prune",
          "actions": [
            "load_scout_outputs",
            "canonicalize_all_candidates_into_yaw_comparable_space",
            "dedupe_aliases_by_region_writer_structure_or_equivalent_transform",
            "global_rank",
            "promote_top_candidates_up_to_limit"
          ],
          "promote_rule": "score_gte_promote_threshold",
          "failover_rule": "if_no_candidate_gte_promote_threshold_then_select_best_medium_confidence_candidate_only_if_score_gte_medium_confidence_threshold_and_debugger_or_reacquisition_path_exists"
        },
        {
          "id": "validate",
          "sequence": [
            "validate_promoted_candidate_1",
            "validate_promoted_candidate_2_if_needed",
            "validate_promoted_candidate_3_if_needed"
          ],
          "main_thread_work_while_validator_runs": [
            "inspect_neighbor_semantics_on_remaining_promoted_candidates",
            "prepare_next_validator_input_only_if_current_candidate_fails"
          ],
          "early_stop_rule": "stop_all_other_work_on_first_passing_candidate"
        },
        {
          "id": "single_fallback_cycle",
          "enter_only_if": "no_candidate_passed_validate",
          "allowed_adjustments": [
            "increase_capture_density_once",
            "use_access_trace_on_best_medium_confidence_candidate_if_available_and_authorized",
            "widen_float64_or_matrix_checks_once_if_not_already_done"
          ],
          "forbidden_adjustments": [
            "new_search_family_outside_candidate_models",
            "broad_pointer_tree_hunt_before_live_candidate",
            "expanding_scope_beyond_single_anchor"
          ]
        },
        {
          "id": "emit_result",
          "actions": [
            "write_.agent/RESULT.json",
            "return_only_RESULT_json"
          ]
        }
      ],
      "success_contract": {
        "must_satisfy": [
          "candidate_changes_predictably_with_yaw",
          "candidate_remains_stable_in_no_yaw_hold_windows",
          "candidate_is_repeatable_across_repeated_sweeps",
          "player_position_and_actor_orientation_remain_interpretable_via_same_neighborhood_or_unambiguous_pairing",
          "anchor_has_address_or_reacquisition_recipe"
        ],
        "preferred": [
          "same_structure_contains_or_neighbors_position_and_orientation_fields",
          "writer_or_access_trace_identifies_source_of_truth"
        ]
      },
      "failure_contract": {
        "on_blocked_or_exhausted_return": [
          "status",
          "precise_blocker_or_reason",
          "best_remaining_candidates_ranked",
          "what_was_tried",
          "smallest_next_untried_step"
        ]
      }
    },
    ".agent/RESULT.schema.json": {
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "title": "YawAnchorResult",
      "type": "object",
      "required": [
        "status",
        "mission_id",
        "anchor",
        "evidence",
        "alternates",
        "notes"
      ],
      "properties": {
        "status": {
          "type": "string",
          "enum": [
            "success",
            "blocked",
            "exhausted"
          ]
        },
        "mission_id": {
          "type": "string",
          "const": "find_one_live_memory_anchor_camera_yaw"
        },
        "anchor": {
          "type": "object",
          "required": [
            "locator",
            "class",
            "encoding",
            "yaw_relation",
            "position_interpretation",
            "actor_orientation_interpretation",
            "confidence"
          ],
          "properties": {
            "locator": {
              "type": "object",
              "required": [
                "kind",
                "value"
              ],
              "properties": {
                "kind": {
                  "type": "string",
                  "enum": [
                    "address",
                    "module_plus_offset",
                    "region_signature",
                    "reacquisition_recipe"
                  ]
                },
                "value": {
                  "type": "string"
                }
              }
            },
            "class": {
              "type": "string",
              "enum": [
                "scalar",
                "pair",
                "vector_component",
                "quaternion_fragment",
                "matrix_element",
                "structure_base"
              ]
            },
            "encoding": {
              "type": "string"
            },
            "yaw_relation": {
              "type": "string"
            },
            "position_interpretation": {
              "type": "string"
            },
            "actor_orientation_interpretation": {
              "type": "string"
            },
            "confidence": {
              "type": "number"
            }
          }
        },
        "evidence": {
          "type": "object",
          "required": [
            "protocol",
            "validation_steps",
            "samples",
            "writer_or_reacquisition",
            "reason_passed"
          ],
          "properties": {
            "protocol": {
              "type": "string"
            },
            "validation_steps": {
              "type": "array",
              "items": {
                "type": "string"
              }
            },
            "samples": {
              "type": "array",
              "minItems": 3,
              "items": {
                "type": "object",
                "required": [
                  "yaw_input",
                  "anchor_value_repr",
                  "note"
                ],
                "properties": {
                  "yaw_input": {
                    "type": "number"
                  },
                  "anchor_value_repr": {
                    "type": "string"
                  },
                  "note": {
                    "type": "string"
                  }
                }
              }
            },
            "writer_or_reacquisition": {
              "type": "string"
            },
            "reason_passed": {
              "type": "string"
            }
          }
        },
        "alternates": {
          "type": "array",
          "maxItems": 2,
          "items": {
            "type": "object",
            "required": [
              "locator_hint",
              "class",
              "score",
              "why_not_chosen"
            ],
            "properties": {
              "locator_hint": {
                "type": "string"
              },
              "class": {
                "type": "string"
              },
              "score": {
                "type": "number"
              },
              "why_not_chosen": {
                "type": "string"
              }
            }
          }
        },
        "notes": {
          "type": "object",
          "required": [
            "scope_respected",
            "fallbacks_used"
          ],
          "properties": {
            "scope_respected": {
              "type": "boolean"
            },
            "fallbacks_used": {
              "type": "array",
              "items": {
                "type": "string"
              }
            }
          }
        }
      }
    },
    "LAUNCH_PROMPT.txt": [
      "Read AGENTS.md, .agent/TASK.json, and .agent/RESULT.schema.json before doing anything else.",
      "Mirror TASK.json stages in a terse plan, then execute without expanding scope.",
      "Create or update .agent/STATE.json immediately after environment discovery.",
      "Keep one main thread for the entire deliverable.",
      "Spawn exactly 2 bounded scout subagents in parallel for Stage parallel_scout: scout_scalar and scout_struct.",
      "While scouts run, the main thread must stay productive: prepare canonicalization rules, dedupe rules, validator inputs, and inspect any known anchor neighborhoods.",
      "Fuse and prune candidates globally. Promote at most 3.",
      "Validate promoted candidates sequentially until one passes. Stop immediately on first pass.",
      "Run at most one fallback cycle if validation fails.",
      "Write only machine-readable JSON to .agent/STATE.json, .agent/results/*.json, and .agent/RESULT.json.",
      "Return exactly the JSON object in .agent/RESULT.json and nothing else."
    ]
  }
}