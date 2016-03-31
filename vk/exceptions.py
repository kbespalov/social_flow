class InvalidAccessToken(Exception):
    pass


class TooManyConnections(Exception):
    pass


class ApiError(Exception):
    pass


class VkDatabaseError(Exception):
    pass
