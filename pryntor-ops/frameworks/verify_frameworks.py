"""Verify distribution metadata and imports without creating or running agents."""
import argparse
import datetime
import importlib
import importlib.metadata
import json

FRAMEWORKS = {
    "langgraph": ("langgraph", "langgraph.graph"),
    "crewai": ("crewai", "crewai"),
    "microsoft": ("agent-framework-core", "agent_framework"),
    "openhands": ("openhands-sdk", "openhands.sdk"),
}


def verify(kind):
    package, module = FRAMEWORKS[kind]
    result = {
        "framework": kind,
        "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model_calls": 0,
        "live_agent": False,
        "verification_scope": "package_metadata_and_import_only",
    }
    try:
        result["packages"] = {package: importlib.metadata.version(package)}
        importlib.import_module(module)
    except Exception as error:
        # Do not include exception messages, which may contain environment values.
        result.update(verified=False, error_type=type(error).__name__)
    else:
        result.update(verified=True, imported_module=module)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("framework", choices=FRAMEWORKS)
    result = verify(parser.parse_args().framework)
    print(json.dumps(result))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
