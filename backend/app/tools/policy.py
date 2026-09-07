"""P0에서 Backend가 LLM 호출 전에 차단할 금지 요청 정책을 정의한다."""

from backend.app.schemas.tools import ToolError


FORBIDDEN_REQUEST_RULES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "PAYMENT_REQUEST",
        ("결제", "payment", "카드 결제"),
        "결제 요청은 이 서비스에서 처리할 수 없습니다.",
    ),
    (
        "SECRET_REQUEST",
        ("api 키", "api key", "토큰 보여", "비밀번호", "secret", "환경변수 보여"),
        "민감정보를 제공하거나 조회할 수 없습니다.",
    ),
    (
        "MEDICAL_DIAGNOSIS_REQUEST",
        ("질병 확진", "질병 진단", "질환 진단", "병을 진단"),
        "동물의 질병을 확진할 수 없습니다. 사육사 또는 수의사에게 확인해 주세요.",
    ),
)


def detect_forbidden_request(message: str) -> ToolError | None:
    """사용자 요청에 P0 금지 영역이 포함됐는지 확인한다.

    Returns:
        금지 요청이면 안전한 오류 정보, 허용 요청이면 None.
    """
    normalized_message = message.casefold().strip()

    for code, keywords, safe_message in FORBIDDEN_REQUEST_RULES:
        if any(keyword in normalized_message for keyword in keywords):
            return ToolError(code=code, message=safe_message)

    return None