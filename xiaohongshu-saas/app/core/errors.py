"""Domain exceptions."""


class SaasError(Exception):
    """Base error."""


class ConfigError(SaasError):
    pass


class AccountError(SaasError):
    pass


class ContentError(SaasError):
    pass


class PublishError(SaasError):
    """Raised when a channel adapter fails to publish."""


class RiskControlError(SaasError):
    """Raised when risk-control rules reject a publish attempt."""


class ChannelNotEnabled(SaasError):
    pass