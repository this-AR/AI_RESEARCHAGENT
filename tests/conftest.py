import os

import pytest


@pytest.fixture(autouse=True)
def mock_env_vars():
    """Automatically set mock environment variables for all tests."""
    # Store original env vars if needed
    old_environ = os.environ.copy()
    
    # Set mock credentials
    os.environ["GROQ_API_KEY"] = "test_groq_key_12345"
    os.environ["SERPER_API_KEY"] = "test_serper_key_12345"
    
    yield
    
    # Restore original env vars
    os.environ.clear()
    os.environ.update(old_environ)
