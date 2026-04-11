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
    """Test RoutingConfig defaults."""

    def test_default_route_is_empty(self):
        config = RoutingConfig()
        assert config.route == []

    def test_default_advise_is_empty(self):
        config = RoutingConfig()
        assert config.advise == []


class TestRoutingResult:
    """Test RoutingResult construction."""

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
    """Test ROLE_ROUTING table for each role."""

    def test_planner_routes_to_builder(self):
        assert ROLE_ROUTING["planner"].route == ["builder"]

    def test_planner_advises_council_keeper(self):
        assert ROLE_ROUTING["planner"].advise == ["council", "keeper"]

    def test_builder_routes_to_planner_ledger(self):
        assert ROLE_ROUTING["builder"].route == ["planner", "ledger"]

    def test_builder_advises_keeper_council(self):
        assert ROLE_ROUTING["builder"].advise == ["keeper", "council"]

    def test_keeper_routes_to_council_ledger(self):
        assert ROLE_ROUTING["keeper"].route == ["council", "ledger"]

    def test_keeper_advises_planner_builder(self):
        assert ROLE_ROUTING["keeper"].advise == ["planner", "builder"]

    def test_ledger_routes_to_none(self):
        assert ROLE_ROUTING["ledger"].route == []

    def test_ledger_advises_keeper_doctor_planner(self):
        assert ROLE_ROUTING["ledger"].advise == ["keeper", "doctor", "planner"]

    def test_council_routes_to_keeper(self):
        assert ROLE_ROUTING["council"].route == ["keeper"]

    def test_council_advises_planner_builder(self):
        assert ROLE_ROUTING["council"].advise == ["planner", "builder"]

    def test_doctor_routes_to_ledger(self):
        assert ROLE_ROUTING["doctor"].route == ["ledger"]

    def test_doctor_advises_keeper_council(self):
        assert ROLE_ROUTING["doctor"].advise == ["keeper", "council"]

    def test_greeter_routes_to_all_roles(self):
        all_roles = ["planner", "builder", "keeper", "ledger", "council", "doctor"]
        assert ROLE_ROUTING["greeter"].route == all_roles

    def test_greeter_advises_none(self):
        assert ROLE_ROUTING["greeter"].advise == []


class TestGreetingTemplates:
    """Test GREETING_TEMPLATES covers all 7 roles."""

    def test_all_roles_have_greetings(self):
        expected = {"planner", "builder", "keeper", "ledger", "council", "doctor", "greeter"}
        assert set(GREETING_TEMPLATES.keys()) == expected

    def test_greetings_are_non_empty(self):
        for role, greeting in GREETING_TEMPLATES.items():
            assert len(greeting) > 0, f"Greeting for {role} is empty"


class TestRoleSkills:
    """Test ROLE_SKILLS: each role has at least one skill."""

    def test_all_roles_have_skills(self):
        expected = {"planner", "builder", "keeper", "ledger", "council", "doctor", "greeter"}
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
    """Test RoleChat initialization."""

    def test_greeting(self):
        chat = RoleChat("planner")
        assert chat.greeting == "What do you want to accomplish?"

    def test_skills(self):
        chat = RoleChat("builder")
        assert len(chat.skills) == 2
        assert chat.skills[0].name == "run"

    def test_routing(self):
        chat = RoleChat("keeper")
        assert chat.routing.route == ["council", "ledger"]

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
    """Test RoleChat.run with and without LLM."""

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
    """Test RoleChat.detect_cross_role for routing detection."""

    def test_detects_route_builder(self):
        chat = RoleChat("planner")
        result = chat.detect_cross_role("[ROUTE:builder] Let's build it")
        assert result is not None
        assert result.action == RoutingAction.ROUTE
        assert result.target_role == "builder"
        assert result.message == "Let's build it"

    def test_detects_advise_keeper(self):
        chat = RoleChat("planner")
        result = chat.detect_cross_role("[ADVISE:keeper] Ask the keeper")
        assert result is not None
        assert result.action == RoutingAction.ADVISE
        assert result.target_role == "keeper"
        assert result.message == "Ask the keeper"

    def test_returns_none_for_normal_response(self):
        chat = RoleChat("planner")
        result = chat.detect_cross_role("Just a normal response")
        assert result is None

    def test_rejects_route_to_non_routeable_role(self):
        chat = RoleChat("ledger")
        result = chat.detect_cross_role("[ROUTE:builder] Cannot do this")
        assert result is None

    def test_rejects_advise_to_non_advisable_role(self):
        chat = RoleChat("greeter")
        result = chat.detect_cross_role("[ADVISE:keeper] Greeter advises none")
        assert result is None

    def test_route_without_message(self):
        chat = RoleChat("planner")
        result = chat.detect_cross_role("[ROUTE:builder]")
        assert result is not None
        assert result.target_role == "builder"
        assert result.message == ""


class TestCanRouteAndAdvise:
    """Test RoleChat.can_route_to and can_advise."""

    def test_can_route_to_valid(self):
        chat = RoleChat("planner")
        assert chat.can_route_to("builder") is True

    def test_cannot_route_to_invalid(self):
        chat = RoleChat("planner")
        assert chat.can_route_to("keeper") is False

    def test_can_advise_valid(self):
        chat = RoleChat("planner")
        assert chat.can_advise("keeper") is True

    def test_cannot_advise_invalid(self):
        chat = RoleChat("planner")
        assert chat.can_advise("builder") is False


class TestSystemPrompt:
    """Test RoleChat.get_system_prompt includes skills and routing."""

    def test_includes_role_name(self):
        chat = RoleChat("planner")
        prompt = chat.get_system_prompt()
        assert "Village Planner" in prompt

    def test_includes_skills(self):
        chat = RoleChat("keeper")
        prompt = chat.get_system_prompt()
        assert "see:" in prompt
        assert "ask:" in prompt

    def test_includes_routing(self):
        chat = RoleChat("builder")
        prompt = chat.get_system_prompt()
        assert "planner, ledger" in prompt
        assert "keeper, council" in prompt


class TestHandoffContext:
    """Test RoleChat handoff context includes conversation summary."""

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
