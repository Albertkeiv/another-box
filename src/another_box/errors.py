class AnotherBoxError(Exception):
    """Base error suitable for displaying to the user."""


class ProfileNotFoundError(AnotherBoxError):
    pass


class SubscriptionError(AnotherBoxError):
    pass


class ValidationError(AnotherBoxError):
    pass


class ProcessStartError(AnotherBoxError):
    pass


class ProcessConflictError(ProcessStartError):
    pass

