from orchestrator_lib import orchestrate
import requests

@orchestrate
def fetch_web_content(url: str):
    """
    Fetches the text content of a web page.
    Note: The @orchestrate decorator will intercept the return value.
    """
    print(f"  [Agent Action] Fetching content from {url}...")
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"  [Agent Action] Error fetching URL: {e}")
        return f"[ERROR: Could not fetch {url}]"

if __name__ == '__main__':
    print("--- Running Agent Task ---")

    # This URL returns a large amount of text, which should trigger the "TOO LONG" rule.
    print("\n[TASK 1] Fetching a large page...")
    result1 = fetch_web_content(url="https://www.rfc-editor.org/rfc/rfc2616")
    print(f"\n>> Final Output for Task 1: {result1}\n")

    # This URL returns a small amount of text, which should pass.
    print("\n[TASK 2] Fetching a small page...")
    result2 = fetch_web_content(url="https://www.example.com")
    print(f"\n>> Final Output for Task 2:\n---\n{result2}\n---")

    print("\n--- Agent tasks finished. ---")
    print("Check the dashboard at http://127.0.0.1:5000 to see the intervention history.")