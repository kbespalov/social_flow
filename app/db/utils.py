import asyncio


def accumulate(function):
    def wrapper(single_item):
        if len(wrapper.bucket) == 1000:
            result = function(wrapper.bucket)
            wrapper.bucket = [single_item]
            return result
        else:
            wrapper.bucket.append(single_item)

    wrapper.bucket = []
    return wrapper
