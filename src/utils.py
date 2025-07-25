import logging
import os
from datetime import datetime
import re
import unicodedata
import json
from pathlib import Path


# Define log file path relative to the project root
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Define log file name with current date
log_file_name = datetime.now().strftime('ai_news_agent_%Y-%m-%d.log')
LOG_FILE_PATH = os.path.join(LOG_DIR, log_file_name)

# Define paths for saving intermediate data
DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / '..' / 'data'
PROCESSED_CONTENT_DIR = DATA_DIR / 'processed_content'
NEWSLETTER_DRAFTS_DIR = DATA_DIR / 'newsletter_drafts'

# Ensure directories exist
PROCESSED_CONTENT_DIR.mkdir(parents=True, exist_ok=True)
NEWSLETTER_DRAFTS_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging():
    """
    Sets up a centralized logging configuration for the application.
    Logs to console and a daily file.
    """
    logger = logging.getLogger('ai_news_agent')
    logger.setLevel(logging.INFO) # Set default logging level

    if not logger.handlers:
        c_handler = logging.StreamHandler()
        c_handler.setLevel(logging.INFO)
        c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(c_format)
        logger.addHandler(c_handler)

        f_handler = logging.FileHandler(LOG_FILE_PATH)
        f_handler.setLevel(logging.DEBUG) # more verbosely to file for debugging
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)

    return logger

logger = setup_logging()


