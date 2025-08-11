import operator

class Rule:
    """A rule consists of conditions and an action to take if they are met."""
    def __init__(self, conditions, action):
        self.conditions = conditions
        self.action = action

    def matches(self, data):
        """Checks if the given data meets all rule conditions."""
        return all(cond.is_met(data) for cond in self.conditions)

class Condition:
    """A condition to be evaluated against the intervention data."""
    OPERATORS = {
        '==': operator.eq,
        '!=': operator.ne,
        '<': operator.lt,
        '<=': operator.le,
        '>': operator.gt,
        '>=': operator.ge,
        'in': lambda a, b: a in b,
        'not in': lambda a, b: a not in b,
        'has_key': lambda d, k: k in d,
    }

    def __init__(self, field, operator, value):
        if operator not in self.OPERATORS:
            raise ValueError(f"Unsupported operator: {operator}")
        self.field = field
        self.operator = operator
        self.value = value

    def is_met(self, data):
        """Checks if the data satisfies the condition."""
        # Support for nested fields, e.g., "kwargs.filename"
        keys = self.field.split('.')
        data_value = data
        for key in keys:
            if isinstance(data_value, dict):
                data_value = data_value.get(key)
            else:
                data_value = None
                break
        
        op_func = self.OPERATORS[self.operator]
        # Ensure the value for 'in' and 'not in' is a container
        if self.operator in ['in', 'not in'] and not isinstance(data_value, (str, list, tuple, dict)):
             return False
        return op_func(data_value, self.value)

class RuleEngine:
    """A simple rule engine to evaluate a set of rules against data."""
    def __init__(self, rules):
        self.rules = rules

    def evaluate(self, data):
        """Evaluates data against rules and returns the first matching action."""
        for rule in self.rules:
            if rule.matches(data):
                return rule.action
        return None 