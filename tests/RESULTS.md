# Offline test results — 2026-11-07T11:30:09+05:30

**124 methods: 124 passed, 0 failed; 0 errors, 0 skipped.**

Python: `D:\python_3.12\python.exe` (3.12.10).

Run from the project directory: `python -B tests/run_tests.py`

External services, OAuth, audio, desktop actions, and Chroma are mocked. SQLite and plain-file tests use temporary fixtures. No live integration readiness is implied.

## Results by suite

| Suite | Passed methods | Failed/error methods |
| --- | ---: | ---: |
| test_core.py | 33 | 0 |
| test_interactions.py | 34 | 0 |
| test_memory_ui.py | 15 | 0 |
| test_services.py | 30 | 0 |
| test_whatsapp.py | 12 | 0 |

## Failures

None. All executed cases passed; unchecked README acceptance items remain unverified or only partly covered.

## Passing cases

- [x] `tests.test_core.BrainTests.test_entry_points_and_tool_error`
- [x] `tests.test_core.BrainTests.test_extract_quoted_paths_and_search_terms`
- [x] `tests.test_core.BrainTests.test_file_dispatch_and_missing_write_arguments`
- [x] `tests.test_core.BrainTests.test_intent_examples_case_and_punctuation`
- [x] `tests.test_core.BrainTests.test_memory_failures_do_not_break_exchange`
- [x] `tests.test_core.BrainTests.test_music_queue_routing`
- [x] `tests.test_core.BrainTests.test_ollama_success_empty_and_errors`
- [x] `tests.test_core.BrainTests.test_pending_file_confirmation_intercepts_yes_and_cancel`
- [x] `tests.test_core.BrainTests.test_regression_calendar_delete_today_does_not_list`
- [x] `tests.test_core.BrainTests.test_regression_intent_collisions`
- [x] `tests.test_core.BrainTests.test_regression_lowercase_city`
- [x] `tests.test_core.BrainTests.test_regression_router_integration_task_commands`
- [x] `tests.test_core.BrainTests.test_regression_task_due_date_priority`
- [x] `tests.test_core.BrainTests.test_regression_task_identifier_parsing`
- [x] `tests.test_core.BrainTests.test_search_context_forwarded`
- [x] `tests.test_core.FilesystemTests.test_confirmation_prevents_mutations`
- [x] `tests.test_core.FilesystemTests.test_find_list_empty_missing_sort_and_errors`
- [x] `tests.test_core.FilesystemTests.test_long_output_preserves_start_and_end`
- [x] `tests.test_core.FilesystemTests.test_open_dispatch_platforms_and_failure`
- [x] `tests.test_core.FilesystemTests.test_path_allow_blacklist_outside_and_traversal`
- [x] `tests.test_core.FilesystemTests.test_pending_confirmation_flow_executes_once_and_cancels`
- [x] `tests.test_core.FilesystemTests.test_plain_read_invalid_encoding_directory_and_extension`
- [x] `tests.test_core.FilesystemTests.test_temporary_write_move_and_mutation_errors`
- [x] `tests.test_core.StartupTests.test_dashboard_port_dispatch`
- [x] `tests.test_core.StartupTests.test_launch_failure_enters_terminal`
- [x] `tests.test_core.StartupTests.test_ollama_absent_aborts_before_services`
- [x] `tests.test_core.StartupTests.test_ollama_health_and_failures`
- [x] `tests.test_core.StartupTests.test_regression_missing_optional_import_is_handled`
- [x] `tests.test_core.StartupTests.test_terminal_input_and_clean_exit`
- [x] `tests.test_core.TaskTests.test_complete_delete_by_id_title_and_missing`
- [x] `tests.test_core.TaskTests.test_create_and_persist_valid_tasks_reject_blank`
- [x] `tests.test_core.TaskTests.test_filters_order_and_empty_results`
- [x] `tests.test_core.TaskTests.test_overdue_boundary_and_completion`
- [x] `tests.test_interactions.MusicTests.test_load_or_play_failure_does_not_set_current_track`
- [x] `tests.test_interactions.MusicTests.test_missing_ffmpeg_prevents_download`
- [x] `tests.test_interactions.MusicTests.test_nonzero_download_with_partial_file_does_not_claim_success`
- [x] `tests.test_interactions.MusicTests.test_play_errors_no_results_download_dependency_and_player`
- [x] `tests.test_interactions.MusicTests.test_play_failure_after_stopping_clears_previous_status`
- [x] `tests.test_interactions.MusicTests.test_play_releases_existing_file_before_replacing_it`
- [x] `tests.test_interactions.MusicTests.test_queue_order_clear_skip_and_pause_dispatch`
- [x] `tests.test_interactions.MusicTests.test_regression_successful_play_updates_now_playing`
- [x] `tests.test_interactions.MusicTests.test_search_found_empty_and_missing_id`
- [x] `tests.test_interactions.MusicTests.test_unplayable_search_result_leaves_existing_track_alone`
- [x] `tests.test_interactions.MusicTests.test_volume_bounds_invalid_and_moods`
- [x] `tests.test_interactions.SystemControlTests.test_apps_path_lookup_launch_and_failure`
- [x] `tests.test_interactions.SystemControlTests.test_click_type_hotkey_dispatch_and_failures`
- [x] `tests.test_interactions.SystemControlTests.test_close_app_matches_executable_name_case_insensitively`
- [x] `tests.test_interactions.SystemControlTests.test_power_commands_all_platforms_and_errors`
- [x] `tests.test_interactions.SystemControlTests.test_process_listing_and_permission_errors`
- [x] `tests.test_interactions.SystemControlTests.test_regression_close_app_does_not_match_unrelated_substring`
- [x] `tests.test_interactions.SystemControlTests.test_screenshot_unique_filenames_and_errors`
- [x] `tests.test_interactions.SystemControlTests.test_volume_brightness_dispatch_and_bounds`
- [x] `tests.test_interactions.VisionTests.test_image_path_validation_and_prompts`
- [x] `tests.test_interactions.VisionTests.test_ocr_text_blank_and_failure`
- [x] `tests.test_interactions.VisionTests.test_ollama_payload_success_and_failures`
- [x] `tests.test_interactions.VisionTests.test_regression_ocr_captures_only_once`
- [x] `tests.test_interactions.VisionTests.test_screen_and_error_capture_prompts_and_failures`
- [x] `tests.test_interactions.VoiceTests.test_listen_silence_timeout_device_and_network_failures`
- [x] `tests.test_interactions.VoiceTests.test_listen_transcript_and_timeout_arguments`
- [x] `tests.test_interactions.VoiceTests.test_speak_repeated_calls_and_blank_input`
- [x] `tests.test_interactions.VoiceTests.test_speech_cancellation_and_engine_failure_reset_state`
- [x] `tests.test_interactions.WakeTests.test_detection_state_sequence_and_handoff`
- [x] `tests.test_interactions.WakeTests.test_no_command_and_loop_exception_recover_idle`
- [x] `tests.test_interactions.WakeTests.test_regression_unrelated_friday_substring_is_not_wake_word`
- [x] `tests.test_interactions.WakeTests.test_start_is_idempotent_without_real_thread`
- [x] `tests.test_interactions.WakeTests.test_transcript_wake_match_and_unrelated_speech`
- [x] `tests.test_interactions.WakeTests.test_wake_word_boundaries_and_punctuation`
- [x] `tests.test_memory_ui.DashboardTests.test_count_parser_no_unread_and_failure_messages`
- [x] `tests.test_memory_ui.DashboardTests.test_regression_status_refresh_does_not_drive_whatsapp_ui`
- [x] `tests.test_memory_ui.DashboardTests.test_service_failures_and_unavailable_memory_fall_back`
- [x] `tests.test_memory_ui.DashboardTests.test_status_cached_within_ttl_and_rebuilds_after_expiry`
- [x] `tests.test_memory_ui.MemoryTests.test_conversation_roles_and_recent_chronology`
- [x] `tests.test_memory_ui.MemoryTests.test_regression_remember_request_stores_one_preference`
- [x] `tests.test_memory_ui.MemoryTests.test_save_memory_id_text_metadata_and_empty_input`
- [x] `tests.test_memory_ui.MemoryTests.test_search_query_contract_empty_and_invalid`
- [x] `tests.test_memory_ui.OptionalStartupTests.test_missing_optional_services_leave_main_usable`
- [x] `tests.test_memory_ui.OptionalStartupTests.test_terminal_still_answers_without_voice_module`
- [x] `tests.test_memory_ui.SourceTests.test_all_application_sources_parse`
- [x] `tests.test_memory_ui.UiTests.test_mic_empty_and_success_callbacks`
- [x] `tests.test_memory_ui.UiTests.test_regression_mic_failure_has_visible_explanation`
- [x] `tests.test_memory_ui.UiTests.test_status_escaping_and_missing_memory`
- [x] `tests.test_memory_ui.UiTests.test_submit_preserves_history_and_empty_input`
- [x] `tests.test_services.CalendarTests.test_create_payload_duration_invalid_input_and_api_failure`
- [x] `tests.test_services.CalendarTests.test_day_bounds_are_local_midnights_with_exclusive_end`
- [x] `tests.test_services.CalendarTests.test_delete_match_no_match_and_api_failure`
- [x] `tests.test_services.CalendarTests.test_duplicate_titles_do_not_delete_arbitrary_event`
- [x] `tests.test_services.CalendarTests.test_event_listing_empty_formatted_and_api_failure`
- [x] `tests.test_services.CalendarTests.test_free_slots_convert_offsets_and_merge_overlaps`
- [x] `tests.test_services.CalendarTests.test_free_slots_empty_overlap_outside_and_full_day`
- [x] `tests.test_services.CalendarTests.test_free_slots_exclude_cancelled_transparent_and_previous_day`
- [x] `tests.test_services.CalendarTests.test_invalid_duration_does_not_start_oauth`
- [x] `tests.test_services.CalendarTests.test_regression_all_day_blocks_free_slots`
- [x] `tests.test_services.CalendarTests.test_regression_create_uses_iana_timezone`
- [x] `tests.test_services.CalendarTests.test_regression_events_pagination`
- [x] `tests.test_services.CalendarTests.test_regression_reject_negative_duration`
- [x] `tests.test_services.CalendarTests.test_today_upcoming_use_configured_timezone`
- [x] `tests.test_services.GmailTests.test_body_plain_nested_html_padding_and_unicode`
- [x] `tests.test_services.GmailTests.test_read_full_message_and_fallback_snippet`
- [x] `tests.test_services.GmailTests.test_read_search_api_failures`
- [x] `tests.test_services.GmailTests.test_regression_gmail_import_without_whatsapp`
- [x] `tests.test_services.GmailTests.test_send_exact_mime_and_api_error`
- [x] `tests.test_services.GmailTests.test_unread_and_search_empty_multiple_limits_and_fields`
- [x] `tests.test_services.OAuthTests.test_missing_first_authorization_refresh_revoked_and_build_failure`
- [x] `tests.test_services.SearchTests.test_alternate_result_fields_and_blank_rows`
- [x] `tests.test_services.SearchTests.test_empty_and_network_errors`
- [x] `tests.test_services.SearchTests.test_web_and_news_format_limit_and_query`
- [x] `tests.test_services.WeatherTests.test_forecast_grouping_and_empty_response`
- [x] `tests.test_services.WeatherTests.test_get_weather_configuration_and_errors`
- [x] `tests.test_services.WeatherTests.test_get_weather_success_and_units`
- [x] `tests.test_services.WeatherTests.test_jacket_cold_warm_and_precipitation`
- [x] `tests.test_services.WeatherTests.test_regression_forecast_explicit_units`
- [x] `tests.test_services.WeatherTests.test_regression_forecast_requests_city_local_timezone`
- [x] `tests.test_whatsapp.WhatsAppTests.test_actions_return_readiness_and_activation_errors_without_typing`
- [x] `tests.test_whatsapp.WhatsAppTests.test_find_visible_window_and_activate`
- [x] `tests.test_whatsapp.WhatsAppTests.test_launch_dispatch_and_failure`
- [x] `tests.test_whatsapp.WhatsAppTests.test_missing_window_bounded_poll`
- [x] `tests.test_whatsapp.WhatsAppTests.test_read_and_unread_honestly_describe_limits`
- [x] `tests.test_whatsapp.WhatsAppTests.test_readiness_success_launch_error_and_existing_error`
- [x] `tests.test_whatsapp.WhatsAppTests.test_regression_fresh_start_failure_reports_cause_immediately`
- [x] `tests.test_whatsapp.WhatsAppTests.test_regression_import_preserves_desktop_failsafe`
- [x] `tests.test_whatsapp.WhatsAppTests.test_regression_startup_timeout_matches_ten_second_claim`
- [x] `tests.test_whatsapp.WhatsAppTests.test_regression_unverified_send_does_not_claim_confirmation`
- [x] `tests.test_whatsapp.WhatsAppTests.test_send_sequence_ascii_and_unicode_forwarding_only`
- [x] `tests.test_whatsapp.WhatsAppTests.test_start_creates_daemon_without_running_it`

## Limits

Live authentication/delivery, actual hardware, browser rendering, real Chroma persistence, clean installation, and full concurrency behavior are not established by this run.

Full traces: [latest.txt](results/latest.txt). Structured results: [latest.json](results/latest.json).
