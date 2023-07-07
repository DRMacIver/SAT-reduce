from hypothesis import settings


settings.register_profile('default', settings(
    deadline=None
))

settings.load_profile('default')