// 由 pnpm api:gen 生成，不要手改
export interface paths {
    "/api/agent-grants": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Grants */
        get: operations["list_grants_api_agent_grants_get"];
        put?: never;
        /** Create Grant */
        post: operations["create_grant_api_agent_grants_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent-grants/{grant_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Revoke Grant */
        delete: operations["revoke_grant_api_agent_grants__grant_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent-grants/audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Audits */
        get: operations["list_audits_api_agent_grants_audit_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent/conversations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Conversations */
        get: operations["list_conversations_api_agent_conversations_get"];
        put?: never;
        /** Create Conversation */
        post: operations["create_conversation_api_agent_conversations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent/conversations/{conversation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Conversation */
        get: operations["get_conversation_api_agent_conversations__conversation_id__get"];
        put?: never;
        post?: never;
        /** Delete Conversation */
        delete: operations["delete_conversation_api_agent_conversations__conversation_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent/conversations/{conversation_id}/messages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Post Message
         * @description 发一条消息并得到助手的回答。stream 为真时返回 text/event-stream：若干 delta，最后 done 或 error。
         *
         *     先确认会话属于本人，然后结束自己的读事务再跑一轮（run_turn 用自己的短会话，调用模型期间不占事务）。
         */
        post: operations["post_message_api_agent_conversations__conversation_id__messages_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent/opening": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Opening
         * @description 今天最该问的一个问题；今天没有该问的、已问完或设置关闭时是 null。pick_opening 在调用模型之前结束读事务。
         */
        get: operations["get_opening_api_agent_opening_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent/opening/{opening_id}/answer": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Answer Opening */
        post: operations["answer_opening_api_agent_opening__opening_id__answer_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent/opening/{opening_id}/decline": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Decline Opening */
        post: operations["decline_opening_api_agent_opening__opening_id__decline_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent/preferences": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Preferences */
        get: operations["list_preferences_api_agent_preferences_get"];
        put?: never;
        /** Add Preference */
        post: operations["add_preference_api_agent_preferences_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent/preferences/{preference_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Preference */
        delete: operations["delete_preference_api_agent_preferences__preference_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Settings */
        get: operations["get_settings_api_agent_settings_get"];
        /** Put Settings */
        put: operations["put_settings_api_agent_settings_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login_api_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_api_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Me */
        get: operations["me_api_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/register": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Register */
        post: operations["register_api_auth_register_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cycle/day-logs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Day Logs */
        get: operations["list_day_logs_api_cycle_day_logs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cycle/day-logs/{log_date}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Put Day Log */
        put: operations["put_day_log_api_cycle_day_logs__log_date__put"];
        post?: never;
        /** Delete Day Log */
        delete: operations["delete_day_log_api_cycle_day_logs__log_date__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cycle/periods": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Periods */
        get: operations["list_periods_api_cycle_periods_get"];
        put?: never;
        /** Create Period */
        post: operations["create_period_api_cycle_periods_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cycle/periods/{period_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Period */
        delete: operations["delete_period_api_cycle_periods__period_id__delete"];
        options?: never;
        head?: never;
        /** Update Period */
        patch: operations["update_period_api_cycle_periods__period_id__patch"];
        trace?: never;
    };
    "/api/cycle/phase": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Phase */
        get: operations["get_phase_api_cycle_phase_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cycle/prediction": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Prediction */
        get: operations["get_prediction_api_cycle_prediction_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cycle/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Settings */
        get: operations["get_settings_api_cycle_settings_get"];
        /** Put Settings */
        put: operations["put_settings_api_cycle_settings_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cycle/stats": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Stats */
        get: operations["get_stats_api_cycle_stats_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cycle/tips": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Tips */
        get: operations["get_tips_api_cycle_tips_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/disclaimer": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Disclaimer */
        get: operations["get_disclaimer_api_disclaimer_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/disclaimer/accept": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Accept */
        post: operations["accept_api_disclaimer_accept_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/disclaimer/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Status */
        get: operations["get_status_api_disclaimer_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/fitness/exercises": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Custom Exercise */
        post: operations["create_custom_exercise_api_fitness_exercises_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/fitness/exercises/{exercise_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Exercise */
        get: operations["get_exercise_api_fitness_exercises__exercise_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/fitness/exercises/{exercise_id}/trend": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Exercise Trend */
        get: operations["exercise_trend_api_fitness_exercises__exercise_id__trend_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/fitness/exercises/custom": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Custom Exercises */
        get: operations["list_custom_exercises_api_fitness_exercises_custom_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/fitness/exercises/custom/{exercise_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Custom Exercise */
        delete: operations["delete_custom_exercise_api_fitness_exercises_custom__exercise_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/fitness/exercises/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search Exercises */
        get: operations["search_exercises_api_fitness_exercises_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/fitness/signal": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Training Signal */
        get: operations["training_signal_api_fitness_signal_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/fitness/summary/week": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Week Summary */
        get: operations["week_summary_api_fitness_summary_week_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/fitness/workouts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Workouts */
        get: operations["list_workouts_api_fitness_workouts_get"];
        put?: never;
        /** Create Workout */
        post: operations["create_workout_api_fitness_workouts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/fitness/workouts/{workout_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Workout */
        get: operations["get_workout_api_fitness_workouts__workout_id__get"];
        /** Replace Workout */
        put: operations["replace_workout_api_fitness_workouts__workout_id__put"];
        post?: never;
        /** Delete Workout */
        delete: operations["delete_workout_api_fitness_workouts__workout_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/llm/assignments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Assignments */
        get: operations["list_assignments_api_llm_assignments_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/llm/assignments/{purpose}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Set Assignment */
        put: operations["set_assignment_api_llm_assignments__purpose__put"];
        post?: never;
        /** Clear Assignment */
        delete: operations["clear_assignment_api_llm_assignments__purpose__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/llm/chat": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Chat */
        post: operations["chat_api_llm_chat_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/llm/models/{model_pk}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Model */
        delete: operations["delete_model_api_llm_models__model_pk__delete"];
        options?: never;
        head?: never;
        /** Update Model */
        patch: operations["update_model_api_llm_models__model_pk__patch"];
        trace?: never;
    };
    "/api/llm/presets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Presets */
        get: operations["list_presets_api_llm_presets_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/llm/providers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Providers */
        get: operations["list_providers_api_llm_providers_get"];
        put?: never;
        /** Create Provider */
        post: operations["create_provider_api_llm_providers_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/llm/providers/{provider_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Provider */
        get: operations["get_provider_api_llm_providers__provider_id__get"];
        put?: never;
        post?: never;
        /** Delete Provider */
        delete: operations["delete_provider_api_llm_providers__provider_id__delete"];
        options?: never;
        head?: never;
        /** Update Provider */
        patch: operations["update_provider_api_llm_providers__provider_id__patch"];
        trace?: never;
    };
    "/api/llm/providers/{provider_id}/fetch-models": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Fetch Models */
        post: operations["fetch_models_api_llm_providers__provider_id__fetch_models_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/llm/providers/{provider_id}/models": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Models */
        get: operations["list_models_api_llm_providers__provider_id__models_get"];
        put?: never;
        /** Add Model */
        post: operations["add_model_api_llm_providers__provider_id__models_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/llm/providers/{provider_id}/test": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Check Saved Provider */
        post: operations["check_saved_provider_api_llm_providers__provider_id__test_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/llm/providers/test": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Check Unsaved Provider */
        post: operations["check_unsaved_provider_api_llm_providers_test_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/me/capabilities": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Capabilities */
        get: operations["get_capabilities_api_me_capabilities_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/constraints": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Constraints */
        get: operations["get_constraints_api_medical_constraints_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List User Events */
        get: operations["list_user_events_api_medical_events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/evidence/{evidence_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download Evidence */
        get: operations["download_evidence_api_medical_evidence__evidence_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Items */
        get: operations["list_items_api_medical_items_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/items/{item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Item */
        get: operations["get_item_api_medical_items__item_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Item */
        patch: operations["update_item_api_medical_items__item_id__patch"];
        trace?: never;
    };
    "/api/medical/items/{item_id}/cancel-proposal": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel Proposal */
        post: operations["cancel_proposal_api_medical_items__item_id__cancel_proposal_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/items/{item_id}/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Confirm Item */
        post: operations["confirm_item_api_medical_items__item_id__confirm_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/items/{item_id}/continue": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Continue Item */
        post: operations["continue_item_api_medical_items__item_id__continue_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/items/{item_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Events */
        get: operations["list_events_api_medical_items__item_id__events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/items/{item_id}/propose-resolution": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Propose Resolution */
        post: operations["propose_resolution_api_medical_items__item_id__propose_resolution_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/items/{item_id}/resolve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resolve Item */
        post: operations["resolve_item_api_medical_items__item_id__resolve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/items/{item_id}/void": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Void Item */
        post: operations["void_item_api_medical_items__item_id__void_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/orders": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Orders */
        get: operations["list_orders_api_medical_orders_get"];
        put?: never;
        /** Create Order */
        post: operations["create_order_api_medical_orders_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/orders/{order_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Order */
        get: operations["get_order_api_medical_orders__order_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/orders/{order_id}/evidence": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Upload Evidence */
        post: operations["upload_evidence_api_medical_orders__order_id__evidence_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/orders/{order_id}/items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Add Manual Item */
        post: operations["add_manual_item_api_medical_orders__order_id__items_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/medical/reviews": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Reviews */
        get: operations["list_reviews_api_medical_reviews_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/nutrition/evaluate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Evaluate */
        post: operations["evaluate_api_nutrition_evaluate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/nutrition/evaluate-meal": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Evaluate Meal Items */
        post: operations["evaluate_meal_items_api_nutrition_evaluate_meal_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/nutrition/foods/{food_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Food */
        get: operations["get_food_api_nutrition_foods__food_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/nutrition/foods/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search Foods */
        get: operations["search_foods_api_nutrition_foods_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/nutrition/meals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Meals */
        get: operations["list_meals_api_nutrition_meals_get"];
        put?: never;
        /** Create Meal */
        post: operations["create_meal_api_nutrition_meals_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/nutrition/meals/{entry_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Meal */
        delete: operations["delete_meal_api_nutrition_meals__entry_id__delete"];
        options?: never;
        head?: never;
        /** Update Meal */
        patch: operations["update_meal_api_nutrition_meals__entry_id__patch"];
        trace?: never;
    };
    "/api/nutrition/needs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Needs */
        get: operations["get_needs_api_nutrition_needs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/nutrition/summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Summary */
        get: operations["get_summary_api_nutrition_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/nutrition/tags": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Tags */
        get: operations["list_tags_api_nutrition_tags_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/recognitions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Recognitions */
        get: operations["list_recognitions_api_photos_recognitions_get"];
        put?: never;
        /**
         * Create Recognition
         * @description 上传一张餐食照片识别为草稿。先结束自己的读事务再识别，调用模型期间不占数据库事务。
         */
        post: operations["create_recognition_api_photos_recognitions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/recognitions/{rec_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Recognition */
        get: operations["get_recognition_api_photos_recognitions__rec_id__get"];
        put?: never;
        post?: never;
        /** Delete Recognition */
        delete: operations["delete_recognition_api_photos_recognitions__rec_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/recognitions/{rec_id}/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Confirm */
        post: operations["confirm_api_photos_recognitions__rec_id__confirm_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/recognitions/{rec_id}/discard": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Discard */
        post: operations["discard_api_photos_recognitions__rec_id__discard_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/recognitions/{rec_id}/image": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Image */
        get: operations["get_image_api_photos_recognitions__rec_id__image_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/recognitions/{rec_id}/items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Update Items */
        put: operations["update_items_api_photos_recognitions__rec_id__items_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/profile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Profile */
        get: operations["get_profile_api_profile_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Patch Profile */
        patch: operations["patch_profile_api_profile_patch"];
        trace?: never;
    };
    "/api/profile/changes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Profile Changes */
        get: operations["get_profile_changes_api_profile_changes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/restaurants/needs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Needs */
        get: operations["list_needs_api_restaurants_needs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/restaurants/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Search */
        post: operations["search_api_restaurants_search_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/restaurants/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Settings */
        get: operations["get_settings_api_restaurants_settings_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/restaurants/settings/area": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Clear Area */
        delete: operations["clear_area_api_restaurants_settings_area_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/restaurants/settings/consent": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Set Consent */
        put: operations["set_consent_api_restaurants_settings_consent_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AcceptRequest */
        AcceptRequest: {
            /** Version */
            version: string;
        };
        /** SettingsOut */
        app__agent__schemas__SettingsOut: {
            /** Openings Enabled */
            openings_enabled: boolean;
        };
        /** ItemOut */
        app__medical__schemas__ItemOut: {
            /**
             * Category
             * @enum {string}
             */
            category: "diet_avoid" | "diet_require" | "medication_diet" | "exercise_limit" | "other";
            /** Closed At */
            closed_at: string | null;
            /** Confidence */
            confidence: ("high" | "medium" | "low") | null;
            /** Confirmed At */
            confirmed_at: string | null;
            /** Content */
            content: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** End Date */
            end_date: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Low Confidence */
            readonly low_confidence: boolean;
            /** Missing Fields */
            missing_fields: string[];
            /** Notes */
            notes: string[];
            /**
             * Order Id
             * Format: uuid
             */
            order_id: string;
            /**
             * Origin
             * @enum {string}
             */
            origin: "extracted" | "manual";
            /** Resolution Proposed At */
            resolution_proposed_at: string | null;
            /** Resolution Reason */
            resolution_reason: string | null;
            /** Review Date */
            review_date: string | null;
            /** Source Excerpt */
            source_excerpt: string | null;
            /**
             * Start Date
             * Format: date
             */
            start_date: string;
            /**
             * Status
             * @enum {string}
             */
            status: "pending_confirmation" | "active" | "pending_review" | "resolved" | "voided";
            /** Subjects */
            subjects: string[];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** EvaluationOut */
        app__nutrition__schemas__EvaluationOut: {
            /**
             * Conclusion
             * @enum {string}
             */
            conclusion: "suitable" | "caution" | "not_recommended";
            /** Data Source */
            data_source: string;
            /** Disclaimer */
            disclaimer: string;
            /** Food Id */
            food_id: string;
            /** Food Name */
            food_name: string;
            /** Grams */
            grams: number;
            nutrients: components["schemas"]["NutrientsOut"];
            /** Reasons */
            reasons: components["schemas"]["ReasonOut"][];
            /** Tradeoff */
            tradeoff: string;
        };
        /** SearchOut */
        app__nutrition__schemas__SearchOut: {
            /** Exact */
            exact: boolean;
            /** Found */
            found: boolean;
            /** Message */
            message: string;
            /** Query */
            query: string;
            /** Results */
            results: components["schemas"]["FoodSummaryOut"][];
        };
        /** EvaluationOut */
        app__photos__schemas__EvaluationOut: {
            /**
             * Conclusion
             * @enum {string}
             */
            conclusion: "suitable" | "caution" | "not_recommended";
            /** Disclaimer */
            disclaimer: string;
            /** Items */
            items: components["schemas"]["ItemEvaluationOut"][];
            /** Unchecked Items */
            unchecked_items: string[];
            /** Unchecked Notice */
            unchecked_notice: string | null;
        };
        /** ItemOut */
        app__photos__schemas__ItemOut: {
            /** Candidates */
            candidates: components["schemas"]["CandidateOut"][];
            /** Confidence */
            confidence: number;
            /** Food Id */
            food_id: string | null;
            /** Food Name */
            food_name: string | null;
            /** Grams */
            grams: number;
            /** Grams Source */
            grams_source: string;
            /** Id */
            id: string;
            /** Match Type */
            match_type: string | null;
            /** Name */
            name: string;
            nutrients: components["schemas"]["NutrientsOut"] | null;
            /** Portion Text */
            portion_text: string;
            /** Review Reasons */
            review_reasons: string[];
            source: components["schemas"]["ItemSourceOut"] | null;
            /**
             * Status
             * @enum {string}
             */
            status: "matched" | "needs_confirmation";
        };
        /** SearchOut */
        app__restaurants__schemas__SearchOut: {
            /** Avoided Types */
            avoided_types: components["schemas"]["AvoidedTypeOut"][];
            center: components["schemas"]["CenterOut"];
            /** Disclaimer */
            disclaimer: string;
            needs: components["schemas"]["NeedsUsedOut"];
            /** Notice */
            notice: string;
            /** Restaurants */
            restaurants: components["schemas"]["RestaurantOut"][];
            /** Type Advice */
            type_advice: components["schemas"]["TypeAdviceOut"][];
        };
        /** SettingsOut */
        app__restaurants__schemas__SettingsOut: {
            area: components["schemas"]["AreaOut"] | null;
            /**
             * Location Consent
             * @enum {string}
             */
            location_consent: "not_asked" | "granted" | "denied";
            /** Should Ask Location */
            should_ask_location: boolean;
        };
        /** AreaOut */
        AreaOut: {
            /** Name */
            name: string;
            /** Saved At */
            saved_at: string | null;
        };
        /** AssignmentOut */
        AssignmentOut: {
            model: components["schemas"]["ModelOut"];
            /** Provider Name */
            provider_name: string;
            /**
             * Purpose
             * @enum {string}
             */
            purpose: "chat" | "vision";
        };
        /** AssignmentSet */
        AssignmentSet: {
            /**
             * Model Id
             * Format: uuid
             */
            model_id: string;
        };
        /** AuditOut */
        AuditOut: {
            /** Capability */
            capability: string;
            /** Client Name */
            client_name: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Credential Kind */
            credential_kind: string;
            /** Duration Ms */
            duration_ms: number;
            /** Error Code */
            error_code: string | null;
            /** Grant Id */
            grant_id: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Outcome */
            outcome: string;
        };
        /** AvoidedTypeOut */
        AvoidedTypeOut: {
            /** Reasons */
            reasons: components["schemas"]["DishReasonOut"][];
            /** Restaurants */
            restaurants: string[];
            /** Type Key */
            type_key: string;
            /** Type Name */
            type_name: string;
        };
        /** Body_create_recognition_api_photos_recognitions_post */
        Body_create_recognition_api_photos_recognitions_post: {
            /** File */
            file: string;
            /**
             * Keep Image
             * @default false
             */
            keep_image: boolean;
        };
        /** Body_upload_evidence_api_medical_orders__order_id__evidence_post */
        Body_upload_evidence_api_medical_orders__order_id__evidence_post: {
            /** File */
            file: string;
        };
        /** CandidateOut */
        CandidateOut: {
            /** Food Id */
            food_id: string;
            /** Name */
            name: string;
        };
        /** CapabilitiesOut */
        CapabilitiesOut: {
            /** Chat */
            chat: boolean | null;
            /** Tools */
            tools: boolean | null;
            /** Vision */
            vision: boolean | null;
        };
        /** CardioItemIn */
        CardioItemIn: {
            /**
             * Distance Km
             * @description 距离，单位千米，0 至 300，可不填
             */
            distance_km?: number | null;
            /**
             * Duration Minutes
             * @description 这项有氧的时长，单位分钟，1 至 600
             */
            duration_minutes: number;
            /**
             * Exercise Id
             * @description 有氧动作的编号，取自搜索动作（search_exercises）结果里的 id，必须是有氧动作
             */
            exercise_id: string;
            /**
             * Rpe
             * @description 这项有氧的主观强度 RPE，1 至 10 的整数（1 非常轻松，10 竭尽全力），可不填
             */
            rpe?: number | null;
        };
        /** CardioOut */
        CardioOut: {
            /** Distance Km */
            distance_km: number | null;
            /** Duration Minutes */
            duration_minutes: number;
            /** Exercise Id */
            exercise_id: string;
            /** Exercise Name */
            exercise_name: string;
            /** Position */
            position: number;
            /** Rpe */
            rpe: number | null;
        };
        /** CenterOut */
        CenterOut: {
            /** Name */
            name: string;
            /**
             * Source
             * @enum {string}
             */
            source: "gps" | "place" | "saved_area";
        };
        /** ChatOut */
        ChatOut: {
            /** Model Id */
            model_id: string;
            /** Provider Name */
            provider_name: string;
            /** Text */
            text: string;
            /** Tool Calls */
            tool_calls: components["schemas"]["ToolCallOut"][];
            usage: components["schemas"]["UsageOut"];
        };
        /** ChatRequest */
        ChatRequest: {
            /**
             * Max Tokens
             * @default 1024
             */
            max_tokens: number;
            /** Messages */
            messages: components["schemas"]["MessageIn"][];
            /**
             * Purpose
             * @enum {string}
             */
            purpose: "chat" | "vision";
        };
        /** ConfirmIn */
        ConfirmIn: {
            /**
             * Eaten On
             * Format: date
             */
            eaten_on: string;
            /**
             * Meal Type
             * @enum {string}
             */
            meal_type: "breakfast" | "lunch" | "dinner" | "snack";
        };
        /** ConflictOut */
        ConflictOut: {
            /** Content */
            content: string;
            /**
             * Item Id
             * Format: uuid
             */
            item_id: string;
            /**
             * Level
             * @enum {string}
             */
            level: "conflict" | "unverifiable";
            /** Message */
            message: string;
            /** Subject */
            subject: string;
            /** Workout Ids */
            workout_ids: string[];
        };
        /** ConnectionReportOut */
        ConnectionReportOut: {
            chat: components["schemas"]["StepReportOut"] | null;
            /**
             * Conclusion
             * @enum {string}
             */
            conclusion: "ok" | "ok_listing_unsupported" | "invalid_key" | "bad_url" | "model_unavailable" | "quota_exceeded" | "rate_limited" | "timeout" | "provider_error" | "bad_request";
            listing: components["schemas"]["StepReportOut"];
            /** Message */
            message: string;
            /** Models Found */
            models_found: number | null;
            /** Ok */
            ok: boolean;
            /** Sample Models */
            sample_models: string[];
        };
        /** ConsentIn */
        ConsentIn: {
            /**
             * Consent
             * @enum {string}
             */
            consent: "granted" | "denied";
        };
        /** ConstraintOut */
        ConstraintOut: {
            /**
             * Category
             * @enum {string}
             */
            category: "diet_avoid" | "diet_require" | "medication_diet" | "exercise_limit" | "other";
            /** Content */
            content: string;
            /** End Date */
            end_date: string | null;
            /**
             * Item Id
             * Format: uuid
             */
            item_id: string;
            /** Needs Review */
            needs_review: boolean;
            /** Resolution Proposed */
            resolution_proposed: boolean;
            /** Review Date */
            review_date: string | null;
            /**
             * Start Date
             * Format: date
             */
            start_date: string;
            /**
             * Status
             * @enum {string}
             */
            status: "pending_confirmation" | "active" | "pending_review" | "resolved" | "voided";
            /** Subjects */
            subjects: string[];
        };
        /** ConstraintsOut */
        ConstraintsOut: {
            /** Constraints */
            constraints: components["schemas"]["ConstraintOut"][];
            /** Reminder */
            reminder: string;
        };
        /** ContinueBody */
        ContinueBody: {
            /**
             * End Date
             * @description 新的预计结束日期，格式 YYYY-MM-DD，不能早于生效日期，且至少在今天之后两天（否则仍算到期）；不填表示不设结束日期
             */
            end_date?: string | null;
            /**
             * Review Date
             * @description 新的复查日期，格式 YYYY-MM-DD，不能早于生效日期，且必须晚于今天；不填表示不设复查日期
             */
            review_date?: string | null;
        };
        /** ConversationCreate */
        ConversationCreate: {
            /** Title */
            title?: string | null;
        };
        /** ConversationDetailOut */
        ConversationDetailOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Messages */
            messages: components["schemas"]["MessageOut"][];
            /** Title */
            title: string | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** ConversationOut */
        ConversationOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Title */
            title: string | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** Coordinate */
        Coordinate: {
            /**
             * Coord Type
             * @default gps
             * @enum {string}
             */
            coord_type: "gps" | "gcj02";
            /** Lat */
            lat: number;
            /** Lng */
            lng: number;
        };
        /** CustomExerciseIn */
        CustomExerciseIn: {
            /** Aliases */
            aliases?: string[];
            /**
             * Equipment
             * @enum {string}
             */
            equipment: "barbell" | "dumbbell" | "machine" | "cable" | "bodyweight" | "kettlebell" | "band" | "none" | "other";
            /**
             * Kind
             * @enum {string}
             */
            kind: "strength" | "cardio";
            /** Met Light */
            met_light?: number | null;
            /** Met Moderate */
            met_moderate?: number | null;
            /** Met Vigorous */
            met_vigorous?: number | null;
            /** Name */
            name: string;
            /** Primary Muscles */
            primary_muscles: ("chest" | "back" | "shoulders" | "biceps" | "triceps" | "quads" | "hamstrings" | "glutes" | "calves" | "core" | "full_body")[];
            /**
             * Traits
             * @default []
             */
            traits: ("high_impact" | "running" | "swimming" | "bending" | "jumping" | "cycling")[];
        };
        /** CycleSettingsOut */
        CycleSettingsOut: {
            /**
             * Status
             * @enum {string}
             */
            status: "tracking" | "pregnant" | "paused";
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** CycleSettingsUpdate */
        CycleSettingsUpdate: {
            /**
             * Status
             * @enum {string}
             */
            status: "tracking" | "pregnant" | "paused";
        };
        /** CycleStatsOut */
        CycleStatsOut: {
            /** Average Pain On Bleeding Days */
            average_pain_on_bleeding_days: number | null;
            /** Avg Cycle Length */
            avg_cycle_length: number | null;
            /** Avg Period Length */
            avg_period_length: number | null;
            /** Cycle Count */
            cycle_count: number;
            /** Cycle Length Std */
            cycle_length_std: number | null;
            /** Logged Days */
            logged_days: number;
            /** Longest Cycle */
            longest_cycle: number | null;
            /** Period Count */
            period_count: number;
            /** Recent Cycle Lengths */
            recent_cycle_lengths: number[];
            /** Shortest Cycle */
            shortest_cycle: number | null;
            /** Top Symptoms */
            top_symptoms: components["schemas"]["SymptomCountOut"][];
        };
        /** DateRangeOut */
        DateRangeOut: {
            /**
             * Earliest
             * Format: date
             */
            earliest: string;
            /**
             * Latest
             * Format: date
             */
            latest: string;
        };
        /** DayLogIn */
        DayLogIn: {
            /** Flow */
            flow?: ("none" | "spotting" | "light" | "medium" | "heavy") | null;
            /** Mood */
            mood?: ("good" | "normal" | "low" | "irritable" | "anxious") | null;
            /** Note */
            note?: string | null;
            /** Pain */
            pain?: number | null;
            /** Symptoms */
            symptoms?: string[];
        };
        /** DayLogOut */
        DayLogOut: {
            /** Flow */
            flow: ("none" | "spotting" | "light" | "medium" | "heavy") | null;
            /**
             * Log Date
             * Format: date
             */
            log_date: string;
            /** Mood */
            mood: ("good" | "normal" | "low" | "irritable" | "anxious") | null;
            /** Note */
            note: string | null;
            /** Pain */
            pain: number | null;
            /** Symptoms */
            symptoms: string[];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** DisclaimerOut */
        DisclaimerOut: {
            /** Text */
            text: string;
            /** Version */
            version: string;
        };
        /** DisclaimerStatus */
        DisclaimerStatus: {
            /** Accepted */
            accepted: boolean;
            /** Accepted At */
            accepted_at: string | null;
            /** Current Version */
            current_version: string;
        };
        /**
         * DishReasonOut
         * @description 引擎给出的原因，连同给出这条原因的代表菜。
         */
        DishReasonOut: {
            /** Code */
            code: string;
            /**
             * Effect
             * @enum {string}
             */
            effect: "block" | "unverifiable" | "caution" | "prefer" | "info";
            /** Food Name */
            food_name: string;
            /** Message */
            message: string;
            /** Ref */
            ref: string;
            /**
             * Source
             * @enum {string}
             */
            source: "medical" | "cycle" | "goal" | "training" | "intake" | "preference";
        };
        /** EvaluateIn */
        EvaluateIn: {
            /**
             * Food Id
             * @description 食物编号，取自搜索食物（search_foods）结果里的 id，不要自己编造
             */
            food_id: string;
            /**
             * Grams
             * @description 要评估的克数，大于 0 且不超过 5000；与 portion 最多填一项，都不填时按这种食物的默认份量
             */
            grams?: number | null;
            /** @description 按常用份量评估（单位加份数）；与 grams 最多填一项，都不填时按这种食物的默认份量 */
            portion?: components["schemas"]["PortionIn"] | null;
        };
        /** EvaluateMealIn */
        EvaluateMealIn: {
            /**
             * Items
             * @description 这一餐里的食物，1 至 20 项，每项一种食物及其分量
             */
            items: components["schemas"]["MealItemIn"][];
        };
        /** EventOut */
        EventOut: {
            /** Action */
            action: string;
            /** Detail */
            detail: {
                [key: string]: unknown;
            } | null;
            /** From Status */
            from_status: ("pending_confirmation" | "active" | "pending_review" | "resolved" | "voided") | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /** Seq */
            seq: number;
            /**
             * Source
             * @enum {string}
             */
            source: "user" | "system" | "extractor" | "agent";
            /**
             * To Status
             * @enum {string}
             */
            to_status: "pending_confirmation" | "active" | "pending_review" | "resolved" | "voided";
        };
        /** EvidenceOut */
        EvidenceOut: {
            /** Content Type */
            content_type: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Filename */
            filename: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Size Bytes */
            size_bytes: number;
        };
        /** ExerciseDetailOut */
        ExerciseDetailOut: {
            /** Aliases */
            aliases: string[];
            /** Custom */
            custom: boolean;
            /**
             * Equipment
             * @enum {string}
             */
            equipment: "barbell" | "dumbbell" | "machine" | "cable" | "bodyweight" | "kettlebell" | "band" | "none" | "other";
            /** Id */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "strength" | "cardio";
            met: components["schemas"]["MetOut"];
            /** Met Source Note */
            met_source_note: string;
            /** Name */
            name: string;
            /** Primary Muscles */
            primary_muscles: ("chest" | "back" | "shoulders" | "biceps" | "triceps" | "quads" | "hamstrings" | "glutes" | "calves" | "core" | "full_body")[];
            /** Traits */
            traits: ("high_impact" | "running" | "swimming" | "bending" | "jumping" | "cycling")[];
        };
        /** ExerciseSearchOut */
        ExerciseSearchOut: {
            /** Exact */
            exact: boolean;
            /** Found */
            found: boolean;
            /** Message */
            message: string;
            /** Query */
            query: string;
            /** Results */
            results: components["schemas"]["ExerciseSummaryOut"][];
        };
        /** ExerciseSummaryOut */
        ExerciseSummaryOut: {
            /** Custom */
            custom: boolean;
            /**
             * Equipment
             * @enum {string}
             */
            equipment: "barbell" | "dumbbell" | "machine" | "cable" | "bodyweight" | "kettlebell" | "band" | "none" | "other";
            /** Id */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "strength" | "cardio";
            /**
             * Match
             * @enum {string}
             */
            match: "exact_name" | "exact_alias" | "prefix" | "contains" | "query_contains";
            /** Name */
            name: string;
            /** Primary Muscles */
            primary_muscles: ("chest" | "back" | "shoulders" | "biceps" | "triceps" | "quads" | "hamstrings" | "glutes" | "calves" | "core" | "full_body")[];
        };
        /** ExerciseTrendOut */
        ExerciseTrendOut: {
            /** Exercise Id */
            exercise_id: string;
            /** Exercise Name */
            exercise_name: string;
            /** Points */
            points: components["schemas"]["TrendPointOut"][];
        };
        /** FetchModelsOut */
        FetchModelsOut: {
            /** Added */
            added: number;
            /** Models */
            models: components["schemas"]["ModelOut"][];
            /** Skipped */
            skipped: number;
            /** Total */
            total: number;
        };
        /** FoodDetailOut */
        FoodDetailOut: {
            /** Aliases */
            aliases: string[];
            /** Category */
            category: string;
            /** Default Grams */
            default_grams: number;
            /** Id */
            id: string;
            /** Kind */
            kind: string;
            /** Name */
            name: string;
            nutrients_per_100g: components["schemas"]["NutrientsOut"];
            /** Portions */
            portions: components["schemas"]["PortionOut"][];
            source: components["schemas"]["SourceOut"];
            /** Tags */
            tags: components["schemas"]["TagOut"][];
        };
        /** FoodSummaryOut */
        FoodSummaryOut: {
            /** Aliases */
            aliases: string[];
            /** Category */
            category: string;
            /** Id */
            id: string;
            /** Kind */
            kind: string;
            /**
             * Match
             * @enum {string}
             */
            match: "exact_name" | "common_name" | "exact_alias" | "prefix" | "contains" | "query_contains";
            /** Name */
            name: string;
        };
        /** GrantCreate */
        GrantCreate: {
            /**
             * Access
             * @enum {string}
             */
            access: "read" | "read_write";
            /**
             * Expires In Days
             * @default 90
             */
            expires_in_days: number;
            /** Name */
            name: string;
        };
        /** GrantCreatedOut */
        GrantCreatedOut: {
            /**
             * Access
             * @enum {string}
             */
            access: "read" | "read_write";
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Token */
            token: string;
            /**
             * Token Notice
             * @default 令牌只显示这一次，请立即保存；遗失后只能吊销并重新创建。
             */
            token_notice: string;
        };
        /** GrantOut */
        GrantOut: {
            /**
             * Access
             * @enum {string}
             */
            access: "read" | "read_write";
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Last Used At */
            last_used_at: string | null;
            /** Name */
            name: string;
            /** Revoked At */
            revoked_at: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "active" | "expired" | "revoked";
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** IgnoredOut */
        IgnoredOut: {
            /** Reason */
            reason: string;
            /** Text */
            text: string;
        };
        /** ImageIn */
        ImageIn: {
            /** Data Base64 */
            data_base64: string;
            /**
             * Mime Type
             * @enum {string}
             */
            mime_type: "image/png" | "image/jpeg" | "image/webp" | "image/gif";
        };
        /** ItemEvaluationOut */
        ItemEvaluationOut: {
            /**
             * Conclusion
             * @enum {string}
             */
            conclusion: "suitable" | "caution" | "not_recommended";
            /** Food Name */
            food_name: string;
            /** Item Id */
            item_id: string;
            /** Reasons */
            reasons: components["schemas"]["ReasonOut"][];
            /** Tradeoff */
            tradeoff: string;
        };
        /**
         * ItemIn
         * @description 修正后的一个识别项。带 id 表示修改原有的项，不带表示新增。
         */
        ItemIn: {
            /** Food Id */
            food_id?: string | null;
            /** Grams */
            grams?: number | null;
            /** Id */
            id?: string | null;
            /** Name */
            name: string;
            /** Portion Text */
            portion_text?: string | null;
        };
        /** ItemSourceOut */
        ItemSourceOut: {
            /** Dataset */
            dataset: string;
            /** License Status */
            license_status: string;
            /** Note */
            note: string;
        };
        /** ItemsUpdate */
        ItemsUpdate: {
            /** Items */
            items: components["schemas"]["ItemIn"][];
        };
        /** ItemUpdate */
        ItemUpdate: {
            /**
             * Category
             * @description 条目类别；不填表示不修改，不能填 null。类别取值：diet_avoid 饮食禁忌，diet_require 饮食要求，medication_diet 用药期间的饮食禁忌，exercise_limit 运动限制，other 其他
             */
            category?: ("diet_avoid" | "diet_require" | "medication_diet" | "exercise_limit" | "other") | null;
            /**
             * Content
             * @description 条目内容，1 至 500 个字；不填表示不修改，不能填 null
             */
            content?: string | null;
            /**
             * End Date
             * @description 预计结束日期，格式 YYYY-MM-DD，不能早于生效日期；填 null 表示长期；不填表示不修改
             */
            end_date?: string | null;
            /**
             * Review Date
             * @description 复查日期，格式 YYYY-MM-DD，不能早于生效日期；填 null 表示没有复查日；不填表示不修改
             */
            review_date?: string | null;
            /**
             * Start Date
             * @description 生效日期，格式 YYYY-MM-DD；不填表示不修改，不能填 null；生效中的条目不能改到今天之后
             */
            start_date?: string | null;
            /**
             * Subjects
             * @description 涉及的食物或行为，例如 辛辣、酒；每项 1 至 64 个字，最多 30 项；不填表示不修改，不能填 null；确认时至少要有一项
             */
            subjects?: string[] | null;
        };
        /** LoginRequest */
        LoginRequest: {
            /** Password */
            password: string;
            /** Username */
            username: string;
        };
        /** ManualItemCreate */
        ManualItemCreate: {
            /**
             * Category
             * @enum {string}
             */
            category: "diet_avoid" | "diet_require" | "medication_diet" | "exercise_limit" | "other";
            /** Content */
            content: string;
            /** End Date */
            end_date?: string | null;
            /** Review Date */
            review_date?: string | null;
            /** Start Date */
            start_date?: string | null;
            /** Subjects */
            subjects?: string[];
        };
        /** MealCreate */
        MealCreate: {
            /**
             * Eaten On
             * Format: date
             * @description 吃这项食物的日期，格式 YYYY-MM-DD，不能晚于今天
             */
            eaten_on: string;
            /**
             * Food Id
             * @description 食物编号，取自搜索食物（search_foods）结果里的 id，不要自己编造
             */
            food_id: string;
            /**
             * Grams
             * @description 吃了多少克，大于 0 且不超过 5000；与 portion 必须且只能填一项
             */
            grams?: number | null;
            /**
             * Meal Type
             * @description 餐次：breakfast 早餐，lunch 午餐，dinner 晚餐，snack 加餐
             * @enum {string}
             */
            meal_type: "breakfast" | "lunch" | "dinner" | "snack";
            /**
             * Note
             * @description 备注，最多 200 个字，可不填
             */
            note?: string | null;
            /** @description 按常用份量记录（单位加份数）；与 grams 必须且只能填一项 */
            portion?: components["schemas"]["PortionIn"] | null;
        };
        /** MealEvaluationOut */
        MealEvaluationOut: {
            /**
             * Conclusion
             * @enum {string}
             */
            conclusion: "suitable" | "caution" | "not_recommended";
            /** Disclaimer */
            disclaimer: string;
            /** Items */
            items: components["schemas"]["app__nutrition__schemas__EvaluationOut"][];
            total: components["schemas"]["NutrientsOut"];
        };
        /** MealItemIn */
        MealItemIn: {
            /**
             * Food Id
             * @description 食物编号，取自搜索食物（search_foods）结果里的 id，不要自己编造
             */
            food_id: string;
            /**
             * Grams
             * @description 要评估的克数，大于 0 且不超过 5000；与 portion 最多填一项，都不填时按这种食物的默认份量
             */
            grams?: number | null;
            /** @description 按常用份量评估（单位加份数）；与 grams 最多填一项，都不填时按这种食物的默认份量 */
            portion?: components["schemas"]["PortionIn"] | null;
        };
        /** MealOut */
        MealOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Eaten On
             * Format: date
             */
            eaten_on: string;
            /** Food Id */
            food_id: string;
            /** Food Name */
            food_name: string;
            /** Grams */
            grams: number;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Meal Type
             * @enum {string}
             */
            meal_type: "breakfast" | "lunch" | "dinner" | "snack";
            /** Note */
            note: string | null;
            nutrients: components["schemas"]["NutrientsOut"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** MealUpdate */
        MealUpdate: {
            /** Eaten On */
            eaten_on?: string | null;
            /** Food Id */
            food_id?: string | null;
            /** Grams */
            grams?: number | null;
            /** Meal Type */
            meal_type?: ("breakfast" | "lunch" | "dinner" | "snack") | null;
            /** Note */
            note?: string | null;
            portion?: components["schemas"]["PortionIn"] | null;
        };
        /**
         * MedicalEventOut
         * @description 全部条目的事件列表里的一条：带上条目的类别与完整内容，前端不必逐条再查。
         */
        MedicalEventOut: {
            /** Action */
            action: string;
            /** Detail */
            detail: {
                [key: string]: unknown;
            } | null;
            /** From Status */
            from_status: ("pending_confirmation" | "active" | "pending_review" | "resolved" | "voided") | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Item Category
             * @enum {string}
             */
            item_category: "diet_avoid" | "diet_require" | "medication_diet" | "exercise_limit" | "other";
            /** Item Content */
            item_content: string;
            /**
             * Item Id
             * Format: uuid
             */
            item_id: string;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /** Seq */
            seq: number;
            /**
             * Source
             * @enum {string}
             */
            source: "user" | "system" | "extractor" | "agent";
            /**
             * To Status
             * @enum {string}
             */
            to_status: "pending_confirmation" | "active" | "pending_review" | "resolved" | "voided";
        };
        /** MessageCreate */
        MessageCreate: {
            /**
             * Stream
             * @default true
             */
            stream: boolean;
            /** Text */
            text: string;
        };
        /** MessageIn */
        MessageIn: {
            /**
             * Images
             * @default []
             */
            images: components["schemas"]["ImageIn"][];
            /**
             * Role
             * @enum {string}
             */
            role: "system" | "user" | "assistant";
            /** Text */
            text: string;
        };
        /**
         * MessageOut
         * @description 给前端看的消息：只有用户与助手的可见内容，没有工具调用、工具结果与 provider_state。
         */
        MessageOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Evidence */
            evidence: string;
            /** Flags */
            flags: string[];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Role
             * @enum {string}
             */
            role: "user" | "assistant";
            /** Text */
            text: string;
        };
        /** MetOut */
        MetOut: {
            /** Light */
            light: number;
            /** Moderate */
            moderate: number;
            /** Vigorous */
            vigorous: number;
        };
        /** ModelCreate */
        ModelCreate: {
            /** Display Name */
            display_name?: string | null;
            /** Model Id */
            model_id: string;
        };
        /** ModelOut */
        ModelOut: {
            capabilities: components["schemas"]["CapabilitiesOut"];
            /** Capability Note */
            capability_note: string | null;
            /** Display Name */
            display_name: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Model Id */
            model_id: string;
            overrides: components["schemas"]["CapabilitiesOut"];
            /**
             * Provider Id
             * Format: uuid
             */
            provider_id: string;
            /**
             * Source
             * @enum {string}
             */
            source: "fetched" | "manual";
            table_capabilities: components["schemas"]["CapabilitiesOut"];
        };
        /** ModelUpdatedOut */
        ModelUpdatedOut: {
            /** Assignment Warnings */
            assignment_warnings: string[];
            capabilities: components["schemas"]["CapabilitiesOut"];
            /** Capability Note */
            capability_note: string | null;
            /** Display Name */
            display_name: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Model Id */
            model_id: string;
            overrides: components["schemas"]["CapabilitiesOut"];
            /**
             * Provider Id
             * Format: uuid
             */
            provider_id: string;
            /**
             * Source
             * @enum {string}
             */
            source: "fetched" | "manual";
            table_capabilities: components["schemas"]["CapabilitiesOut"];
        };
        /** NeedOut */
        NeedOut: {
            /** Description */
            description: string;
            /** Key */
            key: string;
            /** Name */
            name: string;
        };
        /** NeedsOut */
        NeedsOut: {
            /** Carbohydrate G High */
            carbohydrate_g_high: number | null;
            /** Carbohydrate G Low */
            carbohydrate_g_low: number | null;
            /** Energy Kcal */
            energy_kcal: number | null;
            /** Energy Kcal High */
            energy_kcal_high: number | null;
            /** Energy Kcal Low */
            energy_kcal_low: number | null;
            /** Fat G High */
            fat_g_high: number | null;
            /** Fat G Low */
            fat_g_low: number | null;
            /** Fiber G High */
            fiber_g_high: number | null;
            /** Fiber G Low */
            fiber_g_low: number | null;
            /** Missing Fields */
            missing_fields: string[];
            /** Notes */
            notes: string[];
            /** Protein G */
            protein_g: number | null;
            /** Sodium Mg Max */
            sodium_mg_max: number | null;
            /**
             * Status
             * @enum {string}
             */
            status: "ok" | "insufficient_profile";
        };
        /** NeedsUsedOut */
        NeedsUsedOut: {
            /** Keys */
            keys: string[];
            /** Names */
            names: string[];
            /**
             * Source
             * @enum {string}
             */
            source: "rules" | "model" | "none";
        };
        /** NutrientsOut */
        NutrientsOut: {
            /** Calcium Mg */
            calcium_mg?: number | null;
            /** Carbohydrate G */
            carbohydrate_g?: number | null;
            /** Energy Kcal */
            energy_kcal?: number | null;
            /** Fat G */
            fat_g?: number | null;
            /** Fiber G */
            fiber_g?: number | null;
            /** Iron Mg */
            iron_mg?: number | null;
            /** Protein G */
            protein_g?: number | null;
            /** Sodium Mg */
            sodium_mg?: number | null;
        };
        /** OpeningOut */
        OpeningOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Kind */
            kind: string;
            /** Question */
            question: string;
        };
        /** OpeningResponse */
        OpeningResponse: {
            opening: components["schemas"]["OpeningOut"] | null;
        };
        /** OrderCreate */
        OrderCreate: {
            /**
             * Order Date
             * @description 医嘱开具日期，格式 YYYY-MM-DD，不能晚于今天；不填表示今天
             */
            order_date?: string | null;
            /**
             * Text
             * @description 医嘱、病历或复诊单的原文，1 至 5000 个字；照用户给出的原文提交，不要改写或补充
             */
            text: string;
        };
        /** OrderOut */
        OrderOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Evidence */
            evidence: components["schemas"]["EvidenceOut"][];
            /** Extractor */
            extractor: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Ignored */
            ignored: components["schemas"]["IgnoredOut"][];
            /** Items */
            items: components["schemas"]["app__medical__schemas__ItemOut"][];
            /** Notes */
            notes: string[];
            /**
             * Order Date
             * Format: date
             */
            order_date: string;
            /** Source Text */
            source_text: string;
        };
        /**
         * OverridesUpdate
         * @description 出现的项才会修改；值为 true、false 或 null（null 表示回到对照表）。
         */
        OverridesUpdate: {
            /** Chat */
            chat?: boolean | null;
            /** Tools */
            tools?: boolean | null;
            /** Vision */
            vision?: boolean | null;
        };
        /** PeriodCreate */
        PeriodCreate: {
            /**
             * End Date
             * @description 这次经期的结束日期，格式 YYYY-MM-DD，不能早于开始日期、不能晚于今天，单次经期最多 15 天；仍在经期中可不填
             */
            end_date?: string | null;
            /**
             * Start Date
             * Format: date
             * @description 这次经期的开始日期，格式 YYYY-MM-DD，不能晚于今天
             */
            start_date: string;
        };
        /** PeriodOut */
        PeriodOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** End Date */
            end_date: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Start Date
             * Format: date
             */
            start_date: string;
        };
        /** PeriodUpdate */
        PeriodUpdate: {
            /** End Date */
            end_date?: string | null;
            /** Start Date */
            start_date?: string | null;
        };
        /** PhaseOut */
        PhaseOut: {
            /** Cycle Day */
            cycle_day: number | null;
            /**
             * Day
             * Format: date
             */
            day: string;
            /** Days Until Next Period */
            days_until_next_period: number | null;
            /** Disclaimer */
            disclaimer: string;
            /** Flags */
            flags: ("few_cycles" | "irregular" | "cycle_out_of_range" | "overdue" | "long_gap")[];
            /** Is Predicted */
            is_predicted: boolean;
            /**
             * Phase
             * @enum {string}
             */
            phase: "menstrual" | "follicular" | "ovulation" | "luteal" | "unknown";
            /** Reason */
            reason: ("no_data" | "before_first_record" | "insufficient_data" | "overdue" | "long_gap" | "too_far_ahead" | "pregnant" | "paused") | null;
        };
        /** PortionIn */
        PortionIn: {
            /**
             * Count
             * @description 份数，大于 0 且不超过 20，可以是小数
             */
            count: number;
            /**
             * Unit
             * @description 份量单位，例如 碗、个；必须是这种食物常用份量里的单位（见 get_food 结果的 portions）
             */
            unit: string;
        };
        /** PortionOut */
        PortionOut: {
            /** Grams */
            grams: number;
            /** Unit */
            unit: string;
        };
        /** PredictionOut */
        PredictionOut: {
            /** Disclaimer */
            disclaimer: string;
            fertile_window: components["schemas"]["DateRangeOut"] | null;
            /** Flags */
            flags: ("few_cycles" | "irregular" | "cycle_out_of_range" | "overdue" | "long_gap")[];
            next_period_range: components["schemas"]["DateRangeOut"] | null;
            /** Next Period Start */
            next_period_start: string | null;
            /** Notes */
            notes: string[];
            /** Ovulation Day */
            ovulation_day: string | null;
            ovulation_range: components["schemas"]["DateRangeOut"] | null;
            /**
             * Status
             * @enum {string}
             */
            status: "ok" | "insufficient_data" | "paused";
        };
        /** PreferenceCreate */
        PreferenceCreate: {
            /** Content */
            content: string;
        };
        /** PreferenceOut */
        PreferenceOut: {
            /** Content */
            content: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Source
             * @enum {string}
             */
            source: "agent" | "user";
        };
        /** PresetOut */
        PresetOut: {
            /** Base Url */
            base_url: string;
            /** Id */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "openai_compatible" | "anthropic" | "gemini";
            /** Name */
            name: string;
        };
        /** ProfileChangeOut */
        ProfileChangeOut: {
            /**
             * Changed At
             * Format: date-time
             */
            changed_at: string;
            /** Changes */
            changes: {
                [key: string]: unknown;
            };
            /**
             * Id
             * Format: uuid
             */
            id: string;
        };
        /** ProfileOut */
        ProfileOut: {
            /** Activity Level */
            activity_level: ("sedentary" | "light" | "moderate" | "active" | "very_active") | null;
            /** Birth Year */
            birth_year: number | null;
            /** Cycle Tracking Opt Out */
            cycle_tracking_opt_out: boolean;
            /** Diet Preferences */
            diet_preferences: string[];
            /** Food Avoidances */
            food_avoidances: string[];
            /** Gender */
            gender: ("female" | "male" | "other") | null;
            /** Goal */
            goal: ("lose_fat" | "gain_muscle" | "maintain" | "none") | null;
            /** Health Conditions */
            health_conditions: string | null;
            /** Height Cm */
            height_cm: number | null;
            /** Notes */
            notes: string | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Weight Kg */
            weight_kg: number | null;
        };
        /** ProfileUpdate */
        ProfileUpdate: {
            /** Activity Level */
            activity_level?: ("sedentary" | "light" | "moderate" | "active" | "very_active") | null;
            /** Birth Year */
            birth_year?: number | null;
            /** Cycle Tracking Opt Out */
            cycle_tracking_opt_out?: boolean | null;
            /** Diet Preferences */
            diet_preferences?: string[] | null;
            /** Food Avoidances */
            food_avoidances?: string[] | null;
            /** Gender */
            gender?: ("female" | "male" | "other") | null;
            /** Goal */
            goal?: ("lose_fat" | "gain_muscle" | "maintain" | "none") | null;
            /** Health Conditions */
            health_conditions?: string | null;
            /** Height Cm */
            height_cm?: number | null;
            /** Notes */
            notes?: string | null;
            /** Weight Kg */
            weight_kg?: number | null;
        };
        /** ProposalBody */
        ProposalBody: {
            /**
             * Reason
             * @description 提出解除建议的理由，例如医生复查后允许恢复，1 至 500 个字
             */
            reason: string;
        };
        /** ProviderCreate */
        ProviderCreate: {
            /** Api Key */
            api_key: string;
            /** Base Url */
            base_url: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "openai_compatible" | "anthropic" | "gemini";
            /** Name */
            name: string;
        };
        /** ProviderOut */
        ProviderOut: {
            /** Base Url */
            base_url: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Key Hint */
            key_hint: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "openai_compatible" | "anthropic" | "gemini";
            /** Name */
            name: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * ProviderTest
         * @description 测试还没保存的服务；model_id 是模型编号字符串，给了才做对话测试。
         */
        ProviderTest: {
            /** Api Key */
            api_key: string;
            /** Base Url */
            base_url: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "openai_compatible" | "anthropic" | "gemini";
            /** Model Id */
            model_id?: string | null;
        };
        /**
         * ProviderUpdate
         * @description 服务类型不可改（extra=forbid 会拒绝 kind）；字段缺省或为 null 都表示保持原值。
         */
        ProviderUpdate: {
            /** Api Key */
            api_key?: string | null;
            /** Base Url */
            base_url?: string | null;
            /** Name */
            name?: string | null;
        };
        /** ReasonBody */
        ReasonBody: {
            /**
             * Reason
             * @description 理由，可不填；填写时 1 至 500 个字
             */
            reason?: string | null;
        };
        /** ReasonOut */
        ReasonOut: {
            /** Code */
            code: string;
            /**
             * Effect
             * @enum {string}
             */
            effect: "block" | "unverifiable" | "caution" | "prefer" | "info";
            /** Message */
            message: string;
            /** Ref */
            ref: string;
            /**
             * Source
             * @enum {string}
             */
            source: "medical" | "cycle" | "goal" | "training" | "intake" | "preference";
        };
        /** RecognitionOut */
        RecognitionOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Disclaimer */
            disclaimer: string;
            /** Eaten On */
            eaten_on: string | null;
            evaluation: components["schemas"]["app__photos__schemas__EvaluationOut"] | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Image Kept */
            image_kept: boolean;
            /** Items */
            items: components["schemas"]["app__photos__schemas__ItemOut"][];
            /** Meal Entry Ids */
            meal_entry_ids: string[] | null;
            /** Meal Type */
            meal_type: ("breakfast" | "lunch" | "dinner" | "snack") | null;
            /** Model Id */
            model_id: string;
            /** Needs Review */
            needs_review: boolean;
            /**
             * Status
             * @enum {string}
             */
            status: "draft" | "confirmed" | "discarded";
            totals: components["schemas"]["NutrientsOut"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** RecognitionSummaryOut */
        RecognitionSummaryOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Disclaimer */
            disclaimer: string;
            /** Eaten On */
            eaten_on: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Image Kept */
            image_kept: boolean;
            /** Items */
            items: components["schemas"]["app__photos__schemas__ItemOut"][];
            /** Meal Entry Ids */
            meal_entry_ids: string[] | null;
            /** Meal Type */
            meal_type: ("breakfast" | "lunch" | "dinner" | "snack") | null;
            /** Model Id */
            model_id: string;
            /** Needs Review */
            needs_review: boolean;
            /**
             * Status
             * @enum {string}
             */
            status: "draft" | "confirmed" | "discarded";
            totals: components["schemas"]["NutrientsOut"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** RegisterRequest */
        RegisterRequest: {
            /** Password */
            password: string;
            /** Username */
            username: string;
        };
        /** RestaurantOut */
        RestaurantOut: {
            /** Address */
            address: string;
            /**
             * Conclusion
             * @enum {string}
             */
            conclusion: "suitable" | "caution" | "unchecked";
            /** Distance M */
            distance_m: number | null;
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Nav Url */
            nav_url: string;
            /** Rating */
            rating: number | null;
            /** Tip */
            tip: string | null;
            /** Type Key */
            type_key: string | null;
            /** Type Name */
            type_name: string | null;
        };
        /** SavedProviderTest */
        SavedProviderTest: {
            /** Model Id */
            model_id?: string | null;
        };
        /**
         * SearchIn
         * @description 地点三选一：坐标（要求已授权定位）、手动地点（可加城市）、已保存的大致区域。一种都没给时由服务报错。
         */
        SearchIn: {
            /** City */
            city?: string | null;
            location?: components["schemas"]["Coordinate"] | null;
            /** Need */
            need?: string | null;
            /**
             * Needs
             * @default []
             */
            needs: string[];
            /** Place */
            place?: string | null;
            /**
             * Radius
             * @default 2000
             */
            radius: number;
            /**
             * Remember Area
             * @default false
             */
            remember_area: boolean;
            /**
             * Use Saved Area
             * @default false
             */
            use_saved_area: boolean;
        };
        /** SetIn */
        SetIn: {
            /**
             * Reps
             * @description 这一组的次数，1 至 100
             */
            reps: number;
            /**
             * Rest Seconds
             * @description 这一组之后的休息时间，单位秒，0 至 900，可不填
             */
            rest_seconds?: number | null;
            /**
             * Rpe
             * @description 这一组的主观强度 RPE，1 至 10 的整数（1 非常轻松，10 竭尽全力），可不填
             */
            rpe?: number | null;
            /**
             * Weight Kg
             * @description 这一组的重量，单位千克，0 至 500；徒手动作填 0
             */
            weight_kg: number;
        };
        /** SetOut */
        SetOut: {
            /** Reps */
            reps: number;
            /** Rest Seconds */
            rest_seconds: number | null;
            /** Rpe */
            rpe: number | null;
            /** Set Index */
            set_index: number;
            /** Weight Kg */
            weight_kg: number;
        };
        /** SettingsUpdate */
        SettingsUpdate: {
            /** Openings Enabled */
            openings_enabled: boolean;
        };
        /** SourceOut */
        SourceOut: {
            /** Dataset */
            dataset: string;
            /** License Status */
            license_status: string;
            /** Note */
            note: string;
            /** Reference */
            reference: string;
        };
        /** StepReportOut */
        StepReportOut: {
            /** Code */
            code: string | null;
            /** Message */
            message: string;
            /** Ok */
            ok: boolean;
        };
        /** StrengthBlockOut */
        StrengthBlockOut: {
            /** Exercise Id */
            exercise_id: string;
            /** Exercise Name */
            exercise_name: string;
            /** Position */
            position: number;
            /** Sets */
            sets: components["schemas"]["SetOut"][];
        };
        /** StrengthItemIn */
        StrengthItemIn: {
            /**
             * Exercise Id
             * @description 力量动作的编号，取自搜索动作（search_exercises）结果里的 id，必须是力量动作
             */
            exercise_id: string;
            /**
             * Sets
             * @description 按完成顺序排列的每一组，1 至 30 组
             */
            sets: components["schemas"]["SetIn"][];
        };
        /** SummaryOut */
        SummaryOut: {
            /**
             * Date
             * Format: date
             */
            date: string;
            /** Disclaimer */
            disclaimer: string;
            /** Incomplete Fields */
            incomplete_fields: string[];
            /** Meals */
            meals: {
                [key: string]: components["schemas"]["NutrientsOut"];
            };
            needs: components["schemas"]["NeedsOut"];
            /** Remaining */
            remaining: {
                [key: string]: number;
            } | null;
            total: components["schemas"]["NutrientsOut"];
        };
        /** SymptomCountOut */
        SymptomCountOut: {
            /** Days */
            days: number;
            /** Symptom */
            symptom: string;
        };
        /** TagOut */
        TagOut: {
            /** Basis */
            basis: string;
            /** Id */
            id: string;
            /** Kind */
            kind: string;
            /** Name */
            name: string;
            /** Review Status */
            review_status: string;
        };
        /** TipOut */
        TipOut: {
            /** Basis */
            basis: string;
            /**
             * Category
             * @enum {string}
             */
            category: "nutrition" | "tradition" | "lifestyle";
            /** Content */
            content: string;
            /** Id */
            id: string;
            /**
             * Phase
             * @enum {string}
             */
            phase: "menstrual" | "follicular" | "ovulation" | "luteal" | "any";
            /**
             * Severity
             * @enum {string}
             */
            severity: "info" | "caution";
            /** Title */
            title: string;
        };
        /** TipsOut */
        TipsOut: {
            /** Disclaimer */
            disclaimer: string;
            phase: components["schemas"]["PhaseOut"];
            /** Tips */
            tips: components["schemas"]["TipOut"][];
        };
        /** TokenResponse */
        TokenResponse: {
            /** Access Token */
            access_token: string;
            /**
             * Token Type
             * @default bearer
             */
            token_type: string;
        };
        /** ToolCallOut */
        ToolCallOut: {
            /** Arguments */
            arguments: {
                [key: string]: unknown;
            };
            /** Call Id */
            call_id: string | null;
            /** Name */
            name: string;
        };
        /** TrainingSignalOut */
        TrainingSignalOut: {
            /** Conflicts */
            conflicts: components["schemas"]["ConflictOut"][];
            /**
             * Day
             * Format: date
             */
            day: string;
            /** Disclaimer */
            disclaimer: string;
            /** Energy High */
            energy_high: number | null;
            /** Energy Low */
            energy_low: number | null;
            /**
             * Energy Status
             * @enum {string}
             */
            energy_status: "ok" | "missing_body_weight" | "no_training";
            /**
             * Intensity
             * @enum {string}
             */
            intensity: "none" | "light" | "moderate" | "vigorous";
            /** Kinds */
            kinds: ("strength" | "cardio")[];
            /** Muscles */
            muscles: ("chest" | "back" | "shoulders" | "biceps" | "triceps" | "quads" | "hamstrings" | "glutes" | "calves" | "core" | "full_body")[];
            /** Notes */
            notes: string[];
            /** Trained */
            trained: boolean;
            /** Workout Count */
            workout_count: number;
        };
        /** TrendPointOut */
        TrendPointOut: {
            /**
             * Day
             * Format: date
             */
            day: string;
            /** Max Weight Kg */
            max_weight_kg: number;
            /** Sets */
            sets: number;
            /** Total Reps */
            total_reps: number;
            /** Total Volume */
            total_volume: number;
        };
        /**
         * TurnOut
         * @description 一轮对话的结果；流式时 done 事件里是除 text 以外的字段。
         */
        TurnOut: {
            /** Evidence */
            evidence: string;
            /** Flags */
            flags: string[];
            /**
             * Message Id
             * Format: uuid
             */
            message_id: string;
            /** Text */
            text: string;
            /** Tools Used */
            tools_used: string[];
        };
        /** TypeAdviceOut */
        TypeAdviceOut: {
            /** Avoid */
            avoid: string[];
            /**
             * Conclusion
             * @enum {string}
             */
            conclusion: "suitable" | "caution" | "not_recommended";
            /** Moderate */
            moderate: string[];
            /** Order */
            order: string[];
            /** Reasons */
            reasons: components["schemas"]["DishReasonOut"][];
            /** Type Key */
            type_key: string;
            /** Type Name */
            type_name: string;
        };
        /** UsageOut */
        UsageOut: {
            /** Input Tokens */
            input_tokens: number | null;
            /** Output Tokens */
            output_tokens: number | null;
        };
        /** UserOut */
        UserOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Username */
            username: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /** WeekSummaryOut */
        WeekSummaryOut: {
            /** Cardio Minutes */
            cardio_minutes: number;
            /** Energy High Kcal */
            energy_high_kcal: number | null;
            /** Energy Low Kcal */
            energy_low_kcal: number | null;
            /**
             * Energy Status
             * @enum {string}
             */
            energy_status: "ok" | "missing_body_weight";
            /** Muscle Volumes */
            muscle_volumes: {
                [key: string]: number;
            };
            /** Note */
            note: string;
            /** Total Volume */
            total_volume: number;
            /** Training Days */
            training_days: number;
            /**
             * Week End
             * Format: date
             */
            week_end: string;
            /**
             * Week Start
             * Format: date
             */
            week_start: string;
            /** Workout Count */
            workout_count: number;
        };
        /** WorkoutIn */
        WorkoutIn: {
            /**
             * Cardio
             * @description 有氧项目，按完成顺序排列，最多 30 个；与 strength 至少要填一项
             * @default []
             */
            cardio: components["schemas"]["CardioItemIn"][];
            /**
             * Duration Minutes
             * @description 整次训练的时长，单位分钟，1 至 600，可不填
             */
            duration_minutes?: number | null;
            /**
             * Note
             * @description 备注，最多 500 个字，可不填
             */
            note?: string | null;
            /**
             * Performed On
             * Format: date
             * @description 训练日期，格式 YYYY-MM-DD，不能晚于今天
             */
            performed_on: string;
            /**
             * Rpe
             * @description 整次训练的主观强度 RPE，1 至 10 的整数（1 非常轻松，10 竭尽全力），可不填
             */
            rpe?: number | null;
            /**
             * Strength
             * @description 力量动作，按完成顺序排列，最多 30 个；与 cardio 至少要填一项
             * @default []
             */
            strength: components["schemas"]["StrengthItemIn"][];
        };
        /** WorkoutOut */
        WorkoutOut: {
            /** Cardio */
            cardio: components["schemas"]["CardioOut"][];
            /** Conflicts */
            conflicts: components["schemas"]["ConflictOut"][];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Duration Minutes */
            duration_minutes: number | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Note */
            note: string | null;
            /**
             * Performed On
             * Format: date
             */
            performed_on: string;
            /** Rpe */
            rpe: number | null;
            /** Strength */
            strength: components["schemas"]["StrengthBlockOut"][];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    list_grants_api_agent_grants_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GrantOut"][];
                };
            };
        };
    };
    create_grant_api_agent_grants_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GrantCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GrantCreatedOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_grant_api_agent_grants__grant_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                grant_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_audits_api_agent_grants_audit_get: {
        parameters: {
            query?: {
                client_name?: string | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuditOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_conversations_api_agent_conversations_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationOut"][];
                };
            };
        };
    };
    create_conversation_api_agent_conversations_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConversationCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_conversation_api_agent_conversations__conversation_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_conversation_api_agent_conversations__conversation_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    post_message_api_agent_conversations__conversation_id__messages_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MessageCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TurnOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_opening_api_agent_opening_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OpeningResponse"];
                };
            };
        };
    };
    answer_opening_api_agent_opening__opening_id__answer_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                opening_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    decline_opening_api_agent_opening__opening_id__decline_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                opening_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_preferences_api_agent_preferences_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PreferenceOut"][];
                };
            };
        };
    };
    add_preference_api_agent_preferences_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PreferenceCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PreferenceOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_preference_api_agent_preferences__preference_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                preference_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_settings_api_agent_settings_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__agent__schemas__SettingsOut"];
                };
            };
        };
    };
    put_settings_api_agent_settings_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SettingsUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__agent__schemas__SettingsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_api_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_api_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    me_api_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
        };
    };
    register_api_auth_register_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegisterRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_day_logs_api_cycle_day_logs_get: {
        parameters: {
            query?: {
                end?: string | null;
                start?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DayLogOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    put_day_log_api_cycle_day_logs__log_date__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                log_date: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DayLogIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DayLogOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_day_log_api_cycle_day_logs__log_date__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                log_date: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_periods_api_cycle_periods_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PeriodOut"][];
                };
            };
        };
    };
    create_period_api_cycle_periods_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PeriodCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PeriodOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_period_api_cycle_periods__period_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                period_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_period_api_cycle_periods__period_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                period_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PeriodUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PeriodOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_phase_api_cycle_phase_get: {
        parameters: {
            query?: {
                date?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PhaseOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_prediction_api_cycle_prediction_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PredictionOut"];
                };
            };
        };
    };
    get_settings_api_cycle_settings_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CycleSettingsOut"];
                };
            };
        };
    };
    put_settings_api_cycle_settings_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CycleSettingsUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CycleSettingsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_stats_api_cycle_stats_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CycleStatsOut"];
                };
            };
        };
    };
    get_tips_api_cycle_tips_get: {
        parameters: {
            query?: {
                date?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TipsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_disclaimer_api_disclaimer_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DisclaimerOut"];
                };
            };
        };
    };
    accept_api_disclaimer_accept_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AcceptRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DisclaimerStatus"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_status_api_disclaimer_status_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DisclaimerStatus"];
                };
            };
        };
    };
    create_custom_exercise_api_fitness_exercises_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CustomExerciseIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExerciseDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_exercise_api_fitness_exercises__exercise_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                exercise_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExerciseDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    exercise_trend_api_fitness_exercises__exercise_id__trend_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                exercise_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExerciseTrendOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_custom_exercises_api_fitness_exercises_custom_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExerciseDetailOut"][];
                };
            };
        };
    };
    delete_custom_exercise_api_fitness_exercises_custom__exercise_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                exercise_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_exercises_api_fitness_exercises_search_get: {
        parameters: {
            query: {
                q: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExerciseSearchOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    training_signal_api_fitness_signal_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TrainingSignalOut"];
                };
            };
        };
    };
    week_summary_api_fitness_summary_week_get: {
        parameters: {
            query?: {
                start?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WeekSummaryOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_workouts_api_fitness_workouts_get: {
        parameters: {
            query?: {
                end?: string | null;
                start?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkoutOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_workout_api_fitness_workouts_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorkoutIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkoutOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_workout_api_fitness_workouts__workout_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workout_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkoutOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    replace_workout_api_fitness_workouts__workout_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workout_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorkoutIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkoutOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_workout_api_fitness_workouts__workout_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workout_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    list_assignments_api_llm_assignments_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssignmentOut"][];
                };
            };
        };
    };
    set_assignment_api_llm_assignments__purpose__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                purpose: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AssignmentSet"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssignmentOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    clear_assignment_api_llm_assignments__purpose__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                purpose: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    chat_api_llm_chat_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChatRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChatOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_model_api_llm_models__model_pk__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                model_pk: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_model_api_llm_models__model_pk__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                model_pk: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OverridesUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelUpdatedOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_presets_api_llm_presets_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PresetOut"][];
                };
            };
        };
    };
    list_providers_api_llm_providers_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderOut"][];
                };
            };
        };
    };
    create_provider_api_llm_providers_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProviderCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_provider_api_llm_providers__provider_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_provider_api_llm_providers__provider_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_provider_api_llm_providers__provider_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProviderUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    fetch_models_api_llm_providers__provider_id__fetch_models_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FetchModelsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_models_api_llm_providers__provider_id__models_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    add_model_api_llm_providers__provider_id__models_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ModelCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    check_saved_provider_api_llm_providers__provider_id__test_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SavedProviderTest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionReportOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    check_unsaved_provider_api_llm_providers_test_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProviderTest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionReportOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_capabilities_api_me_capabilities_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: boolean;
                    };
                };
            };
        };
    };
    get_constraints_api_medical_constraints_get: {
        parameters: {
            query?: {
                category?: ("diet_avoid" | "diet_require" | "medication_diet" | "exercise_limit" | "other") | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConstraintsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_user_events_api_medical_events_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MedicalEventOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    download_evidence_api_medical_evidence__evidence_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                evidence_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_items_api_medical_items_get: {
        parameters: {
            query?: {
                category?: ("diet_avoid" | "diet_require" | "medication_diet" | "exercise_limit" | "other") | null;
                status?: ("pending_confirmation" | "active" | "pending_review" | "resolved" | "voided") | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__medical__schemas__ItemOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_item_api_medical_items__item_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__medical__schemas__ItemOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_item_api_medical_items__item_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ItemUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__medical__schemas__ItemOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_proposal_api_medical_items__item_id__cancel_proposal_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__medical__schemas__ItemOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    confirm_item_api_medical_items__item_id__confirm_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["ItemUpdate"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__medical__schemas__ItemOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    continue_item_api_medical_items__item_id__continue_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ContinueBody"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__medical__schemas__ItemOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_events_api_medical_items__item_id__events_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EventOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    propose_resolution_api_medical_items__item_id__propose_resolution_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProposalBody"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__medical__schemas__ItemOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resolve_item_api_medical_items__item_id__resolve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["ReasonBody"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__medical__schemas__ItemOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    void_item_api_medical_items__item_id__void_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["ReasonBody"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__medical__schemas__ItemOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_orders_api_medical_orders_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrderOut"][];
                };
            };
        };
    };
    create_order_api_medical_orders_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OrderCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrderOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_order_api_medical_orders__order_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                order_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrderOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_evidence_api_medical_orders__order_id__evidence_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                order_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_evidence_api_medical_orders__order_id__evidence_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvidenceOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    add_manual_item_api_medical_orders__order_id__items_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                order_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ManualItemCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__medical__schemas__ItemOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_reviews_api_medical_reviews_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__medical__schemas__ItemOut"][];
                };
            };
        };
    };
    evaluate_api_nutrition_evaluate_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EvaluateIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__nutrition__schemas__EvaluationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    evaluate_meal_items_api_nutrition_evaluate_meal_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EvaluateMealIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MealEvaluationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_food_api_nutrition_foods__food_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                food_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FoodDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_foods_api_nutrition_foods_search_get: {
        parameters: {
            query: {
                q: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__nutrition__schemas__SearchOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_meals_api_nutrition_meals_get: {
        parameters: {
            query?: {
                date?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MealOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_meal_api_nutrition_meals_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MealCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MealOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_meal_api_nutrition_meals__entry_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                entry_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_meal_api_nutrition_meals__entry_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                entry_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MealUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MealOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_needs_api_nutrition_needs_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NeedsOut"];
                };
            };
        };
    };
    get_summary_api_nutrition_summary_get: {
        parameters: {
            query?: {
                date?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SummaryOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_tags_api_nutrition_tags_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TagOut"][];
                };
            };
        };
    };
    list_recognitions_api_photos_recognitions_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecognitionSummaryOut"][];
                };
            };
        };
    };
    create_recognition_api_photos_recognitions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_create_recognition_api_photos_recognitions_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecognitionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_recognition_api_photos_recognitions__rec_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rec_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecognitionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_recognition_api_photos_recognitions__rec_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rec_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    confirm_api_photos_recognitions__rec_id__confirm_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rec_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConfirmIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecognitionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    discard_api_photos_recognitions__rec_id__discard_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rec_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecognitionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_image_api_photos_recognitions__rec_id__image_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rec_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_items_api_photos_recognitions__rec_id__items_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rec_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ItemsUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecognitionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_profile_api_profile_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileOut"];
                };
            };
        };
    };
    patch_profile_api_profile_patch: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProfileUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_profile_changes_api_profile_changes_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileChangeOut"][];
                };
            };
        };
    };
    list_needs_api_restaurants_needs_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NeedOut"][];
                };
            };
        };
    };
    search_api_restaurants_search_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SearchIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__restaurants__schemas__SearchOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_settings_api_restaurants_settings_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__restaurants__schemas__SettingsOut"];
                };
            };
        };
    };
    clear_area_api_restaurants_settings_area_delete: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    set_consent_api_restaurants_settings_consent_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConsentIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__restaurants__schemas__SettingsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
