"""
Singleton pattern implementation for device classes.
"""

def singleton(cls):
    """
    Decorator to implement the singleton pattern.
    
    This ensures only one instance of a class is created.
    All subsequent calls to the constructor will return the same instance.
    
    Usage:
        @singleton
        class MyClass:
            pass
    """
    instances = {}
    
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance 