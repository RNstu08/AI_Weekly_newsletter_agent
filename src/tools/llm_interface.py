from langchain_community.llms import Ollama
from langchain_community.chat_models import ChatOllama
from langchain_community.llms import HuggingFaceHub
from langchain_core.language_models.llms import BaseLLM
from langchain_core.language_models.chat_models import BaseChatModel
from src.config import get_settings
from src.utils import logger
from typing import Union

settings = get_settings()

def get_ollama_llm() -> Ollama:
    """
    Initializes and returns an Ollama LLM instance based on configuration.
    Assumes Ollama server is running locally or at specified base_url.
    """
    try:
        llm = Ollama(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_MODEL_NAME)
        logger.info(f"Initialized Ollama LLM: {settings.OLLAMA_MODEL_NAME} at {settings.OLLAMA_BASE_URL}")
        # A quick ping to check if it's alive (optional, can add more robust checks)
        # llm.invoke("Hello", config={"max_tokens": 1}) # Simple invoke can check connectivity
        return llm
    except Exception as e:
        logger.error(f"Failed to initialize Ollama LLM: {e}")
        raise

def get_ollama_chat_model() -> ChatOllama:
    """
    Initializes and returns an Ollama ChatModel instance based on configuration.
    """
    try:
        chat_model = ChatOllama(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_MODEL_NAME)
        logger.info(f"Initialized Ollama Chat Model: {settings.OLLAMA_MODEL_NAME} at {settings.OLLAMA_BASE_URL}")
        return chat_model
    except Exception as e:
        logger.error(f"Failed to initialize Ollama Chat Model: {e}")
        raise

def get_huggingface_llm() -> HuggingFaceHub:
    """
    Initializes and returns a HuggingFaceHub LLM instance based on configuration.
    Requires HF_API_TOKEN and HF_MODEL_NAME.
    """
    if not settings.HF_API_TOKEN:
        logger.error("HuggingFace API token (HF_API_TOKEN) not found in environment variables.")
        raise ValueError("HuggingFace API token is required for HuggingFace LLM provider.")
    if not settings.HF_MODEL_NAME:
        logger.error("HuggingFace model name (HF_MODEL_NAME) not found in environment variables.")
        raise ValueError("HuggingFace model name is required for HuggingFace LLM provider.")

    try:
        # Example: using text-generation-inference endpoint or general models
        llm = HuggingFaceHub(
            repo_id=settings.HF_MODEL_NAME,
            huggingfacehub_api_token=settings.HF_API_TOKEN,
            task="text-generation" # Or "text2text-generation", "conversational" etc.
        )
        logger.info(f"Initialized HuggingFace LLM: {settings.HF_MODEL_NAME}")
        return llm
    except Exception as e:
        logger.error(f"Failed to initialize HuggingFace LLM: {e}")
        raise

def get_default_llm() -> Union[BaseLLM, BaseChatModel]:
    """
    Returns the appropriate LLM or ChatModel instance based on the LLM_PROVIDER setting.
    """
    provider = settings.LLM_PROVIDER.lower()
    if provider == "ollama":
        # For chat models like Llama 3, usually ChatOllama is preferred
        return get_ollama_chat_model() if "chat" in settings.OLLAMA_MODEL_NAME.lower() else get_ollama_llm()
    elif provider == "huggingface":
        return get_huggingface_llm()
    else:
        logger.error(f"Unsupported LLM provider specified: {settings.LLM_PROVIDER}")
        raise ValueError(f"Unsupported LLM provider: {settings.LLM_PROVIDER}")

# Example usage:
if __name__ == "__main__":
    # Ensure .env is set up correctly for the desired provider
    # For Ollama: make sure Ollama desktop app is running and 'llama3' model is pulled.
    # Open a new terminal and run: ollama run llama3
    # Then run this script in another terminal.
    # For HuggingFace: set HF_API_TOKEN and HF_MODEL_NAME in .env
    
    try:
        llm_instance = get_default_llm()
        if isinstance(llm_instance, BaseChatModel):
            response = llm_instance.invoke("What is the capital of France?")
            print(f"Chat Model Response: {response.content}")
        elif isinstance(llm_instance, BaseLLM):
            response = llm_instance.invoke("What is the capital of France?")
            print(f"LLM Response: {response}")
    except Exception as e:
        logger.error(f"Test failed: {e}")