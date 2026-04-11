"""Test role-based chat system with routing, skills, and greeting templates."""

from village.roles import (
    GREETING_TEMPLATES,
    ROLE_ROUTING,
    ROLE_SKILLS,
    RoleChat,
    RoleSkill,
    RoutingAction,
    RoutingConfig,
    RoutingResult,
)


class TestRoutingConfig:
    def test_default_route_is_empty(self):
        config = RoutingConfig()
        assert config.route == []

    def test_default_advise_is_empty(self):
        config = RoutingConfig()
        assert config.advise == []


class TestRoutingResult:
    def test_defaults(self):
        result = RoutingResult(action=RoutingAction.NONE)
        assert result.action == RoutingAction.NONE
        assert result.target_role is None
        assert result.message == ""
        assert result.context == {}

    def test_with_values(self):
        result = RoutingResult(
            action=RoutingAction.ROUTE,
            target_role="builder",
            message="go build",
            context={"from_role": "planner"},
        )
        assert result.action == RoutingAction.ROUTE
        assert result.target_role == "builder"
        assert result.message == "go build"
        assert result.context == {"from_role": "planner"}


class TestRoleRouting:
    def test_planner_routes_to_builder(self):
        assert ROLE_ROUTING["planner"].route == ["builder"]

    def test_planner_advises_council_scribe(self):
        assert ROLE_ROUTING["planner"].advise == ["council", "scribe"]

    def test_builder_routes_to_planner(self):
        assert ROLE_ROUTING["builder"].route == ["planner"]

    def test_builder_advises_scribe_council(self):
        assert ROLE_ROUTING["builder"].advise == ["scribe", "council"]

    def test_scribe_routes_to_council(self):
        assert ROLE_ROUTING["scribe"].route == ["council"]

    def test_scribe_advises_planner_builder(self):
        assert ROLE_ROUTING["scribe"].advise == ["planner", "builder"]

    def test_council_routes_to_scribe(self):
        assert ROLE_ROUTING["council"].route == ["scribe"]

    def test_council_advises_planner_builder(self):
        assert ROLE_ROUTING["council"].advise == ["planner", "builder"]

    def test_doctor_routes_to_scribe(self):
        assert ROLE_ROUTING["doctor"].route == ["scribe"]

    def test_doctor_advises_scribe_council(self):
        assert ROLE_ROUTING["doctor"].advise == ["scribe", "council"]

    def test_greeter_routes_to_all_roles(self):
        all_roles = ["planner", "builder", "scribe", "council", "doctor"]
        assert ROLE_ROUTING["greeter"].route == all_roles

    def test_greeter_advises_none(self):
        assert ROLE_ROUTING["greeter"].advise == []


class TestGreetingTemplates:
    def test_all_roles_have_greetings(self):
        expected = {"planner", "builder", "scribe", "council", "doctor", "greeter"}
        assert set(GREETING_TEMPLATES.keys()) == expected

    def test_greetings_are_non_empty(self):
        for role, greeting in GREETING_TEMPLATES.items():
            assert len(greeting) > 0, f"Greeting for {role} is empty"


class TestRoleSkills:
    def test_all_roles_have_skills(self):
        expected = {"planner", "builder", "scribe", "council", "doctor", "greeter"}
        assert set(ROLE_SKILLS.keys()) == expected

    def test_each_role_has_at_least_one_skill(self):
        for role, skills in ROLE_SKILLS.items():
            assert len(skills) >= 1, f"{role} has no skills"

    def test_skill_has_name_and_description(self):
        for role, skills in ROLE_SKILLS.items():
            for skill in skills:
                assert isinstance(skill, RoleSkill)
                assert len(skill.name) > 0
                assert len(skill.description) > 0


