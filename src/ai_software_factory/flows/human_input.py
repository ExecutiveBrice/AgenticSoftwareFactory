from ai_software_factory.models import HumanValidationRequest, HumanValidationResponse


class HumanInputProvider:
    def request(self, request: HumanValidationRequest) -> HumanValidationResponse:
        raise NotImplementedError


class ConsoleHumanInputProvider(HumanInputProvider):
    def request(self, request: HumanValidationRequest) -> HumanValidationResponse:
        print(request.context)
        for question in request.questions:
            print(f"Question: {question}")
        if request.valid_options:
            print("Options: " + ", ".join(request.valid_options))
        return HumanValidationResponse(
            request_id=request.id, decision=input("Decision or answer: ")
        )


class FakeHumanInputProvider(HumanInputProvider):
    def __init__(self, response: HumanValidationResponse) -> None:
        self.response = response

    def request(self, request: HumanValidationRequest) -> HumanValidationResponse:
        if self.response.request_id != request.id:
            raise ValueError("Fake human response targets a different human request")
        if (
            self.response.decision
            and request.valid_options
            and self.response.decision not in request.valid_options
        ):
            raise ValueError("Fake human response decision is not valid for the request")
        return self.response
