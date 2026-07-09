from ai_software_factory.models import HumanValidationRequest, HumanValidationResponse


class HumanInputProvider:
    def request(self, request: HumanValidationRequest) -> HumanValidationResponse:
        raise NotImplementedError


class ConsoleHumanInputProvider(HumanInputProvider):
    def request(self, request: HumanValidationRequest) -> HumanValidationResponse:
        print(request.context)
        return HumanValidationResponse(request_id=request.id, decision=input("Decision: "))


class FakeHumanInputProvider(HumanInputProvider):
    def __init__(self, response: HumanValidationResponse) -> None:
        self.response = response

    def request(self, request: HumanValidationRequest) -> HumanValidationResponse:
        return self.response
