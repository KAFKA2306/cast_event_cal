import jsonschema
from jsonschema import validate

def validate_schema(data, schema):
    """
    Validate event data against a JSON schema defined in models/data_schemas.py.
    """
    try:
        validate(instance=data, schema=schema)
        return True
    except jsonschema.exceptions.ValidationError as e:
        print(f"Schema validation error: {e}")
        return False