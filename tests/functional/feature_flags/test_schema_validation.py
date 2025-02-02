import logging

import pytest  # noqa: F401

from aws_lambda_powertools.utilities.feature_flags.exceptions import SchemaValidationError
from aws_lambda_powertools.utilities.feature_flags.schema import (
    CONDITION_ACTION,
    CONDITION_KEY,
    CONDITION_VALUE,
    CONDITIONS_KEY,
    FEATURE_DEFAULT_VAL_KEY,
    RULE_MATCH_VALUE,
    RULES_KEY,
    ConditionsValidator,
    RuleAction,
    RulesValidator,
    SchemaValidator,
)

logger = logging.getLogger(__name__)

EMPTY_SCHEMA = {"": ""}


def test_invalid_features_dict():
    validator = SchemaValidator(schema=[])
    with pytest.raises(SchemaValidationError):
        validator.validate()


def test_empty_features_not_fail():
    validator = SchemaValidator(schema={})
    validator.validate()


@pytest.mark.parametrize(
    "schema",
    [
        pytest.param({"my_feature": []}, id="feat_as_list"),
        pytest.param({"my_feature": {}}, id="feat_empty_dict"),
        pytest.param({"my_feature": {FEATURE_DEFAULT_VAL_KEY: "False"}}, id="feat_default_non_bool"),
        pytest.param({"my_feature": {FEATURE_DEFAULT_VAL_KEY: False, RULES_KEY: "4"}}, id="feat_rules_non_dict"),
        pytest.param("%<>[]{}|^", id="unsafe-rfc3986"),
    ],
)
def test_invalid_feature(schema):
    validator = SchemaValidator(schema)
    with pytest.raises(SchemaValidationError):
        validator.validate()


def test_valid_feature_dict():
    # empty rules list
    schema = {"my_feature": {FEATURE_DEFAULT_VAL_KEY: False, RULES_KEY: []}}
    validator = SchemaValidator(schema)
    validator.validate()

    # no rules list at all
    schema = {"my_feature": {FEATURE_DEFAULT_VAL_KEY: False}}
    validator = SchemaValidator(schema)
    validator.validate()


def test_invalid_rule():
    # rules list is not a list of dict
    schema = {
        "my_feature": {
            FEATURE_DEFAULT_VAL_KEY: False,
            RULES_KEY: [
                "a",
                "b",
            ],
        }
    }
    validator = SchemaValidator(schema)
    with pytest.raises(SchemaValidationError):
        validator.validate()

    # rules RULE_MATCH_VALUE is not bool
    schema = {
        "my_feature": {
            FEATURE_DEFAULT_VAL_KEY: False,
            RULES_KEY: {
                "tenant id equals 345345435": {
                    RULE_MATCH_VALUE: "False",
                }
            },
        }
    }
    validator = SchemaValidator(schema)
    with pytest.raises(SchemaValidationError):
        validator.validate()

    # missing conditions list
    schema = {
        "my_feature": {
            FEATURE_DEFAULT_VAL_KEY: False,
            RULES_KEY: {
                "tenant id equals 345345435": {
                    RULE_MATCH_VALUE: False,
                }
            },
        }
    }
    validator = SchemaValidator(schema)
    with pytest.raises(SchemaValidationError):
        validator.validate()

    # condition list is empty
    schema = {
        "my_feature": {
            FEATURE_DEFAULT_VAL_KEY: False,
            RULES_KEY: {
                "tenant id equals 345345435": {RULE_MATCH_VALUE: False, CONDITIONS_KEY: []},
            },
        }
    }
    validator = SchemaValidator(schema)
    with pytest.raises(SchemaValidationError):
        validator.validate()

    # condition is invalid type, not list
    schema = {
        "my_feature": {
            FEATURE_DEFAULT_VAL_KEY: False,
            RULES_KEY: {
                "tenant id equals 345345435": {RULE_MATCH_VALUE: False, CONDITIONS_KEY: {}},
            },
        }
    }
    validator = SchemaValidator(schema)
    with pytest.raises(SchemaValidationError):
        validator.validate()