class TestRoleChatInit:
    def test_greeting(self):
        chat = RoleChat("planner")
        assert chat.greeting == "What do you want to accomplish?"

    def test_skills(self):
        chat = RoleChat("builder")
        assert len(chat.skills) == 2
        assert chat.skills[0].name == "run"

    def test_routing(self):
        chat = RoleChat("scribe")
        assert chat.routing.route == ["council"]

    def test_unknown_role_defaults(self):
        chat = RoleChat("unknown")
        assert chat.greeting == "How can I help?"
        assert chat.skills == []
        assert chat.routing.route == []
        assert chat.routing.advise == []

    def test_context_passed_through(self):
        ctx = {"task_id": "bd-123"}
        chat = RoleChat("planner", context=ctx)
        assert chat.context == {"task_id": "bd-123"}


class TestRoleChatRun:
    def test_run_no_llm_echo_response(self):
        chat = RoleChat("planner")
        response = chat.run("hello")
        assert response == "[planner] Received: hello"

    def test_run_with_mock_llm(self):
        def mock_llm(prompt: str) -> str:
            return "mock response"

        chat = RoleChat("builder", llm_call_fn=mock_llm)
        response = chat.run("build something")
        assert response == "mock response"


class TestDetectCrossRole:
    def test_detects_route_builder(self):
        chat = RoleChat("planner")
        result = chat.detect_cross_role("[ROUTE:builder] Let's build it")
        assert result is not None
        assert result.action == RoutingAction.ROUTE
        assert result.target_role == "builder"
        assert result.message == "Let's build it"

    def test_detects_advise_scribe(self):
        chat = RoleChat("planner")
        result = chat.detect_cross_role("[ADVISE:scribe] Ask the scribe")
        assert result is not None
        assert result.action == RoutingAction.ADVISE
        assert result.target_role == "scribe"
        assert result.message == "Ask the scribe"

    def test_returns_none_for_normal_response(self):
        chat = RoleChat("planner")
        result = chat.detect_cross_role("Just a normal response")
        assert result is None

    def test_rejects_route_to_non_routeable_role(self):
        chat = RoleChat("doctor")
        result = chat.detect_cross_role("[ROUTE:builder] Cannot do this")
        assert result is None

    def test_rejects_advise_to_non_advisable_role(self):
        chat = RoleChat("greeter")
        result = chat.detect_cross_role("[ADVISE:scribe] Greeter advises none")
        assert result is None

    def test_route_without_message(self):
        chat = RoleChat("planner")
        result = chat.detect_cross_role("[ROUTE:builder]")
        assert result is not None
        assert result.target_role == "builder"
        assert result.message == ""


class TestCanRouteAndAdvise:
    def test_can_route_to_valid(self):
        chat = RoleChat("planner")
        assert chat.can_route_to("builder") is True

    def test_cannot_route_to_invalid(self):
        chat = RoleChat("planner")
        assert chat.can_route_to("scribe") is False

    def test_can_advise_valid(self):
        chat = RoleChat("planner")
        assert chat.can_advise("scribe") is True

    def test_cannot_advise_invalid(self):
        chat = RoleChat("planner")
        assert chat.can_advise("builder") is False


class TestSystemPrompt:
    def test_includes_role_name(self):
        chat = RoleChat("planner")
        prompt = chat.get_system_prompt()
        assert "Village Planner" in prompt

    def test_includes_skills(self):
        chat = RoleChat("scribe")
        prompt = chat.get_system_prompt()
        assert "see:" in prompt
        assert "ask:" in prompt

    def test_includes_routing(self):
        chat = RoleChat("builder")
        prompt = chat.get_system_prompt()
        assert "planner" in prompt
        assert "scribe, council" in prompt


class TestHandoffContext:
    def test_handoff_includes_from_role(self):
        chat = RoleChat("planner")
        chat.run("hello")
        result = chat.detect_cross_role("[ROUTE:builder] Go build")
        assert result is not None
        assert result.context["from_role"] == "planner"

    def test_handoff_includes_conversation_summary(self):
        chat = RoleChat("planner")
        chat.run("first message")
        result = chat.detect_cross_role("[ROUTE:builder] Go build")
        assert result is not None
        summary = result.context["conversation_summary"]
        assert len(summary) > 0
        assert ("user", "first message") in summary
