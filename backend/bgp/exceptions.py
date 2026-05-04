class BgpAutomacaoError(Exception):
    pass

class IrrValidationError(BgpAutomacaoError):
    pass

class RouterConnectionError(BgpAutomacaoError):
    pass

class RouterInventoryError(BgpAutomacaoError):
    pass

class UserCancelledError(BgpAutomacaoError):
    pass