# --- Main JSON string cleaner (focused on structural extraction and minimal fixes) ---
def clean_json_string(json_str: str) -> str:
    """
    Extracts the most probable JSON string from a given text, focusing on markdown fences
    or outermost braces. It performs minimal, safe string cleaning for common LLM non-JSON output.
    More complex JSON syntax fixing (e.g., escaping inner quotes, fixing missing commas)
    is handled in a retry loop in the calling agent.
    """
    current_str = json_str

    # 1. Normalize unicode whitespace and remove BOM/zero-width spaces. Aggressively strip outer whitespace.
    current_str = unicodedata.normalize("NFKC", current_str).strip()
    current_str = current_str.replace('\ufeff', '').replace('\u200b', '').replace('\u00A0', ' ')
    
    # 2. Extract JSON from markdown code blocks first or find outermost braces.
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", current_str, re.DOTALL)
    if match:
        extracted_json = match.group(1).strip()
        logger.debug("clean_json_string: Extracted JSON from markdown code block.")
    else:
        # If no code block, try to find the outermost JSON object by braces.
        start_brace = current_str.find('{')
        end_brace = current_str.rfind('}')
        if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
            extracted_json = current_str[start_brace : end_brace + 1].strip()
            logger.debug("clean_json_string: Extracted JSON using outermost braces.")
        else:
            logger.warning("clean_json_string: No discernible JSON object structure (missing outer braces or code block). Returning original string for external handling.")
            extracted_json = current_str.strip() # Return the cleaned raw string

    # 3. Perform very basic, non-destructive JSON literal replacements
    # Convert Python-style None/True/False to JSON-style null/true/false (safe)
    extracted_json = extracted_json.replace('None', 'null').replace('True', 'true').replace('False', 'false')
    
    # Remove any stray backticks that might have remained from markdown cleanup
    extracted_json = extracted_json.replace('`', '')

    # Convert single-quoted strings to double-quoted strings (most common LLM mistake)
    # This regex is broad, but essential for parsability. It assumes '...' are meant to be strings.
    extracted_json = re.sub(r"'(.*?)'", r'"\1"', extracted_json)
    
    # Replace unescaped newlines/tabs within what appear to be string values.
    extracted_json = re.sub(r'"((?:[^"\\]|\\.)*)"', lambda m: '"' + m.group(1).replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r') + '"', extracted_json, flags=re.DOTALL)

    return extracted_json.strip() # Final strip


# --- Helper for escaping quotes in string values (for retry logic) ---
def escape_quotes_in_json_string_values(json_string: str) -> str:
    """
    Attempts to escape unescaped double quotes inside string values of a JSON string.
    This is a targeted fix for LLM output issues like 'They"re' or 'control or "brain"'.
    It is designed to be applied *after* initial cleaning by clean_json_string and
    *before* a retry of json.loads().
    """
    logger.debug(f"escape_quotes_in_json_string_values: Attempting to fix unescaped internal quotes. Original (first 200): {json_string[:200]}...")

    # Regex to find quoted strings, then use a callback to fix their internal quotes.
    # It finds a string that starts with a quote, captures its content (non-quote or escaped quote),
    # then makes sure it ends with a quote.
    def fix_internal_quotes_callback(match):
        # match.group(1) is the content INSIDE the outer double quotes of the matched string.
        content = match.group(1)
        
        # This is the core fix: replace any UNESCAPED double quotes within the content with `\"`
        # We need to be careful not to double-escape. So, temporarily unescape first.
        temp_fixed_content = content.replace(r'\"', '[TEMP_ESCAPED_QUOTE_HOLDER]') # Preserve existing escaped quotes
        temp_fixed_content = temp_fixed_content.replace('"', r'\"') # Escape all remaining (unescaped) quotes
        final_content = temp_fixed_content.replace('[TEMP_ESCAPED_QUOTE_HOLDER]', r'\"') # Restore original escapes
        
        return f'"{final_content}"'

    # Apply this fix globally to all strings that match the pattern of a JSON string.
    # This assumes the outer structure (keys, values, arrays) is mostly correct.
    # The `json.loads` will then validate the overall structure.
    fixed_json_string = re.sub(r'"((?:[^"\\]|\\.)*)"', fix_internal_quotes_callback, json_string, flags=re.DOTALL)
    
    logger.debug(f"escape_quotes_in_json_string_values: After fix (first 200): {fixed_json_string[:200]}...")
    return fixed_json_string


def save_state_to_json(state: dict, filename: str, directory: Path):
    """Saves a Python dictionary (representing AgentState) to a JSON file."""
    filepath = directory / filename
    try:
        # Pydantic models need to be .model_dump()ed before JSON serialization
        serializable_state = {}
        for key, value in state.items():
            if hasattr(value, 'model_dump'):
                serializable_state[key] = value.model_dump()
            elif isinstance(value, list) and all(hasattr(item, 'model_dump') for item in value):
                serializable_state[key] = [item.model_dump() for item in value]
            else:
                serializable_state[key] = value
        
        # Handle datetime objects for JSON serialization
        def datetime_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(serializable_state, f, indent=2, default=datetime_serializer)
        logger.info(f"State saved to {filepath}")
    except Exception as e:
        logger.error(f"Failed to save state to {filepath}: {e}", exc_info=True)

def load_state_from_json(filename: str, directory: Path) -> dict:
    """Loads a JSON file back into a Python dictionary."""
    filepath = directory / filename
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        logger.info(f"State loaded from {filepath}")
        
        # We'll return raw dicts and cast them in the calling agent's test function
        return loaded_data
    except FileNotFoundError:
        logger.warning(f"State file not found: {filepath}")
        return {}
    except Exception as e:
        logger.error(f"Failed to load state from {filepath}: {e}", exc_info=True)
        return {}

# Example usage: (Refined test cases to confirm fixes)
if __name__ == "__main__":
    logger.info("This is an informational message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
    logger.debug("This is a debug message, only in file.")

    test_cases = {
        "1_valid_json_with_fences": { "input": """```json\n{"key": "value","number": 123}\n```""", "expect_pass": True },
        "2_single_quote_keys_and_values": { # EXPECTED TO PASS after fixing single quotes
            "input": """{ 'summary': 'This is a summary.','key_entities': ['entity1', 'entity2'] }""",
            "expect_pass": True
        },
        "3_missing_comma_between_keys": { # EXPECTED TO FAIL (json.loads will complain, and that's okay)
            "input": """{"summary": "Another summary""key_entities": ["entity3"] }""",
            "expect_pass": False
        },
        "4_trailing_comma_at_end_of_object": { "input": """{"summary": "Trailing comma summary","key_entities": ["entity4"],}""", "expect_pass": True },
        "5_trailing_comma_in_array_element_as_string": { # EXPECTED TO PASS (post-processing handles content comma)
            "input": """{"key_entities": ["Large Language Model,", "Prompt Engineering Guide"],"trends_identified": ["agent-orchestrated workflows,", "increased AI decision-making autonomy",]}""",
            "expect_pass": True
        },
        "6_key_with_empty_value_after_colon": { "input": """{ "summary": "Malformed list issue.", "key_entities": ,"trends_identified": ["test"]}""", "expect_pass": False }, # Expect FAIL, clean_json_string won't add null anymore
        "7_nested_empty_value": { "input": """{"outer_key": {"inner_list": [ "item1", "item2"],"inner_obj": { "k1": "v1", "k2": }}}""", "expect_pass": False }, # Expect FAIL
        "8_unescaped_newline_in_string_value": { "input": """{"title": "A Title","summary": "  This summary\n has newlines.  ","url": "http://example.com"}""", "expect_pass": True },
        "9_empty_string_after_colon_complex": { "input": """{"some_key": ,"another_key": ""}""", "expect_pass": False }, # Expect FAIL
        "10_llm_style_array_of_strings_comma_sep_value": { # EXPECTED TO PASS (post-processing converts string to list)
            "input": """{"summary": "This is a summary.","key_entities": "entity A, entity B, entity C","trends_identified": "trend X, trend Y"}""",
            "expect_pass": True
        },
        "11_llm_mixed_output_with_text": { "input": """Here is the JSON:```json\n{"summary": "This is a comprehensive summary.","key_entities": ["LangChain"],"trends_identified": ["AI safety",],"extra_field": "This should be ignored."}\n```Some extra text at the end.""", "expect_pass": True },
        "12_escaped_quotes_in_string": { "input": """{"summary": "This summary contains an \\"escaped quote\\" for testing.","key_entities": ["test"]}""", "expect_pass": True },
        "13_unquoted_boolean_and_number_values": { "input": """{"summary": "Summary text","is_valid": true,"count": 123}""", "expect_pass": True },
        "14_empty_curly_braces": { "input": "{}", "expect_pass": True },
        "15_just_array_not_object": { "input": "[]", "expect_pass": False }, # Expected to fail as it expects an object
        "16_text_with_json_inside": { "input": """Some text before { "a": 1, "b": 2 } and some text after""", "expect_pass": True },
        "17_key_value_no_comma_newline": { # EXPECTED TO FAIL (json.loads will complain)
            "input": """{"a": "val1"\n"b": "val2"}""",
            "expect_pass": False
        },
        "18_multiple_commas": { "input": """{"a": 1,,,"b": 2}""", "expect_pass": True },
        "19_missing_quotes_on_key": { "input": """{key: "value"}""", "expect_pass": True },
        "20_missing_quotes_on_string_value": { # EXPECTED TO FAIL (value_without_quotes is not valid JSON string)
            "input": """{"key": value_without_quotes}""",
            "expect_pass": False
        },
        # New test case for the "They"re" issue
        "21_unescaped_internal_double_quote": {
            "input": """{"summary": "Autonomous agents are AIs that understand and respond. They"re a key aspect."}""",
            "expect_pass": True # Expected to pass with new fix
        },
    }

    results = {}
    for name, case in test_cases.items():
        try:
            cleaned = clean_json_string(case["input"])
            
            # Attempt to parse
            parsed = json.loads(cleaned)
            
            # Post-processing content cleanup (for specific fields like key_entities/trends_identified)
            def post_process_list_field(data, field_name):
                if field_name in data:
                    if isinstance(data[field_name], str):
                        # Make sure this internal split also strips trailing commas from elements
                        return [item.strip().rstrip(',') for item in data[field_name].split(',') if item.strip()]
                    elif isinstance(data[field_name], list):
                        # Strip trailing commas from existing list elements
                        return [item.strip().rstrip(',') for item in data[field_name]]
                return [] # Return empty list if not found or malformed

            if "key_entities" in parsed:
                parsed["key_entities"] = post_process_list_field(parsed, "key_entities")
            if "trends_identified" in parsed:
                parsed["trends_identified"] = post_process_list_field(parsed, "trends_identified")
            
            # General cleanup for keys (e.g., removing trailing commas if they survive)
            final_parsed = {}
            for k, v in parsed.items():
                final_parsed[k.strip().rstrip(',')] = v
            parsed = final_parsed

            # If execution reaches here, it passed the parsing check.
            status = "PASS" if case["expect_pass"] else "FAIL (unexpected pass)"
            print(f"\n--- Test Case: {name} --- ({status})")
            print(f"Cleaned String:\n{cleaned}")
            print(f"Parsed JSON:\n{json.dumps(parsed, indent=2)}")
            results[name] = status

        except Exception as e:
            status = "FAIL" if case["expect_pass"] else "PASS (expected failure)"
            print(f"\n--- Test Case: {name} --- ({status})")
            print(f"Error for '{name}': {e}")
            print(f"Problematic string segment (first 200 chars):\n{case['input'][:200]}...")
            results[name] = status

    print("\n--- Test Summary ---")
    for name, status in results.items():
        print(f"{name}: {status}")