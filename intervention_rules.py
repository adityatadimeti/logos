from rules_engine import Rule, Condition

def get_intervention_rules():
    """Returns a list of intervention rules."""

    # Rule 1: If fetched content is too long, replace it with a message.
    rule1 = Rule(
        conditions=[
            Condition('function_name', '==', 'fetch_web_content'),
            Condition('content_length', '>', 50000000000)
        ],
        action=lambda data: {
            "action": "return_value",
            "value": "[TOO LONG]"
        }
    )

    return [rule1] 