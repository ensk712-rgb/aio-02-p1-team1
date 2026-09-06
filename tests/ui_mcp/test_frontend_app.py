from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).parents[2] / "frontend" / "app.py"


def test_login_screen_renders_and_requires_both_fields() -> None:
    app = AppTest.from_file(str(APP_PATH)).run()

    assert not app.exception
    assert len(app.text_input) == 2
    app.button[0].click().run()
    assert not app.exception
    assert len(app.warning) == 1


def test_authenticated_session_renders_dashboard_and_logout() -> None:
    app = AppTest.from_file(str(APP_PATH))
    app.session_state["authenticated"] = True
    app.session_state["user_id"] = "visitor"
    app.session_state["session_id"] = None
    app.session_state["messages"] = []
    app.run()

    assert not app.exception
    assert len(app.chat_input) == 1
    assert any(button.label == "로그아웃" for button in app.button)


def test_chat_history_does_not_render_none_magic_output() -> None:
    app = AppTest.from_file(str(APP_PATH))
    app.session_state["authenticated"] = True
    app.session_state["user_id"] = "visitor"
    app.session_state["session_id"] = "session-1"
    app.session_state["messages"] = [
        {"role": "user", "content": "판다는 어디에 있어?"},
        {
            "role": "assistant",
            "payload": {
                "status": "completed",
                "final_answer": "판다는 판다월드에 있어요.",
                "sources": [],
                "tool_calls": [],
            },
        },
    ]
    app.run()

    assert not app.exception
    assert all(element.value != "None" for element in app.markdown)