def test_invalid_condition():
    # invalid condition action
    schema = {
        "my_feature": {
            FEATURE_DEFAULT_VAL_KEY: False,
            RULES_KEY: {
                "tenant id equals 345345435": {
                    RULE_MATCH_VALUE: False,
                    CONDITIONS_KEY: {CONDITION_ACTION: "stuff", CONDITION_KEY: "a", CONDITION_VALUE: "a"},
                }
            },
        }
    }
    validator = SchemaValidator(schema)
    with pytest.raises(SchemaValidationError):
        validator.validate()

    # missing condition key and value
    schema = {
        "my_feature": {
            FEATURE_DEFAULT_VAL_KEY: False,
            RULES_KEY: {
                "tenant id equals 345345435": {
                    RULE_MATCH_VALUE: False,
                    CONDITIONS_KEY: {CONDITION_ACTION: RuleAction.EQUALS.value},
                }
            },
        }
    }
    validator = SchemaValidator(schema)
    with pytest.raises(SchemaValidationError):
        validator.validate()

    # invalid condition key type, not string
    schema = {
        "my_feature": {
            FEATURE_DEFAULT_VAL_KEY: False,
            RULES_KEY: {
                "tenant id equals 345345435": {
                    RULE_MATCH_VALUE: False,
                    CONDITIONS_KEY: {
                        CONDITION_ACTION: RuleAction.EQUALS.value,
                        CONDITION_KEY: 5,
                        CONDITION_VALUE: "a",
                    },
                }
            },
        }
    }
    validator = SchemaValidator(schema)
    with pytest.raises(SchemaValidationError):
        validator.validate()


def test_valid_condition_all_actions():
    schema = {
        "my_feature": {
            FEATURE_DEFAULT_VAL_KEY: False,
            RULES_KEY: {
                "tenant id equals 645654 and username is a": {
                    RULE_MATCH_VALUE: True,
                    CONDITIONS_KEY: [
                        {
                            CONDITION_ACTION: RuleAction.EQUALS.value,
                            CONDITION_KEY: "tenant_id",
                            CONDITION_VALUE: "645654",
                        },
                        {
                            CONDITION_ACTION: RuleAction.STARTSWITH.value,
                            CONDITION_KEY: "username",
                            CONDITION_VALUE: "a",
                        },
                        {
                            CONDITION_ACTION: RuleAction.ENDSWITH.value,
                            CONDITION_KEY: "username",
                            CONDITION_VALUE: "a",
                        },
                        {
                            CONDITION_ACTION: RuleAction.IN.value,
                            CONDITION_KEY: "username",
                            CONDITION_VALUE: ["a", "b"],
                        },
                        {
                            CONDITION_ACTION: RuleAction.NOT_IN.value,
                            CONDITION_KEY: "username",
                            CONDITION_VALUE: ["c"],
                        },
                    ],
                }
            },
        }
    }
    validator = SchemaValidator(schema)
    validator.validate()


def test_validate_condition_invalid_condition_type():
    # GIVEN an invalid condition type of empty dict
    condition = {}

    # WHEN calling validate_condition
    # THEN raise SchemaValidationError
    with pytest.raises(SchemaValidationError, match="Feature rule condition must be a dictionary"):
        ConditionsValidator.validate_condition(condition=condition, rule_name="dummy")


def test_validate_condition_invalid_condition_action():
    # GIVEN an invalid condition action of foo
    condition = {"action": "INVALID", "key": "tenant_id", "value": "12345"}

    # WHEN calling validate_condition
    # THEN raise SchemaValidationError
    with pytest.raises(SchemaValidationError, match="'action' value must be either"):
        ConditionsValidator.validate_condition_action(condition=condition, rule_name="dummy")


def test_validate_condition_invalid_condition_key():
    # GIVEN a configuration with a missing "key"
    condition = {"action": RuleAction.EQUALS.value, "value": "12345"}

    # WHEN calling validate_condition
    # THEN raise SchemaValidationError
    with pytest.raises(SchemaValidationError, match="'key' value must be a non empty string"):
        ConditionsValidator.validate_condition_key(condition=condition, rule_name="dummy")


def test_validate_condition_missing_condition_value():
    # GIVEN a configuration with a missing condition value
    condition = {
        "action": RuleAction.EQUALS.value,
        "key": "tenant_id",
    }

    # WHEN calling validate_condition
    with pytest.raises(SchemaValidationError, match="'value' key must not be empty"):
        ConditionsValidator.validate_condition_value(condition=condition, rule_name="dummy")


def test_validate_rule_invalid_rule_type():
    # GIVEN an invalid rule type of empty list
    # WHEN calling validate_rule
    # THEN raise SchemaValidationError
    with pytest.raises(SchemaValidationError, match="Feature rule must be a dictionary"):
        RulesValidator.validate_rule(rule=[], rule_name="dummy", feature_name="dummy")


def test_validate_rule_invalid_rule_name():
    # GIVEN a rule name is empty
    # WHEN calling validate_rule_name
    # THEN raise SchemaValidationError
    with pytest.raises(SchemaValidationError, match="Rule name key must have a non-empty string"):
        RulesValidator.validate_rule_name(rule_name="", feature_name="dummy")
