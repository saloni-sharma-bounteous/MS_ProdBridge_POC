#!/usr/bin/env python3
"""Minimal JSON Schema validator (stdlib only, Python 3.8+).

Supports: type, enum, const, required, properties, additionalProperties,
items, minItems, minLength, maxLength, pattern, minimum, maximum,
anyOf, $ref (local '#/$defs/...').  Enough for this toolkit's schemas,
so skills run in locked-down environments without `pip install jsonschema`.

Usage: validate_json.py SCHEMA.json DATA.json
Exit code 0 = valid, 1 = invalid, 2 = usage/IO error.
"""
import json
import re
import sys


def _type_ok(value, t):
    if t == "string":
        return isinstance(value, str)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "array":
        return isinstance(value, list)
    if t == "object":
        return isinstance(value, dict)
    if t == "null":
        return value is None
    return True


def _resolve(ref, root):
    if not ref.startswith("#/"):
        raise ValueError("only local $ref supported: " + ref)
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def validate(data, schema, root=None, path="$"):
    root = root if root is not None else schema
    errors = []
    if "$ref" in schema:
        return validate(data, _resolve(schema["$ref"], root), root, path)
    if "anyOf" in schema:
        if not any(not validate(data, s, root, path) for s in schema["anyOf"]):
            errors.append("%s: does not match any allowed shape" % path)
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(data, x) for x in types):
            errors.append("%s: expected %s, got %s" % (path, "/".join(types), type(data).__name__))
            return errors
    if "enum" in schema and data not in schema["enum"]:
        errors.append("%s: %r not in %s" % (path, data, schema["enum"]))
    if "const" in schema and data != schema["const"]:
        errors.append("%s: expected constant %r" % (path, schema["const"]))
    if isinstance(data, str):
        if "minLength" in schema and len(data) < schema["minLength"]:
            errors.append("%s: shorter than %d characters" % (path, schema["minLength"]))
        if "maxLength" in schema and len(data) > schema["maxLength"]:
            errors.append("%s: longer than %d characters" % (path, schema["maxLength"]))
        if "pattern" in schema and not re.search(schema["pattern"], data):
            errors.append("%s: %r does not match %s" % (path, data, schema["pattern"]))
    if isinstance(data, (int, float)) and not isinstance(data, bool):
        if "minimum" in schema and data < schema["minimum"]:
            errors.append("%s: %s below minimum %s" % (path, data, schema["minimum"]))
        if "maximum" in schema and data > schema["maximum"]:
            errors.append("%s: %s above maximum %s" % (path, data, schema["maximum"]))
    if isinstance(data, list):
        if "minItems" in schema and len(data) < schema["minItems"]:
            errors.append("%s: fewer than %d items" % (path, schema["minItems"]))
        if "items" in schema:
            for i, item in enumerate(data):
                errors.extend(validate(item, schema["items"], root, "%s[%d]" % (path, i)))
    if isinstance(data, dict):
        for key in schema.get("required", []):
            if key not in data:
                errors.append("%s: missing required property '%s'" % (path, key))
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in data:
                errors.extend(validate(data[key], sub, root, "%s.%s" % (path, key)))
        addl = schema.get("additionalProperties", True)
        for key in data:
            if key in props:
                continue
            if addl is False:
                errors.append("%s: unexpected property '%s'" % (path, key))
            elif isinstance(addl, dict):
                errors.extend(validate(data[key], addl, root, "%s.%s" % (path, key)))
    return errors


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    try:
        with open(argv[1], encoding="utf-8") as f:
            schema = json.load(f)
        with open(argv[2], encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2
    errs = validate(data, schema)
    if errs:
        print("INVALID (%d problem%s)" % (len(errs), "" if len(errs) == 1 else "s"))
        for e in errs[:50]:
            print("  - " + e)
        return 1
    print("VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
